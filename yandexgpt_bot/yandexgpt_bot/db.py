"""
Database module for YandexGPT bot using SQLAlchemy.
This module handles database connections, models, and operations for the bot.
"""
import datetime
import json
from typing import Dict, List, Optional, Any
from sqlalchemy import create_engine, Column, Integer, BigInteger, String, Text, DateTime, Boolean, ForeignKey, func, LargeBinary
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship, Session
from sqlalchemy.dialects.postgresql import JSONB
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64
import os

# Use absolute import
from yandexgpt_bot import config

Base = declarative_base()

# Create encryption handler
def get_encryption_key(key_string):
    # Convert string key to bytes using PBKDF2
    salt = b'yandexgpt_bot_salt'  # Use a proper salt in production!
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(key_string.encode()))
    return Fernet(key)

# Global variables
engine = None
Session = None
fernet = None  # Moved to init_db


class Chat(Base):
    """Chat model to store information about each chat"""
    __tablename__ = 'chats'
    
    id = Column(Integer, primary_key=True)
    chat_id = Column(BigInteger, unique=True, nullable=False, index=True)
    is_unlimited = Column(Boolean, default=False)
    username = Column(String(128), nullable=True)  # user username or None
    first_name = Column(String(128), nullable=True)  # user first name (for private chats)
    title = Column(String(256), nullable=True)  # group or channel title
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    
    # Relationships
    system_prompt = relationship("SystemPrompt", uselist=False, back_populates="chat", cascade="all, delete-orphan")
    usage_records = relationship("UsageRecord", back_populates="chat", cascade="all, delete-orphan")
    image_usage_records = relationship("ImageUsageRecord", back_populates="chat", cascade="all, delete-orphan")
    messages = relationship("Message", back_populates="chat", cascade="all, delete-orphan")

    def update_user_info(self, username=None, first_name=None, title=None):
        changed = False
        if username is not None and username != self.username:
            self.username = username
            changed = True
        if first_name is not None and first_name != self.first_name:
            self.first_name = first_name
            changed = True
        if title is not None and title != self.title:
            self.title = title
            changed = True
        return changed


class SystemPrompt(Base):
    """System prompt for each chat"""
    __tablename__ = 'system_prompts'
    
    id = Column(Integer, primary_key=True)
    chat_id = Column(BigInteger, ForeignKey('chats.chat_id', ondelete='CASCADE'), unique=True)
    prompt_text = Column(Text, nullable=False)
    encrypted = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    
    # Relationship
    chat = relationship("Chat", back_populates="system_prompt")
    
    def set_prompt(self, prompt: str) -> None:
        """Encrypt and set the prompt text"""
        if config.USE_DATABASE and self.encrypted and fernet is not None:
            self.prompt_text = fernet.encrypt(prompt.encode()).decode()
        else:
            self.prompt_text = prompt
    
    def get_prompt(self) -> str:
        """Decrypt and return the prompt text"""
        if config.USE_DATABASE and self.encrypted and self.prompt_text and fernet is not None:
            return fernet.decrypt(self.prompt_text.encode()).decode()
        return self.prompt_text


class Message(Base):
    """Message model to store chat messages"""
    __tablename__ = 'messages'
    
    id = Column(Integer, primary_key=True)
    chat_id = Column(BigInteger, ForeignKey('chats.chat_id', ondelete='CASCADE'), index=True)
    role = Column(String(50), nullable=False)  # 'system', 'user', 'assistant'
    content = Column(Text, nullable=False)
    encrypted = Column(Boolean, default=True)
    message_hash = Column(String(128), nullable=True)  # Optional hash for verification
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    sequence = Column(Integer, default=0)  # To maintain order
    
    # Relationship
    chat = relationship("Chat", back_populates="messages")
    
    def set_content(self, content: str) -> None:
        """Encrypt and set the message content"""
        if config.USE_DATABASE and self.encrypted and fernet is not None:
            self.content = fernet.encrypt(content.encode()).decode()
            # Create a hash for verification
            digest = hashes.Hash(hashes.SHA256())
            digest.update(content.encode())
            self.message_hash = base64.b64encode(digest.finalize()).decode()
        else:
            self.content = content
    
    def get_content(self) -> str:
        """Decrypt and return the message content"""
        if config.USE_DATABASE and self.encrypted and self.content and fernet is not None:
            return fernet.decrypt(self.content.encode()).decode()
        return self.content
    
    def verify_content(self) -> bool:
        """Verify the message content has not been tampered with"""
        if not config.USE_DATABASE or not self.encrypted or not self.message_hash or fernet is None:
            return True
        
        decrypted = self.get_content()
        digest = hashes.Hash(hashes.SHA256())
        digest.update(decrypted.encode())
        current_hash = base64.b64encode(digest.finalize()).decode()
        return current_hash == self.message_hash


