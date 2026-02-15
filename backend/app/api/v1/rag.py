"""RAG API endpoints for ingesting, querying, and re-indexing policy documents."""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.services.rag.pipeline import RAGPipeline

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/rag", tags=["rag"])

# Shared pipeline instance
_pipeline = RAGPipeline()


# --- Request / Response schemas ---


class QueryRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    top_k: int = Field(default=5, ge=1, le=20)


class ChunkResult(BaseModel):
    id: str
    policy_document_id: str
    chunk_text: str
    chunk_index: int
    similarity: float
    metadata: dict | None = None


class QueryResponse(BaseModel):
    question: str
    results: list[ChunkResult]
    count: int


class IngestResponse(BaseModel):
    policy_id: str
    chunks_created: int
    message: str


class ReindexResponse(BaseModel):
    total_chunks: int
    message: str


# --- Endpoints ---


@router.post("/ingest/{policy_id}", response_model=IngestResponse)
async def ingest_policy(
    policy_id: UUID,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Ingest a policy document: chunk, embed, and store vectors.

    Requires admin or hr_manager role.
    """
    if current_user.role not in ("admin", "hr_manager"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins and HR managers can ingest policies",
        )

    try:
        chunks_created = await _pipeline.ingest(
            db=db,
            policy_id=policy_id,
            organization_id=current_user.organization_id,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )

    return IngestResponse(
        policy_id=str(policy_id),
        chunks_created=chunks_created,
        message=f"Successfully ingested policy with {chunks_created} chunks",
    )


@router.post("/query", response_model=QueryResponse)
async def query_knowledge_base(
    request: QueryRequest,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Query the RAG knowledge base with a natural language question.

    Results are filtered to the user's organization (tenant isolation).
    """
    chunks = await _pipeline.query(
        db=db,
        question=request.question,
        organization_id=current_user.organization_id,
        top_k=request.top_k,
    )

    results = [
        ChunkResult(
            id=str(c.id),
            policy_document_id=str(c.policy_document_id),
            chunk_text=c.chunk_text,
            chunk_index=c.chunk_index,
            similarity=c.similarity,
            metadata=c.metadata,
        )
        for c in chunks
    ]

    return QueryResponse(
        question=request.question,
        results=results,
        count=len(results),
    )


@router.post("/reindex", response_model=ReindexResponse)
async def reindex_policies(
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Re-index all active policy documents for the organization.

    Requires admin role.
    """
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can trigger a full re-index",
        )

    total_chunks = await _pipeline.reindex(
        db=db,
        organization_id=current_user.organization_id,
    )

    return ReindexResponse(
        total_chunks=total_chunks,
        message=f"Re-indexed all policies: {total_chunks} total chunks",
    )

