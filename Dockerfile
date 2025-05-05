# Используем официальный образ Python
FROM python:3.12-slim

# Устанавливаем рабочую директорию
WORKDIR /app

# Копируем файлы проекта
COPY bot.py unlimited_chats.txt state.json ./

# Устанавливаем зависимости
RUN pip install --no-cache-dir python-telegram-bot>=22 yandex-cloud-ml-sdk>=1 python-dotenv

# Опционально указываем переменные окружения по умолчанию
ENV UNLIMITED_CHAT_IDS_FILE=unlimited_chats.txt \
    STATE_FILE=state.json

# Команда запуска бота
CMD ["python", "bot.py"]