class UsageRecord(Base):
    """Usage record for tracking daily usage limits"""
    __tablename__ = 'usage_records'
    
    id = Column(Integer, primary_key=True)
    chat_id = Column(BigInteger, ForeignKey('chats.chat_id', ondelete='CASCADE'), index=True)
    user_id = Column(BigInteger, nullable=True)  # ID of the user who sent the message
    user_username = Column(String(128), nullable=True)  # username of the user who sent the message
    user_first_name = Column(String(128), nullable=True)  # first name of the user who sent the message
    date = Column(DateTime, default=datetime.datetime.utcnow)
    count = Column(Integer, default=0)
    
    # Relationship
    chat = relationship("Chat", back_populates="usage_records")


class ImageUsageRecord(Base):
    """Image generation usage record for tracking daily limits"""
    __tablename__ = 'image_usage_records'
    
    id = Column(Integer, primary_key=True)
    chat_id = Column(BigInteger, ForeignKey('chats.chat_id', ondelete='CASCADE'), index=True)
    date = Column(DateTime, default=datetime.datetime.utcnow)
    count = Column(Integer, default=0)
    
    # Relationship
    chat = relationship("Chat", back_populates="image_usage_records")


def init_db():
    """Initialize database connection and create tables"""
    global engine, Session, fernet
    
    if not config.USE_DATABASE:
        return False
    
    try:
        engine = create_engine(config.DB_URL)
        Session = sessionmaker(bind=engine)
        Base.metadata.create_all(engine)
        fernet = get_encryption_key(config.DB_ENCRYPTION_KEY)
        return True
    except Exception as e:
        print(f"Database initialization error: {e}")
        return False


# Database utility functions

def get_or_create_chat(session: Session, chat_id: int) -> Chat:
    """Get or create a chat record"""
    chat = session.query(Chat).filter_by(chat_id=chat_id).first()
    if not chat:
        chat = Chat(chat_id=chat_id)
        session.add(chat)
        session.commit()
    return chat


def set_system_prompt(session: Session, chat_id: int, prompt: str) -> SystemPrompt:
    """Set system prompt for a chat"""
    chat = get_or_create_chat(session, chat_id)
    
    system_prompt = session.query(SystemPrompt).filter_by(chat_id=chat_id).first()
    if not system_prompt:
        system_prompt = SystemPrompt(chat_id=chat_id)
        session.add(system_prompt)
    
    system_prompt.set_prompt(prompt)
    session.commit()
    return system_prompt


def get_system_prompt(session: Session, chat_id: int) -> Optional[str]:
    """Get system prompt for a chat"""
    system_prompt = session.query(SystemPrompt).filter_by(chat_id=chat_id).first()
    if system_prompt:
        return system_prompt.get_prompt()
    return None


def add_message(session: Session, chat_id: int, role: str, content: str, sequence: int = None) -> Message:
    """Add a message to chat history"""
    chat = get_or_create_chat(session, chat_id)
    
    if sequence is None:
        # Get the next sequence number
        last_message = session.query(Message).filter_by(chat_id=chat_id).order_by(Message.sequence.desc()).first()
        sequence = (last_message.sequence + 1) if last_message else 0
    
    message = Message(chat_id=chat_id, role=role, sequence=sequence)
    message.set_content(content)
    
    session.add(message)
    session.commit()
    return message


