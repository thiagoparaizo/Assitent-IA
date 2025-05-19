# app/schemas/llm.py
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field

class LLMProviderBase(BaseModel):
    name: str
    provider_type: str
    description: Optional[str] = None
    base_url: Optional[str] = None
    is_active: bool = True

class LLMProviderCreate(LLMProviderBase):
    pass

class LLMProviderUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    base_url: Optional[str] = None
    is_active: Optional[bool] = None

class LLMProviderResponse(LLMProviderBase):
    id: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        orm_mode = True

class LLMModelBase(BaseModel):
    provider_id: int
    name: str
    model_id: str
    max_tokens: Optional[int] = None
    default_temperature: float = 0.7
    supports_functions: bool = False
    supports_vision: bool = False
    is_active: bool = True
    cost_per_1k_tokens: float = 0.0

class LLMModelCreate(LLMModelBase):
    pass

class LLMModelUpdate(BaseModel):
    name: Optional[str] = None
    model_id: Optional[str] = None
    max_tokens: Optional[int] = None
    default_temperature: Optional[float] = None
    supports_functions: Optional[bool] = None
    supports_vision: Optional[bool] = None
    is_active: Optional[bool] = None
    cost_per_1k_tokens: Optional[float] = None

class LLMModelResponse(LLMModelBase):
    id: int
    created_at: datetime
    updated_at: datetime
    provider_name: str  # Campo adicional para UI
    
    class Config:
        orm_mode = True