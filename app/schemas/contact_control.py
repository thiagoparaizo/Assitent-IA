# Em app/schemas/contact_control.py
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import datetime

class ContactListTypeEnum(str, Enum):
    WHITELIST = "whitelist"
    BLACKLIST = "blacklist"

class ContactControlBase(BaseModel):
    agent_id: str
    device_id: int
    contact_id: str
    list_type: ContactListTypeEnum

class ContactControlCreate(ContactControlBase):
    pass

class ContactControlResponse(ContactControlBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class AgentContactConfig(BaseModel):
    agent_id: str
    device_id: int
    default_behavior: ContactListTypeEnum = ContactListTypeEnum.BLACKLIST
    contacts: List[str] = []