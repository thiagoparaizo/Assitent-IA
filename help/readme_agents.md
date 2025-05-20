# Documentação do Sistema de Agentes Inteligentes

## Visão Geral

O sistema de agentes é um componente central da aplicação, responsável por gerenciar assistentes virtuais inteligentes que podem interagir com usuários via diferentes canais (principalmente WhatsApp). A arquitetura de agentes é flexível, permitindo diferentes tipos de agentes com variadas especialidades, capacidades de integração e lógicas de escalação.

## Principais Componentes do Sistema de Agentes

### 1. Modelos de Dados

### 1.1 Modelo de Agente (Agent)

O modelo `Agent` (em `app/db/models/agent.py`) define a estrutura de dados fundamental para armazenar agentes no banco de dados:

```python

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
    escalation_enabled = Column(Boolean, default=False)
    list_escalation_agent_ids = Column(ARRAY(UUID(as_uuid=True)), nullable=True)
    human_escalation_enabled = Column(Boolean, default=False)
    human_escalation_contact = Column(String, nullable=True)
    active = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

```

### 1.2 Esquemas de Agente (Agent Schema)

O arquivo `app/schemas/agent.py` define os esquemas Pydantic para validação e serialização de dados de agentes:

```python

class AgentType(str, Enum):
    GENERAL = "general"# Assistente principal para clientes
    SPECIALIST = "specialist"# Agente especialista interno
    INTEGRATION = "integration"# Agente para integrações externas (MCP)
    HUMAN = "human"# Representação de agente humano
    PERSONAL = "personal"# Agente pessoal que se passa por um humano

class AgentPromptBase(BaseModel):
    role: str
    description: str
    instructions: str
    examples: Optional[List[Dict[str, str]]] = None
    constraints: Optional[List[str]] = None

class Agent(AgentBase):
    id: str
    created_at: datetime
    updated_at: datetime

    def generate_system_prompt(self) -> str:
        """Gera o prompt de sistema completo para o agente."""
# Método que constrói o prompt do sistema a partir dos componentes

```

### 2. Serviços de Agentes

### 2.1 AgentService

O `AgentService` (`app/services/agent.py`) é o componente principal que gerencia operações CRUD e lógica de negócios para agentes:

```python

class AgentService:
    """Serviço para gerenciamento de agentes."""

    def __init__(self, db_session: AsyncSession, redis_client):
        self.db = db_session
        self.redis = redis_client

    def create_agent(self, agent_data: Dict[str, Any]) -> Agent:
        """Cria um novo agente."""

    def get_agent(self, agent_id: str) -> Optional[Agent]:
        """Obtém um agente pelo ID."""

    def get_agents_by_tenant(self, tenant_id: str) -> List[Agent]:
        """Obtém todos os agentes de um tenant."""

    def get_agents_by_tenant_and_relationship_with_current_agent(self, tenant_id: str, current_agent_id: str) -> List[Agent]:
        """Obtém agentes relacionados ao agente atual para escalação."""

    def update_agent(self, agent_id: str, agent_data: Dict[str, Any]) -> Optional[Agent]:
        """Atualiza um agente existente."""

    def delete_agent(self, agent_id: str) -> bool:
        """Remove um agente."""

    def update_agent_status(self, agent_id: str, active: bool) -> bool:
        """Atualiza o status de um agente."""

    async def get_agent_for_device(self, device_id: int, tenant_id: str) -> Optional[Agent]:
        """Obtém o agente ativo para um dispositivo específico."""

    async def get_agent_for_contact(self, device_id: int, tenant_id: str, contact_id: str):
        """Determina qual agente deve responder a um contato específico em um dispositivo."""

```

### 2.2 Orquestração de Agentes (AgentOrchestrator)

O `AgentOrchestrator` (`app/services/orchestrator.py`) gerencia o fluxo de conversas entre usuários e agentes:

```python

class AgentOrchestrator:
    """Orquestrador para gerenciar a comunicação entre agentes."""

    def __init__(self, agent_service, rag_service, redis_client, llm_service, config: SystemConfig = None):
        self.agent_service = agent_service
        self.rag_service = rag_service
        self.redis = redis_client
        self.llm = llm_service
        self.config = config or load_system_config()
        self.memory_service = MemoryService(...) if self.config.memory.enabled else None

    async def start_conversation(self, tenant_id: str, user_id: str, agent_id: Optional[str] = None) -> str:
        """Inicia uma nova conversa."""

    async def process_message(self, conversation_id: str, message: str, agent_id: str, contact_id: str) -> Dict[str, Any]:
        """Processa uma mensagem dentro de uma conversa."""

    async def evaluate_agent_transfer(self, state: ConversationState, message: str) -> List[AgentScore]:
        """Avalia se a conversa deve ser transferida para um agente diferente."""

```

