# Arquitetura de Memória do Sistema Assistente Inteligente

### Introdução

A memória é um componente crítico que permite ao sistema reter informações de conversas anteriores, aprender com interações passadas e fornecer respostas mais contextualizadas e personalizadas aos usuários.

A implementação da memória no sistema vai além de simplesmente armazenar o histórico de conversas. Ela envolve o processamento semântico de informações, extração de conhecimento útil, categorização e recuperação contextual quando relevante para a conversa atual.

## Arquitetura do Sistema de Memória

### Arquivos Principais

Os componentes essenciais do sistema de memória estão distribuídos nos seguintes arquivos:

1. **`app/services/memory.py`**: Define o serviço principal de memória e suas estruturas de dados
2. **`app/services/config.py`**: Contém configurações relacionadas à memória
3. **`app/services/orchestrator.py`**: Integra a memória com o fluxo de conversação
4. **`app/services/rag_faiss.py`**: Implementa a recuperação baseada em embeddings (usado pela memória)

### Classes Principais

### 1. `MemoryType` (Enum em `memory.py`)

Define os tipos de entradas de memória:

```python
class MemoryType(str, Enum):
    """Types of memory entries."""
    CONVERSATION = "conversation"# Resumos de conversas inteiras
    USER_PREFERENCE = "user_preference"# Preferências do usuário
    ISSUE = "issue"# Problemas ou reclamações
    FACT = "fact"# Fatos relevantes sobre o usuário
    ACTION = "action"# Ações tomadas ou recomendadas
```

Cada tipo representa uma categoria diferente de informação memorizada, permitindo recuperação seletiva baseada no contexto atual da conversa.

### 2. `MemoryEntry` (Modelo em `memory.py`)

Representa uma entrada individual na memória:

```python
class MemoryEntry(BaseModel):
    """A single memory entry."""
    id: str
    tenant_id: str
    user_id: str
    type: MemoryType
    content: str
    metadata: Dict[str, Any] = {}
    embedding: Optional[List[float]] = None
    importance: float = 0.5
    created_at: float = time.time()
    last_accessed: float = time.time()
    access_count: int = 0

```

Características importantes:

- **Multi-tenant**: Cada entrada tem um `tenant_id` para separação de dados
- **User-specific**: Entradas são vinculadas a usuários específicos via `user_id`
- **Embeddings**: Vetores de alta dimensão que representam semanticamente o conteúdo
- **Metadados**: Informações adicionais que contextualizam a entrada
- **Rastreamento de uso**: `last_accessed` e `access_count` permitem implementar mecanismos de decaimento e relevância

### 3. `ConversationSummary` (Modelo em `memory.py`)

Armazena diferentes níveis de resumo para uma conversa:

```python
class ConversationSummary(BaseModel):
    """Summary of a conversation at different levels."""
    conversation_id: str
    tenant_id: str
    user_id: str
    brief_summary: str
    detailed_summary: str
    key_points: List[str]
    entities: Dict[str, Any]
    sentiment: str
    created_at: float = time.time()

```

Este modelo captura:

- Resumos em diferentes níveis de granularidade
- Pontos-chave extraídos automaticamente
- Entidades mencionadas (pessoas, produtos, datas, etc.)
- Análise de sentimento (positivo, negativo, neutro, misto)

### 4. `MemoryService` (Serviço em `memory.py`)

Componente central que gerencia toda a funcionalidade de memória:

```python
class MemoryService:
    """Service for managing long-term memory."""

    def __init__(self, llm_service, db_connection_string=None,
                 vector_db_url=None, vector_db_path=None, use_local_storage=True):
# Inicialização...

```

Métodos principais:

- `add_memory`: Adiciona uma nova entrada à memória com embedding
- `recall_memories`: Recupera memórias relevantes para uma consulta
- `generate_conversation_summary`: Gera resumos de conversas em vários níveis
- `get_user_profile`: Constrói um perfil do usuário baseado em suas memórias
- `clean_old_memories`: Remove memórias antigas raramente acessadas

