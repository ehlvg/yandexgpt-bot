# YandexGPT Telegram Bot

## Запуск бота

Для запуска бота выполните:

```bash
# Находясь в корневом каталоге проекта (содержащем папку yandexgpt_bot)
python3 run_bot.py
```

## Конфигурация

Все параметры (токены, лимиты, system prompt и др.) теперь задаются в файле `config.yaml` в корне папки. Пример:

```yaml
telegram_bot_token: 'YOUR_TELEGRAM_BOT_TOKEN'
yc_folder_id: 'YOUR_YC_FOLDER_ID'
yc_api_key: 'YOUR_YC_API_KEY'
data_dir: '.'
unlimited_chat_ids_file: 'unlimited_chats.txt'
state_file: 'state.json'
yandexgpt_model: 'yandexgpt'
max_history_turns: 10
gpt_temperature: 0.7
max_question_len: 4000
daily_limit: 15
image_generation_limit: 5

# Настройки языка интерфейса (english или russian)
language: 'english'

# Администраторы бота - список ID пользователей Telegram с правами админа
admin_chat_ids: [123456789, 987654321]

# Database configuration - optional, set use_database to false to disable
use_database: true
database:
  type: 'postgresql'
  host: 'localhost'
  port: 5432
  user: 'postgres'
  password: 'postgres'
  dbname: 'yagptbot'
  encryption_key: 'your-secure-encryption-key-change-me'

system_prompt: |
  ...
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
# Находясь в корневом каталоге проекта (содержащем папку yandexgpt_bot)
python3 yandexgpt_bot/init_db.py
```

### Миграция данных

Если вы уже использовали бота без базы данных и хотите перенести существующие данные:

```bash
# Находясь в корневом каталоге проекта (содержащем папку yandexgpt_bot)
python3 yandexgpt_bot/migrate_to_db.py
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