### 3. APIs para Gerenciamento de Agentes

### 3.1 Endpoints de Agentes

O módulo `app/api/endpoints/agents.py` define as APIs RESTful para gerenciamento de agentes:

```python

@router.post("/", response_model=schemas.Agent)
async def create_agent(...)

@router.get("/list", response_model=List[schemas.Agent])
async def list_agents(...)

@router.get("/{agent_id}", response_model=schemas.Agent)
async def get_agent(...)

@router.put("/{agent_id}", response_model=schemas.AgentUpdate)
async def update_agent(...)

@router.put("/{agent_id}/status")
async def update_agent_status(...)

@router.delete("/{agent_id}")
async def delete_agent(...)

```

### 3.2 Interface de Administração Web

O módulo `admin/views/agents.py` define as rotas para a interface web de administração de agentes:

```python

@agents_bp.route('/')
@login_required
def index()# Lista agentes

@agents_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create()# Formulário para criar agente

@agents_bp.route('/<agent_id>')
@login_required
def view(agent_id)# Ver detalhes de um agente

@agents_bp.route('/<agent_id>/edit', methods=['GET', 'POST'])
@login_required
def edit(agent_id)# Editar um agente

```

## Detalhamento das Funcionalidades

### 1. Tipos de Agentes

O sistema define vários tipos de agentes, cada um com propósito específico:

1. **GENERAL**: Assistente principal para atendimento geral de clientes
2. **SPECIALIST**: Agente especialista em áreas específicas
3. **INTEGRATION**: Agente para integração com sistemas externos (MCP)
4. **HUMAN**: Representação de atendente humano no sistema
5. **PERSONAL**: Agente pessoal que se comporta como uma pessoa

### 2. Estrutura de Prompts

Os prompts dos agentes têm uma estrutura definida:

### 2.1 Componentes do Prompt

- **Role**: Define o papel/persona do agente
- **Description**: Descrição geral do agente e sua função
- **Instructions**: Instruções detalhadas sobre como o agente deve se comportar
- **Constraints**: Limitações ou restrições que o agente deve seguir
- **Examples**: Exemplos de interações para guiar o comportamento do agente

### 2.2 Geração de Prompt para Sistema

```python

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

# Adiciona instruções específicas baseadas nas capacidades do agente
    if self.human_escalation_enabled:
        prompt += "### Escalação para Atendente Humano:\n"
        prompt += "Quando um cliente solicitar falar com um atendente humano..."

    if self.mcp_enabled:
        prompt += "### Execução de Funções Externas:\n"
        prompt += "Para executar funções externas, use: <comando>EXECUTAR_MCP:{...}</comando>..."

    return prompt

```

### 3. Especialidades de Agentes

Os agentes podem ter especialidades definidas, que são utilizadas para determinar qual agente é mais adequado para lidar com uma consulta:

```python

def _get_agent_specialties(self, agent) -> Dict[str, float]:
    """
    Extract agent specialties from its configuration.

    Returns:
        Dictionary mapping categories to specialty scores
    """
# Base specialties
    specialties = {
        "appointment": 0.0,
        "product_info": 0.0,
        "technical_issue": 0.0,
        "billing": 0.0,
        "complaint": 0.0,
        "general": 0.0,
        "healthcare": 0.0,
        "retail": 0.0,
        "order_tracking": 0.0,
# ... mais categorias
    }

# Extrair especialidades do nome e descrição
    agent_text = f"{agent.name} {agent.description}".lower()

# Dicionário de palavras-chave por especialidade
    specialty_keywords = {
        "appointment": ["appointment", "schedule", "booking", "calendar", ...],
        "healthcare": ["saúde", "médico", "clínica", "hospital", ...],
# ... mais categorias
    }

# Calcular pontuação para cada especialidade
    for category, keywords in specialty_keywords.items():
        for keyword in keywords:
            if keyword in agent_text:
                specialties[category] += 0.3

# Limitar pontuações a 1.0
    for category in specialties:
        specialties[category] = min(specialties[category], 1.0)

    return specialties

```

### 4. Controle de Contatos

Os agentes podem ser configurados para responder apenas a certos contatos (whitelist) ou responder a todos exceto alguns (blacklist):

