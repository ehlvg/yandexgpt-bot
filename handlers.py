import io
import logging
from telegram import Update, constants
from telegram.ext import ContextTypes
from .state import (
    PROMPTS, HISTORIES, UNLIMITED_IDS, _save_state, _ensure_context, _truncate_history,
    _check_and_increment_usage, _check_and_increment_image_usage, _add_message_to_history,
    _reset_chat_history
)
from .config import UNLIMITED_IDS_PATH, MAX_QUESTION_LEN, USE_DATABASE, ADMIN_CHAT_IDS
from .yaclient import generate_reply, generate_image
from .db import update_chat_user_info, Session, add_usage_record, set_system_prompt

# Импортируем обработчик сообщений админки
from .admin_panel import admin_message_handler

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    username = context.bot.username or "the bot"
    text = (
        "👋 <b>Hello!</b> I am an assistant powered by <b>YandexGPT 5 Pro</b>.\n\n"
        "<b>What I can do</b>:\n"
        "• <code>/ask &lt;question&gt;</code> — I will answer (up to 15 requests/day per chat).\n"
        "• <code>/image &lt;description&gt;</code> — I will generate an image from a description (up to 5 requests/day per chat).\n"
        "• <code>/setprompt &lt;text&gt;</code> — I will set a system prompt.\n"
        "• <code>/reset</code> — I will clear the history.\n\n"
        "Chats from the whitelist (<code>{path}</code>) have no limits.\n"
        "In groups, use <code>/ask@{username}</code>."
    ).format(path=UNLIMITED_IDS_PATH.name, username=username)

    await update.effective_message.reply_text(
        text,
        parse_mode=constants.ParseMode.HTML,
        disable_web_page_preview=True,
    )

async def ask_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    if USE_DATABASE:
        session = Session()
        chat = update.effective_chat
        username = getattr(chat, 'username', None)
        first_name = getattr(chat, 'first_name', None)
        title = getattr(chat, 'title', None)
        update_chat_user_info(session, chat_id, username=username, first_name=first_name, title=title)
    if not _check_and_increment_usage(chat_id):
        await update.effective_message.reply_text("🚫 The daily limit of 15 requests has been reached. Please try again tomorrow.")
        return
    question = " ".join(context.args).strip()
    if not question and update.message.reply_to_message:
        question = update.message.reply_to_message.text or ""
    if not question:
        await update.effective_message.reply_text("Usage: /ask <your question>")
        return
    if len(question) > MAX_QUESTION_LEN:
        await update.effective_message.reply_text("⚠️ The question is too long (max 4000 characters).")
        return
    history = _ensure_context(chat_id)
    if USE_DATABASE:
        _add_message_to_history(chat_id, "user", question)
    else:
        history.append({"role": "user", "text": question})
        _truncate_history(history)
    typing_task = context.application.create_task(update.effective_chat.send_chat_action("typing"))
    try:
        answer = await generate_reply(history)
        if USE_DATABASE:
            user = update.effective_user
            add_usage_record(session, chat_id, user_id=user.id, user_username=getattr(user, 'username', None), user_first_name=getattr(user, 'first_name', None))
    except Exception as exc:
        logging.exception("YandexGPT request failed")
        await update.effective_message.reply_text(f"⚠️ Error: {exc}")
        return
    finally:
        typing_task.cancel()
        if USE_DATABASE:
            session.close()
    if USE_DATABASE:
        _add_message_to_history(chat_id, "assistant", answer)
    else:
        history.append({"role": "assistant", "text": answer})
        _save_state()
    await update.effective_message.reply_text(answer, reply_to_message_id=update.message.message_id, parse_mode=None)

