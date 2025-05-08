# Create a new file at app/services/memory.py

from enum import Enum
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timedelta
import time
import json
import hashlib
import asyncio
from pydantic import BaseModel
import httpx

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
    
    def __init__(self, llm_service, db_connection_string=None, vector_db_url=None):
        self.llm = llm_service
        self.db_url = db_connection_string
        self.vector_db_url = vector_db_url
        
        # In-memory fallback if no vector DB is configured
        self._memory_entries = []
        self._summaries = []
    
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
        
        if self.vector_db_url:
            # Store in vector database
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
        
        if self.vector_db_url:
            # Generate embedding for the query
            query_embedding = await self._get_embedding(query) # TODO verificar essa lógica
            # Query vector database
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
                # Fall back to in-memory
        
        # In-memory fallback using simple dot product similarity
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
        
        # Generate brief summary (1-2 sentences)
        brief_summary_prompt = [
            {"role": "system", "content": "Você é especialista em resumir conversas em 1 ou 2 frases, capturando a essência."},
            {"role": "user", "content": f"Resuma esta conversa em 1-2 frases:\n{conversation_text}"}
        ]
        brief_summary = await self.llm.generate_response(brief_summary_prompt)
        
        # Generate detailed summary (paragraph)
        detailed_summary_prompt = [
            {"role": "system", "content": "Você é especialista em resumir conversas em um parágrafo detalhado, porém conciso e objetivo."},
            {"role": "user", "content": f"Resuma esta conversa em um parágrafo detalhado:\n{conversation_text}"}
        ]
        detailed_summary = await self.llm.generate_response(detailed_summary_prompt)
        
        # Extract key points
        key_points_prompt = [
            {"role": "system", "content": "Você é um especialista em extrair pontos-chave de conversas."},
            {"role": "user", "content": f"Extraia 3 a 5 pontos-chave desta conversa como um JSON array:\n{conversation_text}"}
        ]
        key_points_json = await self.llm.generate_response(key_points_prompt)
        
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
        entities_json = await self.llm.generate_response(entities_prompt)
        
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
        sentiment = await self.llm.generate_response(sentiment_prompt)
        
        # Create and return summary
        summary = ConversationSummary(
            conversation_id=conversation_id,
            tenant_id=tenant_id,
            user_id=user_id,
            brief_summary=brief_summary,
            detailed_summary=detailed_summary,
            key_points=key_points,
            entities=entities,
            sentiment=sentiment.strip().lower(),
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
        
        # Extract issues/problems
        issues_prompt = [
            {"role": "system", "content": "Extract user issues, problems or complaints from this conversation as a JSON array."},
            {"role": "user", "content": f"Extract issues from this conversation:\n{conversation_text}"}
        ]
        issues_json = await self.llm.generate_response(issues_prompt)
        
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
        except:
            pass
        
        # Extract important facts
        facts_prompt = [
            {"role": "system", "content": "Extract important facts about the user from this conversation as a JSON array."},
            {"role": "user", "content": f"Extract important facts from this conversation:\n{conversation_text}"}
        ]
        facts_json = await self.llm.generate_response(facts_prompt)
        
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
        except:
            pass
        
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