```python

class ContactListType(enum.Enum):
    WHITELIST = "whitelist"# Apenas responde a contatos nesta lista
    BLACKLIST = "blacklist"# Responde a todos exceto contatos nesta lista

class ContactControl(Base):
    __tablename__ = "agent_contact_controls"

    id = Column(Integer, primary_key=True, index=True)
    agent_id = Column(UUID(as_uuid=True), ForeignKey("agents.id"), nullable=False)
    device_id = Column(Integer, nullable=False)# Manteremos também qual dispositivo
    contact_id = Column(String, nullable=False)# ID do contato (JID/chat_id)
    list_type = Column(Enum(ContactListType), nullable=False)

```

A lógica para determinar qual agente deve responder a um contato é implementada em:

```python

async def get_agent_for_contact(self, device_id: int, tenant_id: str, contact_id: str):
    """
    Determina qual agente deve responder a um contato específico em um dispositivo.
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
            should_response = contact_id in whitelist
        elif blacklist:
# Se existe uma blacklist, o contato NÃO deve estar nela
            should_response = contact_id not in blacklist
        else:
# Se não há listas, o agente responde a todos
            should_response = True
            return self.get_agent(agent_id), should_response

    return self.get_agent(agent_id), should_response

```

### 5. Escalação de Agentes

O sistema suporta dois tipos de escalação:

### 5.1 Escalação para Outro Agente Especialista

```python

# Avalia agentes para possível transferência
async def evaluate_agent_transfer(self, state: ConversationState, message: str) -> List[AgentScore]:
    """
    Avalia se a conversa deve ser transferida para um agente diferente.

    Returns:
        Lista de pontuações de agentes ordenada por relevância
    """
# Obter configuração de transferência
    transfer_config = self.config.agent_transfer

# Verificar se transferências estão habilitadas
    if not transfer_config.enabled:
# Retornar apenas o agente atual com pontuação máxima
        current_agent = self.agent_service.get_agent(state.current_agent_id)
        return [AgentScore(
            agent_id=current_agent.id,
            score=1.0,
            reason="Agent transfers disabled"
        )]

# ... (verificações adicionais)

# Calcular pontuação para cada agente
    for agent in all_agents:
# Calcular pontuação base para este agente
        score, reason = await self._calculate_agent_score(
            agent,
            message,
            conversation_focus,
            recent_messages
        )

# ... (ajustes na pontuação)

        agent_scores.append(AgentScore(
            agent_id=agent.id,
            score=score,
            reason=reason
        ))

# Ordenar por pontuação (maior primeiro)
    result = sorted(agent_scores, key=lambda x: x.score, reverse=True)

    return result

```

### 5.2 Escalação para Humano

O sistema identifica solicitações de escalação para humano nas mensagens do usuário:

```python

# Verificar automaticamente se a mensagem do usuário indica necessidade de escalação
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

```

A escalação para humano é implementada através de comandos especiais no texto de resposta do agente:

```python

async def _process_agent_response(self, response: str, state: ConversationState, current_agent: Agent, config: SystemConfig) -> Dict[str, Any]:
    """
    Processa a resposta do agente para identificar ações.
    """
# Padrão para capturar comandos
    comando_pattern = r'<comando>.*?</comando>'
# Encontrar comandos
    comandos = re.findall(r'<comando>(.*?)</comando>', response, flags=re.DOTALL)
# Remover comandos da resposta visível
    resposta_limpa = re.sub(comando_pattern, '', response, flags=re.DOTALL).strip()

    result = {
        "response": resposta_limpa,
        "next_agent_id": current_agent.id,
        "actions": []
    }

# Processar cada comando
    for comando in comandos:
        if "ESCALAR_PARA_HUMANO" in comando and config.enable_escalation_to_human:
# Verificar se o agente suporta escalação
            escalation_available = False
            escalation_contact = None

            if current_agent.human_escalation_enabled and current_agent.human_escalation_contact:
                escalation_available = True
                escalation_contact = current_agent.human_escalation_contact
            else:
# Buscar agentes humanos
                agents = await self.agent_service.get_agents_by_tenant(state.tenant_id)
                human_agents = [a for a in agents if a.type == AgentType.HUMAN]

                if human_agents:
                    escalation_available = True
                    result["next_agent_id"] = human_agents[0].id
                    escalation_contact = human_agents[0].human_escalation_contact

            if escalation_available and escalation_contact:
# Criar ação de escalação
                result["actions"].append({
                    "type": "human_escalation",
                    "contact": escalation_contact,
                    "conversation_id": state.conversation_id,
                    "conversation_summary": await self._generate_escalation_summary(state)
                })

```

