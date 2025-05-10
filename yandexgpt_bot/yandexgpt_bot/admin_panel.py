"""
Administrative panel module for the YandexGPT bot. Provides bot management interface via Telegram.
"""
import os
import yaml
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, constants
from telegram.ext import ContextTypes, CallbackQueryHandler, CommandHandler
import datetime
import logging
from typing import List, Dict, Any, Optional
import matplotlib.pyplot as plt
import io
from sqlalchemy import func

from .config import ADMIN_CHAT_IDS, USE_DATABASE, LANGUAGE
from .state import UNLIMITED_IDS, _save_state, db_initialized
from .translations import get_text, get_current_language

# Import DB functions if database is enabled
if USE_DATABASE and db_initialized:
    from .db import Session, get_or_create_chat, set_unlimited_status, Chat, UsageRecord, ImageUsageRecord, Message

# Callback data constants
ADD_USER = 'add_user'
REMOVE_USER = 'remove_user'
LIST_USERS = 'list_users'
STATS = 'stats'
BACK = 'back'
CONFIRM_ADD = 'confirm_add'
CONFIRM_REMOVE = 'confirm_remove'
LANGUAGE_MENU = 'language_menu'
SET_LANGUAGE = 'set_language'
SELECT_REMOVE_USER = 'select_remove'

# Admin panel state and cache
admin_states = {}
unlimited_users_cache = {}

async def is_admin(update: Update) -> bool:
    """Check if the user is whitelisted as admin"""
    user_id = update.effective_user.id
    logging.info(f"Verifying admin rights for user {user_id}, admins: {ADMIN_CHAT_IDS}")
    return user_id in ADMIN_CHAT_IDS

def get_main_admin_keyboard(lang=None):
    """Returns the main admin panel keyboard"""
    if lang is None:
        lang = get_current_language()
    keyboard = [
        [
            InlineKeyboardButton(get_text("btn_unlimited_users", lang=lang), callback_data=LIST_USERS),
            InlineKeyboardButton(get_text("btn_statistics", lang=lang), callback_data=STATS)
        ],
        [
            InlineKeyboardButton(get_text("btn_add_user", lang=lang), callback_data=ADD_USER),
            InlineKeyboardButton(get_text("btn_remove_user", lang=lang), callback_data=REMOVE_USER)
        ],
        [
            InlineKeyboardButton(get_text("btn_language", lang=lang), callback_data=LANGUAGE_MENU)
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

async def admin_panel_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler for the /admin command - main admin panel page"""
    if not await is_admin(update):
        await update.message.reply_text(get_text("access_denied", lang=get_current_language()))
        return
    
    lang = get_current_language()
    await update.message.reply_text(
        f"🛠 *{get_text('admin_panel_title', lang=lang)}*\n\n"
        f"{get_text('admin_panel_welcome', lang=lang)}",
        reply_markup=get_main_admin_keyboard(lang=lang),
        parse_mode=constants.ParseMode.MARKDOWN
    )

async def admin_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler for admin panel button clicks"""
    query = update.callback_query
    chat_id = update.effective_chat.id
    lang = get_current_language()
    
    if not await is_admin(update):
        await query.answer(get_text("access_denied", lang=lang))
        return
    
    await query.answer()
    
    data = query.data
    
    if data == BACK:
        admin_states.pop(chat_id, None)  # Reset state
        await query.edit_message_text(
            f"🛠 *{get_text('admin_panel_title', lang=lang)}*\n\n"
            f"{get_text('admin_panel_welcome', lang=lang)}",
            reply_markup=get_main_admin_keyboard(lang=lang),
            parse_mode=constants.ParseMode.MARKDOWN
        )
    
    elif data == LIST_USERS:
        await show_unlimited_users(update, context)
    
    elif data == STATS:
        await show_stats(update, context)
    
    elif data == ADD_USER:
        admin_states[chat_id] = {'action': ADD_USER}
        await query.edit_message_text(
            f"*{get_text('add_user_title', lang=lang)}*\n\n"
            f"{get_text('add_user_description', lang=lang)}\n\n"
            f"{get_text('add_user_share_contact', lang=lang)}",
            parse_mode=constants.ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(get_text("btn_back", lang=lang), callback_data=BACK)]])
        )
    
    elif data == REMOVE_USER:
        await show_users_for_removal(update, context)
    
    elif data == LANGUAGE_MENU:
        await show_language_menu(update, context)
    
    elif data.startswith(SET_LANGUAGE):
        language = data.split(':')[1]
        await set_language(update, context, language)
    
    elif data.startswith(CONFIRM_ADD):
        user_id = int(data.split(':')[1])
        await add_unlimited_user(update, context, user_id)
    
    elif data.startswith(CONFIRM_REMOVE):
        user_id = int(data.split(':')[1])
        await remove_unlimited_user(update, context, user_id)
    
    elif data.startswith(SELECT_REMOVE_USER):
        user_id = int(data.split(':')[1])
        await query.edit_message_text(
            get_text("confirm_remove_user", user_id=user_id, lang=lang),
            parse_mode=constants.ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(get_text("btn_yes", lang=lang), callback_data=f"{CONFIRM_REMOVE}:{user_id}")],
                [InlineKeyboardButton(get_text("btn_no", lang=lang), callback_data=BACK)]
            ])
        )

