from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class TenantBase(BaseModel):
    name: str
    description: Optional[str] = None
    is_active: bool = True


class TenantCreate(TenantBase):
    pass


class TenantUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None


class TenantResponse(TenantBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True