### 6. Integração com Dispositivos WhatsApp

Os agentes são atribuídos a dispositivos WhatsApp:

```python

class DeviceAgent(Base):
    __tablename__ = "device_agent_mappings"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(Integer, nullable=False)
    agent_id = Column(UUID(as_uuid=True), ForeignKey("agents.id"), nullable=False)
    is_active = Column(Boolean, default=True)

```

A lógica para atribuir agentes a dispositivos:

```python

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

```

### 7. Processamento de Mensagens do WhatsApp

O fluxo de processamento de mensagens do WhatsApp:

```python

async def process_whatsapp_message(data: Dict[str, Any], whatsapp_service: WhatsAppService, db: Session):
    """
    Processa mensagens recebidas do WhatsApp usando o sistema de agentes inteligentes.
    """
    try:
# Extrair informações da mensagem
        device_id = data.get("device_id")
        tenant_id = data.get("tenant_id")

        sender = data.get("event", {}).get("Info", {}).get("Sender", {})
        if 'User' in sender:
            sender = sender['User']
        chat_jid = data.get("event", {}).get("Info", {}).get("Chat")

# O contact_id pode ser o ID do remetente ou do chat, dependendo se é grupo ou não
        is_group = data.get("event", {}).get("Info", {}).get("IsGroup", False)
        contact_id = chat_jid if is_group else sender

# ... (processamento adicional)

# Converter para objeto Agent
        agent_service = AgentService(db, None)
        agent, should_response = await agent_service.get_agent_for_contact(device_id, tenant_id, contact_id)

# ... (verificações e preparação)

# Inicializar serviços
        llm_service = await get_llm_service(db, str(tenant_id))
        rag_service = RAGServiceFAISS(tenant_id=tenant_id)

# Configuração do sistema
        config = load_system_config()

# Inicializar orquestrador
        orchestrator = AgentOrchestrator(agent_service, rag_service, redis_client, llm_service, config)

# Verificar se já existe uma conversa para este usuário
        conversation_key = f"whatsapp_conversation:{tenant_id}:{chat_jid}"
        conversation_id = await redis_client.get(conversation_key) if redis_client else None

# ... (mapeamento e processamento)

# Processar a mensagem usando o orquestrador
        result = await orchestrator.process_message(conversation_id, message_content, agent_id=agent.id, contact_id=contact_id)

# Enviar resposta via WhatsApp
        if "response" in result:
            await whatsapp_service.send_message(
                device_id=device_id,
                to=chat_jid,
                message=result["response"]
            )

# Processar ações especiais, como escalação para humano
        if "actions" in result:
            for action in result["actions"]:
                if action["type"] == "human_escalation":
# ... (processo de escalação)

```

### 8. Integração com Retrieval-Augmented Generation (RAG)

Os agentes podem ser configurados para usar categorias específicas de conhecimento (RAG):

```python

# Retrieve RAG context based on agent settings and config
rag_context = []
if tenant_config.rag.enabled and current_agent.rag_categories:
# Limitar o número de categorias a pesquisar
    categories_to_search = current_agent.rag_categories[:tenant_config.rag.categories_hard_limit]

    for category in categories_to_search:
        docs = await self.rag_service.search(
            message,
            category=category,
            limit=tenant_config.rag.default_limit
        )

# Filtrar por limite de relevância
        relevant_docs = [doc for doc in docs if doc.get("relevance_score", 0) >= tenant_config.rag.min_relevance_score]
        rag_context.extend(relevant_docs)

```

### 9. Multi-tenancy

O sistema suporta múltiplos tenants (clientes/organizações), com agentes específicos para cada tenant:

```python

def get_agents_by_tenant(self, tenant_id: str) -> List[Agent]:
    """Obtém todos os agentes de um tenant."""
# Buscar no banco de dados
    query = select(AgentModel).where(AgentModel.tenant_id == int(tenant_id))
    result = self.db.execute(query)
    db_agents = result.scalars().all()

# Converter para schema
    return [self._db_to_schema(db_agent) for db_agent in db_agents]

```

## Funcionalidades Avançadas

### 1. Suporte a MCP (Model Context Protocol)

Os agentes podem ser configurados para executar funções externas através do sistema MCP:

