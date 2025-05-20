# app/schemas/token_usage.py
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, UUID4

class TokenUsageLimitBase(BaseModel):
    tenant_id: Optional[int] = None
    agent_id: Optional[UUID4] = None
    monthly_limit: int
    daily_limit: Optional[int] = None
    warning_threshold: float = 0.8
    notify_email: Optional[str] = None
    notify_webhook_url: Optional[str] = None
    is_active: bool = True

class TokenUsageLimitCreate(TokenUsageLimitBase):
    pass

class TokenUsageLimitUpdate(BaseModel):
    monthly_limit: Optional[int] = None
    daily_limit: Optional[int] = None
    warning_threshold: Optional[float] = None
    notify_email: Optional[str] = None
    notify_webhook_url: Optional[str] = None
    is_active: Optional[bool] = None

class TokenUsageLimitResponse(TokenUsageLimitBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True

class TokenUsageLogBase(BaseModel):
    tenant_id: int
    agent_id: UUID4
    conversation_id: Optional[str] = None
    model_id: int
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    estimated_cost_usd: float = 0.0

class TokenUsageLogCreate(TokenUsageLogBase):
    pass

class TokenUsageLogResponse(TokenUsageLogBase):
    id: UUID4
    timestamp: datetime
    model_name: Optional[str] = None
    agent_name: Optional[str] = None
    tenant_name: Optional[str] = None

    class Config:
        orm_mode = True

class TokenUsageSummary(BaseModel):
    tenant_id: Optional[int] = None
    agent_id: Optional[str] = None
    period: str  # "daily", "monthly", "yearly"
    period_value: str  # e.g., "2025-05", "2025-05-20"
    total_tokens: int
    prompt_tokens: int
    completion_tokens: int
    total_cost_usd: float
    percentage_of_limit: Optional[float] = None
    limit_value: Optional[int] = None

class TokenUsageAlertResponse(BaseModel):
    id: UUID4
    tenant_id: Optional[int] = None
    tenant_name: Optional[str] = None
    agent_id: Optional[str] = None
    agent_name: Optional[str] = None
    limit_type: str
    threshold_value: float
    current_usage: int
    max_limit: int
    notification_sent: bool
    notification_channel: Optional[str] = None
    notification_target: Optional[str] = None
    created_at: datetime

    class Config:
        orm_mode = True