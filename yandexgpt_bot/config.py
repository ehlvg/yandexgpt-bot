import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file if present (for local development)
load_dotenv()

# Required secrets (raise error if missing)
BOT_TOKEN = os.environ.get("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN environment variable is required.")

YC_FOLDER_ID = os.environ.get("YC_FOLDER_ID")
if not YC_FOLDER_ID:
    raise RuntimeError("YC_FOLDER_ID environment variable is required.")

YC_API_KEY = os.environ.get("YC_API_KEY")
if not YC_API_KEY:
    raise RuntimeError("YC_API_KEY environment variable is required.")

# Optional config with defaults
data_dir = os.environ.get("DATA_DIR", ".")
DATA_DIR = data_dir
UNLIMITED_IDS_PATH = Path(data_dir) / os.environ.get("UNLIMITED_CHAT_IDS_FILE", "unlimited_chats.txt")
STATE_FILE = Path(data_dir) / os.environ.get("STATE_FILE", "state.json")
YANDEXGPT_MODEL = os.environ.get("YANDEXGPT_MODEL", "yandexgpt")
MAX_HISTORY_TURNS = int(os.environ.get("MAX_HISTORY_TURNS", 10))
GPT_TEMPERATURE = float(os.environ.get("GPT_TEMPERATURE", 0.7))
MAX_QUESTION_LEN = int(os.environ.get("MAX_QUESTION_LEN", 4000))
DAILY_LIMIT = int(os.environ.get("DAILY_LIMIT", 15))
IMAGE_GENERATION_LIMIT = int(os.environ.get("IMAGE_GENERATION_LIMIT", 5))
DEFAULT_SYSTEM_PROMPT = os.environ.get("SYSTEM_PROMPT", "You are a helpful assistant.")

# Interface language setting ("english" or "russian")
LANGUAGE = os.environ.get("LANGUAGE", "english")

# List of Telegram user IDs with admin privileges (comma-separated)
admin_ids = os.environ.get("ADMIN_CHAT_IDS", "")
ADMIN_CHAT_IDS = set(int(x) for x in admin_ids.split(",") if x.strip().isdigit())

# Database configuration
USE_DATABASE = os.environ.get("USE_DATABASE", "false").lower() == "true"
if USE_DATABASE:
    DB_TYPE = os.environ.get("DB_TYPE", "postgresql")
    DB_HOST = os.environ.get("DB_HOST", "localhost")
    DB_PORT = int(os.environ.get("DB_PORT", 5432))
    DB_USER = os.environ.get("DB_USER", "postgres")
    DB_PASSWORD = os.environ.get("DB_PASSWORD", "postgres")
    DB_NAME = os.environ.get("DB_NAME", "yagptbot")
    DB_ENCRYPTION_KEY = os.environ.get("DB_ENCRYPTION_KEY", "your-secure-encryption-key-change-me")
    DB_URL = f"{DB_TYPE}://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"