```python

elif "EXECUTAR_MCP:" in comando and config.mcp.enabled and current_agent.mcp_enabled:
# Check for MCP function calls# Extract function calls (may be multiple)
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
        logging.info(f"Processing function call {i+1}/{max_calls}: {function_call.get('name')}")

        result["actions"].append({
            "type": "mcp_function",
            "function": function_call,
            "requires_approval": config.mcp.functions_require_approval
        })

```

### 2. Sistema de Memória

O sistema pode manter memória de interações anteriores com usuários:

```python

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
    except Exception as e:
        logging.error(f"Error retrieving memories: {e}")

```

### 3. Geração de Resumos de Conversa

O sistema pode gerar resumos de conversas para facilitar a escalação:

```python

async def _generate_escalation_summary(self, state: ConversationState) -> str:
    """
    Gera um resumo da conversa para escalação humana.
    """
# Obter as últimas mensagens
    recent_messages = state.history[-10:] if len(state.history) >= 10 else state.history[:]

# Filtrar apenas mensagens de usuário e assistente
    filtered_messages = [
        msg for msg in recent_messages
        if msg.get("role") in ["user", "assistant"]
    ]

# Formatar mensagens
    formatted_messages = []
    for msg in filtered_messages:
        timestamp = datetime.fromtimestamp(msg.get("timestamp", 0)).strftime("%H:%M:%S")
        role = "User" if msg.get("role") == "user" else "Assistant"
        content = msg.get("content", "")
        formatted_messages.append(f"[{timestamp}] {role}: {content}")

# Verificar se há resumo recente nos metadados
    if "last_summary" in state.metadata:
        summary = f"Resumo da Conversa: {state.metadata['last_summary'].get('brief', '')}\n\n"
    else:
        summary = "Conversa recente:\n\n"

# Adicionar mensagens recentes
    summary += "\n".join(formatted_messages)

    return summary

```

## Fluxo Completo de Processamento de Mensagens

1. Uma mensagem do WhatsApp é recebida via webhook
2. O sistema determina o dispositivo e tenant associados
3. O agente apropriado é selecionado baseado em:
    - Mapeamento de dispositivo-agente
    - Configurações de whitelist/blacklist de contatos
4. Um ID de conversa é recuperado ou criado
5. O orquestrador processa a mensagem, incluindo:
    - Verificação de limites de conversa
    - Recuperação de contexto de RAG
    - Recuperação de memória relevante
    - Avaliação de possível transferência para outro agente
    - Geração de resposta usando o LLM
    - Processamento de comandos especiais (escalação, MCP)
6. A resposta é enviada de volta para o WhatsApp
7. Ações adicionais são executadas conforme necessário (escalação para humano, chamadas de função, etc.)
8. Os estados da conversa são atualizados no Redis
9. Opcionalmente, um resumo da conversa é gerado e armazenado
10. Quando a conversa excede limites ou expira, ela é arquivada no banco de dados PostgreSQL

## Gerenciamento de Agentes via Interface Administrativa

A interface web administrativa permite gerenciar todos os aspectos dos agentes:

### 1. Listagem de Agentes

```python

@agents_bp.route('/')
@login_required
def index():
# Obter lista de agentes via API
    try:
        response = requests.get(
            f"{Config.API_URL}/agents/",
            headers=get_api_headers()
        )
        response.raise_for_status()
        agents = response.json()
    except requests.exceptions.RequestException as e:
        flash(f"Erro ao obter agentes: {e}", "danger")
        agents = []

    return render_template('agents/index.html', agents=agents)

```

### 2. Criação de Agentes

```python

@agents_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    if request.method == 'POST':
# Obter dados do formulário
        agent_data = {
            'name': request.form.get('name'),
            'type': request.form.get('type'),
            'description': request.form.get('description'),
            'prompt': {
                'role': request.form.get('prompt_role'),
                'description': request.form.get('prompt_description'),
                'instructions': request.form.get('prompt_instructions'),
                'constraints': request.form.get('prompt_constraints', '').splitlines(),
                'examples': json.loads(request.form.get('prompt_examples', '[]'))
            },
            'rag_categories': request.form.getlist('rag_categories'),
            'mcp_enabled': 'mcp_enabled' in request.form,
            'mcp_functions': json.loads(request.form.get('mcp_functions', '[]')),
            'human_escalation_enabled': 'human_escalation_enabled' in request.form,
            'human_escalation_contact': request.form.get('human_escalation_contact')
        }

# Enviar para API
        try:
            response = requests.post(
                f"{Config.API_URL}/agents/",
                headers=get_api_headers(),
                json=agent_data,
                timeout=10
            )
            response.raise_for_status()
            flash("Agente criado com sucesso!", "success")
            return redirect(url_for('agents.index'))
        except requests.exceptions.HTTPError as e:
# [Tratamento de erro]

```

