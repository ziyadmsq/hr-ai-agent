"""Main HR Agent — orchestrates OpenAI chat completions with tool calling.

Falls back to mock/canned responses when no OpenAI API key is configured.
"""

import json
import logging
from typing import Any, AsyncGenerator, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.services.agent.conversation_manager import ConversationManager
from app.services.agent.tools import TOOL_DEFINITIONS, execute_tool

logger = logging.getLogger(__name__)

# Maximum tool-call round-trips per user message to prevent infinite loops
MAX_TOOL_ROUNDS = 5

SYSTEM_PROMPT_TEMPLATE = """You are an AI HR assistant for {org_name}. You help employees with HR-related questions and tasks.

Your capabilities:
- Check leave balances and submit leave requests
- Look up employee information
- Search and explain company HR policies
- Generate HR documents (resignation letters, experience letters, salary certificates, etc.)

Guidelines:
- Be professional, friendly, and concise.
- Always use the available tools to look up real data — never guess or make up numbers.
- When an employee asks about policies, use the search_policies tool first.
- If you cannot find the answer, say so honestly and suggest contacting HR directly.
- Protect employee privacy — only share information about the requesting employee.
- For leave requests, confirm the details with the employee before submitting.
"""

# Canned responses for mock mode (no OpenAI key)
_MOCK_RESPONSES = {
    "leave": "I'd be happy to help with your leave balance! In mock mode, I can't access real data. Please configure an OpenAI API key for full functionality. Your mock leave balance: Annual: 15 remaining, Sick: 10 remaining.",
    "policy": "I can help you find policy information! In mock mode, I'm using canned responses. Please configure an OpenAI API key for RAG-powered policy search.",
    "document": "I can generate HR documents for you! In mock mode, document generation is simulated. Please configure an OpenAI API key for full functionality.",
    "resign": "I understand you're considering resignation. In mock mode, I can guide you through the general process: 1) Submit a formal resignation letter, 2) Serve your notice period, 3) Complete handover. Please configure an OpenAI API key for personalized assistance.",
    "default": "Hello! I'm your AI HR assistant. I can help with leave management, policy questions, and document generation. In mock mode, my responses are limited. Please configure an OpenAI API key for full functionality.",
}


