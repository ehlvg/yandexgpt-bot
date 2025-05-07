# YandexGPT Telegram Bot

## Запуск бота

Есть два способа запуска бота:

### Способ 1: Прямой запуск модуля (рекомендуется)

```bash
# Находясь в любой директории
python3 -m yandexgpt_bot.run_bot
```

### Способ 2: Запуск как пакета Python

```bash
# Находясь в директории, содержащей пакет yandexgpt_bot
python3 -c "from yandexgpt_bot.bot import main; main()"
```

## Configuration

All configuration is now done via **environment variables**. This is secure and works well for Docker deployments. You no longer need a config.yaml file.

### Required environment variables
- `BOT_TOKEN` – Telegram bot token
- `YC_FOLDER_ID` – Yandex Cloud folder ID
- `YC_API_KEY` – Yandex Cloud API key / IAM token

### Optional environment variables (with defaults)
- `DATA_DIR` – Data directory (default: `.`)
- `UNLIMITED_CHAT_IDS_FILE` – Path to unlimited chat IDs file (default: `unlimited_chats.txt`)
- `STATE_FILE` – Path to state file (default: `state.json`)
- `YANDEXGPT_MODEL` – YandexGPT model name (default: `yandexgpt`)
- `MAX_HISTORY_TURNS` – Max history turns (default: `10`)
- `GPT_TEMPERATURE` – GPT temperature (default: `0.7`)
- `MAX_QUESTION_LEN` – Max question length (default: `4000`)
- `DAILY_LIMIT` – Daily request limit per chat (default: `15`)
- `IMAGE_GENERATION_LIMIT` – Daily image generation limit per chat (default: `5`)
- `SYSTEM_PROMPT` – System prompt for the assistant (default: "You are a helpful assistant.")
- `LANGUAGE` – Interface language: `english` or `russian` (default: `english`)
- `ADMIN_CHAT_IDS` – Comma-separated list of Telegram user IDs with admin privileges (e.g. `123456789,987654321`)
- `USE_DATABASE` – Set to `true` to enable database support (default: `false`)
- `DB_TYPE`, `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`, `DB_ENCRYPTION_KEY` – Database connection settings (see below)

### Database environment variables (if `USE_DATABASE=true`)
- `DB_TYPE` – Database type (default: `postgresql`)
- `DB_HOST` – Database host (default: `localhost`)
- `DB_PORT` – Database port (default: `5432`)
- `DB_USER` – Database user (default: `postgres`)
- `DB_PASSWORD` – Database password (default: `postgres`)
- `DB_NAME` – Database name (default: `yagptbot`)
- `DB_ENCRYPTION_KEY` – Encryption key for sensitive data

### Example: Running with Docker

```sh
docker run \
  -e BOT_TOKEN=your-telegram-token \
  -e YC_FOLDER_ID=your-folder-id \
  -e YC_API_KEY=your-yandex-api-key \
  -e ADMIN_CHAT_IDS=123456789,987654321 \
  yourimage
```

For local development, you can create a `.env` file (not committed to git) with your variables:

```
BOT_TOKEN=your-telegram-token
YC_FOLDER_ID=your-folder-id
YC_API_KEY=your-yandex-api-key
ADMIN_CHAT_IDS=123456789,987654321
```

## Административная панель

Бот включает административную панель, доступную только пользователям из списка `admin_chat_ids` в конфигурации. 

> **Важно**: В `admin_chat_ids` нужно указывать ID пользователей Telegram, а не ID чатов. 
> Чтобы узнать свой ID, можно написать боту [@userinfobot](https://t.me/userinfobot).

Функции админ-панели:
- Просмотр списка пользователей с безлимитным доступом
- Добавление/удаление пользователей с безлимитным доступом
- Просмотр статистики использования бота
- Переключение языка интерфейса (английский/русский)

Для доступа к админ-панели отправьте команду `/admin` боту. Панель имеет интуитивно понятный интерфейс с кнопками.

## Поддержка языков

Бот поддерживает два языка интерфейса:
- 🇬🇧 Английский (по умолчанию)
- 🇷🇺 Русский

Язык можно изменить через административную панель, выбрав пункт "🌐 Change Language" / "🌐 Сменить язык".
Выбранный язык сохраняется в конфигурации и применяется ко всем пользователям бота.

## База данных

Бот поддерживает хранение данных в PostgreSQL. В базе данных хранится:
- История сообщений (зашифрованная)
- Системные промпты для каждого чата
- Учет использования (лимиты запросов)
- Статусы неограниченного доступа

Для включения базы данных установите параметр `use_database: true` в `config.yaml` и укажите параметры подключения в разделе `database`.

### Инициализация базы данных

Перед первым запуском бота с базой данных необходимо инициализировать схему базы:

```bash
# Инициализация базы данных
python3 -m yandexgpt_bot.init_db
```

### Миграция данных

Если вы уже использовали бота без базы данных и хотите перенести существующие данные:

```bash
# Миграция данных из файлов в базу данных
python3 -m yandexgpt_bot.migrate_to_db
```

## Зависимости

- Python 3.8+
- python-telegram-bot >= 22
- yandex-cloud-ml-sdk >= 0.9.1
- PyYAML >= 6.0
- SQLAlchemy >= 2.0 (для работы с базой данных)
- psycopg2-binary >= 2.9.5 (для PostgreSQL)
- cryptography >= 40.0 (для шифрования данных)

Установка зависимостей:

```bash
python3 -m pip install -r yandexgpt_bot/requirements.txt
``` 