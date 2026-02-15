"""Embedding service using OpenAI text-embedding-3-small.

Falls back to random vectors when OPENAI_API_KEY is not set (dev/test mode).
"""

import logging
import random
from typing import Optional

from app.core.config import settings

logger = logging.getLogger(__name__)

EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSIONS = 1536


class EmbeddingService:
    """Generate embeddings for text using OpenAI or mock mode."""

    def __init__(self, api_key: Optional[str] = None):
        self._api_key = api_key or settings.OPENAI_API_KEY
        self._client = None
        if self._api_key:
            try:
                from openai import OpenAI

                self._client = OpenAI(api_key=self._api_key)
                logger.info("EmbeddingService initialized with OpenAI client")
            except Exception as e:
                logger.warning(
                    "Failed to initialize OpenAI client, using mock mode: %s", e
                )
        else:
            logger.info(
                "No OPENAI_API_KEY set — EmbeddingService running in mock mode"
            )

    @property
    def is_mock(self) -> bool:
        return self._client is None

    async def embed_text(self, text: str) -> list[float]:
        """Embed a single text string. Returns a 1536-dim vector."""
        if self._client is None:
            return self._mock_embedding()

        response = self._client.embeddings.create(
            model=EMBEDDING_MODEL,
            input=text,
        )
        return response.data[0].embedding

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Embed a list of text strings. Returns list of 1536-dim vectors."""
        if not texts:
            return []

        if self._client is None:
            return [self._mock_embedding() for _ in texts]

        # OpenAI supports batching natively
        response = self._client.embeddings.create(
            model=EMBEDDING_MODEL,
            input=texts,
        )
        # Sort by index to preserve order
        sorted_data = sorted(response.data, key=lambda x: x.index)
        return [item.embedding for item in sorted_data]

    @staticmethod
    def _mock_embedding() -> list[float]:
        """Generate a deterministic-length random vector for dev/test."""
        return [random.uniform(-1, 1) for _ in range(EMBEDDING_DIMENSIONS)]

