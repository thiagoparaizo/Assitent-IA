# Novo modelo ContactControl em app/db/models/contact_control.py
from sqlalchemy import Column, ForeignKey, Integer, Boolean, String, DateTime, Enum, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
import enum

from app.db.session import Base

class ContactListType(enum.Enum):
    WHITELIST = "whitelist"  # Apenas responde a contatos nesta lista
    BLACKLIST = "blacklist"  # Responde a todos exceto contatos nesta lista

class ContactControl(Base):
    __tablename__ = "agent_contact_controls"
    
    id = Column(Integer, primary_key=True, index=True)
    agent_id = Column(UUID(as_uuid=True), ForeignKey("agents.id"), nullable=False)
    device_id = Column(Integer, nullable=False)  # Manteremos também qual dispositivo
    contact_id = Column(String, nullable=False)  # ID do contato (JID/chat_id)
    list_type = Column(Enum(ContactListType), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relacionamento com o agente
    agent = relationship("Agent", back_populates="contact_controls")
    
    # Índice composto para garantir unicidade
    __table_args__ = (
        UniqueConstraint('agent_id', 'device_id', 'contact_id', name='uix_agent_device_contact'),
    )