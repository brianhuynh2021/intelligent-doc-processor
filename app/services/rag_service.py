from __future__ import annotations

import unicodedata
from typing import TYPE_CHECKING, Any, List, Optional, Sequence

from langchain_core.prompts import ChatPromptTemplate

from app.core.config import settings
from app.core.errors import DependencyMissingError, UpstreamServiceError
from app.core.logging import get_logger
from app.core.retry import retry_transient
from app.services.retrieval_service import RetrievalHit, semantic_search

logger = get_logger(__name__)

if TYPE_CHECKING:  # pragma: no cover
    import anthropic
    from openai import OpenAI

_openai_client: "OpenAI | None" = None
_anthropic_client: "anthropic.Anthropic | None" = None
_gemini_module: Any | None = None

_PROVIDER_ALIASES = {
    "openai": "openai",
    "oai": "openai",
    "anthropic": "anthropic",
    "claude": "anthropic",
    "gemini": "gemini",
    "google": "gemini",
}


def _normalize_model_name(model: Optional[str]) -> str:
    if not model:
        return settings.LLM_MODEL
    model_name = model.strip()
    if not model_name:
        return settings.LLM_MODEL
    if model_name.lower().startswith("auto"):
        return settings.LLM_MODEL
    return model_name


def _resolve_provider(model_name: str) -> tuple[str, str]:
    if ":" in model_name:
        prefix, rest = model_name.split(":", 1)
        provider = _PROVIDER_ALIASES.get(prefix.strip().lower())
        if provider:
            cleaned = rest.strip() or model_name
            return provider, cleaned
    if "/" in model_name:
        prefix, rest = model_name.split("/", 1)
        provider = _PROVIDER_ALIASES.get(prefix.strip().lower())
        if provider:
            cleaned = rest.strip() or model_name
            return provider, cleaned
    lower_model = model_name.lower()
    if "claude" in lower_model or "anthropic" in lower_model:
        return "anthropic", model_name
    if "gemini" in lower_model:
        return "gemini", model_name
    return "openai", model_name


def _format_history(history: Sequence) -> str:
    if not history:
        return ""
    lines = []
    for msg in history:
        role = getattr(msg, "role", "user")
        content = getattr(msg, "content", "")
        lines.append(f"{role}: {content}")
    return "\n".join(lines)


def _strip_accents(text: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c)
    )


def _is_document_name_question(question: str) -> bool:
    q = _strip_accents(question).lower()
    keywords = (
        "ten tai lieu",
        "tai lieu nay la gi",
        "tai lieu nay ten gi",
        "ten file",
        "file name",
        "document name",
        "name of the document",
        "document title",
    )
    return any(k in q for k in keywords)


def _collect_doc_names(contexts: List[RetrievalHit]) -> List[str]:
    names = []
    seen = set()
    for hit in contexts:
        payload = hit.payload or {}
        for key in (
            "document_name",
            "document_original_filename",
            "file_name",
            "filename",
            "name",
        ):
            value = payload.get(key)
            if value and value not in seen:
                names.append(value)
                seen.add(value)
                break
    return names


def _lookup_doc_names_by_ids(document_ids: List[int]) -> List[str]:
    if not document_ids:
        return []
    unique_ids = []
    seen = set()
    for doc_id in document_ids:
        if doc_id not in seen:
            unique_ids.append(doc_id)
            seen.add(doc_id)
    try:
        from app.core.database import SessionLocal
        from app.models.document_model import Document
    except Exception:
        return []

    db = SessionLocal()
    try:
        rows = (
            db.query(Document.id, Document.name, Document.original_filename)
            .filter(Document.id.in_(unique_ids))
            .all()
        )
    finally:
        db.close()

    name_by_id = {row[0]: row[1] or row[2] for row in rows}
    return [name_by_id.get(doc_id) for doc_id in unique_ids if name_by_id.get(doc_id)]


