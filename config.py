import yaml
from pathlib import Path

CONFIG_PATH = Path(__file__).parent / "config.yaml"

with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    _cfg = yaml.safe_load(f)

BOT_TOKEN = _cfg["telegram_bot_token"]
YC_FOLDER_ID = _cfg["yc_folder_id"]
YC_API_KEY = _cfg["yc_api_key"]
DATA_DIR = _cfg.get("data_dir", ".")
UNLIMITED_IDS_PATH = Path(DATA_DIR) / _cfg.get("unlimited_chat_ids_file", "unlimited_chats.txt")
STATE_FILE = Path(DATA_DIR) / _cfg.get("state_file", "state.json")
YANDEXGPT_MODEL = _cfg.get("yandexgpt_model", "yandexgpt")
MAX_HISTORY_TURNS = _cfg.get("max_history_turns", 10)
GPT_TEMPERATURE = _cfg.get("gpt_temperature", 0.7)
MAX_QUESTION_LEN = _cfg.get("max_question_len", 4000)
DAILY_LIMIT = _cfg.get("daily_limit", 15)
IMAGE_GENERATION_LIMIT = _cfg.get("image_generation_limit", 5)
DEFAULT_SYSTEM_PROMPT = _cfg["system_prompt"]

# Настройка языка интерфейса (english или russian)
LANGUAGE = _cfg.get("language", "english")

# Список ID чатов с правами администратора
ADMIN_CHAT_IDS = set(_cfg.get("admin_chat_ids", []))

# Database configuration
USE_DATABASE = _cfg.get("use_database", False)
if USE_DATABASE:
    DB_CONFIG = _cfg.get("database", {})
    DB_TYPE = DB_CONFIG.get("type", "postgresql")
    DB_HOST = DB_CONFIG.get("host", "localhost")
    DB_PORT = DB_CONFIG.get("port", 5432)
    DB_USER = DB_CONFIG.get("user", "postgres")
    DB_PASSWORD = DB_CONFIG.get("password", "postgres")
    DB_NAME = DB_CONFIG.get("dbname", "yagptbot")
    DB_ENCRYPTION_KEY = DB_CONFIG.get("encryption_key", "your-secure-encryption-key-change-me")
    
    # Database URL for SQLAlchemy
    DB_URL = f"{DB_TYPE}://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}" 