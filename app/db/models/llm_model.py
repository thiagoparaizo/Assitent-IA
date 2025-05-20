# app/db/models/llm_model.py
from datetime import datetime
from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from app.db.session import Base

class LLMModel(Base):
    __tablename__ = "llm_models"

    id = Column(Integer, primary_key=True, index=True)
    provider_id = Column(Integer, ForeignKey("llm_providers.id"), nullable=False)
    name = Column(String, nullable=False)
    model_id = Column(String, nullable=False)  # Identificador do modelo na API (gpt-4, gemini-pro, etc)
    max_tokens = Column(Integer, nullable=True)
    default_temperature = Column(Float, default=0.7)
    supports_functions = Column(Boolean, default=False)
    supports_vision = Column(Boolean, default=False)
    is_active = Column(Boolean(), default=True)
    cost_per_1k_tokens = Column(Float, default=0.0)  # Custo por 1000 tokens (para tracking)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Definição explícita da relação com LLMProvider
    provider = relationship("LLMProvider", back_populates="models")
    # Definição explícita da relação com TokenUsageLog
    token_usage = relationship("TokenUsageLog", back_populates="model")