# app/services/agent.py
from typing import Dict, List, Optional, Any
import uuid
import json
from enum import Enum
from datetime import datetime
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.agent import Agent as AgentModel
from app.schemas.agent import Agent, AgentPrompt, AgentType

class AgentType(str, Enum):
    GENERAL = "general"           # Assistente principal para clientes
    SPECIALIST = "specialist"     # Agente especialista interno
    INTEGRATION = "integration"   # Agente para integrações externas (MCP)
    HUMAN = "human"               # Representação de agente humano

class AgentPrompt(BaseModel):
    role: str
    description: str
    instructions: str
    examples: Optional[List[Dict[str, str]]] = None
    constraints: Optional[List[str]] = None

# class Agent(BaseModel):
#     id: str = Field(default_factory=lambda: str(uuid.uuid4()))
#     name: str
#     tenant_id: str
#     type: AgentType
#     description: str
#     prompt: AgentPrompt
#     rag_categories: Optional[List[str]] = None
#     mcp_enabled: bool = False
#     mcp_functions: Optional[List[Dict[str, Any]]] = None
#     human_escalation_enabled: bool = False
#     human_escalation_contact: Optional[str] = None
    
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
        
        return prompt

class AgentService:
    """Serviço para gerenciamento de agentes."""
    
    def __init__(self, db_session: AsyncSession, redis_client):
        self.db = db_session
        self.redis = redis_client
        
    async def create_agent(self, agent_data: Dict[str, Any]) -> Agent:
        """Cria um novo agente."""
        # Se ID não foi fornecido, gerar um novo
        if "id" not in agent_data:
            agent_data["id"] = str(uuid.uuid4())
            
        # Verificar se prompt está no formato correto
        if isinstance(agent_data.get("prompt"), dict):
            agent_data["prompt"] = AgentPrompt(**agent_data["prompt"])
            
        # Criar objeto Agent
        agent = Agent(**agent_data)
        
        # Criar registro no banco de dados
        db_agent = AgentModel(
            id=agent.id,
            name=agent.name,
            tenant_id=int(agent.tenant_id),
            type=agent.type.value,
            description=agent.description,
            prompt=agent.prompt.json(),
            rag_categories=json.dumps(agent.rag_categories) if agent.rag_categories else None,
            mcp_enabled=agent.mcp_enabled,
            mcp_functions=json.dumps(agent.mcp_functions) if agent.mcp_functions else None,
            human_escalation_enabled=agent.human_escalation_enabled,
            human_escalation_contact=agent.human_escalation_contact
        )
        
        self.db.add(db_agent)
        await self.db.commit()
        await self.db.refresh(db_agent)
        
        return agent
    
    async def get_agent(self, agent_id: str) -> Optional[Agent]:
        """Obtém um agente pelo ID."""
        # Buscar no banco de dados
        query = select(AgentModel).where(AgentModel.id == agent_id)
        result = await self.db.execute(query)
        db_agent = result.scalar_one_or_none()
        
        if not db_agent:
            return None
        
        # Converter para schema
        return self._db_to_schema(db_agent)
    
    async def get_agents_by_tenant(self, tenant_id: str) -> List[Agent]:
        """Obtém todos os agentes de um tenant."""
        # Buscar no banco de dados
        query = select(AgentModel).where(AgentModel.tenant_id == int(tenant_id))
        
        # Aqui está o problema - não podemos usar await com execute() a menos que estejamos usando AsyncSession
        # Vamos verificar o tipo de self.db
        if hasattr(self.db, 'execute'):
            # Estamos usando uma sessão síncrona
            result = self.db.execute(query)
            db_agents = result.scalars().all()
        else:
            # Estamos usando uma sessão assíncrona
            result = await self.db.execute(query)
            db_agents = result.scalars().all()
        
        # Converter para schema
        return [self._db_to_schema(db_agent) for db_agent in db_agents]
    
    async def update_agent(self, agent_id: str, agent_data: Dict[str, Any]) -> Optional[Agent]:
        """Atualiza um agente existente."""
        # Buscar agente existente
        query = select(AgentModel).where(AgentModel.id == agent_id)
        result = await self.db.execute(query)
        db_agent = result.scalar_one_or_none()
        
        if not db_agent:
            return None
        
        # Atualizar campos
        if "name" in agent_data:
            db_agent.name = agent_data["name"]
            
        if "description" in agent_data:
            db_agent.description = agent_data["description"]
            
        if "prompt" in agent_data:
            prompt_data = agent_data["prompt"]
            if isinstance(prompt_data, dict):
                prompt = AgentPrompt(**prompt_data)
                db_agent.prompt = prompt.json()
            elif isinstance(prompt_data, AgentPrompt):
                db_agent.prompt = prompt_data.json()
                
        if "rag_categories" in agent_data:
            db_agent.rag_categories = json.dumps(agent_data["rag_categories"]) if agent_data["rag_categories"] else None
            
        if "mcp_enabled" in agent_data:
            db_agent.mcp_enabled = agent_data["mcp_enabled"]
            
        if "mcp_functions" in agent_data:
            db_agent.mcp_functions = json.dumps(agent_data["mcp_functions"]) if agent_data["mcp_functions"] else None
            
        if "human_escalation_enabled" in agent_data:
            db_agent.human_escalation_enabled = agent_data["human_escalation_enabled"]
            
        if "human_escalation_contact" in agent_data:
            db_agent.human_escalation_contact = agent_data["human_escalation_contact"]
            
        if "type" in agent_data:
            agent_type = agent_data["type"]
            if isinstance(agent_type, str):
                db_agent.type = agent_type
            elif isinstance(agent_type, AgentType):
                db_agent.type = agent_type.value
                
        # Atualizar timestamp
        db_agent.updated_at = datetime.utcnow()
        
        # Salvar alterações
        await self.db.commit()
        await self.db.refresh(db_agent)
        
        # Retornar agente atualizado
        return self._db_to_schema(db_agent)
    
    async def delete_agent(self, agent_id: str) -> bool:
        """Remove um agente."""
        # Buscar agente existente
        query = select(AgentModel).where(AgentModel.id == agent_id)
        result = await self.db.execute(query)
        db_agent = result.scalar_one_or_none()
        
        if not db_agent:
            return False
        
        # Remover do banco de dados
        await self.db.delete(db_agent)
        await self.db.commit()
        
        return True
    
    def _db_to_schema(self, db_agent: AgentModel) -> Agent:
        """Converte um modelo de banco de dados para um schema."""
        # Converter prompt de JSON para objeto
        prompt_dict = json.loads(db_agent.prompt)
        prompt = AgentPrompt(**prompt_dict)
        
        # Converter rag_categories e mcp_functions de JSON para listas/dicts
        rag_categories = json.loads(db_agent.rag_categories) if db_agent.rag_categories else None
        mcp_functions = json.loads(db_agent.mcp_functions) if db_agent.mcp_functions else None
        
        # Criar objeto Agent
        return Agent(
            id=db_agent.id,
            name=db_agent.name,
            tenant_id=db_agent.tenant_id,
            type=AgentType(db_agent.type),
            description=db_agent.description,
            prompt=prompt,
            rag_categories=rag_categories,
            mcp_enabled=db_agent.mcp_enabled,
            mcp_functions=mcp_functions,
            human_escalation_enabled=db_agent.human_escalation_enabled,
            human_escalation_contact=db_agent.human_escalation_contact,
            created_at=db_agent.created_at,
            updated_at=db_agent.updated_at
        )