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

# Import admin message handler
from .admin_panel import admin_message_handler

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # Restrict access to whitelist
    user_id = update.effective_user.id
    if user_id not in ADMIN_CHAT_IDS:
        await update.effective_message.reply_text("🚫 Access denied. You are not whitelisted.")
        return

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
    # Restrict access to whitelist
    user_id = update.effective_user.id
    if user_id not in ADMIN_CHAT_IDS:
        await update.effective_message.reply_text("🚫 Access denied. You are not whitelisted.")
        return

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
    """Handler for /setprompt command to set system prompt"""
    # Restrict access to whitelist
    user_id = update.effective_user.id
    if user_id not in ADMIN_CHAT_IDS:
        await update.effective_message.reply_text("🚫 Access denied. You are not whitelisted.")
        return

    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    # Update chat info in DB
    if USE_DATABASE:
        session = Session()
        chat = update.effective_chat
        username = getattr(chat, 'username', None)
        first_name = getattr(chat, 'first_name', None)
        title = getattr(chat, 'title', None)
        update_chat_user_info(session, chat_id, username=username, first_name=first_name, title=title)
        session.close()

    # Access check
    is_unlimited = chat_id in UNLIMITED_IDS
    is_admin = user_id in ADMIN_CHAT_IDS
    if not (is_unlimited or is_admin):
        await update.effective_message.reply_text("🚫 Access denied. Only administrators and whitelisted chats can set system prompt.")
        return

    # Get new prompt text
    new_prompt = " ".join(context.args).strip()
    if not new_prompt:
        await update.effective_message.reply_text("Usage: /setprompt <system prompt text>")
        return

    # Save prompt in memory for non-DB mode
    PROMPTS[chat_id] = new_prompt

    try:
        logging.info(f"Setting system prompt for chat {chat_id}")
        
        # Reset chat history
        _reset_chat_history(chat_id)
        
        # Update or create new context with prompt
        if USE_DATABASE:
            # Import inside function to avoid circular imports
            from yandexgpt_bot.db import set_system_prompt as db_set_prompt
            session = Session()
            db_set_prompt(session, chat_id, new_prompt)
            session.close()
        else:
            # For non-DB mode
            HISTORIES[chat_id] = [{"role": "system", "text": new_prompt}]
            
        # Save state if not using DB
        _save_state()
        
        # Recreate context with new prompt
        _ensure_context(chat_id)
        
        # Send confirmation
        await update.effective_message.reply_text("✅ System prompt updated and context reset.")
        
    except Exception as e:
        logging.error(f"Error setting system prompt: {e}")
        await update.effective_message.reply_text(f"⚠️ Error: {e}")

async def reset_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Resets dialogue history and system prompt to default value"""
    # Restrict access to whitelist
    user_id = update.effective_user.id
    if user_id not in ADMIN_CHAT_IDS:
        await update.effective_message.reply_text("🚫 Access denied. You are not whitelisted.")
        return

    chat_id = update.effective_chat.id
    
    # Update chat info in DB
    if USE_DATABASE:
        session = Session()
        chat = update.effective_chat
        username = getattr(chat, 'username', None)
        first_name = getattr(chat, 'first_name', None)
        title = getattr(chat, 'title', None)
        update_chat_user_info(session, chat_id, username=username, first_name=first_name, title=title)
        session.close()
    
    try:
        # Remove custom prompt from memory
        PROMPTS.pop(chat_id, None)
        
        # Use history reset function with DB support
        _reset_chat_history(chat_id)
        
        # Force create new context with default prompt
        _ensure_context(chat_id)
        
        # Save state if not using DB
        _save_state()
        
        await update.effective_message.reply_text("🗑️ Context cleared. Default prompt is used.")
    except Exception as e:
        logging.error(f"Error resetting context: {e}")
        await update.effective_message.reply_text(f"⚠️ Error: {e}")

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logging.error("Exception while handling an update:", exc_info=context.error)

async def image_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # Restrict access to whitelist
    user_id = update.effective_user.id
    if user_id not in ADMIN_CHAT_IDS:
        await update.effective_message.reply_text("🚫 Access denied. You are not whitelisted.")
        return

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
    """Handles regular text messages and contacts"""
    # Restrict access to whitelist for all messages
    user_id = update.effective_user.id
    if user_id not in ADMIN_CHAT_IDS:
        return

    # Check if it should be handled as an admin message
    if await admin_message_handler(update, context):
        return  # Message was handled in admin panel
    
    # Otherwise, you can add other message handling logic
    # For example, respond only to your messages without the /ask command
    pass