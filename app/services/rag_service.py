from __future__ import annotations

import logging
from typing import List, Optional, Sequence

import anthropic
from langchain_core.prompts import ChatPromptTemplate
from openai import OpenAI

from app.core.config import settings
from app.services.retrieval_service import RetrievalHit, semantic_search

logger = logging.getLogger(__name__)


def _format_history(history: Sequence) -> str:
    if not history:
        return ""
    lines = []
    for msg in history:
        role = getattr(msg, "role", "user")
        content = getattr(msg, "content", "")
        lines.append(f"{role}: {content}")
    return "\n".join(lines)


def _build_prompt_messages(question: str, contexts: List[RetrievalHit], history: Sequence | None = None):
    system_prompt = (
        "You are an assistant that answers questions based on provided context chunks.\n"
        "Use only the information in the context. If unsure, say you don't know.\n"
        "Keep answers concise and cite relevant chunk indices when helpful."
    )

    formatted_chunks = []
    for idx, hit in enumerate(contexts, start=1):
        formatted_chunks.append(f"[{idx}] (score={hit.score:.3f}) {hit.text}")
    context_block = "\n".join(formatted_chunks) or "No context available."

    history_block = _format_history(history or [])

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", system_prompt),
            (
                "user",
                "Context:\n{context}\n\nHistory:\n{history}\n\nQuestion: {question}\nAnswer:",
            ),
        ]
    )
    messages = prompt.format_messages(context=context_block, history=history_block, question=question)
    # Convert to OpenAI/Anthropic style payload and normalize role names
    normalized = []
    for m in messages:
        role = m.type
        if role == "human":
            role = "user"
        normalized.append({"role": role, "content": m.content})
    return normalized


def _truncate_contexts(contexts: List[RetrievalHit], max_chars: int) -> List[RetrievalHit]:
    """Trim contexts to a character budget, preserving order."""
    kept = []
    total = 0
    for hit in contexts:
        text = hit.text or ""
        extra = len(text)
        if total + extra > max_chars:
            break
        kept.append(hit)
        total += extra
    return kept


def answer_question(
    question: str,
    *,
    top_k: int = 4,
    score_threshold: Optional[float] = None,
    use_mmr: bool = True,
    mmr_lambda: float = 0.5,
    max_context_chars: int = 6000,
    model: Optional[str] = None,
    filters=None,
    history: Sequence | None = None,
    max_history_messages: int = 10,
) -> tuple[str, List[RetrievalHit], str]:
    """
    Retrieve relevant chunks and generate an answer with the chosen LLM.
    Returns (answer, contexts_used, model_name).
    """
    search_result = semantic_search(
        query=question,
        top_k=top_k,
        score_threshold=score_threshold,
        use_mmr=use_mmr,
        mmr_lambda=mmr_lambda,
        filters=filters,
    )

    contexts = _truncate_contexts(search_result.hits, max_context_chars)

    trimmed_history = list(history or [])[-max_history_messages:] if max_history_messages else []
    messages = _build_prompt_messages(question, contexts, trimmed_history)

    model_name = model or settings.LLM_MODEL
    lower_model = model_name.lower()

    if "claude" in lower_model:
        answer = _call_claude_chat(model_name, messages)
    else:
        answer = _call_openai_chat(model_name, messages, stream=False)

    return answer, contexts, model_name


def stream_answer(
    question: str,
    *,
    top_k: int = 4,
    score_threshold: Optional[float] = None,
    use_mmr: bool = True,
    mmr_lambda: float = 0.5,
    max_context_chars: int = 6000,
    model: Optional[str] = None,
    filters=None,
    history: Sequence | None = None,
    max_history_messages: int = 10,
):
    """
    Stream tokens for OpenAI models. Returns generator and contexts, model.
    """
    search_result = semantic_search(
        query=question,
        top_k=top_k,
        score_threshold=score_threshold,
        use_mmr=use_mmr,
        mmr_lambda=mmr_lambda,
        filters=filters,
    )

    contexts = _truncate_contexts(search_result.hits, max_context_chars)
    trimmed_history = list(history or [])[-max_history_messages:] if max_history_messages else []
    messages = _build_prompt_messages(question, contexts, trimmed_history)

    model_name = model or settings.LLM_MODEL
    if "claude" in model_name.lower():
        # Claude streaming not implemented; fallback to non-stream answer
        answer = _call_claude_chat(model_name, messages)
        return answer, contexts, model_name

    token_gen = _call_openai_chat(model_name, messages, stream=True)
    return token_gen, contexts, model_name


def _call_openai_chat(model_name: str, messages: List[dict], stream: bool = False):
    client = OpenAI(api_key=settings.OPENAI_API_KEY)
    if stream:
        def token_generator():
            completion = client.chat.completions.create(
                model=model_name,
                messages=messages,
                temperature=0.2,
                stream=True,
            )
            for chunk in completion:
                delta = chunk.choices[0].delta.content
                if delta:
                    yield delta

        return token_generator()

    response = client.chat.completions.create(
        model=model_name,
        messages=messages,
        temperature=0.2,
    )
    return response.choices[0].message.content or ""


def _call_claude_chat(model_name: str, messages: List[dict]) -> str:
    api_key = settings.ANTHROPIC_API_KEY or ""
    client = anthropic.Anthropic(api_key=api_key)
    # Anthropic expects messages with role user/assistant; ensure first is system -> convert to meta
    converted = []
    system_content = None
    for msg in messages:
        role = msg.get("role")
        content = msg.get("content") or ""
        if role == "system":
            system_content = content
        else:
            converted.append({"role": role, "content": content})

    response = client.messages.create(
        model=model_name,
        max_tokens=512,
        messages=converted,
        system=system_content,
        temperature=0.2,
    )
    # Anthropic returns list of content blocks
    parts = response.content or []
    text_parts = [getattr(p, "text", "") for p in parts]
    return "\n".join([t for t in text_parts if t])
