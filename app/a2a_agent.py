"""A2A Agent Executor — exposes doc processor skills to other AI agents."""
from __future__ import annotations

import asyncio

from a2a.server.agent_execution.agent_executor import AgentExecutor
from a2a.server.agent_execution.context import RequestContext
from a2a.server.events.event_queue import EventQueue
from a2a.server.tasks.task_updater import TaskUpdater
from a2a.types.a2a_pb2 import Part


def _extract_text(message) -> str:
    parts = []
    for part in message.parts or []:
        if part.WhichOneof("content") == "text":
            parts.append(part.text)
    return " ".join(parts).strip()


def _text_part(text: str) -> Part:
    p = Part()
    p.text = text
    return p


class DocProcessorAgentExecutor(AgentExecutor):
    """
    A2A agent with two skills:
      - search: prefix message with 'search:' → semantic search
      - ask (default) → RAG Q&A
    """

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        updater = TaskUpdater(
            event_queue=event_queue,
            task_id=context.task_id,
            context_id=context.context_id,
        )
        await updater.start_work()

        try:
            user_text = _extract_text(context.message)
            if not user_text:
                await updater.failed(
                    message=updater.new_agent_message(
                        [_text_part("Empty message received.")]
                    )
                )
                return

            loop = asyncio.get_event_loop()

            if user_text.lower().startswith("search:"):
                query = user_text[7:].strip()
                result = await loop.run_in_executor(None, self._search, query)
            else:
                result = await loop.run_in_executor(None, self._ask, user_text)

            await updater.add_artifact(parts=[_text_part(result)], name="result")
            await updater.complete()

        except Exception as exc:
            await updater.failed(
                message=updater.new_agent_message([_text_part(f"Error: {exc}")])
            )

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        updater = TaskUpdater(
            event_queue=event_queue,
            task_id=context.task_id,
            context_id=context.context_id,
        )
        await updater.cancel()

    # ------------------------------------------------------------------ #
    # Internal skill implementations (sync — called via run_in_executor)  #
    # ------------------------------------------------------------------ #

    def _search(self, query: str) -> str:
        from app.services.retrieval_service import semantic_search

        result = semantic_search(query=query, top_k=5)
        if not result.hits:
            return "No relevant documents found."

        parts = []
        for i, hit in enumerate(result.hits, 1):
            doc_name = (
                hit.payload.get("document_name")
                or hit.payload.get("document_original_filename")
                or "Unknown"
            )
            parts.append(f"[{i}] score={hit.score:.3f} | {doc_name}\n{hit.text}")
        return "\n\n---\n\n".join(parts)

    def _ask(self, question: str) -> str:
        from app.services.rag_service import answer_question

        answer, contexts, model_used = answer_question(question=question, top_k=4)

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