class HRAgent:
    """AI HR Agent with OpenAI tool calling and mock fallback."""

    def __init__(self):
        self.conversation_manager = ConversationManager()
        self._client = None
        self._model = "gpt-4o"

        if settings.OPENAI_API_KEY and not settings.OPENAI_API_KEY.startswith("sk-placeholder"):
            try:
                from openai import AsyncOpenAI
                self._client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
                logger.info("HRAgent initialized with OpenAI client (model=%s)", self._model)
            except Exception as e:
                logger.warning("Failed to init OpenAI client, using mock mode: %s", e)
        else:
            logger.info("No OPENAI_API_KEY — HRAgent running in mock mode")

    @property
    def is_mock(self) -> bool:
        return self._client is None

    # ── Public API ────────────────────────────────────────────────────────────

    async def chat(
        self,
        db: AsyncSession,
        conversation_id: UUID,
        user_message: str,
        employee_id: UUID,
        organization_id: UUID,
        org_name: str = "Your Organization",
    ) -> dict[str, Any]:
        """Process a user message and return the assistant response.

        Returns:
            Dict with keys: response (str), tool_calls (list|None), conversation_id (str)
        """
        # Persist user message
        await self.conversation_manager.add_message(
            db, conversation_id, "user", user_message
        )

        if self.is_mock:
            reply = self._mock_reply(user_message)
            await self.conversation_manager.add_message(
                db, conversation_id, "assistant", reply
            )
            return {
                "response": reply,
                "tool_calls": None,
                "conversation_id": str(conversation_id),
            }

        # Build messages list from conversation history
        history = await self.conversation_manager.get_conversation_history(
            db, conversation_id
        )
        messages = self._build_messages(history, org_name)

        # Call OpenAI with tool-calling loop
        all_tool_calls: list[dict] = []
        for _ in range(MAX_TOOL_ROUNDS):
            completion = await self._client.chat.completions.create(
                model=self._model,
                messages=messages,
                tools=TOOL_DEFINITIONS,
                tool_choice="auto",
            )
            choice = completion.choices[0]

            if choice.finish_reason == "tool_calls" or choice.message.tool_calls:
                # Execute each tool call
                messages.append(choice.message.model_dump())
                for tc in choice.message.tool_calls:
                    fn_name = tc.function.name
                    fn_args = json.loads(tc.function.arguments)
                    result_str = await execute_tool(
                        fn_name, fn_args, db, employee_id, organization_id
                    )
                    all_tool_calls.append({
                        "tool": fn_name,
                        "arguments": fn_args,
                        "result": json.loads(result_str),
                    })
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": result_str,
                    })
            else:
                # Final text response
                reply = choice.message.content or ""
                tc_data = all_tool_calls if all_tool_calls else None
                await self.conversation_manager.add_message(
                    db, conversation_id, "assistant", reply, tool_calls=tc_data
                )
                return {
                    "response": reply,
                    "tool_calls": tc_data,
                    "conversation_id": str(conversation_id),
                }

    async def chat_stream(
        self,
        db: AsyncSession,
        conversation_id: UUID,
        user_message: str,
        employee_id: UUID,
        organization_id: UUID,
        org_name: str = "Your Organization",
    ) -> AsyncGenerator[str, None]:
        """Stream a response token-by-token for WebSocket use.

        Yields JSON-encoded event strings:
          {"type": "token", "content": "..."}
          {"type": "tool_call", "tool": "...", "arguments": {...}}
          {"type": "tool_result", "tool": "...", "result": {...}}
          {"type": "done", "conversation_id": "..."}
          {"type": "error", "message": "..."}
        """
        await self.conversation_manager.add_message(
            db, conversation_id, "user", user_message
        )

        if self.is_mock:
            reply = self._mock_reply(user_message)
            await self.conversation_manager.add_message(
                db, conversation_id, "assistant", reply
            )
            yield json.dumps({"type": "token", "content": reply})
            yield json.dumps({"type": "done", "conversation_id": str(conversation_id)})
            return

        history = await self.conversation_manager.get_conversation_history(
            db, conversation_id
        )
        messages = self._build_messages(history, org_name)
        all_tool_calls: list[dict] = []

        for _ in range(MAX_TOOL_ROUNDS):
            # Use streaming for the final text response
            stream = await self._client.chat.completions.create(
                model=self._model,
                messages=messages,
                tools=TOOL_DEFINITIONS,
                tool_choice="auto",
                stream=True,
            )

            collected_content = ""
            collected_tool_calls: list[dict] = []
            current_tc: dict[str, Any] = {}

            async for chunk in stream:
                delta = chunk.choices[0].delta if chunk.choices else None
                if delta is None:
                    continue

                # Accumulate streamed text
                if delta.content:
                    collected_content += delta.content
                    yield json.dumps({"type": "token", "content": delta.content})

                # Accumulate tool calls from deltas
                if delta.tool_calls:
                    for tc_delta in delta.tool_calls:
                        idx = tc_delta.index
                        if idx >= len(collected_tool_calls):
                            collected_tool_calls.append({
                                "id": tc_delta.id or "",
                                "function": {"name": "", "arguments": ""},
                            })
                        entry = collected_tool_calls[idx]
                        if tc_delta.id:
                            entry["id"] = tc_delta.id
                        if tc_delta.function:
                            if tc_delta.function.name:
                                entry["function"]["name"] += tc_delta.function.name
                            if tc_delta.function.arguments:
                                entry["function"]["arguments"] += tc_delta.function.arguments

            # If tool calls were collected, execute them and loop
            if collected_tool_calls:
                # Build the assistant message for the messages list
                assistant_msg: dict[str, Any] = {"role": "assistant", "content": collected_content or None, "tool_calls": []}
                for tc in collected_tool_calls:
                    assistant_msg["tool_calls"].append({
                        "id": tc["id"],
                        "type": "function",
                        "function": tc["function"],
                    })
                messages.append(assistant_msg)

                for tc in collected_tool_calls:
                    fn_name = tc["function"]["name"]
                    fn_args = json.loads(tc["function"]["arguments"])
                    yield json.dumps({"type": "tool_call", "tool": fn_name, "arguments": fn_args})

                    result_str = await execute_tool(
                        fn_name, fn_args, db, employee_id, organization_id
                    )
                    result_data = json.loads(result_str)
                    all_tool_calls.append({
                        "tool": fn_name,
                        "arguments": fn_args,
                        "result": result_data,
                    })
                    yield json.dumps({"type": "tool_result", "tool": fn_name, "result": result_data})
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": result_str,
                    })
                continue  # Loop to get the final text response

            # No tool calls — we have the final response
            tc_data = all_tool_calls if all_tool_calls else None
            await self.conversation_manager.add_message(
                db, conversation_id, "assistant", collected_content, tool_calls=tc_data
            )
            yield json.dumps({"type": "done", "conversation_id": str(conversation_id)})
            return

        # Safety fallback
        reply = "I've gathered the information but reached my processing limit."
        await self.conversation_manager.add_message(
            db, conversation_id, "assistant", reply, tool_calls=all_tool_calls or None
        )
        yield json.dumps({"type": "token", "content": reply})
        yield json.dumps({"type": "done", "conversation_id": str(conversation_id)})

    # ── Private helpers ───────────────────────────────────────────────────────

    def _build_messages(
        self, history: list, org_name: str
    ) -> list[dict[str, Any]]:
        """Convert DB message history into OpenAI messages format."""
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": SYSTEM_PROMPT_TEMPLATE.format(org_name=org_name)}
        ]
        for msg in history:
            # Only include user and assistant text messages.
            # Stored tool_calls are in summary format (for frontend display)
            # and are NOT compatible with the OpenAI API message format.
            # Tool call execution happens within a single turn (in-memory loop)
            # so we never need to replay them from DB.
            if msg.role in ("user", "assistant"):
                entry: dict[str, Any] = {"role": msg.role, "content": msg.content or ""}
                messages.append(entry)
        return messages

    @staticmethod
    def _mock_reply(user_message: str) -> str:
        """Generate a canned response based on keyword matching."""
        lower = user_message.lower()
        if any(w in lower for w in ("leave", "vacation", "day off", "pto", "time off")):
            return _MOCK_RESPONSES["leave"]
        if any(w in lower for w in ("policy", "rule", "guideline", "handbook")):
            return _MOCK_RESPONSES["policy"]
        if any(w in lower for w in ("document", "letter", "certificate", "generate")):
            return _MOCK_RESPONSES["document"]
        if any(w in lower for w in ("resign", "quit", "leaving")):
            return _MOCK_RESPONSES["resign"]
        return _MOCK_RESPONSES["default"]
