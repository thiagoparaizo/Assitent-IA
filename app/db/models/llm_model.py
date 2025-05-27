from datetime import datetime
from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from app.db.session import Base

class LLMModel(Base):
    __tablename__ = "llm_models"

    id = Column(Integer, primary_key=True, index=True)
    provider_id = Column(Integer, ForeignKey("llm_providers.id"), nullable=False)
    name = Column(String, nullable=False)
    model_id = Column(String, nullable=False)  # Identificador do modelo na API (gpt-4, gemini-pro, etc)
    max_tokens = Column(Integer, nullable=True)
    default_temperature = Column(Float, default=0.7)
    supports_functions = Column(Boolean, default=False)
    supports_vision = Column(Boolean, default=False)
    is_active = Column(Boolean(), default=True)
    cost_per_1k_tokens = Column(Float, default=0.0)  # Custo por 1000 tokens (para tracking)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Definição explícita da relação com LLMProvider
    provider = relationship("LLMProvider", back_populates="models")
    # Definição explícita da relação com TokenUsageLog
    token_usage = relationship("TokenUsageLog", back_populates="model")
    
    def to_response_dict(self):
        """Converte o modelo para um dicionário compatível com LLMModelResponse."""
        return {
            "id": self.id,
            "provider_id": self.provider_id,
            "name": self.name,
            "model_id": self.model_id,
            "max_tokens": self.max_tokens,
            "default_temperature": self.default_temperature,
            "supports_functions": self.supports_functions,
            "supports_vision": self.supports_vision,
            "is_active": self.is_active,
            "cost_per_1k_tokens": self.cost_per_1k_tokens,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "provider_name": self.provider.name if self.provider else "Unknown"
        }