# app/db/models/llm_provider.py
from datetime import datetime
from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text
from sqlalchemy.orm import relationship
from app.db.session import Base

class LLMProvider(Base):
    __tablename__ = "llm_providers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, unique=True)
    provider_type = Column(String, nullable=False)  # openai, deepseek, gemini, etc.
    description = Column(Text, nullable=True)
    base_url = Column(String, nullable=True)  # Para APIs personalizadas/self-hosted
    is_active = Column(Boolean(), default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Definição explícita da relação "models" com backref para LLMModel
    models = relationship("LLMModel", back_populates="provider", cascade="all, delete-orphan")