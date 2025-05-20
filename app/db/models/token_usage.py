# app/db/models/token_usage.py
from datetime import datetime
import uuid
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Float, Boolean, UUID
from sqlalchemy.orm import relationship

from app.db.session import Base

class TokenUsageLimit(Base):
    """Armazena limites de uso de tokens por tenant ou agente."""
    __tablename__ = "token_usage_limits"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True)
    agent_id = Column(UUID(as_uuid=True), ForeignKey("agents.id"), nullable=True)
    monthly_limit = Column(Integer, nullable=False)  # Limite mensal em tokens
    daily_limit = Column(Integer, nullable=True)     # Limite diário opcional
    warning_threshold = Column(Float, default=0.8)   # Percentual para acionar alerta (0.8 = 80%)
    notify_email = Column(String, nullable=True)     # Email para notificações
    notify_webhook_url = Column(String, nullable=True) # URL de webhook para notificações
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relacionamentos
    tenant = relationship("Tenant", back_populates="token_limits")
    agent = relationship("Agent", back_populates="token_limits")

class TokenUsageLog(Base):
    """Registra o uso de tokens em chamadas LLM."""
    __tablename__ = "token_usage_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, index=True, default=uuid.uuid4)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    agent_id = Column(UUID(as_uuid=True), ForeignKey("agents.id"), nullable=False)
    conversation_id = Column(String, nullable=True)
    model_id = Column(Integer, ForeignKey("llm_models.id"), nullable=False)
    prompt_tokens = Column(Integer, nullable=False)
    completion_tokens = Column(Integer, nullable=False)
    total_tokens = Column(Integer, nullable=False)
    estimated_cost_usd = Column(Float, default=0.0)
    timestamp = Column(DateTime, default=datetime.utcnow)

    # Relacionamentos
    tenant = relationship("Tenant", back_populates="token_usage")
    agent = relationship("Agent", back_populates="token_usage")
    model = relationship("LLMModel", back_populates="token_usage")

class TokenUsageAlert(Base):
    """Registra alertas enviados para uso de tokens."""
    __tablename__ = "token_usage_alerts"

    id = Column(UUID(as_uuid=True), primary_key=True, index=True, default=uuid.uuid4)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True)
    agent_id = Column(UUID(as_uuid=True), ForeignKey("agents.id"), nullable=True)
    limit_type = Column(String, nullable=False)  # "monthly", "daily"
    threshold_value = Column(Float, nullable=False)  # 0.8 = 80%
    current_usage = Column(Integer, nullable=False)
    max_limit = Column(Integer, nullable=False)
    notification_sent = Column(Boolean, default=False)
    notification_channel = Column(String, nullable=True)  # "email", "webhook"
    notification_target = Column(String, nullable=True)  # email ou URL
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relacionamentos
    tenant = relationship("Tenant", back_populates="token_alerts")
    agent = relationship("Agent", back_populates="token_alerts")