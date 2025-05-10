# Используем официальный образ Python
FROM python:3.12-slim

# Устанавливаем рабочую директорию
WORKDIR /app

# Копируем файлы проекта
COPY . /app/

# Устанавливаем зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Создаем пустой state.json, если он не будет скопирован
RUN if [ ! -f state.json ]; then echo "{}" > state.json; fi

# Опционально указываем переменные окружения по умолчанию
ENV UNLIMITED_CHAT_IDS_FILE=unlimited_chats.txt \
    STATE_FILE=state.json \
    PYTHONPATH=/app

# Указываем порт (требование платформы)
EXPOSE 8080

# Команда запуска бота
CMD ["python", "-m", "yandexgpt_bot.run_bot"]