def _maybe_answer_document_name(
    question: str, contexts: List[RetrievalHit], filters
) -> Optional[str]:
    if not _is_document_name_question(question):
        return None

    names = _collect_doc_names(contexts)
    if not names:
        doc_ids: List[int] = []
        if filters is not None and getattr(filters, "document_id", None) is not None:
            doc_ids.append(int(filters.document_id))
        else:
            for hit in contexts:
                doc_id = (hit.payload or {}).get("document_id")
                if isinstance(doc_id, int):
                    doc_ids.append(doc_id)
                elif isinstance(doc_id, str) and doc_id.isdigit():
                    doc_ids.append(int(doc_id))
        names = _lookup_doc_names_by_ids(doc_ids)

    if not names:
        return None
    if len(names) == 1:
        return f"Document name: {names[0]}."
    return "Document names: " + ", ".join(names) + "."


def _build_prompt_messages(
    question: str, contexts: List[RetrievalHit], history: Sequence | None = None
):
    system_prompt = (
        "You are an assistant that answers questions based on provided context chunks.\n"
        "Use only the information in the context. If unsure, say you don't know.\n"
        "Keep answers concise and cite relevant chunk indices when helpful."
    )

    formatted_chunks = []
    for idx, hit in enumerate(contexts, start=1):
        doc_name = (
            hit.payload.get("document_name")
            or hit.payload.get("document_original_filename")
            or hit.payload.get("file_name")
        )
        source_info = f", doc={doc_name}" if doc_name else ""
        formatted_chunks.append(
            f"[{idx}] (score={hit.score:.3f}{source_info}) {hit.text}"
        )
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
    messages = prompt.format_messages(
        context=context_block, history=history_block, question=question
    )
    # Convert to OpenAI/Anthropic style payload and normalize role names
    normalized = []
    for m in messages:
        role = m.type
        if role == "human":
            role = "user"
        normalized.append({"role": role, "content": m.content})
    return normalized


def _truncate_contexts(
    contexts: List[RetrievalHit], max_chars: int
) -> List[RetrievalHit]:
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

    trimmed_history = (
        list(history or [])[-max_history_messages:] if max_history_messages else []
    )
    messages = _build_prompt_messages(question, contexts, trimmed_history)

    maybe_answer = _maybe_answer_document_name(question, contexts, filters)
    if maybe_answer:
        model_name = _normalize_model_name(model)
        return maybe_answer, contexts, model_name

    model_name = _normalize_model_name(model)
    provider, provider_model = _resolve_provider(model_name)

    if provider == "anthropic":
        answer = _call_claude_chat(provider_model, messages)
    elif provider == "gemini":
        answer = _call_gemini_chat(provider_model, messages)
    else:
        answer = _call_openai_chat(provider_model, messages, stream=False)

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
    trimmed_history = (
        list(history or [])[-max_history_messages:] if max_history_messages else []
    )
    messages = _build_prompt_messages(question, contexts, trimmed_history)

    maybe_answer = _maybe_answer_document_name(question, contexts, filters)
    if maybe_answer:
        model_name = _normalize_model_name(model)
        return maybe_answer, contexts, model_name

    model_name = _normalize_model_name(model)
    provider, provider_model = _resolve_provider(model_name)
    if provider == "anthropic":
        # Claude streaming not implemented; fallback to non-stream answer
        answer = _call_claude_chat(provider_model, messages)
        return answer, contexts, model_name
    if provider == "gemini":
        # Gemini streaming not implemented; fallback to non-stream answer
        answer = _call_gemini_chat(provider_model, messages)
        return answer, contexts, model_name

    token_gen = _call_openai_chat(provider_model, messages, stream=True)
    return token_gen, contexts, model_name


def _call_openai_chat(model_name: str, messages: List[dict], stream: bool = False):
    client = _get_openai_client()
    if stream:

        def token_generator():
            try:
                completion = _openai_create_chat_completion(
                    client=client,
                    model=model_name,
                    messages=messages,
                    stream=True,
                )
            except Exception as exc:
                raise UpstreamServiceError(
                    "LLM provider failed",
                    details=[{"provider": "openai", "model": model_name}],
                ) from exc

            for chunk in completion:
                delta = chunk.choices[0].delta.content
                if delta:
                    yield delta

        return token_generator()

    try:
        response = _openai_create_chat_completion(
            client=client,
            model=model_name,
            messages=messages,
            stream=False,
        )
        return response.choices[0].message.content or ""
    except Exception as exc:
        raise UpstreamServiceError(
            "LLM provider failed",
            details=[{"provider": "openai", "model": model_name}],
        ) from exc


