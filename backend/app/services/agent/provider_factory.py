"""
Provider factory for LangChain ChatModel and Embeddings instances.

Creates the appropriate LangChain provider based on an organization's AI config dict.
Supported providers:
  - Chat: openai, groq, ollama
  - Embeddings: openai, ollama
"""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.embeddings import Embeddings
from langchain_core.language_models.chat_models import BaseChatModel

from app.core.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

_DEFAULT_CHAT_PROVIDER = "openai"
_DEFAULT_CHAT_MODEL = "gpt-4o-mini"
_DEFAULT_EMBEDDING_PROVIDER = "openai"
_DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"
_DEFAULT_OLLAMA_BASE_URL = "http://localhost:11434"


def get_default_ai_config() -> dict[str, Any]:
    """Return a fallback AI config dict built from environment variables.

    This is used when an organization has no ``ai_config`` stored in its
    ``settings`` JSONB column.
    """
    return {
        "chat_provider": _DEFAULT_CHAT_PROVIDER,
        "chat_model": _DEFAULT_CHAT_MODEL,
        "embedding_provider": _DEFAULT_EMBEDDING_PROVIDER,
        "embedding_model": _DEFAULT_EMBEDDING_MODEL,
        "openai_api_key": settings.OPENAI_API_KEY,
        "groq_api_key": settings.GROQ_API_KEY,
        "ollama_base_url": _DEFAULT_OLLAMA_BASE_URL,
        "temperature": 0.3,
    }


# ---------------------------------------------------------------------------
# Chat model factory
# ---------------------------------------------------------------------------


def get_chat_model(ai_config: dict[str, Any]) -> BaseChatModel:
    """Return a LangChain ``BaseChatModel`` for the requested provider.

    Parameters
    ----------
    ai_config:
        Dictionary with at least ``chat_provider`` and ``chat_model``.
        Provider-specific keys (e.g. ``openai_api_key``) are also read.

    Raises
    ------
    ValueError
        If the provider is unknown or required credentials are missing.
    """
    provider = (ai_config.get("chat_provider") or _DEFAULT_CHAT_PROVIDER).lower()
    model = ai_config.get("chat_model") or _DEFAULT_CHAT_MODEL
    temperature = ai_config.get("temperature") or 0.3

    if provider == "openai":
        api_key = ai_config.get("openai_api_key") or settings.OPENAI_API_KEY
        if not api_key:
            raise ValueError(
                "OpenAI API key is required. Set OPENAI_API_KEY env var or "
                "provide 'openai_api_key' in ai_config."
            )
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=model,
            api_key=api_key,
            temperature=temperature,
        )

    if provider == "groq":
        api_key = ai_config.get("groq_api_key") or settings.GROQ_API_KEY
        if not api_key:
            raise ValueError(
                "Groq API key is required. Set GROQ_API_KEY env var or "
                "provide 'groq_api_key' in ai_config."
            )
        from langchain_groq import ChatGroq

        return ChatGroq(
            model=model,
            api_key=api_key,
            temperature=temperature,
        )

    if provider == "ollama":
        base_url = ai_config.get("ollama_base_url", _DEFAULT_OLLAMA_BASE_URL)
        from langchain_ollama import ChatOllama

        return ChatOllama(
            model=model,
            base_url=base_url,
            temperature=temperature,
        )

    raise ValueError(
        f"Unknown chat provider '{provider}'. "
        "Supported providers: openai, groq, ollama."
    )


# ---------------------------------------------------------------------------
# Embeddings factory
# ---------------------------------------------------------------------------


def get_embeddings(ai_config: dict[str, Any]) -> Embeddings:
    """Return a LangChain ``Embeddings`` instance for the requested provider.

    Parameters
    ----------
    ai_config:
        Dictionary with at least ``embedding_provider`` and ``embedding_model``.

    Raises
    ------
    ValueError
        If the provider is unknown or required credentials are missing.
    """
    provider = (ai_config.get("embedding_provider") or _DEFAULT_EMBEDDING_PROVIDER).lower()
    model = ai_config.get("embedding_model") or _DEFAULT_EMBEDDING_MODEL

    if provider == "openai":
        api_key = ai_config.get("openai_api_key") or settings.OPENAI_API_KEY
        if not api_key:
            raise ValueError(
                "OpenAI API key is required for embeddings. Set OPENAI_API_KEY "
                "env var or provide 'openai_api_key' in ai_config."
            )
        from langchain_openai import OpenAIEmbeddings

        return OpenAIEmbeddings(model=model, api_key=api_key)

    if provider == "ollama":
        base_url = ai_config.get("ollama_base_url", _DEFAULT_OLLAMA_BASE_URL)
        from langchain_ollama import OllamaEmbeddings

        return OllamaEmbeddings(model=model, base_url=base_url)

    raise ValueError(
        f"Unknown embedding provider '{provider}'. "
        "Supported providers: openai, ollama."
    )