async def admin_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """
    Handler for text messages in the admin panel
    Returns True if the message was processed as an admin command
    """
    if not await is_admin(update):
        return False
    
    chat_id = update.effective_chat.id
    
    if update.message.contact and chat_id in admin_states and admin_states[chat_id].get('action') == ADD_USER:
        user_id = update.message.contact.user_id
        if not user_id:
            await update.message.reply_text(
                get_text("contact_no_userid", lang=get_current_language()),
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(get_text("btn_back_to_admin", lang=get_current_language()), callback_data=BACK)]])
            )
            return True
            
        await update.message.reply_text(
            get_text("confirm_add_user", user_id=user_id, lang=get_current_language()),
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(get_text("btn_yes", lang=get_current_language()), callback_data=f"{CONFIRM_ADD}:{user_id}")],
                [InlineKeyboardButton(get_text("btn_no", lang=get_current_language()), callback_data=BACK)]
            ])
        )
        return True
    
    if not update.message.text:
        return False
    
    message_text = update.message.text
    
    if chat_id not in admin_states:
        return False
    
    state = admin_states[chat_id]
    
    if state.get('action') == ADD_USER:
        try:
            user_id = int(message_text.strip())
            
            await update.message.reply_text(
                get_text("confirm_add_user", user_id=user_id, lang=get_current_language()),
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton(get_text("btn_yes", lang=get_current_language()), callback_data=f"{CONFIRM_ADD}:{user_id}")],
                    [InlineKeyboardButton(get_text("btn_no", lang=get_current_language()), callback_data=BACK)]
                ])
            )
            return True
        except ValueError:
            await update.message.reply_text(
                get_text("invalid_id", lang=get_current_language()),
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(get_text("btn_back_to_admin", lang=get_current_language()), callback_data=BACK)]])
            )
            return True
    
    elif state.get('action') == REMOVE_USER:
        try:
            selection = int(message_text.strip())
            
            unlimited_users = get_unlimited_users_list()
            
            if selection < 1 or selection > len(unlimited_users):
                await update.message.reply_text(
                    get_text("invalid_selection", lang=get_current_language()),
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(get_text("btn_back_to_admin", lang=get_current_language()), callback_data=BACK)]])
                )
                return True
            
            user_id = unlimited_users[selection - 1]
            
            await update.message.reply_text(
                get_text("confirm_remove_user", user_id=user_id, lang=get_current_language()),
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton(get_text("btn_yes", lang=get_current_language()), callback_data=f"{CONFIRM_REMOVE}:{user_id}")],
                    [InlineKeyboardButton(get_text("btn_no", lang=get_current_language()), callback_data=BACK)]
                ])
            )
            return True
        except ValueError:
            await update.message.reply_text(
                get_text("invalid_selection", lang=get_current_language()),
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(get_text("btn_back_to_admin", lang=get_current_language()), callback_data=BACK)]])
            )
            return True
        except Exception as e:
            logging.error(f"Error processing user selection: {e}")
            await update.message.reply_text(
                get_text("general_error", error=str(e), lang=get_current_language()),
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(get_text("btn_back_to_admin", lang=get_current_language()), callback_data=BACK)]])
            )
            return True
    
    return False

def get_unlimited_users_list() -> List[int]:
    """Gets the list of users with unlimited access"""
    if USE_DATABASE and db_initialized:
        try:
            from .db import Session, Chat
            session = Session()
            chats = session.query(Chat).filter_by(is_unlimited=True).all()
            unlimited_users = [chat.chat_id for chat in chats]
            session.close()
            return sorted(unlimited_users)
        except Exception as e:
            logging.error(f"Error getting unlimited users list: {e}")
            return sorted(list(UNLIMITED_IDS))
    else:
        return sorted(list(UNLIMITED_IDS))

async def get_chat_username(bot, chat_id: int) -> str:
    """Gets the username of a user by chat_id"""
    try:
        chat = await bot.get_chat(chat_id)
        
        if chat.username:
            return f"@{chat.username}"
        elif chat.type == 'private' and chat.first_name:
            return f"{chat.first_name}"
        elif chat.title:
            return f"{chat.title}"
        else:
            return f"{chat_id}"
    except Exception as e:
        logging.error(f"Error getting chat info for {chat_id}: {e}")
        return f"{chat_id}"

