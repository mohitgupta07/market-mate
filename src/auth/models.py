from typing import Optional, List
from datetime import datetime
from sqlalchemy import ForeignKey, String, Text, DateTime, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
import enum
import uuid

from .database import Base
from fastapi_users.db import SQLAlchemyBaseUserTable


# --- User model (from FastAPI Users) ---
class User(SQLAlchemyBaseUserTable[int], Base):  # Or UUID instead of int
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String, nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    is_superuser: Mapped[bool] = mapped_column(default=False, nullable=False)
    is_verified: Mapped[bool] = mapped_column(default=False, nullable=False)
    full_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    
    # Add tier system for rate limiting
    tier: Mapped[str] = mapped_column(String, default="free", nullable=False)  # e.g., free, pro, enterprise
    conversations: Mapped[List["Conversation"]] = relationship(back_populates="user")


# --- Conversation model ---
class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    title: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # Store latest summary for this conversation
    llm_model: Mapped[str] = mapped_column(String, default="gpt-3.5-turbo", nullable=False)  # Store selected LLM model for this conversation

    user: Mapped["User"] = relationship(back_populates="conversations")
    messages: Mapped[List["Message"]] = relationship(back_populates="conversation", cascade="all, delete")


# --- Enum for message roles ---
class RoleEnum(str, enum.Enum):
    system = "system"
    user = "user"
    human = "user"
    ai = "assistant"


# --- Message model ---
class Message(Base):
    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("conversations.id"))
    role: Mapped[RoleEnum] = mapped_column(Enum(RoleEnum), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    conversation: Mapped["Conversation"] = relationship(back_populates="messages")
