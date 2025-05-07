#!/usr/bin/env python3

import sys
from pathlib import Path

# Добавляем родительский каталог в путь Python
sys.path.insert(0, str(Path(__file__).parent.parent))

from yandexgpt_bot.config import USE_DATABASE, DB_URL, UNLIMITED_IDS_PATH
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from yandexgpt_bot.db import Base, Chat

def main():
    print("Checking database connection and data...")
    
    if not USE_DATABASE:
        print("Database is disabled in config")
        return
    
    try:
        # Создаем подключение к базе данных напрямую
        engine = create_engine(DB_URL)
        Session = sessionmaker(bind=engine)
        session = Session()
        
        print("Database connected successfully")
        
        # Добавляем групповой чат из unlimited_chats.txt, если его нет в БД
        group_id = -1002206813481  # ID группового чата из unlimited_chats.txt
        
        group_chat = session.query(Chat).filter_by(chat_id=group_id).first()
        if not group_chat:
            print(f"Adding group chat with ID {group_id} to database...")
            group_chat = Chat(chat_id=group_id, is_unlimited=True)
            session.add(group_chat)
            session.commit()
            print(f"Group chat added successfully")
        
        # Проверяем все записи в БД
        chats = session.query(Chat).all()
        print(f"Found {len(chats)} chats in database:")
        
        for chat in chats:
            print(f"ID: {chat.id}, Chat ID: {chat.chat_id}, Unlimited: {chat.is_unlimited}")
    except Exception as e:
        print(f"Error accessing database: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    main() 