def get_chat_history(session: Session, chat_id: int, limit: int = None) -> List[Dict[str, str]]:
    """Get chat history for a chat"""
    query = session.query(Message).filter_by(chat_id=chat_id).order_by(Message.sequence)
    
    if limit:
        query = query.limit(limit)
    
    messages = query.all()
    history = []
    
    for msg in messages:
        history.append({
            "role": msg.role,
            "text": msg.get_content()
        })
    
    return history


def reset_chat_history(session: Session, chat_id: int) -> None:
    """Reset chat history, keeping only system message"""
    # Keep system message
    system_msg = session.query(Message).filter_by(
        chat_id=chat_id, 
        role="system"
    ).order_by(Message.sequence).first()
    
    # Delete all other messages
    session.query(Message).filter(
        Message.chat_id == chat_id,
        Message.role != "system"
    ).delete()
    
    session.commit()


def check_and_increment_usage(session: Session, chat_id: int, daily_limit: int) -> bool:
    """Check and increment usage, returns True if under limit"""
    chat = get_or_create_chat(session, chat_id)
    
    # Check if unlimited
    if chat.is_unlimited:
        return True
    
    today = datetime.datetime.utcnow().date()
    today_start = datetime.datetime.combine(today, datetime.time.min)
    
    # Get today's usage
    usage = session.query(UsageRecord).filter(
        UsageRecord.chat_id == chat_id,
        UsageRecord.date >= today_start
    ).first()
    
    if not usage:
        usage = UsageRecord(chat_id=chat_id, date=today_start, count=0)
        session.add(usage)
    
    # Check limit
    if usage.count >= daily_limit:
        return False
    
    # Increment
    usage.count += 1
    session.commit()
    return True


def check_and_increment_image_usage(session: Session, chat_id: int, daily_limit: int) -> bool:
    """Check and increment image usage, returns True if under limit"""
    chat = get_or_create_chat(session, chat_id)
    
    # Check if unlimited
    if chat.is_unlimited:
        return True
    
    today = datetime.datetime.utcnow().date()
    today_start = datetime.datetime.combine(today, datetime.time.min)
    
    # Get today's usage
    usage = session.query(ImageUsageRecord).filter(
        ImageUsageRecord.chat_id == chat_id,
        ImageUsageRecord.date >= today_start
    ).first()
    
    if not usage:
        usage = ImageUsageRecord(chat_id=chat_id, date=today_start, count=0)
        session.add(usage)
    
    # Check limit
    if usage.count >= daily_limit:
        return False
    
    # Increment
    usage.count += 1
    session.commit()
    return True


def set_unlimited_status(session: Session, chat_id: int, is_unlimited: bool) -> None:
    """Set unlimited status for a chat"""
    chat = get_or_create_chat(session, chat_id)
    chat.is_unlimited = is_unlimited
    session.commit()


def load_unlimited_ids(session: Session) -> List[int]:
    """Load all chat IDs with unlimited status"""
    chats = session.query(Chat).filter_by(is_unlimited=True).all()
    return [chat.chat_id for chat in chats]


def update_chat_user_info(session: Session, chat_id: int, username=None, first_name=None, title=None):
    """Update username, first_name, and title for a chat if they have changed"""
    chat = session.query(Chat).filter_by(chat_id=chat_id).first()
    if not chat:
        chat = Chat(chat_id=chat_id)
        session.add(chat)
    changed = chat.update_user_info(username=username, first_name=first_name, title=title)
    if changed:
        session.commit()


def add_usage_record(session: Session, chat_id: int, user_id: int = None, user_username: str = None, user_first_name: str = None, date: datetime.datetime = None, count: int = 1):
    """Add a usage record with optional user details"""
    if date is None:
        date = datetime.datetime.utcnow()
    usage = UsageRecord(
        chat_id=chat_id,
        user_id=user_id,
        user_username=user_username,
        user_first_name=user_first_name,
        date=date,
        count=count
    )
    session.add(usage)
    session.commit()
    return usage