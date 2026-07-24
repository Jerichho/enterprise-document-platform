"""Conversation persistence helpers."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.conversation import Citation, Conversation, Message
from app.models.enums import UserRole
from app.models.user import User


class ConversationRepository:
    """Data-access helpers for conversations and messages."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def create(self, *, user_id: UUID, title: str) -> Conversation:
        conversation = Conversation(user_id=user_id, title=title)
        self._db.add(conversation)
        self._db.commit()
        self._db.refresh(conversation)
        return conversation

    def get_by_id(
        self,
        conversation_id: UUID,
        *,
        with_messages: bool = False,
    ) -> Conversation | None:
        statement = select(Conversation).where(Conversation.id == conversation_id)
        if with_messages:
            statement = statement.options(
                selectinload(Conversation.messages).selectinload(Message.citations)
            )
        return self._db.scalar(statement)

    def list_for_user(
        self,
        user: User,
        *,
        page: int,
        page_size: int,
    ) -> tuple[list[Conversation], int]:
        filters = []
        if user.role != UserRole.ADMIN:
            filters.append(Conversation.user_id == user.id)

        base = select(Conversation).where(*filters) if filters else select(Conversation)
        total = self._db.scalar(select(func.count()).select_from(base.subquery())) or 0
        items = list(
            self._db.scalars(
                base.order_by(Conversation.updated_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            ).all()
        )
        return items, total

    def delete(self, conversation: Conversation) -> None:
        self._db.delete(conversation)
        self._db.commit()

    def update_title(self, conversation: Conversation, title: str) -> Conversation:
        conversation.title = title[:300]
        self._db.add(conversation)
        self._db.commit()
        self._db.refresh(conversation)
        return conversation

    def add_message(self, message: Message) -> Message:
        self._db.add(message)
        self._db.commit()
        self._db.refresh(message)
        return message

    def save_assistant_with_citations(
        self,
        message: Message,
        citations: list[Citation],
    ) -> Message:
        self._db.add(message)
        for citation in citations:
            citation.message = message
            self._db.add(citation)
        conversation = self.get_by_id(message.conversation_id)
        if conversation is not None:
            # Touch updated_at
            conversation.title = conversation.title
            self._db.add(conversation)
        self._db.commit()
        self._db.refresh(message)
        return self.get_message(message.id) or message

    def get_message(self, message_id: UUID) -> Message | None:
        statement = (
            select(Message).where(Message.id == message_id).options(selectinload(Message.citations))
        )
        return self._db.scalar(statement)

    def user_can_access(self, conversation: Conversation, user: User) -> bool:
        return user.role == UserRole.ADMIN or conversation.user_id == user.id
