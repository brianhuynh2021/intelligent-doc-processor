from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


class SearchFilter(BaseModel):
    document_id: Optional[int] = None
    owner_id: Optional[int] = None
    content_type: Optional[str] = None
    created_from: Optional[datetime] = None
    created_to: Optional[datetime] = None

    @field_validator("content_type")
    @classmethod
    def _normalize_content_type(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        return v or None

    @model_validator(mode="after")
    def _validate_date_range(self):
        if (
            self.created_from
            and self.created_to
            and self.created_from > self.created_to
        ):
            raise ValueError("created_from must be <= created_to")
        return self


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1)
    top_k: int = Field(5, ge=1, le=50)
    fetch_k: Optional[int] = Field(None, ge=1, le=200)
    score_threshold: Optional[float] = Field(None, ge=-1.0, le=1.0)
    use_mmr: bool = True
    mmr_lambda: float = Field(0.5, ge=0.0, le=1.0)
    filters: Optional[SearchFilter] = None

    @field_validator("query")
    @classmethod
    def _normalize_query(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("query must not be empty")
        return v

    @model_validator(mode="after")
    def _validate_fetch_k(self):
        if self.fetch_k is not None and self.fetch_k < self.top_k:
            raise ValueError("fetch_k must be >= top_k")
        return self


class SearchResult(BaseModel):
    id: Any
    score: float
    text: Optional[str] = None
    payload: Dict[str, Any]


class SearchResponse(BaseModel):
    results: List[SearchResult]
    used_mmr: bool
    total_candidates: int
