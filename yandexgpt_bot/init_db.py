#!/usr/bin/env python3
"""
Database initialization script for YandexGPT bot.
Этот скрипт пересоздаёт все таблицы. После добавления username/first_name/title в Chat обязательно запустите его для применения изменений в схеме БД!
"""
import sys
import logging
from pathlib import Path
from sqlalchemy import create_engine

# Добавляем родительский каталог в путь Python
sys.path.insert(0, str(Path(__file__).parent.parent))

# Прямые импорты из модуля
from yandexgpt_bot import config
from yandexgpt_bot.db import Base

def main():
    if not config.USE_DATABASE:
        print("Database usage is disabled in config.yaml. Set use_database: true to enable.")
        return
    
    print("Initializing database...")
    
    try:
        # Создаем подключение к базе данных
        engine = create_engine(config.DB_URL)
        
        # Пересоздаем все таблицы
        print("Dropping all tables...")
        Base.metadata.drop_all(engine)
        
        print("Creating tables with new schema...")
        Base.metadata.create_all(engine)
        
        print(f"Database schema updated successfully!")
        print(f"Created tables: {', '.join(table.name for table in Base.metadata.tables.values())}")
    except Exception as e:
        print(f"Error updating database schema: {e}")
        return

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main() 