### 3. Edição de Agentes

```python

@agents_bp.route('/<agent_id>/edit', methods=['GET', 'POST'])
@login_required
def edit(agent_id):
    if request.method == 'POST':
# Obter dados do formulário
        agent_data = {
            'name': request.form.get('name'),
            'description': request.form.get('description'),
            'prompt': {
                'role': request.form.get('prompt_role'),
                'description': request.form.get('prompt_description'),
                'instructions': request.form.get('prompt_instructions'),
                'constraints': request.form.get('prompt_constraints', '').splitlines(),
                'examples': json.loads(request.form.get('prompt_examples', '[]'))
            },
            'rag_categories': request.form.getlist('rag_categories'),
            'mcp_enabled': 'mcp_enabled' in request.form,
            'mcp_functions': json.loads(request.form.get('mcp_functions', '[]')),
            'human_escalation_enabled': 'human_escalation_enabled' in request.form,
            'human_escalation_contact': request.form.get('human_escalation_contact'),
            'active': 'active' in request.form,
            'specialties': request.form.getlist('specialties'),
            'escalation_enabled': 'escalation_enabled' in request.form,
            'list_escalation_agent_ids': request.form.getlist('escalation_agent_ids'),
        }

# Enviar para API
        try:
            response = requests.put(
                f"{Config.API_URL}/agents/{agent_id}",
                headers=get_api_headers(),
                json=agent_data,
                timeout=10
            )
            response.raise_for_status()

            flash("Agente atualizado com sucesso!", "success")
            return redirect(url_for('agents.view', agent_id=agent_id))
        except requests.exceptions.HTTPError as e:
# [Tratamento de erro]

```

### 4. Gerenciamento de Configurações de Contato

```python

@agents_bp.route('/<agent_id>/device/<int:device_id>/contacts', methods=['POST'])
@login_required
def manage_contacts(agent_id, device_id):
    """Gerenciar contatos para um dispositivo."""
    try:
        data = request.json
        behavior = data.get('default_behavior')
        contacts = data.get('contacts', [])

        response = requests.post(
            f"{Config.API_URL}/agents/{agent_id}/device/{device_id}/contacts",
            headers=get_api_headers(),
            json={"default_behavior": behavior, "contacts": contacts},
            timeout=10
        )
        response.raise_for_status()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

```

## Detalhamento das Relações entre Componentes

### 1. Relação entre Agentes e Tenants

Cada agente é associado a um tenant específico. A estrutura multi-tenant permite que diferentes organizações (tenants) tenham seus próprios conjuntos de agentes:

```python

class Agent(Base):
# ...
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
# ...
    tenant = relationship("Tenant", back_populates="agents")

```

```python

class Tenant(Base):
# ...
    agents = relationship("Agent", back_populates="tenant", cascade="all, delete-orphan")

```

### 2. Relação entre Agentes e Dispositivos WhatsApp

Existe uma relação muitos-para-muitos entre agentes e dispositivos WhatsApp, gerenciada pela tabela `device_agent_mappings`:

```python

class DeviceAgent(Base):
    __tablename__ = "device_agent_mappings"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(Integer, nullable=False)
    agent_id = Column(UUID(as_uuid=True), ForeignKey("agents.id"), nullable=False)
    is_active = Column(Boolean, default=True)

# Relacionamento com o agente
    agent = relationship("Agent", back_populates="device_mappings")

class Agent(Base):
# ...
    device_mappings = relationship("DeviceAgent", back_populates="agent", cascade="all, delete-orphan")

```

### 3. Relação entre Agentes e Controle de Contatos

Os agentes têm relação com controles de contato que definem whitelist/blacklist de contatos:

```python

class ContactControl(Base):
# ...
    agent_id = Column(UUID(as_uuid=True), ForeignKey("agents.id"), nullable=False)
# ...
    agent = relationship("Agent", back_populates="contact_controls")

class Agent(Base):
# ...
    contact_controls = relationship("ContactControl", back_populates="agent", cascade="all, delete-orphan")

```

### 4. Relação entre Agentes e o Sistema LLM

Os agentes não têm uma relação direta definida no banco de dados com modelos LLM, mas o sistema utiliza a configuração de tenant para determinar qual modelo LLM usar para um agente:

