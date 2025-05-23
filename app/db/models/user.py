#app/db/models/user.py
from datetime import datetime
from typing import Optional
import uuid

from sqlalchemy import UUID, Boolean, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.core.security import get_password_hash, verify_password
from app.db.session import Base


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, index=True, default=uuid.uuid4)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True)
    is_active = Column(Boolean(), default=True)
    is_superuser = Column(Boolean(), default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    tenant = relationship("Tenant", back_populates="users")
    
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
    
    # Função para verificar senha
    def verify_password(self, password: str) -> bool:
        return verify_password(password, self.hashed_password)

    # Função para definir senha
    def set_password(self, password: str) -> None:
        self.hashed_password = get_password_hash(password)