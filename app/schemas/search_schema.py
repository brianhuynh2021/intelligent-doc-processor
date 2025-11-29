from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class SearchFilter(BaseModel):
    document_id: Optional[int] = None
    owner_id: Optional[int] = None
    content_type: Optional[str] = None
    created_from: Optional[datetime] = None
    created_to: Optional[datetime] = None


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1)
    top_k: int = Field(5, ge=1, le=50)
    fetch_k: Optional[int] = Field(None, ge=1, le=200)
    score_threshold: Optional[float] = Field(None, ge=-1.0, le=1.0)
    use_mmr: bool = True
    mmr_lambda: float = Field(0.5, ge=0.0, le=1.0)
    filters: Optional[SearchFilter] = None


class SearchResult(BaseModel):
    id: Any
    score: float
    text: Optional[str] = None
    payload: Dict[str, Any]


class SearchResponse(BaseModel):
    results: List[SearchResult]
    used_mmr: bool
    total_candidates: int
