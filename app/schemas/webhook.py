from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, AnyHttpUrl
import uuid

class WebhookBase(BaseModel):
    url: AnyHttpUrl
    secret: Optional[str] = None
    events: Optional[List[str]] = None
    device_ids: Optional[List[int]] = None
    enabled: bool = True

class WebhookCreate(WebhookBase):
    pass

class WebhookUpdate(BaseModel):
    url: Optional[AnyHttpUrl] = None
    secret: Optional[str] = None
    events: Optional[List[str]] = None
    device_ids: Optional[List[int]] = None
    enabled: Optional[bool] = None

class WebhookResponse(WebhookBase):
    id: uuid.UUID  # Alterado para UUID
    tenant_id: uuid.UUID  # Atualize conforme seu modelo Tenant
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True
        json_encoders = {
            uuid.UUID: lambda v: str(v)  # Converte UUID para string no JSON
        }

class WebhookLogBase(BaseModel):
    status: str
    event_type: Optional[str] = None
    attempt_count: int
    response_code: Optional[int] = None
    response_body: Optional[str] = None
    error_message: Optional[str] = None
    payload: Optional[str] = None

class WebhookLogCreate(WebhookLogBase):
    webhook_id: uuid.UUID

class WebhookLogResponse(WebhookLogBase):
    id: uuid.UUID
    webhook_id: uuid.UUID
    created_at: datetime

    class Config:
        orm_mode = True
        json_encoders = {
            uuid.UUID: lambda v: str(v)
        }