async def show_unlimited_users(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Shows the list of users with unlimited access with their usernames"""
    query = update.callback_query
    lang = get_current_language()
    unlimited_users = get_unlimited_users_list()
    
    if not unlimited_users:
        message = f"*{get_text('unlimited_users_title', lang=lang)}*\n\n{get_text('unlimited_users_empty', lang=lang)}"
        await query.edit_message_text(
            message,
            parse_mode=constants.ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(get_text("btn_back", lang=lang), callback_data=BACK)]])
        )
        return
    
    await query.edit_message_text(
        f"*{get_text('unlimited_users_title', lang=lang)}*\n\n{get_text('loading_users', lang=lang)}",
        parse_mode=constants.ParseMode.MARKDOWN
    )
    
    message = f"*{get_text('unlimited_users_title', lang=lang)}*\n\n"
    
    for idx, user_id in enumerate(unlimited_users, 1):
        username = await get_chat_username(context.bot, user_id)
        message += f"{idx}. {username} (`{user_id}`)\n"
    
    await query.edit_message_text(
        message,
        parse_mode=constants.ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(get_text("btn_back", lang=lang), callback_data=BACK)]])
    )

async def show_users_for_removal(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Shows the list of users for removal from unlimited access"""
    query = update.callback_query
    chat_id = update.effective_chat.id
    lang = get_current_language()
    
    admin_states[chat_id] = {'action': REMOVE_USER}
    
    unlimited_users = get_unlimited_users_list()
    
    if not unlimited_users:
        await query.edit_message_text(
            f"*{get_text('remove_user_title', lang=lang)}*\n\n{get_text('unlimited_users_empty', lang=lang)}",
            parse_mode=constants.ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(get_text("btn_back", lang=lang), callback_data=BACK)]])
        )
        return
    
    await query.edit_message_text(
        f"*{get_text('remove_user_title', lang=lang)}*\n\n{get_text('remove_user_select', lang=lang)}\n\n"
    )
    
    keyboard = []
    
    for idx, user_id in enumerate(unlimited_users, 1):
        username = await get_chat_username(context.bot, user_id)
        message += f"{idx}. {username} (`{user_id}`)\n"
        
        keyboard.append([InlineKeyboardButton(f"{idx}. {username}", callback_data=f"{SELECT_REMOVE_USER}:{user_id}")])
    
    keyboard.append([InlineKeyboardButton(get_text("btn_back", lang=lang), callback_data=BACK)])
    
    await query.edit_message_text(
        message,
        parse_mode=constants.ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def show_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Shows bot usage statistics and activity charts"""
    query = update.callback_query
    lang = get_current_language()
    if USE_DATABASE and db_initialized:
        try:
            session = Session()
            total_chats = session.query(Chat).count()
            unlimited_chats = session.query(Chat).filter_by(is_unlimited=True).count()
            today = datetime.datetime.utcnow().date()
            today_start = datetime.datetime.combine(today, datetime.time.min)
            total_messages = session.query(Message).count()
            today_requests = session.query(UsageRecord).filter(UsageRecord.date >= today_start).count()
            today_images = session.query(ImageUsageRecord).filter(ImageUsageRecord.date >= today_start).count()
            
            last_24h = datetime.datetime.utcnow() - datetime.timedelta(hours=24)
            usage = session.query(UsageRecord).filter(UsageRecord.date >= last_24h).all()
            user_stats = {}
            for rec in usage:
                if rec.user_username:
                    label = f"@{rec.user_username}"
                elif rec.user_first_name:
                    label = rec.user_first_name
                elif rec.user_id:
                    label = str(rec.user_id)
                else:
                    continue
                user_stats.setdefault(label, 0)
                user_stats[label] += rec.count
            sorted_stats = sorted(user_stats.items(), key=lambda x: x[1], reverse=True)
            
            if sorted_stats:
                labels, values = zip(*sorted_stats)
                plt.figure(figsize=(8, max(3, len(labels)*0.5)))
                plt.barh(labels, values, color='skyblue')
                plt.xlabel(get_text("chart_requests_x", default="Requests in 24h", lang=lang))
                plt.title(get_text("chart_requests_title", default="User activity over the last 24 hours", lang=lang))
                plt.tight_layout()
                buf = io.BytesIO()
                plt.savefig(buf, format='png')
                buf.seek(0)
                plt.close()
                await query.message.reply_photo(photo=buf, caption=get_text("chart_requests_24h", lang=lang))
            
            message = (
                f"*{get_text('stats_title', lang=lang)}*\n\n"
                f"{get_text('stats_total_chats', count=total_chats, lang=lang)}\n"
                f"{get_text('stats_unlimited_chats', count=unlimited_chats, lang=lang)}\n"
                f"{get_text('stats_total_messages', count=total_messages, lang=lang)}\n"
                f"{get_text('stats_today_requests', count=today_requests, lang=lang)}\n"
                f"{get_text('stats_today_images', count=today_images, lang=lang)}\n"
            )
            session.close()
        except Exception as e:
            logging.error(f"Error getting statistics: {e}")
            message = get_text("stats_error", error=str(e), lang=lang)
    else:
        message = (
            f"*{get_text('stats_title', lang=lang)}*\n\n"
            f"{get_text('stats_basic', count=len(UNLIMITED_IDS), lang=lang)}"
        )
    await query.edit_message_text(
        message,
        parse_mode=constants.ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(get_text("btn_back", lang=lang), callback_data=BACK)]])
    )

async def show_language_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Shows the language selection menu"""
    query = update.callback_query
    lang = get_current_language()
    message = (
        f"*{get_text('language_title', lang=lang)}*\n\n"
        f"{get_text('language_description', lang=lang)}"
    )
    
    keyboard = [
        [
            InlineKeyboardButton(get_text("btn_english", lang=lang), callback_data=f"{SET_LANGUAGE}:english"),
            InlineKeyboardButton(get_text("btn_russian", lang=lang), callback_data=f"{SET_LANGUAGE}:russian")
        ],
        [
            InlineKeyboardButton(get_text("btn_back", lang=lang), callback_data=BACK)
        ]
    ]
    
    await query.edit_message_text(
        message,
        parse_mode=constants.ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def set_language(update: Update, context: ContextTypes.DEFAULT_TYPE, language: str) -> None:
    """Sets the interface language"""
    query = update.callback_query
    global LANGUAGE
    LANGUAGE = language
    language_text = "English" if language == "english" else "Русский"
    await query.edit_message_text(
        f"✅ {get_text('language_changed', lang=language)}\n\n*Note: Language change will apply for new sessions or after a restart.*",
        parse_mode=constants.ParseMode.MARKDOWN,
        reply_markup=get_main_admin_keyboard(lang=language)
    )

async def add_unlimited_user(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int) -> None:
    """Adds a user to the unlimited access list"""
    query = update.callback_query
    
    try:
        if USE_DATABASE and db_initialized:
            session = Session()
            try:
                get_or_create_chat(session, user_id)
                set_unlimited_status(session, user_id, True)
                UNLIMITED_IDS.add(user_id)
            finally:
                session.close()
        else:
            UNLIMITED_IDS.add(user_id)
            _save_state()
        
        from .config import UNLIMITED_IDS_PATH
        with open(UNLIMITED_IDS_PATH, 'a') as f:
            f.write(f"{user_id}\n")
        
        admin_states.pop(update.effective_chat.id, None)
        await query.edit_message_text(
            get_text("user_added", user_id=user_id, lang=get_current_language()),
            parse_mode=constants.ParseMode.MARKDOWN,
            reply_markup=get_main_admin_keyboard(lang=get_current_language())
        )
    except Exception as e:
        logging.error(f"Error adding user: {e}")
        await query.edit_message_text(
            get_text("add_user_error", error=str(e), lang=get_current_language()),
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(get_text("btn_back", lang=get_current_language()), callback_data=BACK)]])
        )

