# app/schemas/tenant.py
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field

class TenantBase(BaseModel):
    name: str
    description: Optional[str] = None
    is_active: bool = True
    default_llm_provider_id: Optional[int] = None
    default_llm_model_id: Optional[int] = None
    llm_api_key: Optional[str] = None  # Armazenada com segurança

class TenantCreate(TenantBase):
    pass

class TenantUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None
    default_llm_provider_id: Optional[int] = None
    default_llm_model_id: Optional[int] = None
    llm_api_key: Optional[str] = None

class TenantResponse(TenantBase):
    id: int
    created_at: datetime
    updated_at: datetime
    
    llm_provider_name: Optional[str] = None  # Campo adicional para UI
    llm_model_name: Optional[str] = None     # Campo adicional para UI

    class Config:
        orm_mode = True