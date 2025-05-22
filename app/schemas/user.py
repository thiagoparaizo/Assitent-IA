# app/schemas/user.py
from datetime import datetime
from typing import Optional

from pydantic import UUID4, BaseModel, EmailStr, Field, validator


# Shared properties
class UserBase(BaseModel):
    id: Optional[str] = None
    email: Optional[EmailStr] = None
    is_active: Optional[bool] = True
    is_superuser: bool = False
    full_name: Optional[str] = None
    tenant_id: Optional[int] = None
    
    def to_dict(self):
        return {
            "id": str(self.id),  # Convertendo UUID para string
            "email": self.email,
            "full_name" : self.full_name,
            "is_active": self.is_active,
            "is_superuser": self.is_superuser,
            "tenant_id": self.tenant_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }


# Properties to receive via API on creation
class UserCreate(UserBase):
    email: EmailStr
    password: str
    full_name: Optional[str] = None
    tenant_id: Optional[int] = None
    
    class Config:
        schema_extra = {
            "example": {
                "email": "user@example.com",
                "password": "strongpassword",
                "full_name": "John Doe",
                "tenant_id": 1,
                "is_active": True,
                "is_superuser": False
            }
        }


# Properties to receive via API on update
class UserUpdate(UserBase):
    password: Optional[str] = None


# Properties shared by models stored in DB
class UserInDBBase(UserBase):
    id: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        orm_mode = True


# Properties to return via API
class UserResponse(BaseModel):
    id: str
    email: str
    full_name: Optional[str] = None
    tenant_id: Optional[int] = None
    is_active: bool
    is_superuser: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
# class UserResponse(BaseModel):
#     id: UUID4  # Ou str se preferir
#     email: str
#     full_name: Optional[str]
#     tenant_id: Optional[int]
#     is_active: bool
#     is_superuser: bool

#     class Config:
#         json_encoders = {
#             UUID4: lambda v: str(v)  # Converte UUID para string no JSON
#         }


# Properties properties stored in DB
class UserInDB(UserInDBBase):
    hashed_password: str