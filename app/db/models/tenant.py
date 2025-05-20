from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.db.session import Base


class Tenant(Base):
    __tablename__ = "tenants"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True, nullable=False)
    description = Column(String, nullable=True)
    is_active = Column(Boolean(), default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    default_llm_provider_id = Column(Integer, ForeignKey("llm_providers.id"), nullable=True)
    default_llm_model_id = Column(Integer, ForeignKey("llm_models.id"), nullable=True)
    llm_api_key = Column(String, nullable=True)  # Chave API específica do tenant (opcional)

    users = relationship("User", back_populates="tenant")
    webhooks = relationship("Webhook", back_populates="tenant", cascade="all, delete-orphan")
    agents = relationship("Agent", back_populates="tenant", cascade="all, delete-orphan")
    default_llm_provider = relationship("LLMProvider")
    default_llm_model = relationship("LLMModel")
    
    # uso de token
    token_limits = relationship("TokenUsageLimit", back_populates="tenant", cascade="all, delete-orphan")
    token_usage = relationship("TokenUsageLog", back_populates="tenant")
    token_alerts = relationship("TokenUsageAlert", back_populates="tenant")