import datetime as _dt
import json
from pathlib import Path
from typing import Dict, List, Set, Tuple
from yandexgpt_bot.config import STATE_FILE, UNLIMITED_IDS_PATH, DEFAULT_SYSTEM_PROMPT, USE_DATABASE
import logging

# Значения по умолчанию для импортируемых из db функций
db_initialized = False
Session = None
load_unlimited_ids = None
set_unlimited_status = None
get_or_create_chat = None
set_system_prompt = None
get_system_prompt = None
add_message = None
get_chat_history = None
reset_chat_history = None
check_and_increment_usage = None
check_and_increment_image_usage = None

# Import database module if database is enabled
if USE_DATABASE:
    # Импортируем модуль db и инициализируем его
    from yandexgpt_bot import db
    db_initialized = db.init_db()
    
    if db_initialized and db.Session is not None:
        # Присваиваем функции из db после успешной инициализации
        Session = db.Session
        load_unlimited_ids = db.load_unlimited_ids
        set_unlimited_status = db.set_unlimited_status
        get_or_create_chat = db.get_or_create_chat
        set_system_prompt = db.set_system_prompt
        get_system_prompt = db.get_system_prompt
        add_message = db.add_message
        get_chat_history = db.get_chat_history
        reset_chat_history = db.reset_chat_history
        check_and_increment_usage = db.check_and_increment_usage
        check_and_increment_image_usage = db.check_and_increment_image_usage

# In-memory state (fallback when database is not used)
ChatContext = List[Dict[str, str]]
PROMPTS: Dict[int, str] = {}
HISTORIES: Dict[int, ChatContext] = {}
DAILY_USAGE: Dict[int, Tuple[_dt.date, int]] = {}
DAILY_IMAGE_USAGE: Dict[int, Tuple[_dt.date, int]] = {}
UNLIMITED_IDS: Set[int] = set()

def _load_unlimited_ids() -> Set[int]:
    # If database is enabled and initialized, load from database
    if USE_DATABASE and db_initialized and Session is not None and load_unlimited_ids is not None:
        try:
            db_session = Session()
            unlimited_ids = load_unlimited_ids(db_session)
            db_session.close()
            return set(unlimited_ids)
        except Exception as e:
            logging.error(f"Error loading unlimited IDs from database: {e}")
            # Fall back to file-based method
    
    # File-based method
    if not UNLIMITED_IDS_PATH.exists():
        return set()
    ids: Set[int] = set()
    for line in UNLIMITED_IDS_PATH.read_text().splitlines():
        line = line.strip()
        try:
            chat_id = int(line)
            ids.add(chat_id)
            
            # Also update database if enabled
            if USE_DATABASE and db_initialized and Session is not None and set_unlimited_status is not None:
                try:
                    db_session = Session()
                    set_unlimited_status(db_session, chat_id, True)
                    db_session.close()
                except Exception as e:
                    logging.error(f"Error setting unlimited status in database: {e}")
                    
        except ValueError:
            logging.warning(f"Skipping invalid line in unlimited_chats.txt: {line}")
    return ids

UNLIMITED_IDS = _load_unlimited_ids()

def _load_state() -> None:
    # Database is the source of truth when enabled
    if USE_DATABASE and db_initialized:
        # We don't need to load state from file when database is used
        return
        
    # File-based method
    if not STATE_FILE.exists():
        return
    data = json.loads(STATE_FILE.read_text())
    for k, v in data.get("prompts", {}).items():
        PROMPTS[int(k)] = v
    for k, v in data.get("daily_usage", {}).items():
        d = _dt.date.fromisoformat(v[0])
        DAILY_USAGE[int(k)] = (d, v[1])
    for k, v in data.get("image_usage", {}).items():
        d = _dt.date.fromisoformat(v[0])
        DAILY_IMAGE_USAGE[int(k)] = (d, v[1])
    for k, v in data.get("histories", {}).items():
        HISTORIES[int(k)] = v

def _save_state() -> None:
    # If database is enabled, we don't need to save state to file
    if USE_DATABASE and db_initialized:
        return
        
    # File-based method
    data = {
        "prompts": {str(k): v for k, v in PROMPTS.items()},
        "daily_usage": {str(k): [d.isoformat(), c] for k, (d, c) in DAILY_USAGE.items()},
        "image_usage": {str(k): [d.isoformat(), c] for k, (d, c) in DAILY_IMAGE_USAGE.items()},
        "histories": {str(k): v for k, v in HISTORIES.items()},
    }
    STATE_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2))

