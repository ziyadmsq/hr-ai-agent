"""Main HR Agent — orchestrates LangGraph agent with LangChain tool calling.

Falls back to mock/canned responses when no AI provider is configured.
"""

import json
import logging
from typing import Any, AsyncGenerator
from uuid import UUID

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.services.agent.conversation_manager import ConversationManager
from app.services.agent.provider_factory import get_chat_model, get_default_ai_config
from app.services.agent.tools import get_langchain_tools

logger = logging.getLogger(__name__)

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

# Canned responses for mock mode (no AI provider configured)
_MOCK_RESPONSES = {
    "leave": "I'd be happy to help with your leave balance! In mock mode, I can't access real data. Please configure an AI provider for full functionality. Your mock leave balance: Annual: 15 remaining, Sick: 10 remaining.",
    "policy": "I can help you find policy information! In mock mode, I'm using canned responses. Please configure an AI provider for RAG-powered policy search.",
    "document": "I can generate HR documents for you! In mock mode, document generation is simulated. Please configure an AI provider for full functionality.",
    "resign": "I understand you're considering resignation. In mock mode, I can guide you through the general process: 1) Submit a formal resignation letter, 2) Serve your notice period, 3) Complete handover. Please configure an AI provider for personalized assistance.",
    "default": "Hello! I'm your AI HR assistant. I can help with leave management, policy questions, and document generation. In mock mode, my responses are limited. Please configure an AI provider for full functionality.",
}


def _normalize_ai_config(raw_config: dict) -> dict:
    """Convert API-stored ai_config field names to provider_factory field names.

    The API stores config as:
        { provider, model, api_key, base_url, embedding_provider, embedding_model }
    But provider_factory.get_chat_model() expects:
        { chat_provider, chat_model, openai_api_key/groq_api_key, ollama_base_url, temperature }
    """
    provider = (raw_config.get("provider") or "openai").lower()
    api_key = raw_config.get("api_key")

    normalized: dict[str, Any] = {
        "chat_provider": provider,
        "chat_model": raw_config.get("model") or "gpt-4o",
        "embedding_provider": raw_config.get("embedding_provider") or "openai",
        "embedding_model": raw_config.get("embedding_model") or "text-embedding-3-small",
        "temperature": raw_config.get("temperature") or 0.3,
    }

    # Map api_key to the correct provider-specific key
    if api_key:
        if provider == "openai":
            normalized["openai_api_key"] = api_key
        elif provider == "groq":
            normalized["groq_api_key"] = api_key

    # Map base_url for Ollama
    if raw_config.get("base_url"):
        normalized["ollama_base_url"] = raw_config["base_url"]

    return normalized