## Fluxo de Dados e Integrações

### 1. Ciclo de Vida da Memória

O ciclo de vida completo das memórias no sistema inclui:

1. **Criação**: Durante/após conversas, através de `_extract_memories_from_conversation`
2. **Armazenamento**: Em FAISS (local) ou banco de dados vetorial (remoto)
3. **Recuperação**: Durante novas conversas, via similaridade semântica
4. **Atualização**: Incremento de contadores de acesso e timestamps
5. **Decaimento/Remoção**: Limpeza periódica de memórias antigas ou irrelevantes

### 2. Integração com o Orquestrador de Agentes

O `AgentOrchestrator` em `orchestrator.py` gerencia a integração da memória no fluxo de conversação:

```python
async def process_message(self, conversation_id: str, message: str, agent_id: str, contact_id: str) -> Dict[str, Any]:
# ... [código omitido] ...

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

                logging.debug(f"Retrieved {len(memory_context)} relevant memories for conversation {conversation_id}")
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
# Generate summary in the background
        asyncio.create_task(self._generate_and_store_summary(state))

# Update metadata
        state.metadata["last_summary_at"] = time.time()

# Prepare prompt with history, context, and memories
    prompt = self._prepare_prompt(state, current_agent, rag_context, memory_context, contact_id)

# ... [resto do código] ...

```

Pontos-chave desta integração:

- Memórias relevantes são buscadas para cada mensagem
- Resumos são gerados periodicamente em tarefas de fundo
- Memórias alimentam o prompt enviado ao modelo LLM
- O contexto de memória é usado juntamente com o contexto RAG

### 3. Interação com a Configuração do Sistema

O sistema de memória é altamente configurável através de `SystemConfig` em `config.py`:

```python
class MemoryConfig(BaseModel):
    """Configuration for memory system."""
    enabled: bool = True
    vector_db_url: Optional[str] = None
    memory_db_path: Optional[str] = None
    use_local_storage: bool = True
    summary_frequency: int = 10# Messages
    summary_time_threshold: int = 1800# Seconds (30 mins)
    max_memories_per_query: int = 5
    memory_relevance_threshold: float = 0.6
    memory_decay_rate: float = 0.01# Per day
    cleanup_age_days: int = 90

```

Esta configuração permite ajustar:

- Ativação/desativação do sistema de memória
- Caminho para armazenamento local ou URL para serviço remoto
- Frequência de geração de resumos (por contagem ou por tempo)
- Número máximo de memórias a recuperar por consulta
- Limiar de relevância para memórias
- Taxa de decaimento e idade máxima para limpeza

### 4. Integração com o Sistema RAG

Enquanto o RAG (Retrieval-Augmented Generation) se concentra em recuperar conhecimento a partir de documentos externos, a memória trabalha com conhecimento derivado das próprias conversas. Ambos são fontes complementares:

```python
# Do orchestrator.py
async def _prepare_prompt(self, state: ConversationState, agent: Agent,
                         rag_context: List[Any], memory_context: List[Dict[str, Any]] = None) -> List[Dict[str, str]]:
    """Prepares the prompt for the LLM, including history, RAG context, and memories."""
# Start with system prompt from agent configuration
    system_prompt = agent.generate_system_prompt()

# Add RAG context if available
    if rag_context:
        system_prompt += "\n\n## Relevant Knowledge Base Information:\n"
        for i, doc in enumerate(rag_context[:3]):# Limit to top 3 most relevant docs
            system_prompt += f"\nDocument {i+1}:\n{doc['content']}\n"

# Add memory context if available
    if memory_context:
        system_prompt += "\n\n## User Memory and Context:\n"
        for memory in memory_context:
            memory_type_label = memory["type"].value.replace("_", " ").title()
            system_prompt += f"\n{memory_type_label}: {memory['content']}\n"

```

## Implementação Técnica

