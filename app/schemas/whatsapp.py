from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class DeviceBase(BaseModel):
    tenant_id: int
    name: str
    description: Optional[str] = None
    phone_number: Optional[str] = None


class DeviceCreate(DeviceBase):
    pass


class Device(DeviceBase):
    id: int
    status: str
    jid: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    last_seen: Optional[datetime] = None
    requires_reauth: bool = False
    
    class Config:
        from_attributes = True


class DeviceStatus(BaseModel):
    id: int
    status: str
    connected: bool
    requires_reauth: bool
    last_seen: Optional[datetime] = None


class MessageBase(BaseModel):
    jid: str
    content: str = ""
    media_url: Optional[str] = None
    media_type: Optional[str] = None


class MessageSend(MessageBase):
    to: str


class GroupMessageSend(BaseModel):
    message: str


class Message(MessageBase):
    id: int
    device_id: int
    message_id: str
    sender: str
    is_from_me: bool
    is_group: bool
    timestamp: datetime
    received_at: datetime
    
    class Config:
        from_attributes = True


class TrackedEntityBase(BaseModel):
    jid: str
    is_tracked: bool = True
    track_media: bool = True
    allowed_media_types: List[str] = Field(default_factory=lambda: ["image", "audio", "video", "document"])


class TrackedEntityCreate(TrackedEntityBase):
    pass


class TrackedEntity(TrackedEntityBase):
    id: int
    device_id: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True