async def remove_unlimited_user(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int) -> None:
    """Removes a user from the unlimited access list"""
    query = update.callback_query
    
    try:
        if USE_DATABASE and db_initialized:
            session = Session()
            try:
                set_unlimited_status(session, user_id, False)
                UNLIMITED_IDS.discard(user_id)
            finally:
                session.close()
        else:
            UNLIMITED_IDS.discard(user_id)
            _save_state()
        
        from .config import UNLIMITED_IDS_PATH
        if UNLIMITED_IDS_PATH.exists():
            with open(UNLIMITED_IDS_PATH, 'r') as f:
                lines = [line.strip() for line in f if line.strip() and int(line.strip()) != user_id]
            
            with open(UNLIMITED_IDS_PATH, 'w') as f:
                f.write('\n'.join(lines) + ('\n' if lines else ''))
        
        admin_states.pop(update.effective_chat.id, None)
        await query.edit_message_text(
            get_text("user_removed", user_id=user_id, lang=get_current_language()),
            parse_mode=constants.ParseMode.MARKDOWN,
            reply_markup=get_main_admin_keyboard(lang=get_current_language())
        )
    except Exception as e:
        logging.error(f"Error removing user: {e}")
        await query.edit_message_text(
            get_text("remove_user_error", error=str(e), lang=get_current_language()),
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(get_text("btn_back", lang=get_current_language()), callback_data=BACK)]])
        )

def register_admin_handlers(application):
    """Registers handlers for the admin panel"""
    application.add_handler(CommandHandler("admin", admin_panel_cmd))
    application.add_handler(CallbackQueryHandler(admin_callback_handler))