### 1. Armazenamento e Recuperação de Memórias

O sistema oferece duas opções principais de armazenamento:

### Armazenamento Local com FAISS

Para implantações locais ou de menor escala, o sistema usa [FAISS](https://github.com/facebookresearch/faiss) da Facebook Research para armazenamento e pesquisa de vetores:

```python
async def _init_faiss_index(self):
    """Inicializa o índice FAISS para armazenamento local."""
    if self.faiss_index is not None:
        return

    try:
        from langchain.vectorstores import FAISS
        from langchain.schema import Document
        import uuid

# Verificar se já existe um index
        index_file = os.path.join(self.vector_db_path, "index.faiss")

        if os.path.exists(index_file):
# Carregar index existente
            embedding_adapter = self._create_embedding_adapter()

            self.faiss_index = FAISS.load_local(
                self.vector_db_path,
                embedding_adapter,
                "index",
                allow_dangerous_deserialization=True
            )

            print(f"FAISS index loaded from {self.vector_db_path}")
        else:
# Criar um novo index vazio# ... implementação ...

```

### Armazenamento Remoto via API

Para implantações de maior escala, o sistema pode usar um serviço vetorial externo:

```python
async def add_memory(self, entry: MemoryEntry) -> str:
    """
    Adds a new memory entry to the system.
    """
# Generate embedding for this memory for retrieval later
    entry.embedding = await self._get_embedding(entry.content)

# Usar serviço vetorial HTTP se configurado e não estiver usando armazenamento local
    if self.vector_db_url and not self.use_local_storage:
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.vector_db_url}/vectors",
                    json=entry.dict(),
                    timeout=10.0
                )
                response.raise_for_status()
                return response.json()["id"]
        except Exception as e:
            print(f"Error storing memory in vector database: {e}")
# Fall back to local storage or in-memory

```

### 2. Geração de Embeddings

O sistema utiliza o modelo de embeddings disponível do provedor de LLM configurado (como OpenAI):

```python
async def _get_embedding(self, text: str) -> List[float]:
    """
    Gets an embedding vector for the text.
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.openai.com/v1/embeddings",
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.llm.api_key}"
                },
                json={
                    "model": "text-embedding-ada-002",
                    "input": text[:8000]# Truncate to avoid token limits
                },
                timeout=10.0
            )
            response.raise_for_status()
            return response.json()["data"][0]["embedding"]
    except Exception as e:
        print(f"Error getting embedding: {e}")
# Return a random embedding as fallback (not ideal but allows testing)
        import random
        return [random.random() for _ in range(1536)]

```

### 3. Extração Inteligente de Memórias

Durante e após as conversas, o sistema extrai automaticamente memórias relevantes:

```python
async def _extract_memories_from_conversation(
    self,
    conversation_id: str,
    tenant_id: str,
    user_id: str,
    messages: List[Dict[str, Any]],
    summary: ConversationSummary
) -> None:
    """
    Extracts important memories from a conversation.
    """
# Convert messages to a single string for analysis
    conversation_text = "\n".join([
        f"{msg['role'].upper()}: {msg['content']}"
        for msg in messages
    ])

# Extract user preferences
    preferences_prompt = [
        {"role": "system", "content": "Extraia as preferências do usuário desta conversa como um array JSON. Inclua apenas preferências claras e objetivas."},
        {"role": "user", "content": f"Extrair preferências desta conversa:\n{conversation_text}"}
    ]
    preferences_json = await self.llm.generate_response(preferences_prompt)

    try:
        preferences = json.loads(preferences_json)
        if isinstance(preferences, list):
            for pref in preferences:
                if isinstance(pref, str) and pref.strip():
# Create preference memory
                    memory_id = f"pref_{conversation_id}_{hashlib.md5(pref.encode()).hexdigest()[:8]}"
                    memory = MemoryEntry(
                        id=memory_id,
                        tenant_id=tenant_id,
                        user_id=user_id,
                        type=MemoryType.USER_PREFERENCE,
                        content=pref,
                        metadata={
                            "source_conversation": conversation_id,
                            "extracted_at": time.time()
                        }
                    )
                    await self.add_memory(memory)
    except:
        pass

# Extract issues/problems# ... implementação similar ...

# Extract important facts# ... implementação similar ...

# Also store the conversation summary as a memory
    summary_memory_id = f"summary_{conversation_id}"
    summary_memory = MemoryEntry(
        id=summary_memory_id,
        tenant_id=tenant_id,
        user_id=user_id,
        type=MemoryType.CONVERSATION,
        content=summary.detailed_summary,
        metadata={
            "conversation_id": conversation_id,
            "brief_summary": summary.brief_summary,
            "key_points": summary.key_points,
            "sentiment": summary.sentiment,
            "entities": summary.entities
        }
    )
    await self.add_memory(summary_memory)

```

### 4. Multi-tenant e Segurança

O sistema implementa completo isolamento multi-tenant para memórias:

1. **Isolamento por Tenant**: Todas as memórias têm um `tenant_id` para garantir separação
2. **Isolamento por Usuário**: Memórias são vinculadas a usuários específicos dentro de cada tenant
3. **Filtros de Consulta**: Recuperação de memórias sempre filtra por tenant_id e user_id

```python
async def recall_memories(
    self,
    tenant_id: str,
    user_id: str,
    query: str,
    memory_types: Optional[List[MemoryType]] = None,
    limit: int = 5
) -> List[MemoryEntry]:
    """
    Recalls relevant memories based on the query.
    """
# ... código omitido ...

# Filter by tenant and user
    filtered_entries = [
        entry for entry in self._memory_entries
        if entry.tenant_id == tenant_id and entry.user_id == user_id
    ]

```

## Benefícios do Sistema de Memória

### 1. Personalização Aprimorada

O sistema de memória permite:

- **Recuperar preferências do usuário**: Evita repetir as mesmas perguntas
- **Lembrar de problemas anteriores**: Permite referências contextualizadas
- **Reconhecer padrões de comportamento**: Adapta respostas ao perfil do usuário

### 2. Coerência nas Conversas de Longo Prazo

Mesmo com várias conversas separadas:

- O assistente mantém coerência entre sessões
- Evita contradizer-se em recomendações
- Pode referenciar conversas passadas quando relevante

### 3. Escalabilidade e Eficiência

A implementação é projetada para escala:

- **Armazenamento vetorial**: Recuperação eficiente mesmo com milhões de memórias
- **Processamento assíncrono**: Resumos e extração de memórias ocorrem em background
- **Persistência configurável**: Flexibilidade para armazenamento local ou remoto

### 4. Aprendizado Contínuo

O sistema aprende continuamente com cada interação:

- **Extração automática de conhecimento**: Preferências, fatos e problemas
- **Construção progressiva de perfil**: O perfil do usuário se enriquece ao longo do tempo
- **Mecanismo de decaimento**: Memórias antigas têm peso reduzido automaticamente

## Casos de Uso Avançados

### 1. Construção de Perfil de Usuário

O sistema pode criar perfis detalhados dos usuários:

```python
async def get_user_profile(self, tenant_id: str, user_id: str) -> Dict[str, Any]:
    """
    Builds a user profile based on memories.
    """
# Recall all user preferences
    preferences = await self.recall_memories(
        tenant_id=tenant_id,
        user_id=user_id,
        query="user preferences",
        memory_types=[MemoryType.USER_PREFERENCE],
        limit=20
    )

# Recall past issues
    issues = await self.recall_memories(
        tenant_id=tenant_id,
        user_id=user_id,
        query="user issues problems complaints",
        memory_types=[MemoryType.ISSUE],
        limit=10
    )

# ... outras memórias ...

# Build profile
    profile = {
        "user_id": user_id,
        "preferences": [p.content for p in preferences],
        "issues": [i.content for i in issues],
        "facts": [f.content for f in facts],
        "recent_conversations": [
            {
                "id": s.conversation_id,
                "summary": s.brief_summary,
                "sentiment": s.sentiment,
                "timestamp": s.created_at
            }
            for s in recent_summaries
        ]
    }

    return profile

```

Este perfil pode ser usado para:

- Personalizar cumprimentos e recomendações
- Antecipar necessidades do usuário
- Adaptar o tom e estilo de comunicação

### 2. Detecção de Mudança de Tópico

O sistema pode detectar mudanças no foco da conversa:

```python
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

    return distance

```

Isso permite:

- Decidir quando transferir para outro agente especializado
- Identificar quando um usuário muda bruscamente de assunto
- Manter o contexto quando tópicos voltam a ser discutidos

### 3. Personalização por Tenant

O sistema permite configurações específicas por tenant:

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

Isso permite:

- Diferentes políticas de retenção de memória por tenant
- Configurações específicas de extração de memórias
- Ajuste de frequência de resumos por tenant

## Limitações e Considerações

### 1. Privacidade e Conformidade

A implementação atual armazena memórias indefinidamente (sujeito a políticas de limpeza). Para casos de uso que envolvem informações sensíveis:

- **Possível melhoria**: Implementar remoção explícita de memórias a pedido do usuário
- **Consideração**: Adicionar opção para desabilitar completamente a memória para usuários específicos
- **Conformidade LGPD/GDPR**: Mecanismos de exclusão permanente sob demanda

### 2. Desafios Técnicos

Alguns desafios técnicos da implementação:

- **Escalabilidade**: Para sistemas com muitos usuários, o banco de dados vetorial pode se tornar um gargalo
- **Qualidade de Embeddings**: A qualidade da recuperação depende do modelo de embeddings usado
- **Manutenção**: É necessário revisar periodicamente as políticas de limpeza de memória

### 3. Balanceamento entre Personalização e Generalização

O sistema deve equilibrar:

- **Personalização excessiva**: Pode tornar respostas muito específicas e menos úteis em contextos gerais
- **Memória insuficiente**: Pode fazer o usuário repetir informações já fornecidas
- **Custo computacional**: Mais memória = mais processamento e armazenamento

## Conclusão

O sistema de memória implementado é um componente sofisticado que fornece "memória de longo prazo" ao assistente. Ele transforma o assistente de um modelo meramente reativo para um participante ativo que aprende progressivamente com cada interação.

As memórias extraídas de conversas passadas enriquecem significativamente as capacidades do assistente, permitindo:

1. **Personalização**: Adapta respostas ao perfil e histórico de cada usuário
2. **Continuidade**: Mantém coerência entre conversas separadas no tempo
3. **Eficiência**: Evita repetições e reconhece referências a tópicos passados
4. **Aprendizado**: Evolui continuamente seu entendimento de cada usuário

O design modular e configurável permite adaptar o sistema às necessidades específicas de diferentes implantações, desde uso pessoal leve até implantações enterprise com múltiplos tenants.

## Recomendações para Uso Eficiente

1. **Ajuste da frequência de resumos**: Configure `summary_frequency` e `summary_time_threshold` de acordo com o tipo típico de conversa
2. **Balanceie quantidade e qualidade**: Ajuste `max_memories_per_query` e `memory_relevance_threshold` para equilíbrio entre recall e precisão
3. **Defina políticas de retenção**: Configure `cleanup_age_days` de acordo com requisitos de negócio e privacidade
4. **Monitore uso de recursos**: O armazenamento vetorial pode crescer significativamente com muitos usuários ativos

---

Este documento representa uma análise completa do subsistema de memória do Assistente Inteligente, baseada no exame detalhado dos arquivos de código-fonte e suas interdependências funcionais. A implementação representa um sofisticado sistema de memória de longo prazo que eleva significativamente as capacidades do assistente além de um simples modelo conversacional.