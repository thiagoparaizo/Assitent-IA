from datetime import datetime
import uuid
from sqlalchemy import UUID, Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.db.session import Base


class Webhook(Base):
    __tablename__ = "webhooks"

    id = Column(UUID(as_uuid=True), primary_key=True, index=True, default=uuid.uuid4)
    url = Column(String, nullable=False)
    secret = Column(String, nullable=True)
    events = Column(Text, nullable=True)  # JSON string of event types
    device_ids = Column(Text, nullable=True)  # JSON string of device IDs
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Define relationship with tenant
    tenant = relationship("Tenant", back_populates="webhooks")
    logs = relationship("WebhookLog", back_populates="webhook", cascade="all, delete-orphan")


class WebhookLog(Base):
    __tablename__ = "webhook_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, index=True, default=uuid.uuid4)
    webhook_id = Column(UUID(as_uuid=True), ForeignKey("webhooks.id", ondelete="CASCADE"), nullable=False)
    status = Column(String(50), nullable=False)
    event_type = Column(String(100), nullable=True)
    attempt_count = Column(Integer, default=0)
    response_code = Column(Integer, nullable=True)
    response_body = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    payload = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    webhook = relationship("Webhook", back_populates="logs")