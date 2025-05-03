# Adicionar ao arquivo app/db/models/agent.py

from datetime import datetime
import uuid
from sqlalchemy import UUID, Boolean, Column, DateTime, Integer, String, Text, ForeignKey
from sqlalchemy.orm import relationship

from app.db.session import Base

class Agent(Base):
    __tablename__ = "agents"

    id = Column(UUID(as_uuid=True), primary_key=True, index=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    type = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    prompt = Column(Text, nullable=False)
    rag_categories = Column(Text, nullable=True)
    mcp_enabled = Column(Boolean, default=False)
    mcp_functions = Column(Text, nullable=True)
    human_escalation_enabled = Column(Boolean, default=False)
    human_escalation_contact = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    tenant = relationship("Tenant", back_populates="agents")
    
    # Helper method to convert JSON strings to Python objects
    def get_prompt_dict(self):
        if self.prompt:
            return json.loads(self.prompt)
        return {}
    
    def get_rag_categories_list(self):
        if self.rag_categories:
            return json.loads(self.rag_categories)
        return []
    
    def get_mcp_functions_list(self):
        if self.mcp_functions:
            return json.loads(self.mcp_functions)
        return []