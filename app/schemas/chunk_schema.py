from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict


class ChunkBase(BaseModel):
    """
    Common fields for chunks (without DB-only fields).
    """

    document_id: int
    document_owner_id: int

    content: str
    chunk_index: int
    page_number: Optional[int] = None

    char_count: int
    token_count: Optional[int] = None


class ChunkInDB(ChunkBase):
    """
    Full chunk representation returned from DB / API.
    """

    id: int

    embedding: Optional[List[float]] = None
    embedding_model: Optional[str] = None
    embedding_dim: Optional[int] = None

    is_deleted: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
