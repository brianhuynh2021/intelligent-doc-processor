from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.schemas.search_schema import SearchFilter


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1)
    top_k: int = Field(4, ge=1, le=10)
    score_threshold: Optional[float] = Field(None, ge=-1.0, le=1.0)
    use_mmr: bool = True
    mmr_lambda: float = Field(0.5, ge=0.0, le=1.0)
    max_context_chars: int = Field(6000, ge=500, le=20000)
    model: Optional[str] = None  # override default LLM model
    filters: Optional[SearchFilter] = None
    session_id: Optional[int] = None
    stream: bool = False
    max_history_messages: int = Field(10, ge=0, le=50)


class ContextChunk(BaseModel):
    text: str
    score: float
    metadata: Dict[str, Any]


class ChatResponse(BaseModel):
    answer: str
    model: str
    contexts: List[ContextChunk]
    session_id: int
    session_key: str
