# Create a new file at app/services/memory.py

from enum import Enum
import logging
import os
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timedelta
import time
import json
import hashlib
import asyncio
import uuid
from pydantic import BaseModel
import httpx
from app.core.config import Settings, settings
from langchain.schema import Document


from app.services.orchestrator import ConversationState

logger = logging.getLogger(__name__)

class MemoryType(str, Enum):
    """Types of memory entries."""
    CONVERSATION = "conversation"
    USER_PREFERENCE = "user_preference"
    ISSUE = "issue"
    FACT = "fact"
    ACTION = "action"

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

class MemoryService:
    """Service for managing long-term memory."""
    
    def __init__(self, llm_service, db_connection_string=None, 
                 vector_db_url=None, vector_db_path=None, use_local_storage=True):
        self.llm = llm_service
        self.db_url = db_connection_string
        self.vector_db_url = vector_db_url
        self.vector_db_path = vector_db_path or settings.VECTOR_DB_PATH
        self.use_local_storage = use_local_storage
        
        # In-memory fallback if no storage is configured
        self._memory_entries = []
        self._summaries = []
        
        # FAISS index para armazenamento local
        self.faiss_index = None
        self.faiss_docstore = None
        
        # Inicializar armazenamento FAISS se necessário
        if self.use_local_storage and self.vector_db_path:
            # Criar diretório se não existir
            os.makedirs(self.vector_db_path, exist_ok=True)
            
            # Verificar se já existe um index
            index_file = os.path.join(self.vector_db_path, "memory_index.faiss")
            if os.path.exists(index_file):
                # O index será carregado na primeira vez que for necessário
                pass
            
    async def _init_faiss_index(self):
        """Inicializa o índice FAISS para armazenamento local."""
        if self.faiss_index is not None:
            return
        
        try:
            #from langchain.vectorstores import FAISS
            from langchain_community.vectorstores import FAISS
            from langchain.schema import Document
            import uuid
            
            # Verificar se já existe um index
            index_file = os.path.join(self.vector_db_path, "index.faiss")
            
            if os.path.exists(index_file):
                # Carregar index existente
                # Adaptador para compatibilidade com FAISS
                embedding_adapter = self._create_embedding_adapter()
                
                self.faiss_index = FAISS.load_local(
                    self.vector_db_path, 
                    embedding_adapter,  # Usando o adaptador
                    "index",
                    allow_dangerous_deserialization=True
                )
                
                print(f"FAISS index loaded from {self.vector_db_path}")
            else:
                # Criar um novo index vazio
                # Para criar um index vazio, precisamos de pelo menos um documento
                temp_doc = Document(
                    page_content="Temporary document for FAISS initialization",
                    metadata={"temp": True, "id": str(uuid.uuid4())}
                )
                
                # Vamos fazer uma abordagem alternativa - criar um embedding manualmente
                temp_embedding = await self._get_embedding(temp_doc.page_content)
                
                # Em vez de usar o adapter, vamos criar os documentos manualmente
                import numpy as np
                from langchain.schema.embeddings import Embeddings
                
                # Criar um embedding simples do tipo numpy array            
                class SimpleEmbeddings(Embeddings):
                    def embed_documents(self, texts):
                        # Retornar embedding fixo para cada texto
                        return [np.array([0.1] * 1536, dtype=np.float32) for _ in texts]
                    
                    def embed_query(self, text):
                        # Retornar embedding fixo para query
                        return np.array([0.1] * 1536, dtype=np.float32)
                
                # Criar um novo index com embedding estático
                self.faiss_index = FAISS.from_documents([temp_doc], SimpleEmbeddings())
                
                # Salvar o index
                self.faiss_index.save_local(self.vector_db_path, "index")
                
                print(f"New FAISS index created at {self.vector_db_path}")
            
            # Armazenar referência ao docstore
            self.faiss_docstore = self.faiss_index.docstore
            
        except Exception as e:
            print(f"Error initializing FAISS index: {e}")
            import traceback
            traceback.print_exc()
            self.use_local_storage = False  # Fallback para memória

    def _create_embedding_adapter(self):
        """Cria um adaptador compatível com FAISS"""
        from langchain.schema.embeddings import Embeddings
        
        # Classe para adaptar nosso LLM ao formato esperado pelo FAISS
        class AsyncCompatibleEmbeddings(Embeddings):
            def __init__(self, llm_service):
                self.llm_service = llm_service
                
            def embed_documents(self, texts):
                # Implementação síncrona - não use asyncio.run()
                # Em vez disso, use uma solução que funcione com o eventloop atual
                import nest_asyncio
                import asyncio
                
                # Apply nest_asyncio para permitir loops aninhados
                nest_asyncio.apply()
                
                # Criar uma nova coroutine que será executada no loop atual
                async def get_embeddings():
                    embeddings = []
                    for text in texts:
                        embedding = await self.llm_service.get_embeddings(text)
                        embeddings.append(embedding)
                    return embeddings
                
                # Obter o loop atual e executar a coroutine nele
                loop = asyncio.get_event_loop()
                return loop.run_until_complete(get_embeddings())
            
            def embed_query(self, text):
                # Similar à embed_documents, mas para uma única query
                import nest_asyncio
                import asyncio
                
                nest_asyncio.apply()
                
                async def get_embedding():
                    return await self.llm_service.get_embeddings(text)
                
                loop = asyncio.get_event_loop()
                return loop.run_until_complete(get_embedding())
        
        return AsyncCompatibleEmbeddings(self.llm)
    
    # async def add_memory(self, entry: MemoryEntry) -> str:
    #     """
    #     Adds a new memory entry to the system.
        
    #     Args:
    #         entry: The memory entry to add
                
    #     Returns:
    #         The ID of the added memory
    #     """
    #     # Generate embedding for this memory for retrieval later
    #     entry.embedding = await self._get_embedding(entry.content)
        
    #     # Usar serviço vetorial HTTP se configurado e não estiver usando armazenamento local
    #     if self.vector_db_url and not self.use_local_storage:
    #         try:
    #             async with httpx.AsyncClient() as client:
    #                 response = await client.post(
    #                     f"{self.vector_db_url}/vectors",
    #                     json=entry.dict(),
    #                     timeout=10.0
    #                 )
    #                 response.raise_for_status()
    #                 return response.json()["id"]
    #         except Exception as e:
    #             print(f"Error storing memory in vector database: {e}")
    #             # Fall back to local storage or in-memoryy
    #         # ... código HTTP existente ...
        
    #     # Usar FAISS se armazenamento local estiver habilitado
    #     if self.use_local_storage and self.vector_db_path:
    #         try:
    #             # Inicializar FAISS se necessário
    #             await self._init_faiss_index()
                
    #             if self.faiss_index:
    #                 from langchain.schema import Document
                    
    #                 # Converter MemoryEntry para Document
    #                 doc = Document(
    #                     page_content=entry.content,
    #                     metadata={
    #                         "id": entry.id,
    #                         "tenant_id": entry.tenant_id,
    #                         "user_id": entry.user_id,
    #                         "type": entry.type.value,
    #                         "created_at": entry.created_at,
    #                         "last_accessed": entry.last_accessed,
    #                         "access_count": entry.access_count,
    #                         "importance": entry.importance,
    #                         "metadata": json.dumps(entry.metadata)
    #                     }
    #                 )
                    
    #                 # Adicionar documento diretamente ao FAISS
    #                 import numpy as np
    #                 embedding_vector = np.array(entry.embedding, dtype=np.float32)
    #                 self.faiss_index.add_embeddings(
    #                     [(doc.page_content, doc.metadata)], 
    #                     [embedding_vector]
    #                 )
                    
    #                 # Salvar alterações
    #                 self.faiss_index.save_local(self.vector_db_path, "index")
                    
    #                 return entry.id
    #         except Exception as e:
    #             print(f"Error storing memory in FAISS: {e}")
    #             import traceback
    #             traceback.print_exc()
    #             # Fall back to in-memory
        
    #     # In-memory fallback
    #     self._memory_entries.append(entry)
    #     return entry.id
    async def add_memory(self, entry: MemoryEntry) -> str:
        """
        Adds a new memory entry to the system.
        
        Args:
            entry: The memory entry to add
                
        Returns:
            The ID of the added memory
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
        
        # Usar FAISS se armazenamento local estiver habilitado
        if self.use_local_storage and self.vector_db_path:
            try:
                # Inicializar FAISS se necessário
                await self._init_faiss_index()
                
                if self.faiss_index:
                    from langchain.schema import Document
                    
                    # Converter MemoryEntry para Document com metadados corretos
                    doc = Document(
                        page_content=entry.content,
                        metadata={
                            "id": entry.id,
                            "tenant_id": entry.tenant_id,
                            "user_id": entry.user_id,
                            "type": entry.type.value,
                            "created_at": entry.created_at,
                            "last_accessed": entry.last_accessed,
                            "access_count": entry.access_count,
                            "importance": entry.importance,
                            "metadata": json.dumps(entry.metadata)
                        }
                    )
                    
                    # CORREÇÃO: Usar add_documents ao invés de add_embeddings
                    # para evitar problemas com metadados
                    import numpy as np
                    
                    # Criar um documento temporário para adicionar ao FAISS
                    texts = [doc.page_content]
                    metadatas = [doc.metadata]
                    embeddings = [entry.embedding]
                    
                    # Adicionar usando o método correto
                    self.faiss_index.add_texts(
                        texts=texts,
                        metadatas=metadatas,
                        embeddings=embeddings
                    )
                    
                    # Salvar alterações
                    self.faiss_index.save_local(self.vector_db_path, "index")
                    
                    return entry.id
            except Exception as e:
                print(f"Error storing memory in FAISS: {e}")
                import traceback
                traceback.print_exc()
                # Fall back to in-memory
        
        # In-memory fallback
        self._memory_entries.append(entry)
        return entry.id
    
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
        
        Args:
            tenant_id: The tenant ID
            user_id: The user ID
            query: The query text
            memory_types: Optional filter for memory types
            limit: Maximum number of memories to return
            
        Returns:
            List of relevant memory entries
        """
        # Generate embedding for the query
        query_embedding = await self._get_embedding(query)
        
        # 1. Tentar usar serviço HTTP se configurado e não estiver usando armazenamento local
        if self.vector_db_url and not self.use_local_storage:
            try:
                params = {
                    "tenant_id": tenant_id,
                    "user_id": user_id,
                    "limit": limit
                }
                
                if memory_types:
                    params["types"] = [t.value for t in memory_types]
                
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        f"{self.vector_db_url}/search",
                        json={
                            "embedding": query_embedding,
                            "params": params
                        },
                        timeout=10.0
                    )
                    response.raise_for_status()
                    results = response.json()["results"]
                    
                    # Convert back to MemoryEntry objects
                    return [MemoryEntry(**item) for item in results]
            except Exception as e:
                print(f"Error querying vector database: {e}")
                # Fall back to local storage or in-memory
        
        # 2. Tentar usar FAISS local se habilitado
        if self.use_local_storage and self.vector_db_path:
            try:
                # Inicializar FAISS se necessário
                await self._init_faiss_index()
                
                if self.faiss_index:
                    # Realizar busca por similaridade
                    # Buscar mais resultados do que necessário para poder filtrar
                    docs_with_scores = self.faiss_index.similarity_search_with_score(
                        query, k=limit * 3
                    )
                    
                    # Filtrar por tenant_id e user_id
                    filtered_results = []
                    for doc, score in docs_with_scores:
                        doc_tenant_id = doc.metadata.get("tenant_id")
                        doc_user_id = doc.metadata.get("user_id")
                        doc_type = doc.metadata.get("type")
                        
                        # Verificar se corresponde aos filtros
                        if doc_tenant_id == tenant_id and doc_user_id == user_id:
                            # Verificar filtro de tipo se fornecido
                            if memory_types and doc_type:
                                if not any(t.value == doc_type for t in memory_types):
                                    continue
                            
                            # Converter de Document para MemoryEntry
                            try:
                                entry_metadata = json.loads(doc.metadata.get("metadata", "{}"))
                            except:
                                entry_metadata = {}
                                
                            entry = MemoryEntry(
                                id=doc.metadata.get("id", str(uuid.uuid4())),
                                tenant_id=doc_tenant_id,
                                user_id=doc_user_id,
                                type=MemoryType(doc_type) if doc_type else MemoryType.FACT,
                                content=doc.page_content,
                                metadata=entry_metadata,
                                embedding=query_embedding,  # Usar embedding da query como placeholder
                                importance=doc.metadata.get("importance", 0.5),
                                created_at=doc.metadata.get("created_at", time.time()),
                                last_accessed=time.time(),  # Atualizar último acesso
                                access_count=doc.metadata.get("access_count", 0) + 1  # Incrementar
                            )
                            
                            # Calcular relevância
                            relevance = 1.0 / (1.0 + score)  # Converter distância para relevância
                            filtered_results.append((entry, relevance))
                    
                    # Ordenar por relevância
                    filtered_results.sort(key=lambda x: x[1], reverse=True)
                    
                    # Limitar ao número desejado
                    return [entry for entry, _ in filtered_results[:limit]]
            except Exception as e:
                print(f"Error searching FAISS index: {e}")
                # Fall back to in-memory
        
        # 3. Fallback para busca em memória
        if not self._memory_entries:
            return []
        
        # Filter by tenant and user
        filtered_entries = [
            entry for entry in self._memory_entries
            if entry.tenant_id == tenant_id and entry.user_id == user_id
        ]
        
        # Further filter by memory types if specified
        if memory_types:
            filtered_entries = [
                entry for entry in filtered_entries
                if entry.type in memory_types
            ]
        
        # Calculate similarity scores
        entries_with_scores = []
        for entry in filtered_entries:
            if entry.embedding:
                similarity = self._calculate_similarity(query_embedding, entry.embedding)
                entries_with_scores.append((entry, similarity))
        
        # Sort by similarity (highest first)
        entries_with_scores.sort(key=lambda x: x[1], reverse=True)
        
        # Update access tracking for retrieved memories
        for entry, _ in entries_with_scores[:limit]:
            entry.last_accessed = time.time()
            entry.access_count += 1
        
        # Return top entries
        return [entry for entry, _ in entries_with_scores[:limit]]
    
    # app/services/memory.py - Correções necessárias

