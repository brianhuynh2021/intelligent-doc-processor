from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.database import get_db, SessionLocal
from app.schemas.chat_schema import ChatRequest, ChatResponse, ContextChunk
from app.schemas.chat_session_schema import ChatMessageResponse, ChatSessionCreate, ChatSessionResponse
from app.services import chat_service
from app.services.rag_service import answer_question, stream_answer

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/sessions", response_model=ChatSessionResponse)
def create_session(body: ChatSessionCreate, db: Session = Depends(get_db)):
    session = chat_service.create_session(
        db=db,
        name=body.name,
        created_by_user_id=body.created_by_user_id,
    )
    return session


@router.get("/sessions/{session_id}/messages", response_model=list[ChatMessageResponse])
def list_messages(session_id: int, db: Session = Depends(get_db), limit: int = 20):
    session = chat_service.get_session_by_id(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    messages = chat_service.get_messages(db, session_id=session_id, limit=limit)
    return messages


@router.get("/history", response_model=list[ChatMessageResponse])
def get_history(
    session_id: int = Query(..., description="Session ID"),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    session = chat_service.get_session_by_id(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return chat_service.get_messages(db, session_id=session_id, limit=limit)


@router.post("/ask", response_model=ChatResponse)
def ask_question(body: ChatRequest, db: Session = Depends(get_db)):
    # Ensure session
    session = None
    if body.session_id:
        session = chat_service.get_session_by_id(db, body.session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
    else:
        session = chat_service.create_session(db=db)

    history = chat_service.get_messages(
        db=db,
        session_id=session.id,
        limit=body.max_history_messages,
    )

    try:
        if body.stream:
            stream_or_answer, contexts, model_name = stream_answer(
                question=body.question,
                top_k=body.top_k,
                score_threshold=body.score_threshold,
                use_mmr=body.use_mmr,
                mmr_lambda=body.mmr_lambda,
                max_context_chars=body.max_context_chars,
                model=body.model,
                filters=body.filters,
                history=history,
                max_history_messages=body.max_history_messages,
            )

            # stream_or_answer is generator for OpenAI; string for Claude fallback
            if isinstance(stream_or_answer, str):
                answer_text = stream_or_answer
                chat_service.add_message(db, session.id, "user", body.question)
                chat_service.add_message(db, session.id, "assistant", answer_text)
                return ChatResponse(
                    answer=answer_text,
                    model=model_name,
                    contexts=[
                        ContextChunk(text=hit.text or "", score=hit.score, metadata=hit.payload)
                        for hit in contexts
                    ],
                    session_id=session.id,
                    session_key=session.session_key,
                )

            def token_stream():
                chat_service.add_message(db, session.id, "user", body.question)
                collected = []
                for token in stream_or_answer:
                    collected.append(token)
                    yield token
                full_answer = "".join(collected)
                chat_service.add_message(db, session.id, "assistant", full_answer)

            return StreamingResponse(token_stream(), media_type="text/plain")

        answer, contexts, model_name = answer_question(
            question=body.question,
            top_k=body.top_k,
            score_threshold=body.score_threshold,
            use_mmr=body.use_mmr,
            mmr_lambda=body.mmr_lambda,
            max_context_chars=body.max_context_chars,
            model=body.model,
            filters=body.filters,
            history=history,
            max_history_messages=body.max_history_messages,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    # persist
    chat_service.add_message(db, session.id, "user", body.question)
    chat_service.add_message(db, session.id, "assistant", answer)

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
        session_id=session.id,
        session_key=session.session_key,
    )


@router.post("", response_model=ChatResponse)
def chat_alias(body: ChatRequest, db: Session = Depends(get_db)):
    """Alias for /chat/ask"""
    return ask_question(body=body, db=db)


@router.websocket("/ws")
async def chat_websocket(
    websocket: WebSocket,
    session_id: int | None = None,
    top_k: int = 4,
    score_threshold: float | None = None,
    use_mmr: bool = True,
    mmr_lambda: float = 0.5,
    max_context_chars: int = 4000,
    model: str | None = None,
    max_history_messages: int = 10,
):
    await websocket.accept()
    db = SessionLocal()
    try:
        session = None
        if session_id:
            session = chat_service.get_session_by_id(db, session_id)
        if not session:
            session = chat_service.create_session(db=db)

        while True:
            try:
                text = await websocket.receive_text()
            except WebSocketDisconnect:
                break

            history = chat_service.get_messages(db, session_id=session.id, limit=max_history_messages)

            stream_or_answer, contexts, model_name = stream_answer(
                question=text,
                top_k=top_k,
                score_threshold=score_threshold,
                use_mmr=use_mmr,
                mmr_lambda=mmr_lambda,
                max_context_chars=max_context_chars,
                model=model,
                filters=None,
                history=history,
                max_history_messages=max_history_messages,
            )

            chat_service.add_message(db, session.id, "user", text)

            if isinstance(stream_or_answer, str):
                chat_service.add_message(db, session.id, "assistant", stream_or_answer)
                await websocket.send_text(stream_or_answer)
                continue

            collected = []
            async for token in _async_iter(stream_or_answer):
                collected.append(token)
                await websocket.send_text(token)
            full_answer = "".join(collected)
            chat_service.add_message(db, session.id, "assistant", full_answer)

    finally:
        db.close()


async def _async_iter(gen):
    for item in gen:
        yield item