def _ensure_context(chat_id: int) -> ChatContext:
    """Создает или возвращает контекст чата (историю сообщений)"""
    # Database-based method
    if USE_DATABASE and db_initialized and Session is not None and all([
            get_or_create_chat, get_system_prompt, set_system_prompt, 
            add_message, get_chat_history]):
        try:
            db_session = Session()
            
            # Get or create chat
            get_or_create_chat(db_session, chat_id)
            
            # Если у нас есть PROMPTS для этого чата, используем его как источник правды
            if chat_id in PROMPTS:
                system_prompt = PROMPTS[chat_id]
                # Устанавливаем промпт в БД
                set_system_prompt(db_session, chat_id, system_prompt)
                logging.info(f"Set system prompt from PROMPTS for chat {chat_id}")
                
                # Проверяем, есть ли уже системное сообщение
                history = get_chat_history(db_session, chat_id)
                system_message_exists = False
                for msg in history:
                    if msg.get("role") == "system":
                        system_message_exists = True
                        break
                
                # Если нет системного сообщения, добавляем
                if not system_message_exists:
                    add_message(db_session, chat_id, "system", system_prompt, sequence=0)
                    logging.info(f"Added system message for chat {chat_id}")
            else:
                # Иначе получаем промпт из БД
                system_prompt = get_system_prompt(db_session, chat_id)
                
                # Если промпта нет в БД, устанавливаем дефолтный
                if not system_prompt:
                    system_prompt = DEFAULT_SYSTEM_PROMPT
                    set_system_prompt(db_session, chat_id, system_prompt)
                    # Добавляем системное сообщение
                    add_message(db_session, chat_id, "system", system_prompt, sequence=0)
                    logging.info(f"Set default system prompt for chat {chat_id}")
                
                # Сохраняем промпт в память
                PROMPTS[chat_id] = system_prompt
            
            # Получаем историю чата
            from yandexgpt_bot.config import MAX_HISTORY_TURNS
            history = get_chat_history(db_session, chat_id, limit=1 + 2 * MAX_HISTORY_TURNS)
            
            db_session.close()
            return history
        except Exception as e:
            logging.error(f"Error ensuring context from database: {e}")
            # Fall back to in-memory method
    
    # In-memory method
    if chat_id not in HISTORIES:
        prompt = PROMPTS.get(chat_id, DEFAULT_SYSTEM_PROMPT)
        HISTORIES[chat_id] = [{"role": "system", "text": prompt}]
    return HISTORIES[chat_id]

def _truncate_history(history: ChatContext) -> None:
    from yandexgpt_bot.config import MAX_HISTORY_TURNS
    extra = len(history) - (1 + 2 * MAX_HISTORY_TURNS)
    if extra > 0:
        del history[1:1 + extra]

def _is_unlimited(chat_id: int) -> bool:
    # Database-based method
    if USE_DATABASE and db_initialized and Session is not None and get_or_create_chat is not None:
        try:
            db_session = Session()
            chat = get_or_create_chat(db_session, chat_id)
            is_unlimited = chat.is_unlimited
            db_session.close()
            return is_unlimited
        except Exception as e:
            logging.error(f"Error checking unlimited status from database: {e}")
            # Fall back to in-memory method
    
    # In-memory method
    return chat_id in UNLIMITED_IDS

def _check_and_increment_usage(chat_id: int) -> bool:
    # Database-based method
    if USE_DATABASE and db_initialized and Session is not None and check_and_increment_usage is not None:
        try:
            db_session = Session()
            from yandexgpt_bot.config import DAILY_LIMIT
            result = check_and_increment_usage(db_session, chat_id, DAILY_LIMIT)
            db_session.close()
            return result
        except Exception as e:
            logging.error(f"Error checking usage from database: {e}")
            # Fall back to in-memory method
    
    # In-memory method
    if _is_unlimited(chat_id):
        return True
    from yandexgpt_bot.config import DAILY_LIMIT
    today = _dt.date.today()
    last_date, count = DAILY_USAGE.get(chat_id, (today, 0))
    if last_date != today:
        count = 0
    if count >= DAILY_LIMIT:
        return False
    DAILY_USAGE[chat_id] = (today, count + 1)
    return True

def _check_and_increment_image_usage(chat_id: int) -> bool:
    # Database-based method
    if USE_DATABASE and db_initialized and Session is not None and check_and_increment_image_usage is not None:
        try:
            db_session = Session()
            from yandexgpt_bot.config import IMAGE_GENERATION_LIMIT
            result = check_and_increment_image_usage(db_session, chat_id, IMAGE_GENERATION_LIMIT)
            db_session.close()
            return result
        except Exception as e:
            logging.error(f"Error checking image usage from database: {e}")
            # Fall back to in-memory method
    
    # In-memory method
    if _is_unlimited(chat_id):
        return True
    from yandexgpt_bot.config import IMAGE_GENERATION_LIMIT
    today = _dt.date.today()
    last_date, count = DAILY_IMAGE_USAGE.get(chat_id, (today, 0))
    if last_date != today:
        count = 0
    if count >= IMAGE_GENERATION_LIMIT:
        return False
    DAILY_IMAGE_USAGE[chat_id] = (today, count + 1)
    return True

# Add functions to save messages to database
def _add_message_to_history(chat_id: int, role: str, text: str) -> None:
    """Add a message to the chat history (both in-memory and database)"""
    # Add to in-memory history first
    if chat_id in HISTORIES:
        HISTORIES[chat_id].append({"role": role, "text": text})
    
    # Add to database if enabled
    if USE_DATABASE and db_initialized and Session is not None and add_message is not None:
        try:
            db_session = Session()
            add_message(db_session, chat_id, role, text)
            db_session.close()
        except Exception as e:
            logging.error(f"Error adding message to database: {e}")

def _reset_chat_history(chat_id: int) -> None:
    """Reset chat history (both in-memory and database)"""
    # Reset in-memory history
    HISTORIES.pop(chat_id, None)
    
    # Reset database history if enabled
    if USE_DATABASE and db_initialized and Session is not None and reset_chat_history is not None:
        try:
            db_session = Session()
            reset_chat_history(db_session, chat_id)
            db_session.close()
        except Exception as e:
            logging.error(f"Error resetting chat history in database: {e}")

# Load state on import
_load_state() 