class HRAgent:
    """AI HR Agent using LangGraph with LangChain tool calling and mock fallback."""

    def __init__(self, ai_config: dict[str, Any] | None = None):
        self.conversation_manager = ConversationManager()
        self._llm = None
        self._ai_config = ai_config or {}

        # Try to create the LLM from the provided config
        effective_config = self._ai_config if self._ai_config else get_default_ai_config()
        try:
            # Check if we actually have a usable API key
            provider = effective_config.get("chat_provider", "openai")
            has_key = False
            if provider == "openai":
                key = effective_config.get("openai_api_key") or settings.OPENAI_API_KEY
                has_key = bool(key) and not key.startswith("sk-placeholder")
            elif provider == "groq":
                key = effective_config.get("groq_api_key") or settings.GROQ_API_KEY
                has_key = bool(key)
            elif provider == "ollama":
                has_key = True  # Ollama doesn't need an API key

            if has_key:
                self._llm = get_chat_model(effective_config)
                logger.info(
                    "HRAgent initialized with %s (model=%s)",
                    provider,
                    effective_config.get("chat_model", "unknown"),
                )
            else:
                logger.info("No valid API key for %s — HRAgent running in mock mode", provider)
        except Exception as e:
            logger.warning("Failed to init LLM, using mock mode: %s", e)

    @property
    def is_mock(self) -> bool:
        return self._llm is None

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

        # Build LangChain messages from conversation history
        history = await self.conversation_manager.get_conversation_history(
            db, conversation_id
        )
        lc_messages = self._build_messages(history, org_name)

        # Create LangGraph agent with tools bound to this request's context
        tools = get_langchain_tools(db, employee_id, organization_id)
        from langgraph.prebuilt import create_react_agent

        agent = create_react_agent(self._llm, tools)

        # Invoke the agent — LangGraph handles the tool-calling loop automatically
        result = await agent.ainvoke({"messages": lc_messages})

        # Extract the final response and any tool calls from the message history
        reply = ""
        all_tool_calls: list[dict] = []
        for msg in result["messages"]:
            if isinstance(msg, AIMessage):
                if msg.tool_calls:
                    for tc in msg.tool_calls:
                        all_tool_calls.append({
                            "tool": tc["name"],
                            "arguments": tc["args"],
                            "result": None,  # Will be filled from ToolMessage
                        })
                elif msg.content:
                    reply = msg.content
            elif isinstance(msg, ToolMessage):
                # Match tool result to the last tool call without a result
                for tc_entry in all_tool_calls:
                    if tc_entry["result"] is None:
                        try:
                            tc_entry["result"] = json.loads(msg.content)
                        except (json.JSONDecodeError, TypeError):
                            tc_entry["result"] = msg.content
                        break

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
        lc_messages = self._build_messages(history, org_name)

        # Create LangGraph agent with tools bound to this request's context
        tools = get_langchain_tools(db, employee_id, organization_id)
        from langgraph.prebuilt import create_react_agent

        agent = create_react_agent(self._llm, tools)

        # Stream events from the LangGraph agent
        all_tool_calls: list[dict] = []
        final_reply = ""

        async for event in agent.astream_events(
            {"messages": lc_messages}, version="v2"
        ):
            kind = event["event"]

            if kind == "on_chat_model_stream":
                # Token-by-token streaming from the LLM
                chunk = event["data"]["chunk"]
                if hasattr(chunk, "content") and chunk.content and isinstance(chunk.content, str):
                    final_reply += chunk.content
                    yield json.dumps({"type": "token", "content": chunk.content})

            elif kind == "on_tool_start":
                tool_name = event.get("name", "unknown")
                tool_input = event["data"].get("input", {})
                yield json.dumps({"type": "tool_call", "tool": tool_name, "arguments": tool_input})

            elif kind == "on_tool_end":
                tool_name = event.get("name", "unknown")
                raw_output = event["data"].get("output", "")
                # Parse the tool output
                try:
                    if hasattr(raw_output, "content"):
                        result_data = json.loads(raw_output.content)
                    else:
                        result_data = json.loads(str(raw_output))
                except (json.JSONDecodeError, TypeError):
                    result_data = str(raw_output)

                all_tool_calls.append({
                    "tool": tool_name,
                    "arguments": event["data"].get("input", {}),
                    "result": result_data,
                })
                yield json.dumps({"type": "tool_result", "tool": tool_name, "result": result_data})

        tc_data = all_tool_calls if all_tool_calls else None
        await self.conversation_manager.add_message(
            db, conversation_id, "assistant", final_reply, tool_calls=tc_data
        )
        yield json.dumps({"type": "done", "conversation_id": str(conversation_id)})

    # ── Private helpers ───────────────────────────────────────────────────────

    def _build_messages(self, history: list, org_name: str) -> list:
        """Convert DB message history into LangChain message objects."""
        messages = [
            SystemMessage(content=SYSTEM_PROMPT_TEMPLATE.format(org_name=org_name))
        ]
        for msg in history:
            # Only include user and assistant text messages.
            # Stored tool_calls are in summary format (for frontend display)
            # and are NOT compatible with the LangChain message format.
            # Tool call execution happens within a single turn (in-memory loop)
            # so we never need to replay them from DB.
            if msg.role == "user":
                messages.append(HumanMessage(content=msg.content or ""))
            elif msg.role == "assistant":
                messages.append(AIMessage(content=msg.content or ""))
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
