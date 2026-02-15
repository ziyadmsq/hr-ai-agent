"""Chat API endpoints — REST and WebSocket for the AI HR agent."""

import json
import logging
from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import async_session_factory
from app.core.dependencies import get_current_user, get_current_tenant, get_db
from app.core.security import decode_access_token
from app.models.user import User
from app.services.agent.hr_agent import HRAgent

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])

# Singleton agent instance
_agent = HRAgent()


# ── Schemas ───────────────────────────────────────────────────────────────────


class SendMessageRequest(BaseModel):
    conversation_id: str
    content: str


class MessageResponse(BaseModel):
    id: Optional[str] = None
    conversation_id: str
    role: str
    content: str
    tool_calls: Optional[list] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class ConversationResponse(BaseModel):
    id: str
    employee_id: str
    channel: str
    status: str
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    messages: Optional[list[MessageResponse]] = None

    model_config = {"from_attributes": True}


class ConversationListResponse(BaseModel):
    items: list[ConversationResponse]
    total: int


class ChatResponse(BaseModel):
    response: str
    tool_calls: Optional[list] = None
    conversation_id: str


# ── Helpers ───────────────────────────────────────────────────────────────────


def _get_employee_id(user: User) -> UUID:
    if not user.employee_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No employee record linked to this user. Chat requires an employee profile.",
        )
    return user.employee_id


async def _get_org_name(db: AsyncSession, org_id: UUID) -> str:
    from app.models.organization import Organization
    from sqlalchemy import select

    result = await db.execute(select(Organization).where(Organization.id == org_id))
    org = result.scalar_one_or_none()
    return org.name if org else "Your Organization"


# ── REST Endpoints ────────────────────────────────────────────────────────────


@router.post("/conversations", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    current_user: User = Depends(get_current_user),
    org_id: UUID = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Start a new conversation."""
    emp_id = _get_employee_id(current_user)
    conv = await _agent.conversation_manager.create_conversation(
        db, org_id, emp_id, channel="web"
    )
    return ConversationResponse(
        id=str(conv.id),
        employee_id=str(conv.employee_id),
        channel=conv.channel,
        status=conv.status,
        started_at=conv.started_at,
    )


@router.get("/conversations", response_model=ConversationListResponse)
async def list_conversations(
    current_user: User = Depends(get_current_user),
    org_id: UUID = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """List the current user's conversations."""
    emp_id = _get_employee_id(current_user)
    convs = await _agent.conversation_manager.list_conversations(db, org_id, emp_id)
    items = [
        ConversationResponse(
            id=str(c.id),
            employee_id=str(c.employee_id),
            channel=c.channel,
            status=c.status,
            started_at=c.started_at,
            ended_at=c.ended_at,
        )
        for c in convs
    ]
    return ConversationListResponse(items=items, total=len(items))


@router.get("/conversations/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(
    conversation_id: UUID,
    current_user: User = Depends(get_current_user),
    org_id: UUID = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Get a conversation with all its messages."""
    conv = await _agent.conversation_manager.get_conversation(db, conversation_id, org_id)
    if conv is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    # Verify the conversation belongs to this employee
    emp_id = _get_employee_id(current_user)
    if conv.employee_id != emp_id and current_user.role not in ("admin", "hr_manager"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    messages = [
        MessageResponse(
            id=str(m.id),
            conversation_id=str(m.conversation_id),
            role=m.role,
            content=m.content,
            tool_calls=m.tool_calls,
            created_at=m.created_at,
        )
        for m in (conv.messages or [])
    ]
    return ConversationResponse(
        id=str(conv.id),
        employee_id=str(conv.employee_id),
        channel=conv.channel,
        status=conv.status,
        started_at=conv.started_at,
        ended_at=conv.ended_at,
        messages=messages,
    )


@router.post("/message", response_model=ChatResponse)
async def send_message(
    data: SendMessageRequest,
    current_user: User = Depends(get_current_user),
    org_id: UUID = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Send a message and get an AI response."""
    emp_id = _get_employee_id(current_user)
    conversation_id = UUID(data.conversation_id)

    # Verify conversation exists and belongs to user
    conv = await _agent.conversation_manager.get_conversation(db, conversation_id, org_id)
    if conv is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    if conv.employee_id != emp_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    if conv.status != "active":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Conversation is closed")

    org_name = await _get_org_name(db, org_id)
    result = await _agent.chat(
        db=db,
        conversation_id=conversation_id,
        user_message=data.content,
        employee_id=emp_id,
        organization_id=org_id,
        org_name=org_name,
    )
    return ChatResponse(**result)


# ── WebSocket Endpoint ────────────────────────────────────────────────────────


@router.websocket("/ws")
async def websocket_chat(websocket: WebSocket):
    """WebSocket endpoint for real-time streaming chat.

    Protocol:
    1. Client connects and sends an auth message: {"type": "auth", "token": "<jwt>"}
    2. Client sends chat messages: {"type": "message", "conversation_id": "<id>", "content": "..."}
    3. Server streams back events (see HRAgent.chat_stream for event types)
    """
    await websocket.accept()

    user = None
    org_id = None
    employee_id = None

    try:
        # Wait for auth message
        auth_data = await websocket.receive_json()
        if auth_data.get("type") != "auth" or not auth_data.get("token"):
            await websocket.send_json({"type": "error", "message": "First message must be auth"})
            await websocket.close(code=4001)
            return

        # Authenticate
        try:
            payload = decode_access_token(auth_data["token"])
        except ValueError:
            await websocket.send_json({"type": "error", "message": "Invalid token"})
            await websocket.close(code=4001)
            return

        user_id = payload.get("sub")
        if not user_id:
            await websocket.send_json({"type": "error", "message": "Invalid token payload"})
            await websocket.close(code=4001)
            return

        # Get user from DB
        async with async_session_factory() as db:
            from sqlalchemy import select
            result = await db.execute(
                select(User).where(User.id == UUID(user_id))
            )
            user = result.scalar_one_or_none()
            if not user or not user.is_active:
                await websocket.send_json({"type": "error", "message": "User not found"})
                await websocket.close(code=4001)
                return

            org_id = user.organization_id
            employee_id = user.employee_id
            if not employee_id:
                await websocket.send_json({"type": "error", "message": "No employee profile"})
                await websocket.close(code=4001)
                return

            org_name = await _get_org_name(db, org_id)

        await websocket.send_json({"type": "auth_ok"})

        # Message loop
        while True:
            data = await websocket.receive_json()
            if data.get("type") != "message":
                await websocket.send_json({"type": "error", "message": "Expected type: message"})
                continue

            conversation_id = data.get("conversation_id")
            content = data.get("content", "").strip()
            if not conversation_id or not content:
                await websocket.send_json({"type": "error", "message": "conversation_id and content required"})
                continue

            async with async_session_factory() as db:
                try:
                    conv_uuid = UUID(conversation_id)
                    conv = await _agent.conversation_manager.get_conversation(db, conv_uuid, org_id)
                    if not conv or conv.employee_id != employee_id:
                        await websocket.send_json({"type": "error", "message": "Conversation not found"})
                        continue

                    async for event in _agent.chat_stream(
                        db=db,
                        conversation_id=conv_uuid,
                        user_message=content,
                        employee_id=employee_id,
                        organization_id=org_id,
                        org_name=org_name,
                    ):
                        await websocket.send_text(event)

                    await db.commit()
                except Exception as e:
                    logger.exception("WebSocket chat error")
                    await websocket.send_json({"type": "error", "message": str(e)})

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception as e:
        logger.exception("WebSocket error")
        try:
            await websocket.close(code=1011)
        except Exception:
            pass
