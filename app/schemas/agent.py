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
    PERSONAL = "personal"         # Agente pessoal que se passa por um humano

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
    escalation_enabled: bool = False
    specialties: Optional[List[str]] = Field(default_factory=list)  # Lista vazia como padrão
    list_escalation_agent_ids: Optional[List[str]] = Field(default_factory=list)
    human_escalation_enabled: bool = False
    human_escalation_contact: Optional[str] = None
    active: bool = False

class AgentCreate(AgentBase):
    pass

class AgentUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    prompt: Optional[AgentPrompt] = None
    rag_categories: Optional[List[str]] = None
    mcp_enabled: Optional[bool] = None
    mcp_functions: Optional[List[Dict[str, Any]]] = None
    escalation_enabled: bool = False
    list_escalation_agent_ids: Optional[List[str]] = None
    human_escalation_enabled: Optional[bool] = None
    human_escalation_contact: Optional[str] = None
    active: Optional[bool] = None

class Agent(AgentBase):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    def generate_system_prompt(self) -> str:
        """Gera o prompt de sistema completo para o agente."""
        prompt = f"# {self.prompt.role}\n\n"
        prompt += f"{self.prompt.description}\n\n"
        prompt += "## Instruções:\n"
        prompt += f"{self.prompt.instructions}\n\n"
        
        if self.prompt.constraints:
            prompt += "## Restrições:\n"
            for constraint in self.prompt.constraints:
                prompt += f"- {constraint}\n"
            prompt += "\n"
        
        if self.prompt.examples:
            prompt += "## Exemplos:\n"
            for i, example in enumerate(self.prompt.examples):
                prompt += f"### Exemplo {i+1}:\n"
                for key, value in example.items():
                    prompt += f"**{key}**: {value}\n"
                prompt += "\n"
        
        if self.human_escalation_enabled:
            prompt += "### Escalação para Atendente Humano:\n"
            prompt += "Quando um cliente solicitar falar com um atendente humano ou quando você perceber que não consegue resolver o problema adequadamente, "
            prompt += "envie um comando para escalar a conversa, usando: <comando>ESCALAR_PARA_HUMANO</comando>\n"
            prompt += "Exemplo: \"Entendo sua situação. Vou transferir você para um atendente humano que poderá ajudá-lo melhor. <comando>ESCALAR_PARA_HUMANO</comando> Aguarde um momento, por favor.\"\n\n"
        
        if self.escalation_enabled and self.list_escalation_agent_ids:
            prompt += "### Transferência para Agentes Especializados:\n"
            prompt += "Quando identificar que a solicitação do cliente requer conhecimento especializado (comercial, suporte técnico, etc.), "
            prompt += "use: <comando>CONSULTAR_ESPECIALISTA:tipo_de_especialização</comando>\n"
            prompt += "Exemplos:\n"
            prompt += "- Para questões comerciais/vendas: \"Vou conectar você com nosso especialista comercial. <comando>CONSULTAR_ESPECIALISTA:comercial</comando>\"\n"
            prompt += "- Para questões técnicas/suporte: \"Vou transferir para nosso especialista técnico. <comando>CONSULTAR_ESPECIALISTA:suporte</comando>\"\n"
            prompt += "- Use termos como: comercial, vendas, suporte, técnico, especialista\n\n"
        
        if self.mcp_enabled:
            prompt += "### Execução de Funções Externas:\n"
            prompt += "Para executar funções externas, use: <comando>EXECUTAR_MCP:{\"name\":\"nome_da_função\",\"parameters\":{...}}</comando>\n"
            prompt += "Exemplo: \"Vou verificar essa informação para você. <comando>EXECUTAR_MCP:{\"name\":\"buscar_status_pedido\",\"parameters\":{\"pedido_id\":\"12345\"}}</comando> Aguarde um momento enquanto consulto seu pedido.\"\n\n"
        
        return prompt

    class Config:
        from_attributes = True