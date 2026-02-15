"""Vector retriever using pgvector cosine similarity search.

Queries the policy_chunks table for the most relevant chunks,
filtered by organization_id for tenant isolation.
"""

import logging
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

DEFAULT_TOP_K = 5


@dataclass
class RetrievedChunk:
    """A chunk retrieved from the vector store with its similarity score."""

    id: UUID
    policy_document_id: UUID
    chunk_text: str
    chunk_index: int
    similarity: float
    metadata: dict | None


class VectorRetriever:
    """Retrieve relevant policy chunks using pgvector cosine similarity."""

    def __init__(self, top_k: int = DEFAULT_TOP_K):
        self.top_k = top_k

    async def retrieve(
        self,
        db: AsyncSession,
        query_embedding: list[float],
        organization_id: UUID,
        top_k: int | None = None,
    ) -> list[RetrievedChunk]:
        """Find the top-k most similar chunks for a given query embedding.

        Args:
            db: Async database session.
            query_embedding: The embedding vector of the user's query.
            organization_id: Filter results to this tenant.
            top_k: Number of results to return (overrides default).

        Returns:
            List of RetrievedChunk sorted by similarity (highest first).
        """
        k = top_k or self.top_k

        # Use pgvector's cosine distance operator (<=>)
        # Cosine distance = 1 - cosine_similarity, so we convert back
        query = text(
            """
            SELECT
                id,
                policy_document_id,
                chunk_text,
                chunk_index,
                metadata,
                1 - (embedding <=> :embedding::vector) AS similarity
            FROM policy_chunks
            WHERE organization_id = :org_id
              AND embedding IS NOT NULL
            ORDER BY embedding <=> :embedding::vector
            LIMIT :limit
            """
        )

        embedding_str = "[" + ",".join(str(v) for v in query_embedding) + "]"

        result = await db.execute(
            query,
            {
                "embedding": embedding_str,
                "org_id": str(organization_id),
                "limit": k,
            },
        )

        rows = result.fetchall()
        chunks = []
        for row in rows:
            chunks.append(
                RetrievedChunk(
                    id=row.id,
                    policy_document_id=row.policy_document_id,
                    chunk_text=row.chunk_text,
                    chunk_index=row.chunk_index,
                    similarity=float(row.similarity),
                    metadata=row.metadata,
                )
            )

        logger.info(
            "Retrieved %d chunks for org %s (top_k=%d)",
            len(chunks),
            organization_id,
            k,
        )
        return chunks

