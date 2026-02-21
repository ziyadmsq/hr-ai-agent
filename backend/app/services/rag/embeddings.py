"""Embedding service using LangChain Embeddings abstraction.

Supports OpenAI and Ollama via provider_factory. Falls back to random
vectors when no valid API key / provider is available (dev/test mode).
"""

import logging
import random
from typing import Any, Optional

from app.core.config import settings

logger = logging.getLogger(__name__)

EMBEDDING_DIMENSIONS = 1536


def _map_ai_config(raw_config: dict[str, Any]) -> dict[str, Any]:
    """Map org-level AI config field names to provider_factory format.

    The API stores config with fields: ``provider``, ``model``, ``api_key``,
    ``base_url``, ``embedding_provider``, ``embedding_model``.

    ``provider_factory.get_embeddings()`` expects: ``embedding_provider``,
    ``embedding_model``, ``openai_api_key``, ``ollama_base_url``.
    """
    mapped: dict[str, Any] = {}
    # Pass through embedding-specific fields as-is, falling back to defaults for empty strings
    if "embedding_provider" in raw_config:
        mapped["embedding_provider"] = raw_config["embedding_provider"] or "openai"
    if "embedding_model" in raw_config:
        mapped["embedding_model"] = raw_config["embedding_model"] or "text-embedding-3-small"

    # Map api_key → openai_api_key (when embedding_provider is openai)
    provider = raw_config.get("embedding_provider") or "openai"
    if provider == "openai" and "api_key" in raw_config:
        mapped["openai_api_key"] = raw_config["api_key"]
    # If openai_api_key is already present (factory format), keep it
    if "openai_api_key" in raw_config:
        mapped["openai_api_key"] = raw_config["openai_api_key"]

    # Map base_url → ollama_base_url (when embedding_provider is ollama)
    if provider == "ollama" and "base_url" in raw_config:
        mapped["ollama_base_url"] = raw_config["base_url"]
    if "ollama_base_url" in raw_config:
        mapped["ollama_base_url"] = raw_config["ollama_base_url"]

    return mapped


class EmbeddingService:
    """Generate embeddings using LangChain or mock mode."""

    def __init__(self, ai_config: Optional[dict[str, Any]] = None):
        from app.services.agent.provider_factory import (
            get_default_ai_config,
            get_embeddings,
        )

        self._embeddings = None  # LangChain Embeddings instance

        # Build the effective config
        if ai_config is not None:
            effective_config = _map_ai_config(ai_config)
        else:
            effective_config = get_default_ai_config()

        # Determine if we can actually create an embeddings client
        provider = effective_config.get("embedding_provider", "openai")
        has_key = False
        if provider == "openai":
            key = effective_config.get("openai_api_key") or settings.OPENAI_API_KEY
            has_key = bool(key) and key != "sk-placeholder"
        elif provider == "ollama":
            # Ollama doesn't need an API key, just a reachable server
            has_key = True

        if has_key:
            try:
                self._embeddings = get_embeddings(effective_config)
                logger.info(
                    "EmbeddingService initialized with LangChain (%s)", provider
                )
            except Exception as e:
                logger.warning(
                    "Failed to initialize LangChain embeddings, using mock mode: %s",
                    e,
                )
        else:
            logger.info(
                "No valid API key for embedding provider '%s' — "
                "EmbeddingService running in mock mode",
                provider,
            )

    @property
    def is_mock(self) -> bool:
        return self._embeddings is None

    async def embed_text(self, text: str) -> list[float]:
        """Embed a single text string. Returns a 1536-dim vector."""
        if self._embeddings is None:
            return self._mock_embedding()

        return await self._embeddings.aembed_query(text)

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Embed a list of text strings. Returns list of 1536-dim vectors."""
        if not texts:
            return []

        if self._embeddings is None:
            return [self._mock_embedding() for _ in texts]

        return await self._embeddings.aembed_documents(texts)

    @staticmethod
    def _mock_embedding() -> list[float]:
        """Generate a deterministic-length random vector for dev/test."""
        return [random.uniform(-1, 1) for _ in range(EMBEDDING_DIMENSIONS)]

