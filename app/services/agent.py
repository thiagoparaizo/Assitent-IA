# app/services/agent.py
from typing import Dict, List, Optional, Any
import uuid
import json
from enum import Enum
from datetime import datetime
from fastapi import HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.agent import Agent as AgentModel
from app.db.models.contact_control import ContactControl, ContactListType
from app.db.models.device_agent import DeviceAgent
from app.schemas.agent import Agent, AgentPrompt, AgentType
from app.services.whatsapp import WhatsAppService
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("app.services.agent")

class AgentType(str, Enum):
    GENERAL = "general"           # Assistente principal para clientes
    SPECIALIST = "specialist"     # Agente especialista interno
    INTEGRATION = "integration"   # Agente para integrações externas (MCP)
    HUMAN = "human"               # Representação de agente humano
    PERSONAL = "personal"         # Agente pessoal que se passa por um humano

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
        
        if self.human_escalation_enabled:
            prompt += "### Escalação para Atendente Humano:\n"
            prompt += "Quando um cliente solicitar falar com um atendente humano ou quando você perceber que não consegue resolver o problema adequadamente, "
            prompt += "envie um comando para escalar a conversa, usando: <comando>ESCALAR_PARA_HUMANO</comando>\n"
            prompt += "Exemplo: \"Entendo sua situação. Vou transferir você para um atendente humano que poderá ajudá-lo melhor. <comando>ESCALAR_PARA_HUMANO</comando> Aguarde um momento, por favor.\"\n\n"
        
        if self.mcp_enabled:
            prompt += "### Execução de Funções Externas:\n"
            prompt += "Para executar funções externas, use: <comando>EXECUTAR_MCP:{\"name\":\"nome_da_função\",\"parameters\":{...}}</comando>\n"
            prompt += "Exemplo: \"Vou verificar essa informação para você. <comando>EXECUTAR_MCP:{\"name\":\"buscar_status_pedido\",\"parameters\":{\"pedido_id\":\"12345\"}}</comando> Aguarde um momento enquanto consulto seu pedido.\"\n\n"
        
        return prompt

