# Adicionar ao arquivo app/schemas/agent.py

from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from enum import Enum
import uuid
from datetime import datetime

class AgentType(str, Enum):
    GENERAL = "general"           # Assistente principal para clientes
    SPECIALIST = "specialist"     # Agente especialista interno
    INTEGRATION = "integration"   # Agente para integrações externas (MCP)
    HUMAN = "human"               # Representação de agente humano

class AgentPromptBase(BaseModel):
    role: str
    description: str
    instructions: str
    examples: Optional[List[Dict[str, str]]] = None
    constraints: Optional[List[str]] = None

class AgentPromptCreate(AgentPromptBase):
    pass

class AgentPrompt(AgentPromptBase):
    class Config:
        orm_mode = True

class AgentBase(BaseModel):
    name: str
    tenant_id: int
    type: AgentType
    description: str
    prompt: AgentPrompt
    rag_categories: Optional[List[str]] = None
    mcp_enabled: bool = False
    mcp_functions: Optional[List[Dict[str, Any]]] = None
    human_escalation_enabled: bool = False
    human_escalation_contact: Optional[str] = None

class AgentCreate(AgentBase):
    pass

class AgentUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    prompt: Optional[AgentPrompt] = None
    rag_categories: Optional[List[str]] = None
    mcp_enabled: Optional[bool] = None
    mcp_functions: Optional[List[Dict[str, Any]]] = None
    human_escalation_enabled: Optional[bool] = None
    human_escalation_contact: Optional[str] = None

class Agent(AgentBase):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True