```python

# Obter configurações do tenant (se especificado)
if tenant_id:
    try:
        tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
        if tenant:
# Usar configurações específicas do tenant
            if tenant.default_llm_model_id:
                model = db.query(LLMModel).filter(LLMModel.id == tenant.default_llm_model_id).first()
                provider = model.provider if model else None
            elif tenant.default_llm_provider_id:
                provider = db.query(LLMProvider).filter(LLMProvider.id == tenant.default_llm_provider_id).first()
                model = db.query(LLMModel).filter(
                    LLMModel.provider_id == provider.id,
                    LLMModel.is_active == True
                ).first() if provider else None

```

### 5. Relação entre Agentes e Categorias RAG

Cada agente pode ter várias categorias RAG associadas, que são usadas para buscar contexto relevante:

```python

class Agent(Base):
# ...
    rag_categories = Column(Text, nullable=True)# JSON string de categorias

```

```python

# Retrieve RAG context based on agent settings and config
rag_context = []
if tenant_config.rag.enabled and current_agent.rag_categories:
# Limitar o número de categorias a pesquisar
    categories_to_search = current_agent.rag_categories[:tenant_config.rag.categories_hard_limit]

    for category in categories_to_search:
        docs = await self.rag_service.search(
            message,
            category=category,
            limit=tenant_config.rag.default_limit
        )

```

## Configurações Avançadas de Agentes

### 1. Configuração de Sistema

O sistema utiliza um arquivo de configuração centralizado que define comportamentos globais para todos os agentes:

```python

class SystemConfig(BaseModel):
    """Main configuration for the agent system."""
    agent_transfer: AgentTransferConfig = AgentTransferConfig()
    memory: MemoryConfig = MemoryConfig()
    rag: RAGConfig = RAGConfig()
    mcp: MCPConfig = MCPConfig()
    logging: LoggingConfig = LoggingConfig()

# Additional system-wide settings
    default_tenant_id: Optional[str] = None
    default_agent_id: Optional[str] = None
    max_conversation_length: int = 100
    conversation_timeout_minutes: int = 60
    enable_escalation_to_human: bool = True

```

### 2. Configurações Específicas de Tenant

As configurações podem ser sobrescritas por tenant:

```python

def apply_tenant_overrides(self, tenant_id: str) -> 'SystemConfig':
    """Create a new config with tenant-specific overrides applied."""
    tenant_config = self.get_tenant_config(tenant_id)
    if not tenant_config:
        return self

# Create a copy of this config
    new_config = SystemConfig.parse_obj(self.dict())

# Apply tenant overrides
    for key, value in tenant_config.items():
        if key in new_config.__dict__ and isinstance(value, dict):
# Update nested config
            nested_config = getattr(new_config, key)
            for nested_key, nested_value in value.items():
                if nested_key in nested_config.__dict__:
                    setattr(nested_config, nested_key, nested_value)
        elif key in new_config.__dict__:
            setattr(new_config, key, value)

    return new_config

```

## Melhores Práticas para Construção de Agentes

Com base na análise do código, as seguintes melhores práticas podem ser identificadas para construção de agentes eficazes:

### 1. Construção de Prompts Eficazes

1. **Definição clara do papel (role)**: Um prompt de sistema deve começar com uma definição clara e concisa do papel do agente.
2. **Descrição detalhada**: Inclua uma descrição que forneça contexto sobre quem é o agente e qual sua função.
3. **Instruções específicas**: Forneça instruções detalhadas e bem estruturadas sobre como o agente deve se comportar e responder.
4. **Restrições explícitas**: Defina claramente quaisquer limitações ou restrições que o agente deve seguir.
5. **Exemplos concretos**: Inclua exemplos de interações modelo para orientar o comportamento do agente.

Exemplo de estrutura:

```

# Assistente de Atendimento Médico

Você é um assistente virtual especializado em agendamentos e orientações para uma clínica médica. Seu objetivo é fornecer informações precisas, agendar consultas e orientar pacientes sobre procedimentos.

## Instruções:
1. Seja sempre cortês e professional, usando linguagem acessível.
2. Ao agendar consultas, solicite nome completo, data de nascimento e informações de contato.
3. Explique procedimentos médicos em termos simples, evitando jargão técnico.
4. Quando não souber uma resposta, indique que precisará consultar a equipe médica.
5. Priorize emergências e encaminhe casos urgentes para o contato imediato da clínica.

## Restrições:
- Nunca forneça diagnósticos médicos ou prescrições.
- Não compartilhe informações confidenciais sobre outros pacientes.
- Não faça promessas de resultados ou garantias de tratamentos.
- Sempre respeite a privacidade do paciente.

## Exemplos:
### Exemplo 1:
**Usuário**: Preciso marcar uma consulta para amanhã com o Dr. Silva.
**Resposta**: Entendo que você gostaria de agendar uma consulta com o Dr. Silva para amanhã. Infelizmente, a agenda dele está completa para amanhã. Posso verificar a disponibilidade para depois de amanhã ou ainda esta semana. Qual seria sua preferência de horário?

```

