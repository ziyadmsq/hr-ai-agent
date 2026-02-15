"""RAG pipeline: ingest, query, and re-index policy documents.

Orchestrates the chunker, embedding service, and vector retriever.
"""

import logging
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.policy_chunk import PolicyChunk
from app.models.policy_document import PolicyDocument
from app.services.rag.chunker import DocumentChunker
from app.services.rag.embeddings import EmbeddingService
from app.services.rag.retriever import RetrievedChunk, VectorRetriever

logger = logging.getLogger(__name__)


class RAGPipeline:
    """High-level RAG operations: ingest, query, re-index."""

    def __init__(self):
        self.embedding_service = EmbeddingService()
        self.chunker = DocumentChunker()
        self.retriever = VectorRetriever()

    async def ingest(
        self,
        db: AsyncSession,
        policy_id: UUID,
        organization_id: UUID,
    ) -> int:
        """Ingest a policy document: chunk it, embed chunks, store vectors.

        Args:
            db: Async database session.
            policy_id: The policy document to ingest.
            organization_id: Tenant ID for isolation.

        Returns:
            Number of chunks created.

        Raises:
            ValueError: If the policy document is not found or doesn't
                        belong to the organization.
        """
        # Fetch the policy document
        result = await db.execute(
            select(PolicyDocument).where(
                PolicyDocument.id == policy_id,
                PolicyDocument.organization_id == organization_id,
            )
        )
        policy = result.scalar_one_or_none()
        if policy is None:
            raise ValueError(
                f"PolicyDocument {policy_id} not found for org {organization_id}"
            )

        # Delete existing chunks for this document (re-ingest)
        await db.execute(
            delete(PolicyChunk).where(
                PolicyChunk.policy_document_id == policy_id
            )
        )

        # Chunk the document
        chunks = self.chunker.chunk_document(
            content=policy.content,
            policy_document_id=policy.id,
            organization_id=policy.organization_id,
            title=policy.title,
            category=policy.category,
        )

        if not chunks:
            logger.warning("No chunks produced for policy %s", policy_id)
            return 0

        # Embed all chunk texts
        texts = [c.text for c in chunks]
        embeddings = await self.embedding_service.embed_texts(texts)

        # Store chunks with embeddings
        for chunk, embedding in zip(chunks, embeddings):
            db_chunk = PolicyChunk(
                policy_document_id=chunk.policy_document_id,
                organization_id=chunk.organization_id,
                chunk_text=chunk.text,
                chunk_index=chunk.index,
                embedding=embedding,
                metadata_=chunk.metadata,
            )
            db.add(db_chunk)

        await db.flush()

        logger.info(
            "Ingested policy %s: %d chunks created", policy_id, len(chunks)
        )
        return len(chunks)

    async def query(
        self,
        db: AsyncSession,
        question: str,
        organization_id: UUID,
        top_k: int = 5,
    ) -> list[RetrievedChunk]:
        """Query the knowledge base with a natural language question.

        Args:
            db: Async database session.
            question: The user's question.
            organization_id: Tenant ID for isolation.
            top_k: Number of chunks to retrieve.

        Returns:
            List of relevant chunks with similarity scores.
        """
        query_embedding = await self.embedding_service.embed_text(question)
        return await self.retriever.retrieve(
            db=db,
            query_embedding=query_embedding,
            organization_id=organization_id,
            top_k=top_k,
        )

    async def reindex(
        self,
        db: AsyncSession,
        organization_id: UUID,
    ) -> int:
        """Re-index all active policy documents for an organization.

        Args:
            db: Async database session.
            organization_id: Tenant ID.

        Returns:
            Total number of chunks created across all documents.
        """
        result = await db.execute(
            select(PolicyDocument).where(
                PolicyDocument.organization_id == organization_id,
                PolicyDocument.is_active.is_(True),
            )
        )
        policies = result.scalars().all()

        total_chunks = 0
        for policy in policies:
            count = await self.ingest(db, policy.id, organization_id)
            total_chunks += count

        logger.info(
            "Re-indexed %d policies for org %s: %d total chunks",
            len(policies),
            organization_id,
            total_chunks,
        )
        return total_chunks