class AgentService:
    """Serviço para gerenciamento de agentes."""
    
    def __init__(self, db_session: AsyncSession, redis_client):
        self.db = db_session
        self.redis = redis_client
        
    def create_agent(self, agent_data: Dict[str, Any]) -> Agent:
        """Cria um novo agente."""
        # Se ID não foi fornecido, gerar um novo
        if "id" not in agent_data:
            agent_data["id"] = str(uuid.uuid4())
            
        # Adicionar timestamps se não existirem
        if "created_at" not in agent_data:
            agent_data["created_at"] = datetime.utcnow()
        if "updated_at" not in agent_data:
            agent_data["updated_at"] = datetime.utcnow()
            
        try:
            
            # Extrair o prompt antes de criar o Agent
            prompt_data = agent_data.pop("prompt")
            if isinstance(prompt_data, dict):
                prompt = AgentPrompt(**prompt_data)
            else:
                prompt = prompt_data  # Já é um AgentPrompt
            
            # Criar objeto Agent sem o prompt
            agent = Agent(
                **agent_data,
                prompt=prompt.dict() if hasattr(prompt, "dict") else prompt.model_dump()  # Tenta dict() ou model_dump() dependendo da versão do Pydantic
            )
            
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
            self.db.commit()
            self.db.refresh(db_agent)
            
            return agent
        except Exception as e:
            print(f"Erro ao criar agente: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    def get_agent(self, agent_id: str) -> Optional[Agent]:
        """Obtém um agente pelo ID."""
        # Buscar no banco de dados
        query = select(AgentModel).where(AgentModel.id == agent_id)
        result = self.db.execute(query)
        db_agent = result.scalar_one_or_none()
        
        if not db_agent:
            return None
        
        # Converter para schema
        return self._db_to_schema(db_agent)
    
    def get_agents_by_tenant(self, tenant_id: str) -> List[Agent]:
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
            result = self.db.execute(query)
            db_agents = result.scalars().all()
        
        # Converter para schema
        return [self._db_to_schema(db_agent) for db_agent in db_agents]
    
    # Obter agentes com relação com o agente atual # TODO validar
    # def get_agents_by_tenant_and_relationship_with_current_agent(self, tenant_id: str, current_agent_id: str) -> List[Agent]:
    #     """Obtém todos os agentes relacionados ao agente atual para escalação."""
    #     # Buscar o agente atual
    #     current_agent = self.get_agent(current_agent_id)
    #     if not current_agent or not current_agent.escalation_enabled or not current_agent.list_escalation_agent_ids:
    #         return []
        
    #     # Obter a lista de IDs de agentes para escalação
    #     escalation_agent_ids = current_agent.list_escalation_agent_ids
    #     if isinstance(escalation_agent_ids, str):
    #         # Se for JSON string
    #         escalation_agent_ids = json.loads(escalation_agent_ids)
        
    #     # Buscar os agentes relacionados
    #     related_agents = []
    #     for agent_id in escalation_agent_ids:
    #         agent = self.get_agent(agent_id)
    #         if agent and agent.tenant_id == int(tenant_id) and agent.active:
    #             related_agents.append(agent)
        
    #     return related_agents
    def get_agents_by_tenant_and_relationship_with_current_agent(self, tenant_id: str, current_agent_id: str) -> List[Agent]:
        """Obtém todos os agentes relacionados ao agente atual para escalação."""
        # Buscar o agente atual
        current_agent = self.get_agent(current_agent_id)
        if not current_agent or not current_agent.escalation_enabled or not current_agent.list_escalation_agent_ids:
            logging.debug("get_agents_by_tenant_and_relationship_with_current_agent > Agent not found or escalation is disabled")
            return []
        
        # Obter a lista de IDs de agentes para escalação
        escalation_agent_ids = current_agent.list_escalation_agent_ids
        if isinstance(escalation_agent_ids, str):
            # Se for JSON string
            escalation_agent_ids = json.loads(escalation_agent_ids)
            logging.debug("get_agents_by_tenant_and_relationship_with_current_agent > escalation_agent_ids: %s", escalation_agent_ids)
        
        # Buscar todos os agentes relacionados em uma única consulta
        query = select(AgentModel).where(
            AgentModel.tenant_id == int(tenant_id),
            AgentModel.id.in_(escalation_agent_ids),
            AgentModel.active == True
        )
        
        result = self.db.execute(query)
        db_agents = result.scalars().all()
        logging.debug("get_agents_by_tenant_and_relationship_with_current_agent > db_agents count: %s", len(db_agents))
        
        # Converter para schema
        return [self._db_to_schema(db_agent) for db_agent in db_agents]
    
    
    def update_agent(self, agent_id: str, agent_data: Dict[str, Any]) -> Optional[Agent]:
        """Atualiza um agente existente."""
        # Buscar agente existente
        query = select(AgentModel).where(AgentModel.id == agent_id)
        result = self.db.execute(query)
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
        
        if "list_escalation_agent_ids" in agent_data:
            # CORREÇÃO: Converter strings para objetos UUID
            escalation_ids = agent_data["list_escalation_agent_ids"]
            if escalation_ids:
                try:
                    # Converter cada ID string para UUID
                    uuid_list = []
                    for agent_id_str in escalation_ids:
                        if isinstance(agent_id_str, str):
                            uuid_list.append(uuid.UUID(agent_id_str))
                        elif isinstance(agent_id_str, uuid.UUID):
                            uuid_list.append(agent_id_str)
                    
                    db_agent.list_escalation_agent_ids = uuid_list
                except ValueError as e:
                    logging.error(f"Erro ao converter UUID: {e}")
                    raise ValueError(f"ID de agente inválido: {e}")
            else:
                db_agent.list_escalation_agent_ids = None
            
        if "type" in agent_data:
            agent_type = agent_data["type"]
            if isinstance(agent_type, str):
                db_agent.type = agent_type
            elif isinstance(agent_type, AgentType):
                db_agent.type = agent_type.value
                
        # Atualizar timestamp
        db_agent.updated_at = datetime.utcnow()
        
        # Salvar alterações
        self.db.commit()
        self.db.refresh(db_agent)
        
        # Retornar agente atualizado
        return self._db_to_schema(db_agent)
    
    def delete_agent(self, agent_id: str) -> bool:
        """Remove um agente."""
        # Buscar agente existente
        query = select(AgentModel).where(AgentModel.id == agent_id)
        result = self.db.execute(query)
        db_agent = result.scalar_one_or_none()
        
        if not db_agent:
            return False
        
        # Remover do banco de dados
        self.db.delete(db_agent)
        self.db.commit()
        
        return True
    
    def _db_to_schema(self, db_agent: AgentModel) -> Agent:
        """Converte um modelo de banco de dados para um schema."""
        # Converter prompt de JSON para objeto
        prompt_dict = json.loads(db_agent.prompt)
        prompt = AgentPrompt(**prompt_dict)
        
        # Converter rag_categories e mcp_functions de JSON para listas/dicts
        rag_categories = json.loads(db_agent.rag_categories) if db_agent.rag_categories else []
        mcp_functions = json.loads(db_agent.mcp_functions) if db_agent.mcp_functions else []
        
        # Certifique-se de que o ID seja uma string
        agent_id = str(db_agent.id)
        
        # Garantir que especialidades e agentes de escalação existam
        specialties = json.loads(db_agent.specialties) if db_agent.specialties else []
        # list_escalation_agent_ids = json.loads(db_agent.list_escalation_agent_ids) if db_agent.list_escalation_agent_ids else []
        
        list_escalation_agent_ids = []
        if db_agent.list_escalation_agent_ids:
            if isinstance(db_agent.list_escalation_agent_ids, list):
                # Se for um array nativo (lista de UUIDs), converter para strings
                list_escalation_agent_ids = [str(uuid_obj) for uuid_obj in db_agent.list_escalation_agent_ids]
            elif isinstance(db_agent.list_escalation_agent_ids, str):
                # Compatibilidade: se ainda vier como JSON string
                try:
                    list_escalation_agent_ids = json.loads(db_agent.list_escalation_agent_ids)
                except json.JSONDecodeError:
                    # Se não conseguir fazer parse como JSON, assumir que é uma string única
                    list_escalation_agent_ids = [db_agent.list_escalation_agent_ids]
        
        # Criar objeto Agent
        return Agent(
            id=agent_id,  # Garantir que seja string
            name=db_agent.name,
            tenant_id=db_agent.tenant_id,
            type=AgentType(db_agent.type),
            specialties=specialties,
            description=db_agent.description,
            prompt=prompt_dict,
            rag_categories=rag_categories,
            mcp_enabled=db_agent.mcp_enabled,
            mcp_functions=mcp_functions,
            escalation_enabled=db_agent.escalation_enabled,
            list_escalation_agent_ids=list_escalation_agent_ids,
            human_escalation_enabled=db_agent.human_escalation_enabled,
            human_escalation_contact=db_agent.human_escalation_contact,
            active=db_agent.active,
            created_at=db_agent.created_at,
            updated_at=db_agent.updated_at
        )
    def update_agent_status(self, agent_id: str, active: bool) -> bool:
        """Atualiza o status de um agente."""
        # Buscar agente existente
        query = select(AgentModel).where(AgentModel.id == agent_id)
        result = self.db.execute(query)
        db_agent = result.scalar_one_or_none()
        
        if not db_agent:
            return False
            
        # Atualizar campo active
        db_agent.active = active
        
        # Atualizar timestamp
        db_agent.updated_at = datetime.utcnow()
        
        # Salvar alterações
        self.db.commit()
        self.db.refresh(db_agent)
        
        return True
    
    def assign_agent_to_device(self, agent_id: str, device_id: int) -> bool:
        """Atribui um agente a um dispositivo específico."""
        # Verificar se o agente existe
        agent = self.get_agent(agent_id)
        if not agent:
            return False
        
        # Desativar mapeamentos ativos existentes para este dispositivo
        query = select(DeviceAgent).where(
            DeviceAgent.device_id == device_id,
            DeviceAgent.is_active == True
        )
        result = self.db.execute(query)
        existing_mappings = result.scalars().all()
        
        for mapping in existing_mappings:
            mapping.is_active = False
        
        # Criar novo mapeamento
        new_mapping = DeviceAgent(
            device_id=device_id,
            agent_id=agent_id,
            is_active=True
        )
        
        self.db.add(new_mapping)
        self.db.commit()
        return True

    async def get_agent_for_device(self, device_id: int, tenant_id: str) -> Optional[Agent]:
        """
        Obtém o agente ativo para um dispositivo específico.
        Se não houver um agente específico, retorna o agente geral do tenant.
        """
        # Buscar mapeamento ativo para este dispositivo
        query = select(DeviceAgent).join(AgentModel).where(
            DeviceAgent.device_id == device_id,
            DeviceAgent.is_active == True,
            AgentModel.tenant_id == tenant_id
        )
        result = self.db.execute(query)
        mapping = result.scalar_one_or_none()
        
        if mapping:
            # Retornar o agente mapeado para este dispositivo
            return self.get_agent(mapping.agent_id)
        
        # Fallback: buscar agente geral do tenant
        # general_agents = await self.get_agents_by_tenant_and_type(tenant_id, AgentType.GENERAL)
        # if general_agents:
        #     return general_agents[0]
        
        return None
    
    async def get_agent_for_contact(self, device_id: int, tenant_id: str, contact_id: str):
        """
        Determina qual agente deve responder a um contato específico em um dispositivo.
        
        Lógica:
        1. Buscar agentes específicos para o dispositivo
        2. Para cada agente, verificar se o contato está em uma whitelist ou blacklist
        3. Se não houver nenhum agente específico, usar o agente geral do tenant
        """
        # Buscar todos os mapeamentos de dispositivo-agente ativos
        query = select(DeviceAgent).join(AgentModel).where(
            DeviceAgent.device_id == device_id,
            DeviceAgent.is_active == True,
            AgentModel.tenant_id == tenant_id,
            AgentModel.active == True
        )
        result = self.db.execute(query)
        device_agents = result.scalars().all()
        
        if not device_agents:
            logger.info("Nenhum agente mapeado para este dispositivo")
            print("Nenhum agente mapeado para este dispositivo")
            
            # Nenhum agente mapeado para este dispositivo, usar fallback
            #general_agents = self.get_agents_by_tenant_and_type(tenant_id, AgentType.GENERAL)
            return None, False
        
        should_response = False
        
        # Verificar cada agente mapeado para o dispositivo
        for device_agent in device_agents:
            agent_id = device_agent.agent_id
            
            # Verificar controle de contatos para este agente
            contact_query = select(ContactControl).where(
                ContactControl.agent_id == agent_id,
                ContactControl.device_id == device_id
            )
            contact_result = self.db.execute(contact_query)
            contacts = contact_result.scalars().all()
            
            # Agrupar por tipo de lista
            whitelist = [c.contact_id for c in contacts if c.list_type == ContactListType.WHITELIST]
            blacklist = [c.contact_id for c in contacts if c.list_type == ContactListType.BLACKLIST]
            
            # Determinar se este agente deve responder
            if whitelist:
                # Se existe uma whitelist, o contato deve estar nela
                should_response = contact_id in whitelist or contact_id.replace("@s.whatsapp.net", "") in whitelist
            elif blacklist:
                # Se existe uma blacklist, o contato NÃO deve estar nela
                should_response = contact_id not in blacklist  or contact_id.replace("@s.whatsapp.net", "") in blacklist
            else:
                # Se não há listas, o agente responde a todos
                should_response = True
                return self.get_agent(agent_id), should_response
            
            
        
        # Nenhum agente específico deve responder a este contato
        # Usar o agente geral do tenant como fallback
        # na verdade, não retornar nada aqui
        return self.get_agent(agent_id), should_response

    async def manage_contact_list(self, agent_id: str, device_id: int, contacts: List[str], 
                                list_type: ContactListType) -> bool:
        """
        Gerencia a lista de contatos para um agente específico.
        Substitui a lista atual pelo conjunto fornecido.
        """
        try:
            # Remover controles existentes para este agente/dispositivo/tipo
            delete_query = delete(ContactControl).where(
                ContactControl.agent_id == agent_id,
                ContactControl.device_id == device_id,
                ContactControl.list_type == list_type
            )
            self.db.execute(delete_query)
            
            # Adicionar novos controles
            for contact_id in contacts:
                control = ContactControl(
                    agent_id=agent_id,
                    device_id=device_id,
                    contact_id=contact_id,
                    list_type=list_type
                )
                self.db.add(control)
            
            self.db.commit()
            return True
        except Exception as e:
            logger.error(f"Erro ao gerenciar lista de contatos: {e}")
            self.db.rollback()
            return False

    def add_contact_to_list(self, agent_id: str, device_id: int, contact_id: str, 
                                list_type: ContactListType) -> bool:
        """
        Adiciona um contato à lista especificada (whitelist ou blacklist).
        """
        try:
            # Verificar se já existe
            query = select(ContactControl).where(
                ContactControl.agent_id == agent_id,
                ContactControl.device_id == device_id,
                ContactControl.contact_id == contact_id,
                ContactControl.list_type == list_type
            )
            result = self.db.execute(query)
            existing = result.scalar_one_or_none()
            
            if not existing:
                control = ContactControl(
                    agent_id=agent_id,
                    device_id=device_id,
                    contact_id=contact_id,
                    list_type=list_type
                )
                self.db.add(control)
                self.db.commit()
            
            return True
        except Exception as e:
            logger.error(f"Erro ao adicionar contato à lista: {e}")
            self.db.rollback()
            return False

    def remove_contact_from_list(self, agent_id: str, device_id: int, contact_id: str, 
                                    list_type: ContactListType) -> bool:
        """
        Remove um contato da lista especificada.
        """
        try:
            delete_query = delete(ContactControl).where(
                ContactControl.agent_id == agent_id,
                ContactControl.device_id == device_id,
                ContactControl.contact_id == contact_id,
                ContactControl.list_type == list_type
            )
            self.db.execute(delete_query)
            self.db.commit()
            return True
        except Exception as e:
            logger.error(f"Erro ao remover contato da lista: {e}")
            self.db.rollback()
            return False
        
    async def get_devices_for_agent(self, agent_id: str) -> List[Dict[str, Any]]:
        """
        Obtém os dispositivos associados a um agente.
        """
        # Buscar mapeamentos ativos
        query = select(DeviceAgent).where(
            DeviceAgent.agent_id == agent_id,
            DeviceAgent.is_active == True
        )
        result = self.db.execute(query)
        mappings = result.scalars().all()
        
        # Buscar detalhes dos dispositivos
        devices = []
        for mapping in mappings:
            # Aqui você precisará implementar a lógica para buscar os detalhes do dispositivo
            # Isso depende de como os dispositivos são armazenados (podem estar em outro serviço)
            try:
                # Exemplo usando um serviço WhatsApp
                whatsapp_service = WhatsAppService()
                device_info = await whatsapp_service.get_device(mapping.device_id)
                
                if device_info:
                    devices.append(device_info)
            except Exception as e:
                logger.error(f"Erro ao buscar detalhes do dispositivo {mapping.device_id}: {e}")
        
        return devices

    def unassign_agent_from_device(self, agent_id: str, device_id: int) -> bool:
        """
        Remove a associação de um agente com um dispositivo.
        """
        # Buscar mapeamento existente
        query = select(DeviceAgent).where(
            DeviceAgent.agent_id == agent_id,
            DeviceAgent.device_id == device_id,
            DeviceAgent.is_active == True
        )
        result = self.db.execute(query)
        mapping = result.scalar_one_or_none()
        
        if mapping:
            # Desativar mapeamento
            mapping.is_active = False
            self.db.commit()
            return True
        
        return False