"""Add policy_chunks table for RAG system

Revision ID: 002
Revises: 001
Create Date: 2026-02-15

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "policy_chunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "policy_document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("policy_documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id"),
            nullable=False,
        ),
        sa.Column("chunk_text", sa.Text, nullable=False),
        sa.Column("chunk_index", sa.Integer, nullable=False),
        sa.Column("embedding", Vector(1536), nullable=True),
        sa.Column("metadata", postgresql.JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    # Index for fast vector similarity search
    op.create_index(
        "ix_policy_chunks_embedding",
        "policy_chunks",
        ["embedding"],
        postgresql_using="ivfflat",
        postgresql_with={"lists": 100},
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )

    # Index for tenant isolation queries
    op.create_index(
        "ix_policy_chunks_org_id",
        "policy_chunks",
        ["organization_id"],
    )

    # Index for looking up chunks by policy document
    op.create_index(
        "ix_policy_chunks_policy_doc_id",
        "policy_chunks",
        ["policy_document_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_policy_chunks_policy_doc_id", table_name="policy_chunks")
    op.drop_index("ix_policy_chunks_org_id", table_name="policy_chunks")
    op.drop_index("ix_policy_chunks_embedding", table_name="policy_chunks")
    op.drop_table("policy_chunks")

