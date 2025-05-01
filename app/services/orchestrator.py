# app/services/orchestrator.py
from typing import Dict, List, Optional, Any
import json
import time
import uuid
from pydantic import BaseModel

from app.services.agent import Agent, AgentType
from app.services.rag import RAGService

class ConversationState(BaseModel):
    conversation_id: str
    tenant_id: str
    user_id: str
    current_agent_id: str
    history: List[Dict[str, Any]]
    metadata: Dict[str, Any] = {}
    last_updated: float = 0

class AgentOrchestrator:
    """Orquestrador para gerenciar a comunicação entre agentes."""
    
    def __init__(self, agent_service, rag_service, redis_client, llm_service):
        self.agent_service = agent_service
        self.rag_service = rag_service
        self.redis = redis_client
        self.llm = llm_service
        
    async def start_conversation(self, tenant_id: str, user_id: str) -> str:
        """Inicia uma nova conversa."""
        # Buscar agente primário do tenant
        agents = await self.agent_service.get_agents_by_tenant(tenant_id)
        general_agents = [a for a in agents if a.type == AgentType.GENERAL]
        
        if not general_agents:
            raise ValueError(f"Tenant {tenant_id} não possui agente primário configurado")
        
        primary_agent = general_agents[0]
        
        # Criar estado da conversa
        conversation_id = str(uuid.uuid4())
        state = ConversationState(
            conversation_id=conversation_id,
            tenant_id=tenant_id,
            user_id=user_id,
            current_agent_id=primary_agent.id,
            history=[],
            last_updated=time.time()
        )
        
        # Salvar estado no Redis
        await self.save_conversation_state(state)
        
        return conversation_id
    
    async def process_message(self, conversation_id: str, message: str) -> Dict[str, Any]:
        """Processa uma mensagem dentro de uma conversa existente."""
        # Recuperar estado da conversa
        state = await self.get_conversation_state(conversation_id)
        if not state:
            raise ValueError(f"Conversa {conversation_id} não encontrada")
        
        # Adicionar mensagem ao histórico
        state.history.append({
            "role": "user",
            "content": message,
            "timestamp": time.time()
        })
        
        # Obter agente atual
        current_agent = await self.agent_service.get_agent(state.current_agent_id)
        
        # Determinar se precisa de contexto do RAG
        rag_context = []
        if current_agent.rag_categories:
            for category in current_agent.rag_categories:
                docs = await self.rag_service.search(message, category=category)
                rag_context.extend(docs)
        
        # Preparar prompt com histórico e contexto
        prompt = self._prepare_prompt(state, current_agent, rag_context)
        
        # Obter resposta do modelo
        response = await self.llm.generate_response(prompt)
        
        # Processar a resposta para identificar ações
        processed_response = await self._process_agent_response(response, state, current_agent)
        
        # Atualizar estado da conversa
        state.history.append({
            "role": "assistant",
            "agent_id": current_agent.id,
            "content": processed_response["response"],
            "timestamp": time.time()
        })
        
        state.last_updated = time.time()
        
        # Se houve mudança de agente, registrar
        if processed_response.get("next_agent_id") and processed_response["next_agent_id"] != current_agent.id:
            state.current_agent_id = processed_response["next_agent_id"]
            
            # Registrar transição de agente no histórico
            next_agent = await self.agent_service.get_agent(state.current_agent_id)
            state.history.append({
                "role": "system",
                "content": f"Conversa transferida para {next_agent.name}",
                "timestamp": time.time()
            })
        
        # Salvar estado atualizado
        await self.save_conversation_state(state)
        
        return {
            "response": processed_response["response"],
            "conversation_id": conversation_id,
            "current_agent": current_agent.name,
            "actions": processed_response.get("actions", [])
        }
    
    async def _process_agent_response(self, response: str, state: ConversationState, current_agent: Agent) -> Dict[str, Any]:
        """Processa a resposta do agente para identificar ações especiais."""
        result = {
            "response": response,
            "next_agent_id": current_agent.id,
            "actions": []
        }
        
        # Verificar se há solicitação de especialista
        if "CONSULTAR_ESPECIALISTA:" in response:
            # Extrair informações do especialista necessário
            specialization = response.split("CONSULTAR_ESPECIALISTA:")[1].split("\n")[0].strip()
            
            # Buscar agente especialista
            agents = await self.agent_service.get_agents_by_tenant(state.tenant_id)
            specialists = [a for a in agents if a.type == AgentType.SPECIALIST and specialization.lower() in a.name.lower()]
            
            if specialists:
                # Transferir para o especialista
                result["next_agent_id"] = specialists[0].id
                result["actions"].append({
                    "type": "specialist_consultation",
                    "specialist_id": specialists[0].id,
                    "context": response
                })
                
                # Limpar a tag da resposta
                result["response"] = response.replace(f"CONSULTAR_ESPECIALISTA:{specialization}", "")
        
        # Verificar se há solicitação de escalação para humano
        if "ESCALAR_PARA_HUMANO" in response:
            # Verificar se o agente permite escalação
            if current_agent.human_escalation_enabled and current_agent.human_escalation_contact:
                result["actions"].append({
                    "type": "human_escalation",
                    "contact": current_agent.human_escalation_contact,
                    "conversation_summary": self._generate_conversation_summary(state)
                })
                
                # Limpar a tag da resposta
                result["response"] = response.replace("ESCALAR_PARA_HUMANO", "")
        
        # Verificar se há chamada de função MCP
        if "EXECUTAR_MCP:" in response:
            # Extrair informações da função
            function_data = response.split("EXECUTAR_MCP:")[1].split("\n")[0].strip()
            try:
                function_call = json.loads(function_data)
                result["actions"].append({
                    "type": "mcp_function",
                    "function": function_call
                })
                
                # Limpar a tag da resposta
                result["response"] = response.replace(f"EXECUTAR_MCP:{function_data}", "")
            except json.JSONDecodeError:
                pass
        
        return result
    
    def _prepare_prompt(self, state: ConversationState, agent: Agent, rag_context: List[Any]) -> Dict[str, Any]:
        """Prepara o prompt completo para o agente, incluindo histórico e contexto."""
        # Implementação do prompt...
        pass
    
    def _generate_conversation_summary(self, state: ConversationState) -> str:
        """Gera um resumo da conversa para escalação."""
        # Implementação do resumo...
        pass
    
    async def save_conversation_state(self, state: ConversationState) -> None:
        """Salva o estado da conversa no Redis."""
        key = f"conversation:{state.conversation_id}"
        await self.redis.set(key, state.json())
        await self.redis.expire(key, 60 * 60 * 24)  # Expirar em 24 horas
    
    async def get_conversation_state(self, conversation_id: str) -> Optional[ConversationState]:
        """Recupera o estado da conversa do Redis."""
        key = f"conversation:{conversation_id}"
        data = await self.redis.get(key)
        if not data:
            return None
        return ConversationState.parse_raw(data)