async def setprompt_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /setprompt для установки системного промпта"""
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    # Обновляем информацию о чате в БД
    if USE_DATABASE:
        session = Session()
        chat = update.effective_chat
        username = getattr(chat, 'username', None)
        first_name = getattr(chat, 'first_name', None)
        title = getattr(chat, 'title', None)
        update_chat_user_info(session, chat_id, username=username, first_name=first_name, title=title)
        session.close()

    # Проверка прав доступа
    is_unlimited = chat_id in UNLIMITED_IDS
    is_admin = user_id in ADMIN_CHAT_IDS
    if not (is_unlimited or is_admin):
        await update.effective_message.reply_text("🚫 Доступ запрещен. Только администраторы и чаты из белого списка могут устанавливать системный промпт.")
        return

    # Получаем текст нового промпта
    new_prompt = " ".join(context.args).strip()
    if not new_prompt:
        await update.effective_message.reply_text("Использование: /setprompt <текст системного промпта>")
        return

    # Сохраняем промпт в память для режима без БД
    PROMPTS[chat_id] = new_prompt

    try:
        logging.info(f"Setting system prompt for chat {chat_id}")
        
        # Сброс истории чата
        _reset_chat_history(chat_id)
        
        # Обновляем или создаем новый контекст с промптом
        if USE_DATABASE:
            # Импортируем внутри функции чтобы избежать циклических импортов
            from yandexgpt_bot.db import set_system_prompt as db_set_prompt
            session = Session()
            db_set_prompt(session, chat_id, new_prompt)
            session.close()
        else:
            # Для режима без БД
            HISTORIES[chat_id] = [{"role": "system", "text": new_prompt}]
            
        # Сохраняем состояние, если не используем БД
        _save_state()
        
        # Пересоздаем контекст с новым промптом
        _ensure_context(chat_id)
        
        # Отправляем подтверждение
        await update.effective_message.reply_text("✅ Системный промпт обновлен и контекст сброшен.")
        
    except Exception as e:
        logging.error(f"Ошибка при установке системного промпта: {e}")
        await update.effective_message.reply_text(f"⚠️ Произошла ошибка: {e}")

async def reset_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Сбрасывает историю диалога и системный промпт к значению по умолчанию"""
    chat_id = update.effective_chat.id
    
    # Обновляем информацию о чате в БД
    if USE_DATABASE:
        session = Session()
        chat = update.effective_chat
        username = getattr(chat, 'username', None)
        first_name = getattr(chat, 'first_name', None)
        title = getattr(chat, 'title', None)
        update_chat_user_info(session, chat_id, username=username, first_name=first_name, title=title)
        session.close()
    
    try:
        # Удаляем из памяти кастомный промпт
        PROMPTS.pop(chat_id, None)
        
        # Используем функцию сброса истории с поддержкой БД
        _reset_chat_history(chat_id)
        
        # Принудительно создаем новый контекст с промптом по умолчанию
        _ensure_context(chat_id)
        
        # Сохраняем состояние, если не используем БД
        _save_state()
        
        await update.effective_message.reply_text("🗑️ Контекст очищен. Используется стандартный промпт.")
    except Exception as e:
        logging.error(f"Ошибка при сбросе контекста: {e}")
        await update.effective_message.reply_text(f"⚠️ Произошла ошибка: {e}")

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logging.error("Exception while handling an update:", exc_info=context.error)

async def image_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    description = " ".join(context.args).strip()
    if not description:
        await update.effective_message.reply_text("Usage: /image <description>")
        return
    chat_id = update.effective_chat.id
    if USE_DATABASE:
        session = Session()
        chat = update.effective_chat
        username = getattr(chat, 'username', None)
        first_name = getattr(chat, 'first_name', None)
        title = getattr(chat, 'title', None)
        update_chat_user_info(session, chat_id, username=username, first_name=first_name, title=title)
        user = update.effective_user
        add_usage_record(session, chat_id, user_id=user.id, user_username=getattr(user, 'username', None), user_first_name=getattr(user, 'first_name', None))
        session.close()
    if not _check_and_increment_image_usage(chat_id):
        await update.effective_message.reply_text("🚫 The daily image generation limit of 5 requests has been reached. Please try again tomorrow.")
        return
    typing_task = context.application.create_task(update.effective_chat.send_chat_action("upload_photo"))
    try:
        image_bytes = await generate_image(description)
    except Exception as exc:
        logging.exception("YandexART request failed")
        await update.effective_message.reply_text(f"⚠️ Error generating image: {exc}")
        return
    finally:
        typing_task.cancel()
    await update.effective_message.reply_photo(photo=io.BytesIO(image_bytes))

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает обычные текстовые сообщения и контакты"""
    # Проверяем, нужно ли обработать как админ-сообщение
    if await admin_message_handler(update, context):
        return  # Сообщение было обработано в админке
    
    # В противном случае можно добавить другую логику обработки сообщений
    # Например, отвечать только в ответ на ваши сообщения, без команды /ask
    pass 