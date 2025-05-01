from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class Tenant(BaseModel):
    id: int
    name: str
    description: Optional[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime