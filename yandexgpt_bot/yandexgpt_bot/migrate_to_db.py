#!/usr/bin/env python3
"""
Migration script to transfer data from JSON files to database.
This script will read the state.json and unlimited_chats.txt files
and populate the database with their data.
"""
import sys
import json
import logging
import datetime
from pathlib import Path

# Add parent directory to path to import the bot package
sys.path.insert(0, str(Path(__file__).parent.parent))

from yandexgpt_bot.config import USE_DATABASE, STATE_FILE, UNLIMITED_IDS_PATH
# Импортируем только db модуль, а не его функции
from yandexgpt_bot import db

def load_state_from_file():
    """Load state from JSON file"""
    if not STATE_FILE.exists():
        print(f"State file {STATE_FILE} does not exist.")
        return None
    
    try:
        with open(STATE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading state file: {e}")
        return None

def load_unlimited_ids_from_file():
    """Load unlimited IDs from file"""
    if not UNLIMITED_IDS_PATH.exists():
        print(f"Unlimited IDs file {UNLIMITED_IDS_PATH} does not exist.")
        return []
    
    try:
        with open(UNLIMITED_IDS_PATH, 'r', encoding='utf-8') as f:
            return [int(line.strip()) for line in f if line.strip().isdigit()]
    except Exception as e:
        print(f"Error loading unlimited IDs file: {e}")
        return []

def migrate_data():
    """Migrate data from files to database"""
    if not USE_DATABASE:
        print("Database usage is disabled in config.yaml. Set use_database: true to enable.")
        return False
    
    # Initialize database
    if not db.init_db():
        print("Failed to initialize database. Check connection parameters in config.yaml")
        return False
    
    # Проверяем, что Session существует после инициализации
    if db.Session is None:
        print("Database session initialization failed. Session is None.")
        return False
    
    # Start a session
    session = db.Session()
    
    try:
        # Load state from file
        state_data = load_state_from_file()
        if not state_data:
            print("No state data to migrate.")
            return False
        
        # Migrate unlimited IDs
        unlimited_ids = load_unlimited_ids_from_file()
        for chat_id in unlimited_ids:
            db.set_unlimited_status(session, chat_id, True)
            print(f"Set unlimited status for chat ID {chat_id}")
        
        # Migrate prompts
        prompts = state_data.get("prompts", {})
        for chat_id_str, prompt in prompts.items():
            chat_id = int(chat_id_str)
            db.set_system_prompt(session, chat_id, prompt)
            print(f"Migrated system prompt for chat ID {chat_id}")
        
        # Migrate chat histories
        histories = state_data.get("histories", {})
        for chat_id_str, messages in histories.items():
            chat_id = int(chat_id_str)
            for i, message in enumerate(messages):
                role = message.get("role", "")
                text = message.get("text", "")
                if role and text:
                    db.add_message(session, chat_id, role, text, sequence=i)
            print(f"Migrated {len(messages)} messages for chat ID {chat_id}")
        
        # Migrate daily usage
        daily_usage = state_data.get("daily_usage", {})
        for chat_id_str, usage_data in daily_usage.items():
            chat_id = int(chat_id_str)
            date_str, count = usage_data
            date = datetime.datetime.fromisoformat(date_str)
            
            # Skip if not today (we only care about today's usage for rate limiting)
            if date.date() == datetime.datetime.utcnow().date():
                # Add usage records manually to match the count
                for i in range(count):
                    db.check_and_increment_usage(session, chat_id, 9999)  # Use a high limit to ensure it succeeds
                print(f"Migrated usage count of {count} for chat ID {chat_id}")
        
        # Migrate image usage
        image_usage = state_data.get("image_usage", {})
        for chat_id_str, usage_data in image_usage.items():
            chat_id = int(chat_id_str)
            date_str, count = usage_data
            date = datetime.datetime.fromisoformat(date_str)
            
            # Skip if not today
            if date.date() == datetime.datetime.utcnow().date():
                # Add usage records manually to match the count
                for i in range(count):
                    db.check_and_increment_image_usage(session, chat_id, 9999)  # Use a high limit
                print(f"Migrated image usage count of {count} for chat ID {chat_id}")
        
        session.commit()
        print("Migration completed successfully!")
        return True
    
    except Exception as e:
        session.rollback()
        print(f"Error during migration: {e}")
        return False
    
    finally:
        session.close()

def main():
    print("Starting migration from JSON files to database...")
    success = migrate_data()
    
    if success:
        print("\nMigration completed successfully!")
        print("You can now use the bot with the database backend.")
        print("Tip: Backup your state.json and unlimited_chats.txt files before proceeding.")
    else:
        print("\nMigration failed. Please check the errors above.")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main() 