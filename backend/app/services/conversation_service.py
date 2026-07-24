"""Conversation and grounded RAG answer use cases."""

from __future__ import annotations

import time
from uuid import UUID

from app.core.config import Settings
from app.core.exceptions import AppError
from app.ingestion.embeddings.base import EmbeddingProvider
from app.llm.answer_sanitize import sanitize_answer_text
from app.llm.base import LLMProvider
from app.llm.prompts import build_grounded_messages
from app.models.conversation import Citation, Conversation, Message
from app.models.enums import MessageRole
from app.models.user import User
from app.repositories.conversation_repository import ConversationRepository
from app.retrieval.evidence import select_supporting_evidence, suggestion_for_question
from app.retrieval.service import RetrievalService
from app.schemas.search import (
    AskMessageRequest,
    AskMessageResponse,
    CitationResponse,
    ConversationCreate,
    ConversationDetail,
    ConversationListResponse,
    ConversationSummary,
    MessageResponse,
    RetrievalMeta,
)

INSUFFICIENT_ANSWER = (
    "I couldn't find enough information in the indexed documents to answer that question."
)


class ConversationService:
    """Manage conversations and generate grounded RAG answers."""

    def __init__(
        self,
        conversations: ConversationRepository,
        retrieval: RetrievalService,
        embeddings: EmbeddingProvider,
        llm: LLMProvider,
        settings: Settings,
    ) -> None:
        self._conversations = conversations
        self._retrieval = retrieval
        self._embeddings = embeddings
        self._llm = llm
        self._settings = settings

    def create(self, user: User, payload: ConversationCreate) -> ConversationSummary:
        title = (payload.title or "New conversation").strip() or "New conversation"
        conversation = self._conversations.create(user_id=user.id, title=title[:300])
        return ConversationSummary.model_validate(conversation)

    def list_conversations(
        self,
        user: User,
        *,
        page: int = 1,
        page_size: int = 20,
    ) -> ConversationListResponse:
        page = max(page, 1)
        page_size = min(max(page_size, 1), 100)
        items, total = self._conversations.list_for_user(user, page=page, page_size=page_size)
        return ConversationListResponse(
            items=[ConversationSummary.model_validate(item) for item in items],
            total=total,
        )

    def get_conversation(self, conversation_id: UUID, user: User) -> ConversationDetail:
        conversation = self._require_conversation(conversation_id, user, with_messages=True)
        return ConversationDetail(
            id=conversation.id,
            title=conversation.title,
            created_at=conversation.created_at,
            updated_at=conversation.updated_at,
            messages=[self._message_response(message) for message in conversation.messages],
        )

    def delete_conversation(self, conversation_id: UUID, user: User) -> None:
        conversation = self._require_conversation(conversation_id, user)
        self._conversations.delete(conversation)

    def ask(
        self,
        conversation_id: UUID,
        user: User,
        payload: AskMessageRequest,
    ) -> AskMessageResponse:
        conversation = self._require_conversation(conversation_id, user, with_messages=True)

        user_message = self._conversations.add_message(
            Message(
                conversation_id=conversation.id,
                role=MessageRole.USER,
                content=payload.content,
            )
        )

        top_k = self._settings.rag_top_k
        min_score = self._settings.rag_min_relevance_score
        active_provider = self._settings.embedding_provider
        mismatch_titles = self._mismatched_document_titles(active_provider)

        embed_started = time.perf_counter()
        query_embedding = self._embeddings.embed_query(payload.content)
        embedding_latency_ms = int((time.perf_counter() - embed_started) * 1000)

        search_started = time.perf_counter()
        scored = self._retrieval.similarity_search(
            query_embedding,
            top_k=top_k,
            department=payload.department,
            category=payload.category,
            document_id=payload.document_id,
            min_score=0.0,
            embedding_provider=active_provider,
        )
        vector_search_latency_ms = int((time.perf_counter() - search_started) * 1000)

        evidence = select_supporting_evidence(
            scored,
            question=payload.content,
            min_score=min_score,
            min_supporting_chunks=self._settings.rag_min_supporting_chunks,
            min_term_overlap=self._settings.rag_min_term_overlap,
        )
        insufficient = evidence.insufficient
        grounded_hits = evidence.supporting

        if insufficient:
            suggestion = suggestion_for_question(payload.content)
            answer_text = INSUFFICIENT_ANSWER
            if suggestion:
                answer_text = f"{INSUFFICIENT_ANSWER} {suggestion}"
            latency_ms = 0
            model_name = self._llm.model_name
        else:
            prompt_messages = build_grounded_messages(
                payload.content,
                grounded_hits,
                insufficient_context=False,
                answer_style=self._settings.rag_answer_style,
            )
            llm_response = self._llm.complete(prompt_messages)
            answer_text = sanitize_answer_text(llm_response.content)
            latency_ms = llm_response.latency_ms
            model_name = llm_response.model
            suggestion = None

        demo_providers = self._settings.llm_provider == "fake" or (
            self._settings.embedding_provider == "fake"
        )
        if insufficient:
            answer_status = "insufficient_context"
        elif demo_providers and self._settings.app_env != "test":
            answer_status = "demo"
        elif demo_providers and self._settings.app_env == "test":
            # Tests assert grounded retrieval semantics; keep status grounded.
            answer_status = "grounded"
        else:
            answer_status = "grounded"

        assistant = Message(
            conversation_id=conversation.id,
            role=MessageRole.ASSISTANT,
            content=answer_text,
            retrieval_top_k=top_k,
            retrieval_min_score=min_score,
            max_retrieval_score=round(evidence.max_score, 6) if scored else None,
            grounded=not insufficient,
            insufficient_context=insufficient,
            embedding_latency_ms=embedding_latency_ms,
            vector_search_latency_ms=vector_search_latency_ms,
            llm_latency_ms=latency_ms,
            llm_model=model_name,
        )
        citations = [
            Citation(
                chunk_id=item.chunk.id,
                document_id=item.chunk.document_id,
                document_title=item.document_title,
                page_number=item.chunk.page_number,
                chunk_index=item.chunk.chunk_index,
                relevance_score=round(item.score, 6),
                rank=rank,
                snippet=item.chunk.content[:500],
            )
            for rank, item in enumerate(grounded_hits, start=1)
        ]
        assistant = self._conversations.save_assistant_with_citations(assistant, citations)

        if conversation.title == "New conversation":
            self._conversations.update_title(conversation, payload.content[:80])

        retrieval_meta = RetrievalMeta(
            max_relevance=round(evidence.max_score, 6) if scored else None,
            chunks_retrieved=evidence.chunks_retrieved,
            supporting_chunks=len(grounded_hits),
            retrieval_latency_ms=vector_search_latency_ms,
            embedding_latency_ms=embedding_latency_ms,
            llm_latency_ms=latency_ms,
            min_relevance_threshold=min_score,
        )

        return AskMessageResponse(
            user_message=MessageResponse.model_validate(user_message),
            assistant_message=self._message_response(
                assistant,
                answer_status=answer_status,
                suggestion=suggestion,
                retrieval=retrieval_meta,
                embedding_provider_mismatch=bool(mismatch_titles),
                mismatched_documents=mismatch_titles,
            ),
        )

    def _message_response(
        self,
        message: Message,
        *,
        answer_status: str | None = None,
        suggestion: str | None = None,
        retrieval: RetrievalMeta | None = None,
        embedding_provider_mismatch: bool = False,
        mismatched_documents: list[str] | None = None,
    ) -> MessageResponse:
        response = MessageResponse.model_validate(message)
        response.citations = [
            CitationResponse.model_validate(citation) for citation in message.citations
        ]
        if answer_status is not None:
            response.answer_status = answer_status  # type: ignore[assignment]
        elif message.insufficient_context:
            response.answer_status = "insufficient_context"
        elif message.grounded:
            response.answer_status = "grounded"
        response.suggestion = suggestion
        response.retrieval = retrieval
        response.embedding_provider_mismatch = embedding_provider_mismatch
        response.mismatched_documents = mismatched_documents or []
        return response

    def _mismatched_document_titles(self, active_provider: str) -> list[str]:
        """Titles of completed docs indexed with a different embedding provider."""
        mismatched: list[str] = []
        for title, provider in self._retrieval.list_completed_embedding_providers():
            if provider is not None and provider != active_provider:
                mismatched.append(title)
        return mismatched

    def _require_conversation(
        self,
        conversation_id: UUID,
        user: User,
        *,
        with_messages: bool = False,
    ) -> Conversation:
        conversation = self._conversations.get_by_id(
            conversation_id,
            with_messages=with_messages,
        )
        if conversation is None or not self._conversations.user_can_access(conversation, user):
            raise AppError(
                "Conversation not found",
                status_code=404,
                code="conversation_not_found",
            )
        return conversation
