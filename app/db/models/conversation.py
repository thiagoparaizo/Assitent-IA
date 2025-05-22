# app/models/conversation.py
"""
Modelos relacionados à conversa para evitar importações circulares.
"""

from typing import Dict, List, Optional, Any
import time
from pydantic import BaseModel

class ConversationState(BaseModel):
    """Estado de uma conversa."""
    conversation_id: str
    tenant_id: str
    user_id: str
    current_agent_id: str
    history: List[Dict[str, Any]]
    metadata: Dict[str, Any] = {}
    last_updated: float = 0
    
    class Config:
        from_attributes = True  # Updated from orm_mode

class AgentScore(BaseModel):
    """Represents a score for an agent's ability to handle a conversation."""
    agent_id: str
    score: float
    reason: str
    
    class Config:
        from_attributes = True