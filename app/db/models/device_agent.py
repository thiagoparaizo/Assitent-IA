# Novo modelo DeviceAgent em app/db/models/device_agent.py
from sqlalchemy import Column, ForeignKey, Integer, Boolean, String, DateTime, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime

from app.db.session import Base

class DeviceAgent(Base):
    __tablename__ = "device_agent_mappings"
    
    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(Integer, nullable=False)
    agent_id = Column(UUID(as_uuid=True), ForeignKey("agents.id"), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relacionamento com o agente
    agent = relationship("Agent", back_populates="device_mappings")
    
    # Índice composto para garantir unicidade
    __table_args__ = (
        UniqueConstraint('device_id', 'is_active', name='uix_device_active_agent'),
    )