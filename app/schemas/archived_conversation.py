from datetime import datetime
from typing import Dict, List, Optional, Any
from pydantic import BaseModel

class ArchivedConversationBase(BaseModel):
    conversation_id: str
    tenant_id: str
    user_id: str
    message_count: int
    archive_reason: Optional[str] = None

class ArchivedConversationCreate(ArchivedConversationBase):
    history: List[Dict[str, Any]]
    meta_data: Optional[Dict[str, Any]] = None

class ArchivedConversation(ArchivedConversationBase):
    id: int
    history: List[Dict[str, Any]]
    meta_data: Optional[Dict[str, Any]] = None
    archived_at: datetime
    created_at: datetime

    class Config:
        orm_mode = True
        
class PaginatedArchivedConversations(BaseModel):
    total: int
    items: List[ArchivedConversation]
    page: int
    pages: int
    filters: Optional[Dict[str, Any]] = None