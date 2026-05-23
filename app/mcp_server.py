"""MCP server exposing the document processor as AI-callable tools."""
from __future__ import annotations

import json
import logging
import sys
from typing import Optional

from mcp.server.fastmcp import FastMCP

from app.core.config import settings  # noqa: F401 — triggers env/settings init

# MCP uses stdio for the protocol — redirect all logging to stderr so it
# never corrupts the stdout channel that Claude Desktop reads from.
logging.basicConfig(stream=sys.stderr)
for _handler in logging.root.handlers:
    _handler.stream = sys.stderr  # type: ignore[attr-defined]


mcp = FastMCP(
    "intelligent-doc-processor",
    instructions=(
        "AI document processing server. "
        "Use search_documents to find relevant chunks, ask_document to get RAG answers, "
        "list_documents to see all files, and get_document_info for document details."
    ),
)


@mcp.tool()
def search_documents(
    query: str,
    top_k: int = 5,
    score_threshold: Optional[float] = None,
    document_id: Optional[int] = None,
) -> str:
    """Search documents using semantic similarity.

    Args:
        query: The search query text.
        top_k: Number of top results to return (default 5).
        score_threshold: Minimum similarity score between 0 and 1 (optional).
        document_id: Restrict search to a specific document by ID (optional).
    """
    from app.services.retrieval_service import semantic_search

    filters: Optional[dict] = {"document_id": document_id} if document_id else None

    result = semantic_search(
        query=query,
        top_k=top_k,
        score_threshold=score_threshold,
        filters=filters,
    )

    if not result.hits:
        return "No relevant documents found."

    parts = []
    for i, hit in enumerate(result.hits, 1):
        doc_name = (
            hit.payload.get("document_name")
            or hit.payload.get("document_original_filename")
            or hit.payload.get("file_name")
            or "Unknown"
        )
        parts.append(f"[{i}] score={hit.score:.3f} | {doc_name}\n{hit.text}")

    return "\n\n---\n\n".join(parts)


@mcp.tool()
def ask_document(
    question: str,
    document_id: Optional[int] = None,
    model: Optional[str] = None,
    top_k: int = 4,
) -> str:
    """Ask a question and get an AI answer grounded in your documents.

    Args:
        question: The question to answer.
        document_id: Limit context to a specific document (optional).
        model: LLM to use, e.g. 'gpt-4o', 'claude-sonnet-4-6' (uses server default if omitted).
        top_k: Number of context chunks to retrieve (default 4).
    """
    from app.services.rag_service import answer_question

    filters: Optional[dict] = {"document_id": document_id} if document_id else None

    answer, contexts, model_used = answer_question(
        question=question,
        top_k=top_k,
        model=model,
        filters=filters,
    )

    sources: list[str] = []
    seen: set[str] = set()
    for hit in contexts:
        name = (
            hit.payload.get("document_name")
            or hit.payload.get("document_original_filename")
            or "Unknown"
        )
        if name not in seen:
            sources.append(name)
            seen.add(name)

    lines = [f"Answer: {answer}"]
    if sources:
        lines.append(f"Sources: {', '.join(sources)}")
    lines.append(f"Model: {model_used}")
    return "\n".join(lines)


@mcp.tool()
def list_documents(skip: int = 0, limit: int = 20) -> str:
    """List all uploaded documents with their processing status.

    Args:
        skip: Number of documents to skip for pagination (default 0).
        limit: Maximum documents to return, capped at 100 (default 20).
    """
    from app.core.database import SessionLocal
    from app.models.document_model import Document

    limit = min(limit, 100)
    db = SessionLocal()
    try:
        total = db.query(Document).filter(Document.is_deleted.is_(False)).count()
        docs = (
            db.query(Document)
            .filter(Document.is_deleted.is_(False))
            .order_by(Document.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )
    finally:
        db.close()

    if not docs:
        return "No documents found."

    lines = [f"Total: {total} document(s) — showing {len(docs)}\n"]
    for doc in docs:
        lines.append(
            f"ID={doc.id} | {doc.name} | status={doc.status} "
            f"| {doc.content_type} | {doc.file_size} bytes | created={doc.created_at}"
        )
    return "\n".join(lines)


@mcp.tool()
def get_document_info(document_id: int) -> str:
    """Get detailed metadata for a specific document.

    Args:
        document_id: The numeric document ID.
    """
    from app.core.database import SessionLocal
    from app.models.document_model import Document

    db = SessionLocal()
    try:
        doc = (
            db.query(Document)
            .filter(Document.id == document_id, Document.is_deleted.is_(False))
            .first()
        )
    finally:
        db.close()

    if not doc:
        return f"Document {document_id} not found."

    info = {
        "id": doc.id,
        "name": doc.name,
        "original_filename": doc.original_filename,
        "content_type": doc.content_type,
        "file_size": doc.file_size,
        "status": doc.status,
        "processing_step": doc.processing_step,
        "processing_progress": doc.processing_progress,
        "error_count": doc.error_count,
        "last_error": doc.last_error,
        "created_at": str(doc.created_at),
        "updated_at": str(doc.updated_at),
    }
    return json.dumps(info, indent=2)


if __name__ == "__main__":
    mcp.run()
