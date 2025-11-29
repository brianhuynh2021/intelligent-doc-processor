from fastapi import APIRouter, HTTPException

from app.schemas.chat_schema import ChatRequest, ChatResponse, ContextChunk
from app.services.rag_service import answer_question

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/ask", response_model=ChatResponse)
def ask_question(body: ChatRequest):
    try:
        answer, contexts, model_name = answer_question(
            question=body.question,
            top_k=body.top_k,
            score_threshold=body.score_threshold,
            use_mmr=body.use_mmr,
            mmr_lambda=body.mmr_lambda,
            max_context_chars=body.max_context_chars,
            model=body.model,
            filters=body.filters,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    return ChatResponse(
        answer=answer or "",
        model=model_name,
        contexts=[
            ContextChunk(
                text=hit.text or "",
                score=hit.score,
                metadata=hit.payload,
            )
            for hit in contexts
        ],
    )
