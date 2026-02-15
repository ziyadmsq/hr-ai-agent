"""Conversation management — CRUD for conversations and messages.

Persists chat history to the database for the AI agent.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.conversation import Conversation
from app.models.message import Message

logger = logging.getLogger(__name__)


class ConversationManager:
    """Manage conversations and messages for the HR agent."""

    async def create_conversation(
        self,
        db: AsyncSession,
        organization_id: UUID,
        employee_id: UUID,
        channel: str = "web",
    ) -> Conversation:
        """Create a new conversation."""
        conversation = Conversation(
            organization_id=organization_id,
            employee_id=employee_id,
            channel=channel,
            status="active",
        )
        db.add(conversation)
        await db.flush()
        await db.refresh(conversation)
        logger.info("Created conversation %s for employee %s", conversation.id, employee_id)
        return conversation

    async def get_conversation(
        self,
        db: AsyncSession,
        conversation_id: UUID,
        organization_id: UUID,
    ) -> Optional[Conversation]:
        """Get a conversation by ID with messages loaded."""
        result = await db.execute(
            select(Conversation)
            .options(selectinload(Conversation.messages))
            .where(
                Conversation.id == conversation_id,
                Conversation.organization_id == organization_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_conversations(
        self,
        db: AsyncSession,
        organization_id: UUID,
        employee_id: UUID,
    ) -> list[Conversation]:
        """List all conversations for an employee."""
        result = await db.execute(
            select(Conversation)
            .where(
                Conversation.organization_id == organization_id,
                Conversation.employee_id == employee_id,
            )
            .order_by(Conversation.started_at.desc())
        )
        return list(result.scalars().all())

    async def add_message(
        self,
        db: AsyncSession,
        conversation_id: UUID,
        role: str,
        content: str,
        tool_calls: Optional[dict[str, Any]] = None,
    ) -> Message:
        """Add a message to a conversation."""
        message = Message(
            conversation_id=conversation_id,
            role=role,
            content=content,
            tool_calls=tool_calls,
        )
        db.add(message)
        await db.flush()
        return message

    async def get_conversation_history(
        self,
        db: AsyncSession,
        conversation_id: UUID,
    ) -> list[Message]:
        """Get all messages in a conversation, ordered by creation time."""
        result = await db.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.asc())
        )
        return list(result.scalars().all())

    async def close_conversation(
        self,
        db: AsyncSession,
        conversation_id: UUID,
        organization_id: UUID,
    ) -> Optional[Conversation]:
        """Close a conversation."""
        conversation = await self.get_conversation(db, conversation_id, organization_id)
        if conversation is None:
            return None
        conversation.status = "closed"
        conversation.ended_at = datetime.now(timezone.utc)
        await db.flush()
        logger.info("Closed conversation %s", conversation_id)
        return conversation