# Primeiro, corrigir o import (linha 87)
from langchain_community.vectorstores import FAISS  # Usar o import correto
from langchain.schema import Document

class MemoryService:
    # ... código existente ...
    
    async def add_memory(self, entry: MemoryEntry) -> str:
        """
        Adds a new memory entry to the system.
        
        Args:
            entry: The memory entry to add
                
        Returns:
            The ID of the added memory
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
        
        # Usar FAISS se armazenamento local estiver habilitado
        if self.use_local_storage and self.vector_db_path:
            try:
                # Inicializar FAISS se necessário
                await self._init_faiss_index()
                
                if self.faiss_index:
                    from langchain.schema import Document
                    
                    # Converter MemoryEntry para Document com metadados corretos
                    doc = Document(
                        page_content=entry.content,
                        metadata={
                            "id": entry.id,
                            "tenant_id": entry.tenant_id,
                            "user_id": entry.user_id,
                            "type": entry.type.value,
                            "created_at": entry.created_at,
                            "last_accessed": entry.last_accessed,
                            "access_count": entry.access_count,
                            "importance": entry.importance,
                            "metadata": json.dumps(entry.metadata)
                        }
                    )
                    
                    # CORREÇÃO: Usar add_documents ao invés de add_embeddings
                    # para evitar problemas com metadados
                    import numpy as np
                    
                    # Criar um documento temporário para adicionar ao FAISS
                    texts = [doc.page_content]
                    metadatas = [doc.metadata]
                    embeddings = [entry.embedding]
                    
                    # Adicionar usando o método correto
                    self.faiss_index.add_texts(
                        texts=texts,
                        metadatas=metadatas,
                        embeddings=embeddings
                    )
                    
                    # Salvar alterações
                    self.faiss_index.save_local(self.vector_db_path, "index")
                    
                    return entry.id
            except Exception as e:
                print(f"Error storing memory in FAISS: {e}")
                import traceback
                traceback.print_exc()
                # Fall back to in-memory
        
        # In-memory fallback
        self._memory_entries.append(entry)
        return entry.id

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
            
            logging.info(f"Gerando resumo para a conversa {state.conversation_id}")
            
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
            
            logging.info(f"Resumo gerado e armazenado para conversa {state.conversation_id}")
            
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

    
    async def generate_conversation_summary(
        self, 
        conversation_id: str,
        tenant_id: str, 
        user_id: str,
        messages: List[Dict[str, Any]]
    ) -> ConversationSummary:
        """
        Gera resumos hierárquicos de uma conversa.
        
        Args:
            conversation_id: The conversation ID
            tenant_id: The tenant ID
            user_id: The user ID
            messages: List of messages in the conversation
            
        Returns:
            A ConversationSummary object
        """
        # Filter to just user and assistant messages
        filtered_messages = [
            msg for msg in messages
            if msg.get("role") in ["user", "assistant"]
        ]
        
        if not filtered_messages:
            return None
        
        # Convert messages to a single string
        conversation_text = "\n".join([
            f"{msg['role'].upper()}: {msg['content']}"
            for msg in filtered_messages
        ])
        
        try:
            # Generate brief summary (1-2 sentences)
            brief_summary_prompt = [
                {"role": "system", "content": "Você é especialista em resumir conversas em 1 ou 2 frases, capturando a essência."},
                {"role": "user", "content": f"Resuma esta conversa em 1-2 frases:\n{conversation_text}"}
            ]
            brief_summary_response = await self.llm.generate_response(brief_summary_prompt)
            
            # Handle tuple response - extract the text part
            if isinstance(brief_summary_response, tuple):
                brief_summary = brief_summary_response[0] if brief_summary_response else ""
            else:
                brief_summary = brief_summary_response
            
            # Ensure it's a string and clean it
            brief_summary = str(brief_summary).strip() if brief_summary else "Resumo não disponível"
            
            # Generate detailed summary (paragraph)
            detailed_summary_prompt = [
                {"role": "system", "content": "Você é especialista em resumir conversas em um parágrafo detalhado, porém conciso e objetivo."},
                {"role": "user", "content": f"Resuma esta conversa em um parágrafo detalhado:\n{conversation_text}"}
            ]
            detailed_summary_response = await self.llm.generate_response(detailed_summary_prompt)
            
            # Handle tuple response - extract the text part
            if isinstance(detailed_summary_response, tuple):
                detailed_summary = detailed_summary_response[0] if detailed_summary_response else ""
            else:
                detailed_summary = detailed_summary_response
            
            # Ensure it's a string and clean it
            detailed_summary = str(detailed_summary).strip() if detailed_summary else "Resumo detalhado não disponível"
            
            # Extract key points
            key_points_prompt = [
                {"role": "system", "content": "Você é um especialista em extrair pontos-chave de conversas."},
                {"role": "user", "content": f"Extraia 3 a 5 pontos-chave desta conversa como um JSON array:\n{conversation_text}"}
            ]
            key_points_response = await self.llm.generate_response(key_points_prompt)
            
            # Handle tuple response - extract the text part
            if isinstance(key_points_response, tuple):
                key_points_json = key_points_response[0] if key_points_response else "[]"
            else:
                key_points_json = key_points_response
            
            # Ensure it's a string
            key_points_json = str(key_points_json).strip() if key_points_json else "[]"
            
            # Parse key points from JSON
            try:
                key_points = json.loads(key_points_json)
                if not isinstance(key_points, list):
                    key_points = ["Falha ao extrair pontos-chave devidamente."]
            except:
                key_points = ["Falha ao extrair pontos-chave"]
            
            # Extract entities (people, products, etc.)
            entities_prompt = [
                {"role": "system", "content": "Você é especialista em extrair entidades (pessoas, produtos, locais, datas, problemas) de conversas. Retorne como JSON."},
                {"role": "user", "content": f"Extraia entidades desta conversa como um objeto JSON com categorias como chaves:\n{conversation_text}"}
            ]
            entities_response = await self.llm.generate_response(entities_prompt)
            
            # Handle tuple response - extract the text part
            if isinstance(entities_response, tuple):
                entities_json = entities_response[0] if entities_response else "{}"
            else:
                entities_json = entities_response
            
            # Ensure it's a string
            entities_json = str(entities_json).strip() if entities_json else "{}"
            
            # Parse entities from JSON
            try:
                entities = json.loads(entities_json)
                if not isinstance(entities, dict):
                    entities = {}
            except:
                entities = {}
            
            # Analyze sentiment
            sentiment_prompt = [
                {"role": "system", "content": "Analise o sentimento desta conversa. Responda apenas uma palavra: positivo, negativo, neutro ou misto."},
                {"role": "user", "content": f"Determine o sentimento desta conversa:\n{conversation_text}"}
            ]
            sentiment_response = await self.llm.generate_response(sentiment_prompt)
            
            # Handle tuple response - extract the text part
            if isinstance(sentiment_response, tuple):
                sentiment = sentiment_response[0] if sentiment_response else "neutro"
            else:
                sentiment = sentiment_response
            
            # Ensure it's a string and clean it
            sentiment = str(sentiment).strip().lower() if sentiment else "neutro"
            
            # Create and return summary
            summary = ConversationSummary(
                conversation_id=conversation_id,
                tenant_id=tenant_id,
                user_id=user_id,
                brief_summary=brief_summary,
                detailed_summary=detailed_summary,
                key_points=key_points,
                entities=entities,
                sentiment=sentiment,
                created_at=time.time()
            )
            
            # Store summary
            if self.vector_db_url:
                try:
                    async with httpx.AsyncClient() as client:
                        await client.post(
                            f"{self.vector_db_url}/summaries",
                            json=summary.dict(),
                            timeout=10.0
                        )
                except Exception as e:
                    print(f"Error storing summary in vector database: {e}")
                    # Fall back to in-memory
            
            # In-memory fallback
            self._summaries.append(summary)
            
            # Extract memories from this conversation
            await self._extract_memories_from_conversation(
                conversation_id, tenant_id, user_id, 
                filtered_messages, summary
            )
            
            return summary
            
        except Exception as e:
            print(f"Error in generate_conversation_summary: {e}")
            import traceback
            traceback.print_exc()
            
            # Return a minimal summary in case of error
            return ConversationSummary(
                conversation_id=conversation_id,
                tenant_id=tenant_id,
                user_id=user_id,
                brief_summary="Erro ao gerar resumo",
                detailed_summary="Não foi possível gerar resumo detalhado devido a erro técnico",
                key_points=["Erro na geração de resumo"],
                entities={},
                sentiment="neutro",
                created_at=time.time()
            )
    
    async def get_user_profile(self, tenant_id: str, user_id: str) -> Dict[str, Any]:
        """
        Builds a user profile based on memories.
        
        Args:
            tenant_id: The tenant ID
            user_id: The user ID
            
        Returns:
            A dictionary with user profile information
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
        
        # Recall important facts about user
        facts = await self.recall_memories(
            tenant_id=tenant_id,
            user_id=user_id,
            query="important user facts details",
            memory_types=[MemoryType.FACT],
            limit=10
        )
        
        # Get recent conversation summaries
        recent_summaries = [
            s for s in self._summaries
            if s.tenant_id == tenant_id and s.user_id == user_id
        ]
        recent_summaries.sort(key=lambda x: x.created_at, reverse=True)
        recent_summaries = recent_summaries[:5]
        
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
    
    # async def _extract_memories_from_conversation(
    #     self, 
    #     conversation_id: str,
    #     tenant_id: str,
    #     user_id: str,
    #     messages: List[Dict[str, Any]],
    #     summary: ConversationSummary
    # ) -> None:
    #     """
    #     Extracts important memories from a conversation.
        
    #     Args:
    #         conversation_id: The conversation ID
    #         tenant_id: The tenant ID
    #         user_id: The user ID
    #         messages: The conversation messages
    #         summary: The conversation summary
    #     """
    #     # Convert messages to a single string for analysis
    #     conversation_text = "\n".join([
    #         f"{msg['role'].upper()}: {msg['content']}"
    #         for msg in messages
    #     ])
        
    #     # Extract user preferences
    #     preferences_prompt = [
    #         {"role": "system", "content": "Extraia as preferências do usuário desta conversa como um array JSON. Inclua apenas preferências claras e objetivas."},
    #         {"role": "user", "content": f"Extrair preferências desta conversa:\n{conversation_text}"}
    #     ]
    #     preferences_json = await self.llm.generate_response(preferences_prompt)
        
    #     try:
    #         preferences = json.loads(preferences_json)
    #         if isinstance(preferences, list):
    #             for pref in preferences:
    #                 if isinstance(pref, str) and pref.strip():
    #                     # Create preference memory
    #                     memory_id = f"pref_{conversation_id}_{hashlib.md5(pref.encode()).hexdigest()[:8]}"
    #                     memory = MemoryEntry(
    #                         id=memory_id,
    #                         tenant_id=tenant_id,
    #                         user_id=user_id,
    #                         type=MemoryType.USER_PREFERENCE,
    #                         content=pref,
    #                         metadata={
    #                             "source_conversation": conversation_id,
    #                             "extracted_at": time.time()
    #                         }
    #                     )
    #                     await self.add_memory(memory)
    #     except:
    #         pass
        
    #     # Extract issues/problems
    #     issues_prompt = [
    #         {"role": "system", "content": "Extract user issues, problems or complaints from this conversation as a JSON array."},
    #         {"role": "user", "content": f"Extract issues from this conversation:\n{conversation_text}"}
    #     ]
    #     issues_json = await self.llm.generate_response(issues_prompt)
        
    #     try:
    #         issues = json.loads(issues_json)
    #         if isinstance(issues, list):
    #             for issue in issues:
    #                 if isinstance(issue, str) and issue.strip():
    #                     # Create issue memory
    #                     memory_id = f"issue_{conversation_id}_{hashlib.md5(issue.encode()).hexdigest()[:8]}"
    #                     memory = MemoryEntry(
    #                         id=memory_id,
    #                         tenant_id=tenant_id,
    #                         user_id=user_id,
    #                         type=MemoryType.ISSUE,
    #                         content=issue,
    #                         metadata={
    #                             "source_conversation": conversation_id,
    #                             "extracted_at": time.time()
    #                         }
    #                     )
    #                     await self.add_memory(memory)
    #     except:
    #         pass
        
    #     # Extract important facts
    #     facts_prompt = [
    #         {"role": "system", "content": "Extract important facts about the user from this conversation as a JSON array."},
    #         {"role": "user", "content": f"Extract important facts from this conversation:\n{conversation_text}"}
    #     ]
    #     facts_json = await self.llm.generate_response(facts_prompt)
        
    #     try:
    #         facts = json.loads(facts_json)
    #         if isinstance(facts, list):
    #             for fact in facts:
    #                 if isinstance(fact, str) and fact.strip():
    #                     # Create fact memory
    #                     memory_id = f"fact_{conversation_id}_{hashlib.md5(fact.encode()).hexdigest()[:8]}"
    #                     memory = MemoryEntry(
    #                         id=memory_id,
    #                         tenant_id=tenant_id,
    #                         user_id=user_id,
    #                         type=MemoryType.FACT,
    #                         content=fact,
    #                         metadata={
    #                             "source_conversation": conversation_id,
    #                             "extracted_at": time.time()
    #                         }
    #                     )
    #                     await self.add_memory(memory)
    #     except:
    #         pass
        
    #     # Also store the conversation summary as a memory
    #     summary_memory_id = f"summary_{conversation_id}"
    #     summary_memory = MemoryEntry(
    #         id=summary_memory_id,
    #         tenant_id=tenant_id,
    #         user_id=user_id,
    #         type=MemoryType.CONVERSATION,
    #         content=summary.detailed_summary,
    #         metadata={
    #             "conversation_id": conversation_id,
    #             "brief_summary": summary.brief_summary,
    #             "key_points": summary.key_points,
    #             "sentiment": summary.sentiment,
    #             "entities": summary.entities
    #         }
    #     )
    #     await self.add_memory(summary_memory)
    
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
        
        Args:
            conversation_id: The conversation ID
            tenant_id: The tenant ID
            user_id: The user ID
            messages: The conversation messages
            summary: The conversation summary
        """
        # Convert messages to a single string for analysis
        conversation_text = "\n".join([
            f"{msg['role'].upper()}: {msg['content']}"
            for msg in messages
        ])
        
        try:
            # Extract user preferences
            preferences_prompt = [
                {"role": "system", "content": "Extraia as preferências do usuário desta conversa como um array JSON. Inclua apenas preferências claras e objetivas."},
                {"role": "user", "content": f"Extrair preferências desta conversa:\n{conversation_text}"}
            ]
            
            # CORREÇÃO: Tratar resposta em tupla
            preferences_response = await self.llm.generate_response(preferences_prompt)
            
            # Handle tuple response
            if isinstance(preferences_response, tuple):
                preferences_json = preferences_response[0] if preferences_response else "[]"
            else:
                preferences_json = preferences_response
            
            preferences_json = str(preferences_json).strip() if preferences_json else "[]"
            
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
            except json.JSONDecodeError as e:
                logging.warning(f"Erro ao parsear preferências JSON: {e}")
            except Exception as e:
                logging.error(f"Erro ao processar preferências: {e}")
            
            # Extract issues/problems
            issues_prompt = [
                {"role": "system", "content": "Extraia problemas, questões ou reclamações do usuário desta conversa como um array JSON."},
                {"role": "user", "content": f"Extrair problemas desta conversa:\n{conversation_text}"}
            ]
            
            issues_response = await self.llm.generate_response(issues_prompt)
            
            # Handle tuple response
            if isinstance(issues_response, tuple):
                issues_json = issues_response[0] if issues_response else "[]"
            else:
                issues_json = issues_response
            
            issues_json = str(issues_json).strip() if issues_json else "[]"
            
            try:
                issues = json.loads(issues_json)
                if isinstance(issues, list):
                    for issue in issues:
                        if isinstance(issue, str) and issue.strip():
                            # Create issue memory
                            memory_id = f"issue_{conversation_id}_{hashlib.md5(issue.encode()).hexdigest()[:8]}"
                            memory = MemoryEntry(
                                id=memory_id,
                                tenant_id=tenant_id,
                                user_id=user_id,
                                type=MemoryType.ISSUE,
                                content=issue,
                                metadata={
                                    "source_conversation": conversation_id,
                                    "extracted_at": time.time()
                                }
                            )
                            await self.add_memory(memory)
            except json.JSONDecodeError as e:
                logging.warning(f"Erro ao parsear issues JSON: {e}")
            except Exception as e:
                logging.error(f"Erro ao processar issues: {e}")
            
            # Extract important facts
            facts_prompt = [
                {"role": "system", "content": "Extraia fatos importantes sobre o usuário desta conversa como um array JSON."},
                {"role": "user", "content": f"Extrair fatos importantes desta conversa:\n{conversation_text}"}
            ]
            
            facts_response = await self.llm.generate_response(facts_prompt)
            
            # Handle tuple response
            if isinstance(facts_response, tuple):
                facts_json = facts_response[0] if facts_response else "[]"
            else:
                facts_json = facts_response
            
            facts_json = str(facts_json).strip() if facts_json else "[]"
            
            try:
                facts = json.loads(facts_json)
                if isinstance(facts, list):
                    for fact in facts:
                        if isinstance(fact, str) and fact.strip():
                            # Create fact memory
                            memory_id = f"fact_{conversation_id}_{hashlib.md5(fact.encode()).hexdigest()[:8]}"
                            memory = MemoryEntry(
                                id=memory_id,
                                tenant_id=tenant_id,
                                user_id=user_id,
                                type=MemoryType.FACT,
                                content=fact,
                                metadata={
                                    "source_conversation": conversation_id,
                                    "extracted_at": time.time()
                                }
                            )
                            await self.add_memory(memory)
            except json.JSONDecodeError as e:
                logging.warning(f"Erro ao parsear facts JSON: {e}")
            except Exception as e:
                logging.error(f"Erro ao processar facts: {e}")
            
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
            
            logging.info(f"Memórias extraídas e armazenadas para conversa {conversation_id}")
            
        except Exception as e:
            logging.error(f"Erro geral ao extrair memórias da conversa {conversation_id}: {e}")
            import traceback
            logging.error(f"Stack trace: {traceback.format_exc()}")
    
    async def _get_embedding(self, text: str) -> List[float]:
        """
        Gets an embedding vector for the text.
        
        Args:
            text: The text to embed
            
        Returns:
            List of floating point values representing the embedding
        """
        # In a real implementation, this would call an embedding model
        # For now, we'll use a simple placeholder
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
                        "input": text[:8000]  # Truncate to avoid token limits
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
    
    def _calculate_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """
        Calculates the cosine similarity between two vectors.
        
        Args:
            vec1: First vector
            vec2: Second vector
            
        Returns:
            Similarity score between 0 and 1
        """
        if len(vec1) != len(vec2):
            return 0
        
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        magnitude1 = sum(a * a for a in vec1) ** 0.5
        magnitude2 = sum(b * b for b in vec2) ** 0.5
        
        if magnitude1 * magnitude2 == 0:
            return 0
        
        return dot_product / (magnitude1 * magnitude2)
    
    async def clean_old_memories(self, tenant_id: Optional[str] = None, days_threshold: int = 90) -> int:
        """
        Cleans up old, rarely accessed memories.
        
        Args:
            tenant_id: Optional tenant ID to limit cleaning
            days_threshold: Age threshold in days
            
        Returns:
            Number of memories removed
        """
        timestamp_threshold = time.time() - (days_threshold * 24 * 60 * 60)
        
        # In a real implementation, this would delete from the vector DB
        if self.vector_db_url:
            try:
                params = {"timestamp_threshold": timestamp_threshold}
                if tenant_id:
                    params["tenant_id"] = tenant_id
                
                async with httpx.AsyncClient() as client:
                    response = await client.delete(
                        f"{self.vector_db_url}/memories/clean",
                        params=params,
                        timeout=30.0
                    )
                    response.raise_for_status()
                    return response.json()["removed_count"]
            except Exception as e:
                print(f"Error cleaning memories from vector database: {e}")
        
        # In-memory fallback
        if tenant_id:
            old_count = len(self._memory_entries)
            self._memory_entries = [
                entry for entry in self._memory_entries
                if not (entry.tenant_id == tenant_id and entry.last_accessed < timestamp_threshold)
            ]
            return old_count - len(self._memory_entries)
        else:
            old_count = len(self._memory_entries)
            self._memory_entries = [
                entry for entry in self._memory_entries
                if entry.last_accessed >= timestamp_threshold
            ]
            return old_count - len(self._memory_entries)