### 2. Definição de Especialidades

Para criar um agente especializado eficaz:

1. Escolha um conjunto focado de especialidades relacionadas
2. Use palavras-chave específicas da área no nome e descrição do agente
3. Configure categorias RAG alinhadas com as especialidades

Por exemplo, para um agente especialista em saúde:

- Especialidades: "healthcare", "medical_exams", "health_insurance"
- Palavras-chave no nome/descrição: "médico", "clínica", "saúde", "consulta", "tratamento"
- Categorias RAG: "medical_knowledge", "procedures", "insurance_plans"

### 3. Configuração de Escalação

Para configurar escalação eficaz:

1. **Escalonamento para especialistas**:
    - Habilite `escalation_enabled` para o agente primário
    - Configure `list_escalation_agent_ids` com IDs de agentes especialistas
2. **Escalonamento para humanos**:
    - Habilite `human_escalation_enabled` para permitir escalação
    - Configure `human_escalation_contact` com o contato WhatsApp do atendente humano
    - Implemente comandos de escalação nos prompts do agente

## Otimização de Desempenho

### 1. Balanceamento de Carga

O sistema permite atribuir diferentes agentes a diferentes dispositivos WhatsApp, o que pode ser usado para balancear carga:

```python

def assign_agent_to_device(self, agent_id: str, device_id: int) -> bool:
    """Atribui um agente a um dispositivo específico."""
# Verificar se o agente existe
    agent = self.get_agent(agent_id)
    if not agent:
        return False

# Desativar mapeamentos ativos existentes para este dispositivo# ...

# Criar novo mapeamento
    new_mapping = DeviceAgent(
        device_id=device_id,
        agent_id=agent_id,
        is_active=True
    )

    self.db.add(new_mapping)
    self.db.commit()
    return True

```

### 2. Uso Eficiente de RAG

O código implementa estratégias para uso eficiente de RAG:

1. Limitar o número de categorias RAG pesquisadas:

```python

categories_to_search = current_agent.rag_categories[:tenant_config.rag.categories_hard_limit]

```

1. Filtrar documentos por limite de relevância:

```python

relevant_docs = [doc for doc in docs if doc.get("relevance_score", 0) >= tenant_config.rag.min_relevance_score]

```

1. Configurar limites por tenant:

```python

self.rag.default_limit = 5# Número máximo de documentos por categoria
self.rag.min_relevance_score = 0.7# Pontuação mínima de relevância
self.rag.categories_hard_limit = 3# Limite máximo de categorias por consulta

```

## Conclusão

O sistema de agentes na aplicação é uma implementação sofisticada e modular que permite:

1. **Flexibilidade em tipos de agentes**: Desde assistentes gerais até especialistas e representações de humanos
2. **Personalização por tenant**: Cada cliente/organização pode ter seus próprios agentes configurados
3. **Integração com WhatsApp**: Atribuição dinâmica de agentes a dispositivos e contatos
4. **Transferência inteligente**: Capacidade de transferir conversas entre agentes com base na relevância
5. **Escalação para humanos**: Detecção de necessidade de intervenção humana e encaminhamento
6. **Acesso a conhecimento**: Integração com sistema RAG para fornecer contexto relevante
7. **Memória de conversas**: Armazenamento e recuperação de informações de conversas anteriores
8. **Funções externas**: Capacidade de executar ações em sistemas externos via MCP

A arquitetura do sistema é bem estruturada, seguindo padrões de desenvolvimento modernos como:

- Separação clara entre modelos, esquemas e serviços
- Uso de injeção de dependência para componentes
- Configuração centralizada e sobrescritível por tenant
- Interface administrativa abrangente para gerenciamento
- Persistência em banco de dados relacional e cache Redis

Esta implementação fornece uma base sólida para desenvolver assistentes virtuais sofisticados que podem atender a uma ampla variedade de casos de uso, desde atendimento ao cliente até suporte técnico especializado.
