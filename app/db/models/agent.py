# Adicionar ao arquivo app/db/models/agent.py

from datetime import datetime
import json
import uuid
from sqlalchemy import ARRAY, UUID, Boolean, Column, DateTime, Integer, String, Text, ForeignKey
from sqlalchemy.orm import relationship

from app.db.session import Base

class Agent(Base):
    __tablename__ = "agents"

    id = Column(UUID(as_uuid=True), primary_key=True, index=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    type = Column(String, nullable=False)
    specialties = Column(Text, nullable=True)
    description = Column(Text, nullable=True)
    prompt = Column(Text, nullable=False)
    rag_categories = Column(Text, nullable=True)
    mcp_enabled = Column(Boolean, default=False)
    mcp_functions = Column(Text, nullable=True)
    escalation_enabled = Column(Boolean, default=False) # novo
    list_escalation_agent_ids = Column(ARRAY(UUID(as_uuid=True)), nullable=True) ## list_escalation_agent_ids = Column(Text, nullable=True) # Armazenará um JSON com a lista de IDs
    human_escalation_enabled = Column(Boolean, default=False)
    human_escalation_contact = Column(String, nullable=True)
    active = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    tenant = relationship("Tenant", back_populates="agents")
    device_mappings = relationship("DeviceAgent", back_populates="agent", cascade="all, delete-orphan")
    contact_controls = relationship("ContactControl", back_populates="agent", cascade="all, delete-orphan")
    
    # Token Usage
    token_limits = relationship("TokenUsageLimit", back_populates="agent", cascade="all, delete-orphan")
    token_usage = relationship("TokenUsageLog", back_populates="agent")
    token_alerts = relationship("TokenUsageAlert", back_populates="agent")
    
    # Helper method to convert JSON strings to Python objects
    def get_prompt_dict(self):
        if self.prompt:
            return json.loads(self.prompt)
        return {}
    
    def get_specialties_list(self):
        if self.specialties:
            return json.loads(self.specialties)
        return []
    
    def get_rag_categories_list(self):
        if self.rag_categories:
            return json.loads(self.rag_categories)
        return []
    
    def get_mcp_functions_list(self):
        if self.mcp_functions:
            return json.loads(self.mcp_functions)
        return []
    
    # def get_escalation_agent_ids(self):
    #     """Retorna a lista de IDs de agentes para escalação."""
    #     if self.list_escalation_agent_ids:
    #         if isinstance(self.list_escalation_agent_ids, str):
    #             # Se for armazenado como JSON string
    #             return json.loads(self.list_escalation_agent_ids)
    #         # Se for ARRAY nativo
    #         return self.list_escalation_agent_ids
    #     return []
    
    def get_escalation_agent_ids(self):
        """Retorna a lista de IDs de agentes para escalação."""
        if self.list_escalation_agent_ids:
            # Se for ARRAY nativo do PostgreSQL (já são objetos UUID)
            if isinstance(self.list_escalation_agent_ids, list):
                # Converter UUIDs para strings se necessário
                return [str(uuid_obj) if isinstance(uuid_obj, uuid.UUID) else str(uuid_obj) 
                    for uuid_obj in self.list_escalation_agent_ids]
            # Se por algum motivo ainda vier como JSON string (compatibilidade)
            elif isinstance(self.list_escalation_agent_ids, str):
                try:
                    return json.loads(self.list_escalation_agent_ids)
                except json.JSONDecodeError:
                    # Se não conseguir fazer parse, retornar como lista com um elemento
                    return [self.list_escalation_agent_ids]
        return []
    
    