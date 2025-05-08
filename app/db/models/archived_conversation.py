from datetime import datetime
import uuid
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB

from app.db.session import Base

class ArchivedConversation(Base):
    __tablename__ = "archived_conversations"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(String, nullable=False, index=True)
    tenant_id = Column(String, nullable=False, index=True)
    user_id = Column(String, nullable=False, index=True)
    history = Column(JSONB, nullable=False)  # PostgreSQL JSONB para armazenar o histórico
    meta_data = Column(JSONB, nullable=True)  # PostgreSQL JSONB para armazenar metadados
    message_count = Column(Integer, default=0)
    archive_reason = Column(String, nullable=True)
    archived_at = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)