def _call_claude_chat(model_name: str, messages: List[dict]) -> str:
    client = _get_anthropic_client()
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

    try:
        response = _anthropic_create_message(
            client=client,
            model=model_name,
            system=system_content,
            messages=converted,
        )
    except Exception as exc:
        raise UpstreamServiceError(
            "LLM provider failed",
            details=[{"provider": "anthropic", "model": model_name}],
        ) from exc

    # Anthropic returns list of content blocks
    parts = response.content or []
    text_parts = [getattr(p, "text", "") for p in parts]
    return "\n".join([t for t in text_parts if t])


def _call_gemini_chat(model_name: str, messages: List[dict]) -> str:
    genai = _get_gemini_module()
    prompt = _messages_to_prompt(messages)
    try:
        model = genai.GenerativeModel(model_name)
        response = _gemini_generate_content(model=model, prompt=prompt)
    except Exception as exc:
        raise UpstreamServiceError(
            "LLM provider failed",
            details=[{"provider": "gemini", "model": model_name}],
        ) from exc
    return _extract_gemini_text(response)


def _messages_to_prompt(messages: List[dict]) -> str:
    lines = []
    for msg in messages:
        role = (msg.get("role") or "user").lower()
        if role == "assistant":
            label = "Assistant"
        elif role == "system":
            label = "System"
        else:
            label = "User"
        content = msg.get("content") or ""
        lines.append(f"{label}: {content}")
    return "\n".join(lines)


def _extract_gemini_text(response: Any) -> str:
    text = getattr(response, "text", None)
    if text:
        return text
    candidates = getattr(response, "candidates", None) or []
    parts = []
    for candidate in candidates:
        content = getattr(candidate, "content", None)
        for part in getattr(content, "parts", []) or []:
            part_text = getattr(part, "text", None)
            if part_text:
                parts.append(part_text)
    return "\n".join(parts)


def _get_openai_client() -> "OpenAI":
    global _openai_client
    if _openai_client is None:
        try:
            from openai import OpenAI  # type: ignore
        except ModuleNotFoundError as exc:
            raise DependencyMissingError(
                "openai is required for OpenAI models",
                details=[{"dependency": "openai"}],
            ) from exc
        _openai_client = OpenAI(api_key=settings.OPENAI_API_KEY)
    return _openai_client


def _get_anthropic_client():
    global _anthropic_client
    if _anthropic_client is None:
        try:
            import anthropic  # type: ignore
        except ModuleNotFoundError as exc:
            raise DependencyMissingError(
                "anthropic is required for Claude models",
                details=[{"dependency": "anthropic"}],
            ) from exc
        api_key = settings.ANTHROPIC_API_KEY or ""
        _anthropic_client = anthropic.Anthropic(api_key=api_key)
    return _anthropic_client


def _get_gemini_module():
    global _gemini_module
    if _gemini_module is None:
        try:
            import google.generativeai as genai  # type: ignore
        except ModuleNotFoundError as exc:
            raise DependencyMissingError(
                "google-generativeai is required for Gemini models",
                details=[{"dependency": "google-generativeai"}],
            ) from exc
        api_key = settings.GEMINI_API_KEY or ""
        if not api_key:
            raise DependencyMissingError(
                "GEMINI_API_KEY is required for Gemini models",
                details=[{"env": "GEMINI_API_KEY", "alt_env": "GOOGLE_API_KEY"}],
            )
        genai.configure(api_key=api_key)
        _gemini_module = genai
    return _gemini_module


@retry_transient
def _openai_create_chat_completion(
    *, client: Any, model: str, messages: List[dict], stream: bool
):
    return client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0.2,
        stream=stream,
    )


@retry_transient
def _anthropic_create_message(
    *, client: Any, model: str, system: str | None, messages: List[dict]
):
    return client.messages.create(
        model=model,
        max_tokens=512,
        messages=messages,
        system=system,
        temperature=0.2,
    )


@retry_transient
def _gemini_generate_content(*, model: Any, prompt: str):
    return model.generate_content(prompt)
