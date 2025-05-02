from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, AnyHttpUrl

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
    id: str
    tenant_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True

class WebhookLogBase(BaseModel):
    status: str
    event_type: Optional[str] = None
    attempt_count: int
    response_code: Optional[int] = None
    response_body: Optional[str] = None
    error_message: Optional[str] = None
    payload: Optional[str] = None

class WebhookLogCreate(WebhookLogBase):
    webhook_id: str

class WebhookLogResponse(WebhookLogBase):
    id: str
    webhook_id: str
    created_at: datetime

    class Config:
        orm_mode = True