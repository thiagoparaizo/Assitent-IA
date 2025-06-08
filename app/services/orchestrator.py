# app/services/orchestrator.py
import asyncio
from datetime import datetime
import os
import re
from typing import Dict, List, Optional, Any, Tuple
import json
import time
import uuid
from app.core.config import Settings, settings


from app.services.memory import MemoryService, MemoryEntry, MemoryType, ConversationSummary

from app.services.config import SystemConfig, load_system_config
import logging

from app.services.agent import Agent, AgentType
from app.services.token_counter import TokenCounterService
#from app.services.rag import RAGService
from app.db.models.conversation import ConversationState, AgentScore

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("app.services.orchestrator")

# class ConversationState(BaseModel):
#     conversation_id: str
#     tenant_id: str
#     user_id: str
#     current_agent_id: str
#     history: List[Dict[str, Any]]
#     metadata: Dict[str, Any] = {}
#     last_updated: float = 0

class AgentScore:
    """Represents a score for an agent's ability to handle a conversation."""
    
    def __init__(self, agent_id: str, score: float, reason: str):
        self.agent_id = agent_id
        self.score = score
        self.reason = reason

class AgentOrchestrator:
    """Orquestrador para gerenciar a comunicação entre agentes."""
    
    def __init__(self, agent_service, rag_service, redis_client, llm_service, config: SystemConfig = None, token_counter_service: TokenCounterService = None):
        self.agent_service = agent_service
        self.rag_service = rag_service
        self.redis = redis_client
        self.llm = llm_service
        
        
        # Load or use provided config
        self.config = config or load_system_config()
        
        # Set up logging based on config
        self._setup_logging()
        
        # Initialize memory service with config
        if self.config.memory.enabled:
            self.memory_service = MemoryService(
                llm_service, 
                vector_db_url=self.config.memory.vector_db_url,
                vector_db_path=self.config.memory.memory_db_path or settings.MEMORY_DB_PATH,
                use_local_storage=self.config.memory.use_local_storage
            )
        else:
            self.memory_service = None
            
        # Inicializar o serviço de contagem de tokens
        self.token_counter_service = token_counter_service
        
        # Se não foi fornecido mas temos acesso ao banco de dados, criar
        if self.token_counter_service is None and hasattr(self.agent_service, 'db'):
            try:
                from app.services.token_counter import TokenCounterService
                self.token_counter_service = TokenCounterService(self.agent_service.db)
            except Exception as e:
                print(f"Aviso: Não foi possível criar TokenCounterService: {e}")
                self.token_counter_service = None
            
        # Log initialization
        logger.info(f"AgentOrchestrator initialized with config: {self.config}")

    def _setup_logging(self):
        """Set up logging based on configuration."""
        log_level = getattr(logging, self.config.logging.level.value.upper())
        
        # Configure root logger
        logger = logging.getLogger()
        logger.setLevel(log_level)
        
        # Clear existing handlers
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)
        
        # Add console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(log_level)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        
        # Add file handler if configured
        if self.config.logging.log_to_file:
            # Make sure log directory exists
            log_dir = os.path.dirname(self.config.logging.log_file_path)
            os.makedirs(log_dir, exist_ok=True)
            
            if self.config.logging.log_rotation:
                # Use rotating file handler for log rotation
                from logging.handlers import RotatingFileHandler
                file_handler = RotatingFileHandler(
                    self.config.logging.log_file_path,
                    maxBytes=self.config.logging.max_log_size_mb * 1024 * 1024,
                    backupCount=5
                )
            else:
                file_handler = logging.FileHandler(self.config.logging.log_file_path)
                
            file_handler.setLevel(log_level)
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        
    async def start_conversation(self, tenant_id: str, user_id: str, agent_id: Optional[str] = None) -> str:
        """Inicia uma nova conversa."""
        
        if not agent_id:
            # Buscar agente primário do tenant
            agents = await self.agent_service.get_agents_by_tenant(tenant_id)
            general_agents = [a for a in agents if a.type == AgentType.GENERAL]
            
            if not general_agents:
                raise ValueError(f"Tenant {tenant_id} não possui agente primário configurado")
            
            primary_agent = general_agents[0]
            agent_id = primary_agent.id
        
        # Criar estado da conversa
        conversation_id = str(uuid.uuid4())
        state = ConversationState(
            conversation_id=conversation_id,
            tenant_id=tenant_id,
            user_id=user_id,
            current_agent_id=agent_id,
            history=[],
            last_updated=time.time()
        )
        
        # Salvar estado no Redis
        await self.save_conversation_state(state)
        
        return conversation_id
    
    async def process_message(self, conversation_id: str, message: str, agent_id: str, contact_id: str, audio_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Processes a message within a conversation."""
        # Get the system config for this tenant
        state = await self.get_conversation_state(conversation_id)
        
        # Variables to track if we created a new conversation
        new_conversation_created = False
        new_conversation_id = None
        reset_reason = None
        
        if not state:
            logger.info(f"process_message > Conversation {conversation_id} not found, creating a new one")
            print(f"process_message > Conversation {conversation_id} not found, creating a new one")
            
            # Para criar uma nova conversa, precisamos do tenant_id e do user_id
            # Tente extrair do formato conversation_id, se possível
            # Ou recupere de outro lugar, se necessário

            # Por enquanto, use uma abordagem de espaço reservado - você precisará adaptar isso
            # à sua implementação específica
            parts = conversation_id.split(":")
            if len(parts) >= 3:
                # Assuming format like "conversation:tenant_id:user_id"
                tenant_id = parts[1]
                user_id = parts[2]
            else:
                # Fallback - might need to be changed for your implementation
                tenant_id = "default"
                user_id = "unknown"
                
            # Create new conversation
            new_conversation_id = await self.start_conversation(tenant_id, user_id, agent_id)
            logger.info(f"process_message > Created new conversation {new_conversation_id} as {conversation_id} was not found")
            
            # Get the new state
            state = await self.get_conversation_state(new_conversation_id)
            new_conversation_created = True
            reset_reason = "expired"
            
            if not state:
                raise ValueError(f"Failed to create new conversation state")
            
            # Add system message
            state.history.append({
                "role": "system",
                "content": "Sua conversa anterior expirou ou não foi encontrada. Iniciamos uma nova conversa para você.",
                "timestamp": time.time()
            })
            
            # Update metadata
            state.metadata["previous_conversation_id"] = conversation_id
            state.metadata["reset_reason"] = "expired_or_not_found"
        
        
        
        # Apply tenant-specific config overrides
        tenant_config = self.config.apply_tenant_overrides(state.tenant_id)
        
        # Check conversation length limit
        if len(state.history) >= tenant_config.max_conversation_length:
            logger.info(f"process_message > Conversation {conversation_id} reached message limit. Creating new conversation.")
            print(f"process_message > Conversation {conversation_id} reached message limit. Creating new conversation.")
            # Set reason for archiving
            state.metadata["archive_reason"] = "max_length_exceeded"
            
            # Archive the current conversation
            await self._archive_conversation(state)
            
            # Create new conversation
            new_conversation_id = await self.start_conversation(state.tenant_id, state.user_id, agent_id)
            
            # Get the new state
            state = await self.get_conversation_state(new_conversation_id)
            new_conversation_created = True
            reset_reason = "max_length"
            
            # Add system message explaining what happened
            state.history.append({
                "role": "system",
                "content": "Sua conversa anterior atingiu o limite de mensagens. Iniciamos uma nova conversa para você.",
                "timestamp": time.time()
            })
            
            # Update metadata
            state.metadata["previous_conversation_id"] = conversation_id
            state.metadata["reset_reason"] = "max_length_exceeded"
        
        # Check conversation timeout
        last_update_time = state.last_updated
        current_time = time.time()
        time_diff_minutes = (current_time - last_update_time) / 60
        
        if time_diff_minutes > tenant_config.conversation_timeout_minutes: #verificar se o agente for pessoal, não expirar conversa
            logger.info(f"process_message > Conversation {conversation_id} timed out after {time_diff_minutes:.1f} minutes. Creating new conversation.")
            print(f"process_message > Conversation {conversation_id} timed out after {time_diff_minutes:.1f} minutes. Creating new conversation.")
            # Set reason for archiving
            state.metadata["archive_reason"] = "conversation_timeout"
            
            # Archive the current conversation
            await self._archive_conversation(state)
            
            # Create new conversation
            new_conversation_id = await self.start_conversation(state.tenant_id, state.user_id, agent_id)
            
            # Get the new state
            state = await self.get_conversation_state(new_conversation_id)
            new_conversation_created = True
            reset_reason = "timeout"
            
            # Add system message explaining what happened
            state.history.append({
                "role": "system",
                "content": "Sua conversa anterior expirou devido à inatividade. Iniciamos uma nova conversa para você.",
                "timestamp": time.time()
            })
            
            # Update metadata
            state.metadata["previous_conversation_id"] = conversation_id
            state.metadata["reset_reason"] = "conversation_timeout"
        
        # Add the user message to history
        state.history.append({
            "role": "user",
            "content": message,
            "timestamp": current_time
        })
        
        # Update state metadata with config settings
        state.metadata.update({
            "transfer_threshold": tenant_config.agent_transfer.default_threshold,
            "max_transfers": tenant_config.agent_transfer.max_transfers_per_conversation,
            "memory_enabled": tenant_config.memory.enabled,
            "rag_enabled": tenant_config.rag.enabled,
        })
        
        # AQUI: Verificar automaticamente se a mensagem do usuário indica necessidade de escalação
        current_agent_id = state.current_agent_id
        current_agent = self.agent_service.get_agent(current_agent_id)
        
        if current_agent.human_escalation_enabled and tenant_config.enable_escalation_to_human:
            auto_escalation_keywords = [
                "falar com humano", "atendente humano", "pessoa real", 
                "atendente real", "não quero falar com robô", "quero falar com alguém", 
                "não está ajudando", "gerente", "supervisor", "falar com uma pessoa", 
                "assistente de verdade", "atendimento humano", "pessoa de verdade",
                "não entendeu", "conversar com alguém", "não resolveu"
            ]
            
            need_escalation = False
            for keyword in auto_escalation_keywords:
                if keyword.lower() in message.lower():
                    need_escalation = True
                    break
            
            # Se detectar necessidade de escalação, adicionar nota especial ao histórico
            if need_escalation:
                state.history.append({
                    "role": "system",
                    "content": "O usuário solicitou atendimento humano. Inclua <comando>ESCALAR_PARA_HUMANO</comando> em sua resposta.",
                    "timestamp": time.time()
                })
                
                # Também podemos adicionar um log para acompanhamento
                logger.info(f"process_message > Detectada necessidade de escalação automática na conversa {conversation_id}")
        
       
        
        # Determine if we should transfer
        current_agent_id = state.current_agent_id
        transfer_to_id = None
        transfer_reason = None
        
        logger.info(f"process_message > Current agent: {current_agent_id}")
        
        if current_agent.escalation_enabled:
            logger.info(f"process_message > Current agent {current_agent_id} is escalation enabled.")
            print(f"process_message > Current agent {current_agent_id} is escalation enabled.")
            # Rest of the processing logic remains similar...
            # Evaluate whether we should transfer to another agent
            agent_scores = await self.evaluate_agent_transfer(state, message)
            logger.info(f"process_message > Agent scores: {agent_scores}")
            
            # Get the best agent (might be the current one)
            best_agent_score = agent_scores[0]
            transfer_threshold = state.metadata.get(
                "transfer_threshold", 
                tenant_config.agent_transfer.default_threshold
            )
            
            # Check if best agent is different from current and meets threshold
            if best_agent_score.agent_id != current_agent_id and best_agent_score.score > transfer_threshold:
                logger.info(f"process_message > Best agent {best_agent_score.agent_id} has score {best_agent_score.score}, above threshold {transfer_threshold}. Transferring...")
                transfer_to_id = best_agent_score.agent_id
                transfer_reason = best_agent_score.reason
                
                # Update transfer count
                state.metadata["transfer_count"] = state.metadata.get("transfer_count", 0) + 1
        else:
            logger.info(f"process_message > Current agent {current_agent_id} is not escalation enabled.")
            print(f"process_message > Current agent {current_agent_id} is not escalation enabled.")
        
        # Get current agent (either the same or after transfer)
        if transfer_to_id is not None:
            # Log the transfer decision
            logger.info(f"process_message > Transferring conversation {conversation_id} from agent {current_agent_id} to {transfer_to_id}: {transfer_reason}")
            
            state.history.append({
                "role": "system",
                "content": f"Transferring to agent {transfer_to_id} ({transfer_reason})",
                "timestamp": time.time()
            })
            
            # Update current agent
            state.current_agent_id = transfer_to_id
            current_agent = self.agent_service.get_agent(transfer_to_id)
            logger.info(f"process_message > Updated current agent to {transfer_to_id} and name {current_agent.name}")    
            
        
        else:
            logger.info(f"process_message > Not transferring conversation {conversation_id} from agent {current_agent_id}.")
            # Update current agent
            current_agent = self.agent_service.get_agent(current_agent_id)
        
        # Retrieve RAG context based on agent settings and config
        rag_context = []
        if tenant_config.rag.enabled and current_agent.rag_categories:
            logger.info(f"process_message > Retrieving RAG context for agent {current_agent_id}")
            # Limit the number of categories to search
            categories_to_search = current_agent.rag_categories[:tenant_config.rag.categories_hard_limit]
            logger.info(f"process_message > Categories to search: {categories_to_search}")
            
            for category in categories_to_search:
                docs = await self.rag_service.search(
                    message, 
                    category=category,
                    limit=tenant_config.rag.default_limit
                )
                
                # Filter by relevance threshold
                relevant_docs = [doc for doc in docs if doc.get("relevance_score", 0) >= tenant_config.rag.min_relevance_score]
                rag_context.extend(relevant_docs)
                
            logger.info(f"Retrieved {len(rag_context)} relevant RAG docs for conversation {conversation_id}")
        
        # Retrieve relevant memories if enabled
        memory_context = []
        if tenant_config.memory.enabled and self.memory_service:
            try:
                relevant_memories = await self.memory_service.recall_memories(
                    tenant_id=state.tenant_id,
                    user_id=state.user_id,
                    query=message,
                    limit=tenant_config.memory.max_memories_per_query
                )
                
                if relevant_memories:
                    # Filter by relevance threshold
                    memory_context = [
                        {"content": m.content, "type": m.type} 
                        for m in relevant_memories
                    ]
                    
                    logger.info(f"Retrieved {len(memory_context)} relevant memories for conversation {conversation_id}")
            except Exception as e:
                logging.error(f"Error retrieving memories: {e}")
        
        # Check if it's time to generate a summary
        should_summarize = False
        message_count = len(state.history)
        last_summary_at = state.metadata.get("last_summary_at", 0)
        time_since_summary = time.time() - last_summary_at
        
        if (tenant_config.memory.enabled and 
            (message_count % tenant_config.memory.summary_frequency == 0 or 
            time_since_summary > tenant_config.memory.summary_time_threshold)):
            should_summarize = True

        if should_summarize and self.memory_service:
            try:
                # Generate summary in the background
                asyncio.create_task(self._generate_and_store_summary(state))
                
                # Update metadata
                state.metadata["last_summary_at"] = time.time()
            except Exception as e:
                logging.error(f"Erro ao agendar geração de resumo: {str(e)}")
                # Continue sem interromper o fluxo principal
        
        # Prepare prompt with history, context, memories and audio
        prompt = self._prepare_prompt(state, current_agent, rag_context, memory_context, contact_id, audio_data)
        
        ## Comentado pois o audio foi transcrito no inicio
        # # Get response from LLM
        # if audio_data and self.llm.supports_audio:
        #     # Para modelos que suportam áudio, usar método especial
        #     response, token_usage = await self.llm.generate_response_with_audio(prompt, audio_data)
        #     if response is None or 'Erro na geração com áudio' in response or 'Audio input modality is not enabled for models' in response:
        #         print("Erro na geração com áudio ou audio input modality is not enabled for models: ", response)
        #         logging.error(f"Erro na geração com áudio ou audio input modality is not enabled for models: {response}")
        #         response = "error_audio_processing"
        # else:
        #     # Get response from LLM - Método padrão para texto
        #     response, token_usage = await self.llm.generate_response(prompt)
        
        # Get response from LLM - sempre usar método de texto já que áudio foi transcrito
        response, token_usage = await self.llm.generate_response(prompt)

        # Registrar uso de tokens - Implementação melhorada
        if hasattr(self, 'token_counter_service') and self.token_counter_service:
            try:
                # Obter informações do modelo
                model_id = getattr(self.llm, 'model_id', None)
                
                # Se model_id não estiver disponível, tentar obter por nome
                if model_id is None and hasattr(self.llm, 'model'):
                    # Tenta encontrar o modelo pelo nome no banco de dados
                    try:
                        model_name = self.llm.model
                        from app.db.models.llm_model import LLMModel
                        db_session = getattr(self.token_counter_service, 'db', None)
                        if db_session:
                            model = db_session.query(LLMModel).filter(LLMModel.model_id == model_name).first()
                            if model:
                                model_id = model.id
                            else:
                                # Se não encontrar, usa ID 1 como fallback
                                model_id = 1
                    except Exception as e:
                        # Logar erro mas continuar
                        print(f"Erro ao buscar modelo por nome: {e}")
                        model_id = 1
                
                # Garantir que temos um ID de modelo válido
                if model_id is None:
                    model_id = 1  # Usar ID 1 como fallback
                
                # Registrar o uso
                await self.token_counter_service.log_token_usage(
                    tenant_id=int(state.tenant_id),
                    agent_id=current_agent.id,
                    model_id=model_id,
                    prompt_tokens=token_usage.get('prompt_tokens', 0),
                    completion_tokens=token_usage.get('completion_tokens', 0),
                    conversation_id=conversation_id
                )
            except Exception as e:
                # Logar erro mas não interromper o fluxo principal
                print(f"Erro ao registrar uso de tokens: {e}")
        
        # Process the response for actions
        processed_response = await self._process_agent_response(response, state, current_agent, tenant_config)
        
        # Add to history
        state.history.append({
            "role": "assistant",
            "agent_id": current_agent.id,
            "content": processed_response["response"],
            "timestamp": time.time()
        })
        
        # Add any action history if needed
        for action in processed_response.get("actions", []):
            if action.get("type") == "mcp_function":
                # Log function calls to history
                state.history.append({
                    "role": "system",
                    "content": f"Function call: {action['function']['name']}",
                    "timestamp": time.time(),
                    "metadata": {
                        "function_call": action["function"]
                    }
                })
            elif action.get("type") == "human_escalation":
                # Log escalation to history
                state.history.append({
                    "role": "system",
                    "content": f"Escalated to human: {action['contact']}",
                    "timestamp": time.time(),
                    "metadata": {
                        "escalation_info": action
                    }
                })
        
        state.last_updated = time.time()
        
        # Save updated state
        await self.save_conversation_state(state)
        
        # Return result
        result = {
            "response": processed_response["response"],
            "conversation_id": conversation_id,
            "current_agent": current_agent.name,
            "actions": processed_response.get("actions", []),
            "new_conversation_id": new_conversation_id if new_conversation_created else None,
            "conversation_reset": new_conversation_created,
            "reset_reason": reset_reason
        }
        
        if transfer_to_id:
            result["transfer_info"] = {
                "transferred": transfer_to_id is not None,
                "from_agent": None if not transfer_to_id else current_agent_id,
                "to_agent": transfer_to_id,
                "reason": transfer_reason
            }
        
        return result
    
    async def _process_agent_response(self, response: str, state: ConversationState, current_agent: Agent, config: SystemConfig) -> Dict[str, Any]:
        """
        Processes the response from the agent to identify actions.
        
        Args:
            response: Raw response from LLM
            state: Conversation state
            current_agent: Current agent handling the conversation
            config: System configuration
            
        Returns:
            Processed
            response with actions
        """
        
        # Padrão para capturar comandos
        comando_pattern = r'<comando>.*?</comando>'

        # Encontrar todos os comandos (caso queira os comandos para uso posterior, usar o grupo)
        comandos = re.findall(r'<comando>(.*?)</comando>', response, flags=re.DOTALL)

        # Remover os comandos da resposta visível (inclusive as tags)
        resposta_limpa = re.sub(comando_pattern, '', response, flags=re.DOTALL).strip()
        resposta_limpa = '\n'.join(line for line in resposta_limpa.splitlines() if line.strip())

        result = {
            "response": resposta_limpa,
            "next_agent_id": current_agent.id,
            "actions": []
        }
        
        # Processar cada comando encontrado
        for comando in comandos:
            if "ESCALAR_PARA_HUMANO" in comando and config.enable_escalation_to_human:
                # Determine if agent supports escalation
                escalation_available = False
                escalation_contact = None
                
                if current_agent.human_escalation_enabled and current_agent.human_escalation_contact:
                    escalation_available = True
                    escalation_contact = current_agent.human_escalation_contact
                else:
                    # Look for human agents
                    try:
                        agents = await self.agent_service.get_agents_by_tenant(state.tenant_id)
                        human_agents = [a for a in agents if a.type == AgentType.HUMAN]
                        
                        if human_agents:
                            escalation_available = True
                            result["next_agent_id"] = human_agents[0].id
                            escalation_contact = human_agents[0].human_escalation_contact
                    except Exception as e:
                        logging.error(f"Error finding human agent: {e}")
                
                if escalation_available and escalation_contact:
                    # Create escalation action
                    result["actions"].append({
                        "type": "human_escalation",
                        "contact": escalation_contact,
                        "conversation_id": state.conversation_id,
                        "conversation_summary": await self._generate_escalation_summary(state)
                    })
                    
                    # Clean response
                    result["response"] = result["response"].replace("ESCALAR_PARA_HUMANO", "")
                    
                    logger.info(f"Human escalation triggered to {escalation_contact}")
                else:
                    # Remove the tag but add explanation
                    result["response"] = result["response"].replace(
                        "ESCALAR_PARA_HUMANO", 
                        "[Nota: Escalação para humano solicitada, mas não há agentes humanos disponíveis no momento.]"
                    )
                    
                    logging.warning("Human escalation requested but no human agents available")
                
            elif "EXECUTAR_MCP:" in comando and config.mcp.enabled and current_agent.mcp_enabled:
                # Check for MCP function calls
                # Extract function calls (may be multiple)
                function_calls = []
                for function_call_text in response.split("EXECUTAR_MCP:")[1:]:
                    # Extract the JSON function call
                    function_data = function_call_text.split("\n")[0].strip()
                    try:
                        function_call = json.loads(function_data)
                        function_calls.append(function_call)
                        
                        # Clean the response
                        result["response"] = result["response"].replace(f"EXECUTAR_MCP:{function_data}", "")
                    except json.JSONDecodeError:
                        logging.warning(f"Invalid function call format: {function_data}")
                
                # Process function calls (up to configured limit)
                max_calls = min(len(function_calls), config.mcp.max_function_calls_per_message)
                for i, function_call in enumerate(function_calls[:max_calls]):
                    logger.info(f"Processing function call {i+1}/{max_calls}: {function_call.get('name')}")
                    
                    result["actions"].append({
                        "type": "mcp_function",
                        "function": function_call,
                        "requires_approval": config.mcp.functions_require_approval
                    })
                
            elif "CONSULTAR_ESPECIALISTA:" in comando:
                # Extract specialization information
                specialization = response.split("CONSULTAR_ESPECIALISTA:")[1].split("\n")[0].strip()
                
                # Look for specialists
                try:
                    # Buscar agentes relacionados para escalação
                    related_agents = await self.agent_service.get_agents_by_tenant_and_relationship_with_current_agent(
                        tenant_id=state.tenant_id,
                        current_agent_id=current_agent.id
                    )
                    
                    # Procurar um especialista apropriado
                    if related_agents:
                        # Escolher o agente com base na especialização mencionada
                        # Poderia implementar um algoritmo de correspondência melhor
                        best_match = None
                        for agent in related_agents:
                            if (specialization.lower() in agent.name.lower() or
                                specialization.lower() in agent.description.lower()):
                                best_match = agent
                                break
                        
                        # Se não encontrou por nome, usar o primeiro disponível
                        if not best_match and related_agents:
                            best_match = related_agents[0]
                        
                        if best_match:
                            result["next_agent_id"] = best_match.id
                            result["actions"].append({
                                "type": "specialist_consultation",
                                "specialist_id": best_match.id,
                                "specialization": specialization,
                                "context": response
                            })
                            
                            # Limpar resposta
                            result["response"] = result["response"].replace(f"CONSULTAR_ESPECIALISTA:{specialization}", "")
                            
                            logger.info(f"Escalação para especialista solicitada: {specialization}, encaminhado para: {best_match.name}")
                            return result
                except Exception as e:
                    logging.error(f"Error finding specialist: {e}")
        
        return result
    
    def _prepare_prompt(
        self, 
        state: ConversationState, 
        agent: Agent, 
        rag_context: List[Any], 
        memory_context: List[Dict[str, Any]] = None, 
        contact_id: str = None,
        audio_data: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, str]]:
        """
        Prepares the prompt for the LLM, including history, RAG context, and memories.
        """
        # Start with system prompt from agent configuration
        system_prompt = agent.generate_system_prompt()
        
        if contact_id:
            system_prompt += f"\n\n## Contact ID: {contact_id}\n"
        
        # Add RAG context if available
        if rag_context:
            system_prompt += "\n\n## Relevant Knowledge Base Information:\n"
            for i, doc in enumerate(rag_context[:3]):  # Limit to top 3 most relevant docs
                system_prompt += f"\nDocument {i+1}:\n{doc['content']}\n"
        
        # Add memory context if available
        if memory_context:
            system_prompt += "\n\n## User Memory and Context:\n"
            for memory in memory_context:
                memory_type_label = memory["type"].value.replace("_", " ").title()
                system_prompt += f"\n{memory_type_label}: {memory['content']}\n"
        
        if audio_data:
            system_prompt += "\n\n## Áudio Recebido:\n"
            system_prompt += "O usuário enviou uma mensagem de áudio. Use o conteúdo do áudio para responder adequadamente.\n"
        
        # linguagem de resposta
        system_prompt += "\n\n## Linguagem de resposta: Portugues Brasileiro\n"
        
        
        # Prepare conversation history
        messages = [{"role": "system", "content": system_prompt}]
        
        # Extract the relevant conversation history (last 10 exchanges)
        history = []
        for msg in state.history[-20:]:  # Get last 20 messages
            if msg["role"] in ["user", "assistant"]:
                history.append({"role": msg["role"], "content": msg["content"]})
            elif msg["role"] == "system" and "Transferring to agent" in msg["content"]:
                # Skip agent transfer messages in the prompt
                continue
        
        # Add history to messages
        messages.extend(history)
        
        return messages
    
    async def _generate_escalation_summary(self, state: ConversationState) -> str:
        """
        Generates a summary of the conversation for human escalation.
        
        Args:
            state: Conversation state
            
        Returns:
            Summary text
        """
        # Get the last few messages (max 10)
        recent_messages = state.history[-10:] if len(state.history) >= 10 else state.history[:]
        
        # Filter to just user and assistant messages
        filtered_messages = [
            msg for msg in recent_messages
            if msg.get("role") in ["user", "assistant"]
        ]
        
        # Format messages
        formatted_messages = []
        for msg in filtered_messages:
            timestamp = datetime.fromtimestamp(msg.get("timestamp", 0)).strftime("%H:%M:%S")
            role = "User" if msg.get("role") == "user" else "Assistant"
            content = msg.get("content", "")
            formatted_messages.append(f"[{timestamp}] {role}: {content}")
        
        # Check if there's a recent summary in metadata
        if "last_summary" in state.metadata:
            summary = f"Conversation Summary: {state.metadata['last_summary'].get('brief', '')}\n\n"
        else:
            summary = "Recent conversation:\n\n"
        
        # Add recent messages
        summary += "\n".join(formatted_messages)
        
        return summary
    
    def _generate_conversation_summary(self, state: ConversationState) -> str:
        """Gera um resumo da conversa para escalação."""
        # Implementação do resumo...
        pass
    
    async def save_conversation_state(self, state: ConversationState) -> None:
        """Salva o estado da conversa no Redis."""
        if not self.redis:
            return
        key = f"conversation:{state.conversation_id}"
        await self.redis.set(key, state.json())
        await self.redis.expire(key, 60 * 60 * 24)  # Expirar em 24 horas
    
    async def get_conversation_state(self, conversation_id: str) -> Optional[ConversationState]:
        """Recupera o estado da conversa do Redis."""
        if not self.redis:
            logger.info(f"[DEBUG] Cliente Redis não inicializado")
            return None
        
        # Garantir que o conversation_id seja uma string
        if isinstance(conversation_id, bytes):
            conversation_id = conversation_id.decode('utf-8')
        
        key = f"conversation:{conversation_id}"
        logger.info(f"[DEBUG] Buscando estado da conversa com a chave: {key}")
        try:
            data = await self.redis.get(key)
            
            if not data:
                logger.info(f"[DEBUG] Nenhum dado encontrado para a chave {key}")
                
                # Tentar buscar diretamente se o conversation_id já contém o prefixo
                if conversation_id.startswith("conversation:"):
                    direct_key = conversation_id
                    logger.info(f"[DEBUG] Tentando buscar diretamente com a chave: {direct_key}")
                    data = await self.redis.get(direct_key)
                    if not data:
                        logger.info(f"[DEBUG] Nenhum dado encontrado para a chave direta {direct_key}")
                        return None
                else:
                    return None
            
            logger.info(f"[DEBUG] Dados encontrados para conversa {conversation_id}")
            return ConversationState.parse_raw(data)
        except Exception as e:
            logger.info(f"[DEBUG] Erro ao recuperar estado da conversa: {e}")
            return None
    
    # async def _generate_and_store_summary(self, state: ConversationState) -> None:
    #     """
    #     Gera e armazena um resumo da conversa.
        
    #     Args:
    #         state: Estado da conversa
    #     """
    #     try:
    #         # Verificar se o serviço de memória está ativo
    #         if not self.memory_service:
    #             logging.warning(f"Tentativa de gerar resumo, mas o serviço de memória não está ativo")
    #             return
            
    #         logger.info(f"Gerando resumo para a conversa {state.conversation_id}")
            
    #         # Gerar resumo
    #         summary = await self.memory_service.generate_conversation_summary(
    #             conversation_id=state.conversation_id,
    #             tenant_id=state.tenant_id,
    #             user_id=state.user_id,
    #             messages=state.history
    #         )
            
    #         if not summary:
    #             logging.warning(f"Falha ao gerar resumo para conversa {state.conversation_id}")
    #             return
            
    #         # Armazenar o resumo nos metadados do estado
    #         state.metadata["last_summary"] = {
    #             "brief": summary.brief_summary,
    #             "detailed": summary.detailed_summary,
    #             "key_points": summary.key_points,
    #             "sentiment": summary.sentiment,
    #             "generated_at": time.time()
    #         }
            
    #         # Salvar estado atualizado
    #         await self.save_conversation_state(state)
            
    #         logger.info(f"Resumo gerado e armazenado para conversa {state.conversation_id}")
            
    #         # Verificar se precisa extrair memórias adicionais
    #         # Nota: O método generate_conversation_summary já extrai memórias básicas,
    #         # mas podemos adicionar lógica adicional aqui se necessário
            
    #     except Exception as e:
    #         logging.error(f"Erro ao gerar resumo da conversa: {str(e)}")
            
    #         # Log adicional para debugging
    #         import traceback
    #         logging.error(f"Stack trace completo: {traceback.format_exc()}")
            
    #         # Registrar o erro nos metadados
    #         state.metadata["last_summary_error"] = {
    #             "error": str(e),
    #             "timestamp": time.time(),
    #             "error_type": type(e).__name__
    #         }
            
    #         # Salvar estado mesmo com erro
    #         try:
    #             await self.save_conversation_state(state)
    #         except Exception as save_error:
    #             logging.error(f"Erro adicional ao salvar estado após falha de resumo: {str(save_error)}")
    
    async def _generate_and_store_summary(self, state: ConversationState) -> None:
        """
        Gera e armazena um resumo da conversa.
        
        Args:
            state: Estado da conversa
        """
        try:
            # Verificar se o serviço de memória está ativo
            if not self.memory_service:
                logging.warning(f"Tentativa de gerar resumo, mas o serviço de memória não está ativo")
                return
            
            logger.info(f"Gerando resumo para a conversa {state.conversation_id}")
            
            # Gerar resumo
            summary = await self.memory_service.generate_conversation_summary(
                conversation_id=state.conversation_id,
                tenant_id=state.tenant_id,
                user_id=state.user_id,
                messages=state.history
            )
            
            if not summary:
                logging.warning(f"Falha ao gerar resumo para conversa {state.conversation_id}")
                return
            
            # Armazenar o resumo nos metadados do estado
            state.metadata["last_summary"] = {
                "brief": summary.brief_summary,
                "detailed": summary.detailed_summary,
                "key_points": summary.key_points,
                "sentiment": summary.sentiment,
                "generated_at": time.time()
            }
            
            # Salvar estado atualizado
            await self.save_conversation_state(state)
            
            logger.info(f"Resumo gerado e armazenado para conversa {state.conversation_id}")
            
        except Exception as e:
            logging.error(f"Erro ao gerar resumo da conversa: {str(e)}")
            
            # Log adicional para debugging
            import traceback
            logging.error(f"Stack trace completo: {traceback.format_exc()}")
            
            # Registrar o erro nos metadados
            state.metadata["last_summary_error"] = {
                "error": str(e),
                "timestamp": time.time(),
                "error_type": type(e).__name__
            }
            
            # Salvar estado mesmo com erro
            try:
                await self.save_conversation_state(state)
            except Exception as save_error:
                logging.error(f"Erro adicional ao salvar estado após falha de resumo: {str(save_error)}")


    # Add method to get user profile with memories
    async def get_user_profile(self, tenant_id: str, user_id: str) -> Dict[str, Any]:
        """
        Retrieves a user profile with their memories and conversation history.
        """
        return await self.memory_service.get_user_profile(tenant_id, user_id)

    # Add method to start conversation with memory loading
    async def start_conversation(self, tenant_id: str, user_id: str, agent_id: Optional[str] = None) -> str:
        """
        Starts a new conversation with memory context.
        """
        if not agent_id:
            # Original implementation
            agents = await self.agent_service.get_agents_by_tenant(tenant_id)
            general_agents = [a for a in agents if a.type == AgentType.GENERAL]
            
            if not general_agents:
                raise ValueError(f"Tenant {tenant_id} não possui agente primário configurado")
            
            primary_agent = general_agents[0]
            agent_id = primary_agent.id
        
        # Create conversation state
        conversation_id = str(uuid.uuid4())
        state = ConversationState(
            conversation_id=conversation_id,
            tenant_id=tenant_id,
            user_id=user_id,
            current_agent_id=agent_id,
            history=[],
            last_updated=time.time()
        )
        
        # Get user profile from memory
        if self.memory_service:
            try:
                user_profile = await self.memory_service.get_user_profile(tenant_id, user_id)
                
                # Add relevant profile info to conversation state
                if user_profile:
                    state.metadata["user_profile"] = user_profile
                    
                    # Add greeting message with personalization if user has history
                    if user_profile.get("recent_conversations"):
                        # Has previous history
                        state.history.append({
                            "role": "system",
                            "content": "User has previous conversation history.",
                            "timestamp": time.time()
                        })
                        
                        logger.info(f"Carregado perfil do usuário {user_id} com {len(user_profile.get('recent_conversations', []))} conversas anteriores")
            except Exception as e:
                logging.error(f"Error retrieving user profile for {user_id}: {e}")
        
        # Save state
        await self.save_conversation_state(state)
        
        return conversation_id
    
    def _calculate_topic_change(self, previous_focus: Dict[str, float], current_focus: Dict[str, float]) -> float:
        """
        Calculate how much the conversation topic has changed.
        
        Args:
            previous_focus: Previous topic distribution
            current_focus: Current topic distribution
            
        Returns:
            Change score between 0.0 and 1.0
        """
        # Calculate Euclidean distance between focus vectors
        squared_diff_sum = 0
        for category in set(previous_focus.keys()) | set(current_focus.keys()):
            prev_value = previous_focus.get(category, 0)
            curr_value = current_focus.get(category, 0)
            squared_diff_sum += (prev_value - curr_value) ** 2
        
        # Normalize to 0-1 range
        distance = min(1.0, squared_diff_sum ** 0.5)
        logger.info(f"_calculate_topic_change > Topic change distance: {distance}")
        
        return distance
    
    async def evaluate_agent_transfer(self, state: ConversationState, message: str) -> List[AgentScore]:
        """
        Evaluates if the conversation should be transferred to a different agent.
        
        Returns:
            List of agent scores ordered by relevance
        """
        # Get transfer config
        transfer_config = self.config.agent_transfer
        logger.info("evaluate_agent_transfer > Transfer config: %s", transfer_config)
        
        # Check if transfers are enabled #TODO inlcuir verificação de transfer no agent atual
        if not transfer_config.enabled:
            logger.info("evaluate_agent_transfer > Transfers disabled")
            # Return only current agent with max score
            current_agent = self.agent_service.get_agent(state.current_agent_id)
            return [AgentScore(
                agent_id=current_agent.id,
                score=1.0,
                reason="Agent transfers disabled"
            )]
        
        # Get current agent
        current_agent = self.agent_service.get_agent(state.current_agent_id)
        logger.info("evaluate_agent_transfer > Current agent id: %s", current_agent.id)
        
        # Check minimum messages before transfer
        if len(state.history) < transfer_config.min_messages_before_transfer:
            logger.info(f"evaluate_agent_transfer > Not enough messages before transfer (current length history: {len(state.history)}). Returning current agent")
            return [AgentScore(
                agent_id=current_agent.id,
                score=1.0,
                reason="Not enough messages for transfer evaluation"
            )]
        
        # Check max transfers per conversation
        transfer_count = state.metadata.get("transfer_count", 0)
        if transfer_count >= transfer_config.max_transfers_per_conversation:
            logger.info("evaluate_agent_transfer > Max transfers per conversation reached. Current transfer count: %s. Returning current agent", transfer_count)
            return [AgentScore(
                agent_id=current_agent.id,
                score=1.0,
                reason="Maximum transfers reached"
            )]
        
        # Check cool down period after last transfer
        last_transfer_index = -1
        for i, msg in enumerate(reversed(state.history)):
            if msg.get("role") == "system" and ("Transferring to agent" in msg.get("content", "") or "Transferring to general agent" in msg.get("content", "") or "Transferindo para agente" in msg.get("content", "")):
                last_transfer_index = len(state.history) - i - 1
                break
        
        if last_transfer_index != -1:
            messages_since_transfer = len(state.history) - last_transfer_index - 1
            if messages_since_transfer < transfer_config.cool_down_messages:
                logger.info("evaluate_agent_transfer > Cool down period after last transfer. Messages since last transfer: %s. Returning current agent", messages_since_transfer)
                return [AgentScore(
                    agent_id=current_agent.id,
                    score=1.0,
                    reason=f"In transfer cool-down period ({messages_since_transfer}/{transfer_config.cool_down_messages})"
                )]
        
        # Get recent message history (last 5 messages)
        recent_messages = state.history[-5:] if len(state.history) >= 5 else state.history[:]
        
        # Get all agents for this tenant
        all_agents = self.agent_service.get_agents_by_tenant_and_relationship_with_current_agent(state.tenant_id, state.current_agent_id) # TODO trocar por get_agents_by_tenant_and_relationship_with_current_agent
        logger.info("evaluate_agent_transfer > All agents in tenant: %s", all_agents)
        
        # Initialize scores
        agent_scores = []
        
        # Add configurable threshold from conversation state metadata or config
        transfer_threshold = state.metadata.get(
            "transfer_threshold", 
            transfer_config.default_threshold
        )
        
        # Calculate the conversation focus
        conversation_focus = await self._analyze_conversation_focus(recent_messages, message)
        logger.info("evaluate_agent_transfer > Conversation focus: %s", conversation_focus)
        
        # Check for repetitive transfers (avoid transfer loops)
        recent_transfers = self._count_recent_transfers(state, 10)  # Look at last 10 exchanges
        transfer_penalty = min(transfer_config.default_transfer_penalty * recent_transfers, 0.5)
        logger.info("evaluate_agent_transfer > Recent transfers: %s. Transfer penalty: %s", recent_transfers, transfer_penalty)
        
        # Check for topic change
        previous_focus = state.metadata.get("previous_focus", {})
        topic_change_score = 0
        if previous_focus:
            topic_change_score = self._calculate_topic_change(previous_focus, conversation_focus)
            
        logger.info("evaluate_agent_transfer > Topic change score: %s", topic_change_score)
        
        # Store current focus for future comparison
        state.metadata["previous_focus"] = conversation_focus
        
        # Evaluate each agent
        for agent in all_agents:
            # Skip the current agent
            if agent.id == current_agent.id:
                agent_scores.append(AgentScore(
                    agent_id=agent.id,
                    score=0.7,  # Default score for current agent
                    reason="Current handling agent"
                ))
                continue
            
            # Calculate base score for this agent
            score, reason = await self._calculate_agent_score(
                agent, 
                message, 
                conversation_focus,
                recent_messages
            )
            
            # Apply transfer penalty to avoid loops
            if recent_transfers > 1:
                logger.info("evaluate_agent_transfer > Applying transfer penalty")
                score -= transfer_penalty
                reason += f" (Transfer penalty: -{transfer_penalty:.2f})"
            
            # Apply topic change bonus if applicable
            if topic_change_score > 0.3 and score > 0.4:
                logger.info("evaluate_agent_transfer > Applying topic change bonus")
                topic_bonus = min(transfer_config.topic_change_bonus, 0.3)
                score += topic_bonus
                reason += f" (Topic change bonus: +{topic_bonus:.2f})"
            
            agent_scores.append(AgentScore(
                agent_id=agent.id,
                score=score,
                reason=reason
            ))
        
        # Sort by score (highest first)
        result = sorted(agent_scores, key=lambda x: x.score, reverse=True)
        
        # Log the evaluation result
        logger.info(f"evaluate_agent_transfer > RESUTADO Agent transfer evaluation: {[f'{a.agent_id}: {a.score:.2f} ({a.reason})' for a in result[:3]]}")
        
        return result

    async def _analyze_conversation_focus(self, recent_messages: List[Dict[str, Any]], current_message: str) -> Dict[str, float]:
        """
        Analyzes the focus/topics of the conversation.
        
        Returns:
            Dictionary mapping categories to their relevance scores
        """
        # Combine recent messages with current message
        all_text = current_message + " " + " ".join([msg["content"] for msg in recent_messages 
                                                if msg["role"] in ["user", "assistant"]])
        
        # Inicializar um dicionário maior de categorias
        categories = {
            # Categorias existentes
            "appointment": 0.0,
            "product_info": 0.0,
            "technical_issue": 0.0,
            "billing": 0.0,
            "complaint": 0.0,
            "general": 0.0,
            
            # Novas categorias
            "healthcare": 0.0,
            "retail": 0.0,
            "sports": 0.0,
            "crafts": 0.0,
            "professional": 0.0,
            "finance": 0.0,
            "tourism": 0.0,
            "education": 0.0,
            "real_estate": 0.0,
            "automotive": 0.0,
            "logistics": 0.0,
            "events": 0.0,
            "pets": 0.0,
            "wellness": 0.0,
            "technology": 0.0,
            "legal": 0.0,
            "escalation": 0.0,
            "transfer": 0.0
        }
        
        # Palavras-chave expandidas por categoria (inglês e português)
        keywords = {
            "appointment": [
                # Inglês
                "appointment", "schedule", "book", "booking", "reservation", "meeting", "reschedule", 
                "cancel", "available", "time slot", "calendar", "diary", "slot", "date", "when",
                # Português
                "agendar", "agendamento", "marcar", "horário", "consulta", "reservar", "reserva", 
                "cancelar", "reagendar", "disponível", "horários", "calendário", "agenda", "data", 
                "quando", "que horas", "que dia", "disponibilidade", "vaga", "compromisso"
            ],
            
            "product_info": [
                # Inglês
                "product", "information", "details", "specs", "specifications", "how does", "features", 
                "what is", "tell me about", "description", "catalog", "manual", "guide", "how to use",
                "benefits", "advantages", "characteristics", "model", "version", "size", "color",
                # Português
                "produto", "informação", "informações", "detalhes", "especificações", "funcionalidades", 
                "características", "como funciona", "o que é", "me fale sobre", "descrição", "catálogo", 
                "manual", "guia", "como usar", "benefícios", "vantagens", "modelo", "versão", "tamanho", 
                "cor", "ficha técnica", "dados técnicos"
            ],
            
            "technical_issue": [
                # Inglês
                "problem", "issue", "error", "not working", "broken", "help", "fix", "bug", "crash",
                "freeze", "slow", "malfunction", "defect", "fault", "trouble", "difficulty", "support",
                "repair", "maintenance", "troubleshoot", "restore", "recover",
                # Português
                "problema", "erro", "não funciona", "quebrado", "quebrou", "ajuda", "consertar", 
                "defeito", "travou", "lento", "mau funcionamento", "falha", "dificuldade", "suporte", 
                "reparo", "manutenção", "resolver", "restaurar", "recuperar", "bug", "travando", 
                "parou de funcionar", "não liga", "não abre", "falhou"
            ],
            
            "billing": [
                # Inglês
                "bill", "billing", "payment", "charge", "charged", "refund", "price", "cost", "subscription",
                "invoice", "receipt", "transaction", "account", "balance", "fee", "money", "pay", "paid",
                "credit card", "debit", "installment", "discount", "promotion", "offer",
                # Português
                "conta", "cobrança", "pagamento", "cobrado", "reembolso", "preço", "custo", "assinatura",
                "fatura", "nota fiscal", "recibo", "transação", "saldo", "taxa", "dinheiro", "pagar", 
                "cartão de crédito", "débito", "parcela", "desconto", "promoção", "oferta", "valor", 
                "mensalidade", "anuidade", "grátis", "gratuito"
            ],
            
            "complaint": [
                # Inglês
                "unhappy", "disappointed", "complaint", "complain", "manager", "supervisor", "unsatisfied", 
                "poor", "bad", "terrible", "awful", "worst", "angry", "frustrated", "furious", "outraged",
                "unacceptable", "disgusted", "horrible", "disgusting", "pathetic", "useless",
                # Português
                "insatisfeito", "decepcionado", "reclamação", "reclamar", "gerente", "supervisor", 
                "ruim", "péssimo", "terrível", "horrível", "pior", "raiva", "frustrado", "furioso", 
                "inaceitável", "nojento", "patético", "inútil", "indignado", "revoltado", "chateado",
                "descontente", "irritado", "aborrecido"
            ],
            
            "healthcare": [
                # Inglês
                "doctor", "medical", "health", "clinic", "hospital", "patient", "treatment", "medicine",
                "prescription", "appointment", "diagnosis", "therapy", "surgery", "nurse", "physician",
                "dentist", "pharmacy", "medication", "symptom", "pain", "illness", "disease",
                # Português
                "médico", "saúde", "clínica", "hospital", "paciente", "tratamento", "remédio", "receita",
                "consulta", "diagnóstico", "terapia", "cirurgia", "enfermeiro", "dentista", "farmácia",
                "medicamento", "sintoma", "dor", "doença", "enfermidade", "mal-estar", "exame", 
                "laboratório", "raio-x", "ultrassom"
            ],
            
            "retail": [
                # Inglês
                "store", "shop", "shopping", "purchase", "buy", "buying", "shipping", "delivery", "item", 
                "product", "stock", "inventory", "sale", "discount", "promotion", "catalog", "order",
                "cart", "checkout", "online", "website", "marketplace", "brand", "size", "color",
                # Português
                "loja", "compra", "comprar", "comprando", "entrega", "item", "produto", "estoque", 
                "venda", "desconto", "promoção", "catálogo", "pedido", "carrinho", "site", "online",
                "mercado", "marca", "tamanho", "cor", "shopping", "varejo", "atacado", "liquidação"
            ],
            
            "sports": [
                # Inglês
                "sport", "sports", "gym", "fitness", "training", "coach", "workout", "exercise", "athlete",
                "team", "match", "game", "competition", "tournament", "league", "championship", "player",
                "equipment", "gear", "nutrition", "diet", "performance", "muscle", "strength",
                # Português
                "esporte", "esportes", "academia", "fitness", "treino", "treinador", "exercício", 
                "atleta", "time", "jogo", "partida", "competição", "torneio", "campeonato", "jogador",
                "equipamento", "nutrição", "dieta", "performance", "músculo", "força", "condicionamento",
                "modalidade", "futebol", "basquete", "vôlei", "natação"
            ],
            
            "crafts": [
                # Inglês
                "craft", "crafts", "handmade", "custom", "customized", "art", "creative", "design", 
                "personalized", "DIY", "hobby", "create", "make", "build", "paint", "draw", "sew",
                "knit", "wood", "pottery", "jewelry", "decoration", "gift", "unique",
                # Português
                "artesanato", "feito à mão", "personalizado", "arte", "criativo", "design", "criar",
                "fazer", "construir", "pintar", "desenhar", "costurar", "tricô", "madeira", "cerâmica",
                "joias", "decoração", "presente", "único", "exclusivo", "customizado", "bordado",
                "crochê", "scrapbook", "bricolagem"
            ],
            
            "professional": [
                # Inglês
                "service", "professional", "consulting", "consultation", "contract", "project", "business",
                "corporate", "company", "office", "meeting", "presentation", "proposal", "client",
                "customer", "enterprise", "organization", "management", "strategy", "solution",
                # Português
                "serviço", "profissional", "consultoria", "consulta", "contrato", "projeto", "negócio",
                "empresa", "escritório", "reunião", "apresentação", "proposta", "cliente", "corporativo",
                "organização", "gestão", "estratégia", "solução", "atendimento", "assessoria",
                "prestação de serviços", "terceirizado"
            ],
            
            "finance": [
                # Inglês
                "bank", "banking", "financial", "finance", "investment", "invest", "account", "money",
                "loan", "credit", "debit", "interest", "rate", "mortgage", "insurance", "savings",
                "budget", "tax", "stock", "bond", "portfolio", "currency", "exchange",
                # Português
                "banco", "financeiro", "finanças", "investimento", "investir", "conta", "dinheiro",
                "empréstimo", "crédito", "débito", "juros", "taxa", "financiamento", "seguro", 
                "poupança", "orçamento", "imposto", "ação", "câmbio", "moeda", "carteira", 
                "aplicação", "rendimento", "capital"
            ],
            
            "tourism": [
                # Inglês
                "travel", "traveling", "trip", "tourist", "tourism", "vacation", "holiday", "tour", 
                "booking", "hotel", "flight", "destination", "package", "guide", "excursion", "resort",
                "passport", "visa", "luggage", "sightseeing", "adventure", "cruise", "rental",
                # Português
                "viagem", "viajar", "turista", "turismo", "férias", "feriado", "passeio", "reserva",
                "hotel", "voo", "destino", "pacote", "guia", "excursão", "resort", "passaporte",
                "visto", "bagagem", "pontos turísticos", "aventura", "cruzeiro", "aluguel",
                "roteiro", "hospedagem", "pousada"
            ],
            
            "education": [
                # Inglês
                "school", "education", "educational", "course", "class", "lesson", "student", "teacher",
                "professor", "learn", "learning", "study", "studying", "university", "college", "degree",
                "certificate", "training", "workshop", "seminar", "exam", "test", "grade", "homework",
                # Português
                "escola", "educação", "educacional", "curso", "aula", "lição", "aluno", "estudante",
                "professor", "professora", "aprender", "estudar", "universidade", "faculdade", "diploma",
                "certificado", "treinamento", "workshop", "seminário", "prova", "teste", "nota",
                "tarefa", "ensino", "aprendizado", "disciplina"
            ],
            
            "real_estate": [
                # Inglês
                "property", "real estate", "house", "home", "apartment", "rent", "rental", "buy", 
                "purchase", "sell", "sale", "lease", "mortgage", "landlord", "tenant", "neighborhood",
                "location", "furnished", "unfurnished", "utilities", "deposit", "contract", "broker",
                # Português
                "imóvel", "imobiliária", "casa", "lar", "apartamento", "alugar", "aluguel", "comprar",
                "vender", "venda", "locação", "financiamento", "proprietário", "inquilino", "bairro",
                "localização", "mobiliado", "sem móveis", "condomínio", "depósito", "fiador", "corretor",
                "terreno", "lote", "construção", "reforma"
            ],
            
            "automotive": [
                # Inglês
                "car", "vehicle", "auto", "automobile", "repair", "maintenance", "garage", "mechanic",
                "engine", "brake", "tire", "oil", "service", "inspection", "insurance", "license",
                "registration", "fuel", "gas", "battery", "transmission", "dealer", "warranty",
                # Português
                "carro", "veículo", "automóvel", "auto", "reparo", "manutenção", "oficina", "mecânico",
                "motor", "freio", "pneu", "óleo", "serviço", "revisão", "seguro", "licença", "habilitação",
                "combustível", "gasolina", "bateria", "câmbio", "concessionária", "garantia",
                "peças", "acessórios", "lavagem", "detalhamento"
            ],
            
            "logistics": [
                # Inglês
                "delivery", "shipping", "package", "parcel", "tracking", "courier", "shipment", 
                "transport", "transportation", "freight", "cargo", "warehouse", "distribution",
                "supply chain", "pickup", "drop-off", "express", "standard", "overnight",
                # Português
                "entrega", "envio", "pacote", "encomenda", "rastreamento", "correio", "transportadora",
                "transporte", "frete", "carga", "depósito", "armazém", "distribuição", "logística",
                "retirada", "express", "sedex", "pac", "motoboy", "coleta", "expedição"
            ],
            
            "events": [
                # Inglês
                "event", "events", "party", "celebration", "concert", "show", "performance", "ticket",
                "booking", "reservation", "venue", "location", "date", "time", "guest", "invitation",
                "wedding", "birthday", "anniversary", "conference", "meeting", "seminar", "festival",
                # Português
                "evento", "eventos", "festa", "celebração", "comemoração", "show", "espetáculo", 
                "ingresso", "reserva", "local", "data", "horário", "convidado", "convite", "casamento",
                "aniversário", "conferência", "reunião", "seminário", "festival", "formatura",
                "buffet", "decoração", "organização"
            ],
            
            "pets": [
                # Inglês
                "pet", "pets", "animal", "animals", "dog", "cat", "bird", "fish", "veterinary", "vet",
                "grooming", "care", "food", "toy", "training", "health", "vaccine", "medicine",
                "shelter", "adoption", "breed", "puppy", "kitten", "walk", "exercise",
                # Português
                "pet", "pets", "animal", "animais", "cachorro", "cão", "gato", "pássaro", "peixe",
                "veterinário", "banho", "tosa", "cuidado", "ração", "brinquedo", "adestramento",
                "saúde", "vacina", "remédio", "abrigo", "adoção", "raça", "filhote", "passeio",
                "exercício", "petshop", "aquário"
            ],
            
            "wellness": [
                # Inglês
                "spa", "massage", "beauty", "treatment", "relaxation", "therapy", "well-being", "wellness",
                "facial", "manicure", "pedicure", "hair", "salon", "skin", "cosmetic", "aesthetic",
                "meditation", "yoga", "stress", "mental health", "self-care", "mindfulness",
                # Português
                "spa", "massagem", "beleza", "tratamento", "relaxamento", "terapia", "bem-estar",
                "facial", "manicure", "pedicure", "cabelo", "salão", "pele", "cosmético", "estético",
                "meditação", "yoga", "estresse", "saúde mental", "autocuidado", "mindfulness",
                "estética", "depilação", "limpeza de pele", "hidratação"
            ],
            
            "technology": [
                # Inglês
                "computer", "software", "hardware", "tech", "technology", "IT", "system", "digital",
                "internet", "website", "app", "application", "programming", "coding", "database",
                "server", "network", "security", "backup", "cloud", "artificial intelligence", "AI",
                # Português
                "computador", "software", "hardware", "tecnologia", "TI", "sistema", "digital",
                "internet", "site", "aplicativo", "app", "programação", "código", "banco de dados",
                "servidor", "rede", "segurança", "backup", "nuvem", "inteligência artificial", "IA",
                "informática", "dados", "plataforma", "desenvolvimento"
            ],
            
            "legal": [
                # Inglês
                "lawyer", "attorney", "legal", "law", "rights", "contract", "agreement", "lawsuit",
                "court", "judge", "justice", "legislation", "regulation", "compliance", "liability",
                "intellectual property", "patent", "copyright", "trademark", "litigation", "dispute",
                # Português
                "advogado", "jurídico", "lei", "direito", "direitos", "contrato", "acordo", "processo",
                "tribunal", "juiz", "justiça", "legislação", "regulamentação", "compliance", 
                "responsabilidade", "propriedade intelectual", "patente", "marca", "litígio", "disputa",
                "advocacia", "legal", "jurisprudência", "documentos"
            ],
            
            "escalation": [
                # Inglês
                "speak to manager", "talk to human", "need supervisor", "escalate", "real person",
                "human agent", "transfer", "connect me", "not satisfied", "speak to someone else",
                "this isn't helping", "I want to talk", "get me a person", "human support",
                # Português
                "falar com gerente", "atendente humano", "preciso supervisor", "escalar", "pessoa real",
                "agente humano", "transferir", "me conectar", "não satisfeito", "falar com outra pessoa",
                "isso não está ajudando", "quero falar", "me passar uma pessoa", "suporte humano",
                "quero falar com alguém", "não resolve", "preciso de ajuda", "outra pessoa"
            ],
            
            "commercial": [
                # Comercial/Vendas
                "orçamento", "proposta", "preço", "valor", "custo", "contratar", "comprar",
                "vendas", "comercial", "kit", "comodato", "mensalidade", "adesão",
                "arena", "quadra", "campo", "instalação", "câmera", "sistema viplay",
                # Inglês
                "quote", "proposal", "price", "cost", "buy", "purchase", "sales", "commercial"
            ],
            
            "support": [
                # Suporte Técnico
                "problema", "erro", "não funciona", "quebrou", "ajuda", "suporte",
                "câmera offline", "sistema não grava", "senha", "login", "site",
                "app", "ewelink", "painel", "configuração", "compartilhamento",
                # Inglês
                "problem", "error", "not working", "broken", "help", "support",
                "offline", "password", "configuration"
            ],
            
            "transfer": [
                # Inglês
                "transfer", "redirect", "connect", "forward", "route", "send to", "pass to", 
                "different department", "another agent", "specialist", "expert", "technical support",
                "transferring to agent","transferring to department", "transferring to area","transferring to",
                "specialist", "expert", "transfer", "forward", "escalate",
                # Português
                "transferir", "redirecionar", "conectar", "encaminhar", "enviar para", "passar para",
                "outro departamento", "outro agente", "especialista", "expert", "suporte técnico",
                "setor específico", "departamento", "área", "transferindo",
                "especialista", "comercial", "suporte", "técnico", "vendas",
                "quero falar com", "preciso de", "transferir", "encaminhar",
            ]
        }
        
        # Calcular scores
        all_text_lower = f"{current_message} {' '.join([msg.get('content', '') for msg in recent_messages])}".lower()
    
        for category, words in keywords.items():
            for word in words:
                if word in all_text_lower:
                    categories[category] += 0.3  # Increment score for each keyword found
        
        # Ensure general category gets a minimum score
        categories["general"] = max(0.3, 1.0 - sum(categories.values()))
        
        # Normalize scores
        total = sum(categories.values())
        if total > 0:
            for category in categories:
                categories[category] /= total
        
        return categories

    async def _calculate_agent_score(self, agent, message: str, conversation_focus: Dict[str, float], 
                                recent_messages: List[Dict[str, Any]]) -> Tuple[float, str]:
        """
        Calculates a score for how well an agent can handle the current conversation.
        
        Returns:
            Tuple of (score, reason)
        """
        score = 0.0
        reasons = []
        
        # 1. Check if agent has explicit specialties that match conversation focus
        agent_explicit_specialties = agent.get_specialties_list() if hasattr(agent, 'get_specialties_list') else []
        if agent_explicit_specialties:
            explicit_match_score = 0.0
            for specialty in agent_explicit_specialties:
                if specialty.lower() in conversation_focus:
                    explicit_match_score += conversation_focus[specialty.lower()] * 0.5
                    
            if explicit_match_score > 0:
                score += explicit_match_score
                reasons.append(f"Especialidade explícita: {explicit_match_score:.2f}")
        
        # 2. Check if agent type matches conversation focus
        agent_specialties = self._get_agent_specialties(agent)
        
        focus_score = 0.0
        for category, focus_value in conversation_focus.items():
            if category in agent_specialties:
                focus_score += focus_value * agent_specialties[category]
        
        score += focus_score
        if focus_score > 0.3:
            reasons.append(f"Relevância do tópico: {focus_score:.2f}")
            
        # Boost para agentes especializados quando há correspondência
        if focus_score > 0.2 and agent.type == AgentType.SPECIALIST:
            score += 0.4  # Boost adicional para especialistas
            reasons.append("Agente especialista relevante")

        # Boost específico para contexto comercial/vendas
        if conversation_focus.get("commercial", 0) > 0.15 and "comercial" in agent.name.lower():
            score += 0.5
            reasons.append("Contexto comercial detectado")

        # Boost específico para contexto de suporte
        if conversation_focus.get("support", 0) > 0.15 and "suporte" in agent.name.lower():
            score += 0.5
            reasons.append("Contexto de suporte detectado")
        
        # 3. Check if the agent has the right RAG categories for this conversation
        if agent.rag_categories and message:
            rag_score = await self._calculate_rag_relevance(agent, message)
            score += rag_score
            if rag_score > 0.2:
                reasons.append(f"Base de conhecimento: {rag_score:.2f}")
        
        # 4. Check agent's MCP capabilities if needed in this conversation
        if "API_CALL" in message or "SYSTEM" in message:
            mcp_score = 0.3 if agent.mcp_enabled else 0.0
            score += mcp_score
            if mcp_score > 0:
                reasons.append("Capacidade MCP necessária")
        
        # 5. Check for human escalation needs
        escalation_indicators = [
            "speak to human", "real person", "manager", "supervisor", "unhappy", "complaint",
            "falar com humano", "pessoa real", "gerente", "supervisor", "insatisfeito", "reclamação",
            "atendente", "responsável"
        ]
        
        if any(indicator in message.lower() for indicator in escalation_indicators):
            human_score = 0.5 if agent.type == AgentType.HUMAN or agent.human_escalation_enabled else 0.0
            score += human_score
            if human_score > 0:
                reasons.append("Provável necessidade de escalação humana")
        
        # 6. Check for agent's escalation capability if enabled
        if hasattr(agent, 'escalation_enabled') and agent.escalation_enabled and 'escalation' in conversation_focus:
            escalation_score = 0.4
            score += escalation_score
            reasons.append("Capacidade de escalação disponível")
        
        # Generate final reason text
        reason = ", ".join(reasons) if reasons else "Sem forte correspondência"
        
        logger.info(f"_calculate_agent_score > return Score: {score}, Reason: {reason}")
        
        return score, reason

    def _get_agent_specialties(self, agent) -> Dict[str, float]:
        """
        Extract agent specialties from its configuration.
        
        Returns:
            Dictionary mapping categories to specialty scores
        """
        # Base specialties (mantendo as originais e adicionando novas)
        specialties = {
            # Categorias originais
            "appointment": 0.0,
            "product_info": 0.0,
            "technical_issue": 0.0,
            "billing": 0.0,
            "complaint": 0.0,
            "general": 0.0,
            
            # Novas categorias de saúde
            "healthcare": 0.0,
            "medical_exams": 0.0,
            "health_insurance": 0.0,
            
            # Categorias de varejo e e-commerce
            "retail": 0.0,
            "order_tracking": 0.0,
            "returns": 0.0,
            "after_sales": 0.0,
            
            # Categorias de esportes e lazer
            "sports": 0.0,
            "equipment_rental": 0.0,
            "class_booking": 0.0,
            
            # Pequenos negócios e artesanato
            "small_business": 0.0,
            "crafts": 0.0,
            "custom_orders": 0.0,
            
            # Serviços profissionais
            "professional_services": 0.0,
            "consulting": 0.0,
            "quotes": 0.0,
            
            # Finanças e contabilidade
            "finance": 0.0,
            "accounting": 0.0,
            "invoicing": 0.0,
            "tax": 0.0,
            
            # Turismo e hotelaria
            "tourism": 0.0,
            "hotel": 0.0,
            "reservations": 0.0,
            "travel": 0.0,
            
            # Educação e cursos
            "education": 0.0,
            "courses": 0.0,
            "student_support": 0.0,
            
            # Imobiliário
            "real_estate": 0.0,
            "property": 0.0,
            "rental": 0.0,
            
            # Automotivo
            "automotive": 0.0,
            "vehicles": 0.0,
            "maintenance": 0.0,
            
            # Logística e transporte
            "logistics": 0.0,
            "shipping": 0.0,
            "delivery": 0.0,
            
            # Eventos e entretenimento
            "events": 0.0,
            "entertainment": 0.0,
            "tickets": 0.0,
            
            # Pet shop
            "pets": 0.0,
            "veterinary": 0.0,
            
            # Bem-estar e estética
            "wellness": 0.0,
            "beauty": 0.0,
            
            # Tecnologia
            "technology": 0.0,
            "it_support": 0.0,
            
            # Jurídico
            "legal": 0.0,
            "law": 0.0,
            
            "transfer": 0.0,
            "commercial": 0.0,
            "sales": 0.0,
            "support": 0.0,
            "technical_support": 0.0,
        }
        
        # Default score based on agent type
        if agent.type == AgentType.GENERAL: 
            specialties["general"] = 0.8
        elif agent.type == AgentType.HUMAN:
            specialties["complaint"] = 0.9
        
        # Extract specialties from name and description
        agent_text = f"{agent.name} {agent.description}".lower()
        
        # Dicionário expandido de palavras-chave por especialidade
        specialty_keywords = {
            # Categorias originais
            "appointment": ["appointment", "schedule", "booking", "calendar", "agendamento", "agendar", "marcar", "horário", "reservar"],
            "product_info": ["product", "catalog", "information", "details", "specs", "produto", "catálogo", "informação", "detalhes", "especificações"],
            "technical_issue": ["technical", "support", "help", "troubleshoot", "issue", "técnico", "suporte", "ajuda", "problema", "defeito"],
            "billing": ["billing", "payment", "invoice", "financial", "refund", "pagamento", "fatura", "cobrança", "financeiro", "reembolso"],
            "complaint": ["complaint", "escalation", "resolution", "satisfaction", "reclamação", "problema", "insatisfação", "resolução"],
            
            
            # Saúde e Bem-Estar
            "healthcare": ["saúde", "médico", "clínica", "hospital", "tratamento", "consulta", "health", "doctor", "clinic", "treatment"],
            "medical_exams": ["exame", "laboratório", "resultado", "médico", "test", "laboratory", "exam", "results"],
            "health_insurance": ["plano de saúde", "convênio", "seguro saúde", "cobertura", "insurance", "coverage", "health plan"],
            
            # Varejo e E-commerce
            "retail": ["loja", "compra", "produto", "estoque", "promoção", "store", "purchase", "retail", "sale"],
            "order_tracking": ["pedido", "rastreamento", "entrega", "status", "order", "tracking", "delivery", "status"],
            "returns": ["troca", "devolução", "reembolso", "garantia", "return", "exchange", "refund", "warranty"],
            
            # Esportes e Lazer
            "sports": ["esporte", "academia", "treino", "atividade", "sports", "gym", "training", "activity"],
            "equipment_rental": ["aluguel", "equipamento", "material", "empréstimo", "rental", "equipment", "gear", "loan"],
            "class_booking": ["aula", "turma", "professor", "instrutor", "class", "teacher", "instructor", "course"],
            
            # Pequenos Negócios e Artesanato
            "small_business": ["negócio", "empresa", "empreendedor", "business", "company", "entrepreneur"],
            "crafts": ["artesanato", "feito à mão", "artesanal", "craft", "handmade", "artisanal"],
            "custom_orders": ["personalizado", "sob medida", "encomenda", "custom", "personalized", "bespoke", "order"],
            
            # Serviços Profissionais
            "professional_services": ["serviço", "profissional", "contrato", "service", "professional", "contract"],
            "consulting": ["consultoria", "assessoria", "especialista", "consulting", "advisory", "specialist"],
            "quotes": ["orçamento", "proposta", "cotação", "quote", "proposal", "estimate"],
            
            # Finanças e Contabilidade
            "finance": ["financeiro", "banco", "investimento", "finance", "bank", "investment"],
            "accounting": ["contabilidade", "contador", "fiscal", "accounting", "accountant", "tax"],
            "invoicing": ["nota fiscal", "fatura", "boleto", "invoice", "bill", "receipt"],
            
            # Turismo e Hotelaria
            "tourism": ["turismo", "viagem", "passeio", "tourism", "travel", "tour"],
            "hotel": ["hotel", "pousada", "hospedagem", "acomodação", "lodging", "accommodation"],
            "reservations": ["reserva", "booking", "check-in", "check-out"],
            
            # Educação e Cursos
            "education": ["educação", "escola", "faculdade", "universidade", "education", "school", "college", "university"],
            "courses": ["curso", "treinamento", "aula", "workshop", "course", "training", "class", "workshop"],
            "student_support": ["aluno", "estudante", "matrícula", "student", "enrollment", "academic"],
            
            # Imobiliário
            "real_estate": ["imobiliária", "imóvel", "propriedade", "real estate", "property"],
            "property": ["casa", "apartamento", "comercial", "terreno", "house", "apartment", "commercial", "land"],
            "rental": ["aluguel", "locação", "inquilino", "rental", "lease", "tenant"],
            
            # Automotivo
            "automotive": ["automóvel", "carro", "veículo", "automotive", "car", "vehicle"],
            "vehicles": ["modelo", "marca", "ano", "quilometragem", "model", "brand", "year", "mileage"],
            "maintenance": ["oficina", "mecânico", "revisão", "conserto", "garage", "mechanic", "service", "repair"],
            
            # Logística e Transporte
            "logistics": ["logística", "transporte", "envio", "logistics", "transport", "shipping"],
            "shipping": ["frete", "entrega", "remessa", "transportadora", "shipping", "delivery", "courier"],
            
            # Eventos e Entretenimento
            "events": ["evento", "festa", "conferência", "show", "event", "party", "conference", "show"],
            "entertainment": ["entretenimento", "lazer", "diversão", "entertainment", "leisure", "fun"],
            "tickets": ["ingresso", "bilhete", "reserva", "ticket", "reservation"],
            
            # Pet shop
            "pets": ["pet", "animal", "cachorro", "gato", "dog", "cat", "animal"],
            "veterinary": ["veterinário", "clínica", "vacina", "pet", "veterinary", "clinic", "vaccine"],
            
            # Bem-estar e Estética
            "wellness": ["bem-estar", "saúde", "spa", "massagem", "wellness", "health", "spa", "massage"],
            "beauty": ["beleza", "estética", "tratamento", "beauty", "esthetic", "treatment"],
            
            # Tecnologia
            "technology": ["tecnologia", "computador", "sistema", "software", "technology", "computer", "system", "software"],
            "it_support": ["suporte", "técnico", "manutenção", "support", "technical", "maintenance"],
            
            # Jurídico
            "legal": ["jurídico", "legal", "direito", "legal", "law", "rights"],
            "law": ["advogado", "processo", "contrato", "lawyer", "lawsuit", "contract"],
            
            "commercial": ["comercial", "vendas", "sales", "specialist comercial", "commercial"],
            "sales": ["vendas", "sales", "comercial", "orçamento", "proposta"],
            "support": ["suporte", "support", "técnico", "technical", "problema", "issue"],
            "technical_support": ["suporte técnico", "technical support", "técnico", "problema técnico"],
            "transfer": ["transfer", "escalation", "specialist", "especialista"],
        }
        
        # Calcular pontuação para cada especialidade
        for category, keywords in specialty_keywords.items():
            for keyword in keywords:
                if keyword in agent_text:
                    specialties[category] += 0.4
        
        # Cap scores at 1.0
        for category in specialties:
            specialties[category] = min(specialties[category], 1.0)
            
        # Boost específico para agentes especializados # TODO verificar mais opções aqui
        if "comercial" in agent_text or "vendas" in agent_text:
            specialties["commercial"] = 0.9
            specialties["sales"] = 0.9
            specialties["transfer"] = 0.8
            
        if "suporte" in agent_text or "support" in agent_text:
            specialties["support"] = 0.9
            specialties["technical_support"] = 0.9
            specialties["transfer"] = 0.8
        
        return specialties

    async def _calculate_rag_relevance(self, agent, message: str) -> float:
        """
        Calculate how relevant an agent's RAG categories are to the message.
        
        Returns:
            Relevance score between 0.0 and 1.0
        """
        if not agent.rag_categories:
            return 0.0
        
        relevance = 0.0
        
        # Find if any documents in the agent's categories match the query
        for category in agent.rag_categories:
            try:
                # Search with a low limit to quickly check relevance
                results = await self.rag_service.search(message, category=category, limit=2)
                if results and len(results) > 0:
                    # Add score based on the top result's score
                    top_score = results[0].get("relevance_score", 0.0)
                    relevance += min(top_score, 0.4)  # Cap individual category contribution
            except Exception:
                # Error handling - continue with other categories
                pass
        
        # Cap overall relevance
        return min(relevance, 0.6)

    def _count_recent_transfers(self, state: ConversationState, max_messages: int) -> int:
        """
        Count the number of agent transfers in recent conversation history.
        
        Returns:
            Number of agent transfers
        """
        transfers = 0
        agent_sequence = []
        
        # Look at recent messages to extract agent transfers
        for message in reversed(state.history[-max_messages:] if len(state.history) >= max_messages else state.history):
            if message["role"] == "assistant" and "agent_id" in message:
                agent_sequence.append(message["agent_id"])
        
        # Count changes in agent_id
        for i in range(1, len(agent_sequence)):
            if agent_sequence[i] != agent_sequence[i-1]:
                transfers += 1
        
        return transfers
    
    async def list_conversations_by_tenant(self, tenant_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Lists conversations for a specific tenant.
        
        Args:
            tenant_id: The tenant ID
            limit: Maximum number of conversations to return
            
        Returns:
            List of conversation information dictionaries
        """
        conversations = []
        
        try:
            # Get all keys matching the pattern
            pattern = f"conversation:*"
            if not self.redis:
                logging.error("Redis client not initialized")
                print("Redis client not initialized")
                return []
                
            keys = await self.redis.keys(pattern)
            
            # Get each conversation state
            for key in keys[:limit * 2]:  # Get more than needed to filter by tenant
                try:
                    data = await self.redis.get(key)
                    if data:
                        state = ConversationState.parse_raw(data)
                        
                        # Filter by tenant
                        if state.tenant_id == tenant_id:
                            # Add basic info
                            conversations.append({
                                "conversation_id": state.conversation_id,
                                "user_id": state.user_id,
                                "current_agent_id": state.current_agent_id,
                                "message_count": len(state.history),
                                "last_updated": state.last_updated,
                                # Add summary if available
                                "summary": state.metadata.get("last_summary", {}).get("brief", None)
                            })
                            
                            if len(conversations) >= limit:
                                break
                except Exception as e:
                    logging.warning(f"Error parsing conversation state for key {key}: {e}")
                    continue
        except Exception as e:
            logging.error(f"Error listing conversations: {e}")
        
        # Sort by last updated (most recent first)
        conversations.sort(key=lambda x: x.get("last_updated", 0), reverse=True)
        
        return conversations[:limit]

    async def list_conversations_by_user(self, tenant_id: str, user_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Lists conversations for a specific user within a tenant.
        
        Args:
            tenant_id: The tenant ID
            user_id: The user ID
            limit: Maximum number of conversations to return
            
        Returns:
            List of conversation information dictionaries
        """
        conversations = []
        
        try:
            if not self.redis:
                logging.error("Redis client not initialized")
                print("Redis client not initialized")
                return []
            
            # Get all keys matching the pattern
            pattern = f"conversation:*"
            keys = await self.redis.keys(pattern)
            
            # Get each conversation state
            for key in keys[:limit * 2]:  # Get more than needed to filter
                try:
                    data = await self.redis.get(key)
                    if data:
                        state = ConversationState.parse_raw(data)
                        
                        # Filter by tenant and user
                        if state.tenant_id == tenant_id and state.user_id == user_id:
                            # Add basic info
                            conversations.append({
                                "conversation_id": state.conversation_id,
                                "user_id": state.user_id,
                                "current_agent_id": state.current_agent_id,
                                "message_count": len(state.history),
                                "last_updated": state.last_updated,
                                # Add summary if available
                                "summary": state.metadata.get("last_summary", {}).get("brief", None)
                            })
                            
                            if len(conversations) >= limit:
                                break
                except Exception as e:
                    logging.warning(f"Error parsing conversation state for key {key}: {e}")
                    continue
        except Exception as e:
            logging.error(f"Error listing conversations: {e}")
        
        # Sort by last updated (most recent first)
        conversations.sort(key=lambda x: x.get("last_updated", 0), reverse=True)
        
        return conversations[:limit]
    
    async def _archive_conversation(self, state: ConversationState) -> None:
        """
        Arquiva uma conversa para armazenamento persistente no PostgreSQL.
        
        Args:
            state: O estado da conversa a ser arquivado
        """
        try:
            from app.db.models.archived_conversation import ArchivedConversation
            from app.db.session import SessionLocal
            
            # Criar uma sessão do banco de dados
            db = SessionLocal()
            
            try:
                # Criar o objeto do modelo
                archived_conversation = ArchivedConversation(
                    conversation_id=state.conversation_id,
                    tenant_id=state.tenant_id,
                    user_id=state.user_id,
                    history=state.history,  # PostgreSQL JSONB pode armazenar diretamente
                    meta_data=state.metadata,  # PostgreSQL JSONB pode armazenar diretamente
                    message_count=len(state.history),
                    archive_reason=state.metadata.get("archive_reason", "unknown"),
                    archived_at=datetime.utcnow()
                )
                
                # Adicionar e salvar no banco de dados
                db.add(archived_conversation)
                db.commit()
                
                logger.info(f"Conversa {state.conversation_id} arquivada com sucesso no banco de dados")
                print(f"Conversa {state.conversation_id} arquivada com sucesso no banco de dados")
            finally:
                db.close()
                
        except Exception as e:
            print(f"Erro ao arquivar conversa {state.conversation_id}: {e}")
            logger.error(f"Falha ao arquivar conversa {state.conversation_id}: {e}")
            logger.exception(e)  # Registra o stack trace completo
            # Continuar com o fluxo mesmo se o arquivamento falhar
            
    async def map_user_to_conversation(self, tenant_id: str, user_id: str, conversation_id: str) -> None:
        """
        Mapeia um usuário para sua conversa atual com um TTL mais longo que a própria conversa.
        
        Args:
            tenant_id: O ID do tenant
            user_id: O ID do usuário (normalmente um JID do WhatsApp)
            conversation_id: O ID da conversa
        """
        if not self.redis:
            return
            
        mapping_key = f"user_conversation_map:{tenant_id}:{user_id}"
        await self.redis.set(mapping_key, conversation_id)
        # Usar um TTL muito mais longo para este mapeamento (7 dias)
        await self.redis.expire(mapping_key, 60 * 60 * 24 * 7)
        
    async def get_user_conversation_id(self, tenant_id: str, user_id: str) -> Optional[str]:
        """
        Obtém o ID da conversa atual para um usuário.
        
        Args:
            tenant_id: O ID do tenant
            user_id: O ID do usuário
            
        Returns:
            O ID da conversa ou None se não encontrado
        """
        if not self.redis:
            return None
            
        mapping_key = f"user_conversation_map:{tenant_id}:{user_id}" 
        data = await self.redis.get(mapping_key)
        
        if data:
            if isinstance(data, bytes):
                return data.decode('utf-8')
            return data
        return None

