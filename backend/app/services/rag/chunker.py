"""Document chunker that splits policy documents into overlapping token-based chunks.

Uses tiktoken for accurate token counting with the OpenAI embedding model.
"""

import logging
from dataclasses import dataclass
from uuid import UUID

import tiktoken

logger = logging.getLogger(__name__)

# Use cl100k_base encoding (same as text-embedding-3-small)
ENCODING_NAME = "cl100k_base"
DEFAULT_CHUNK_SIZE = 500  # tokens
DEFAULT_OVERLAP = 50  # tokens


@dataclass
class Chunk:
    """A chunk of text with metadata."""

    text: str
    index: int
    policy_document_id: UUID
    organization_id: UUID
    metadata: dict


class DocumentChunker:
    """Split policy documents into overlapping chunks based on token count."""

    def __init__(
        self,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        overlap: int = DEFAULT_OVERLAP,
    ):
        self.chunk_size = chunk_size
        self.overlap = overlap
        self._encoding = tiktoken.get_encoding(ENCODING_NAME)

    def chunk_document(
        self,
        content: str,
        policy_document_id: UUID,
        organization_id: UUID,
        title: str = "",
        category: str | None = None,
    ) -> list[Chunk]:
        """Split document content into overlapping chunks.

        Args:
            content: The full text of the policy document.
            policy_document_id: FK to the policy document.
            organization_id: FK to the organization (tenant isolation).
            title: Document title for metadata.
            category: Optional category for metadata.

        Returns:
            List of Chunk objects with text, index, and metadata.
        """
        tokens = self._encoding.encode(content)

        if not tokens:
            return []

        chunks: list[Chunk] = []
        start = 0
        index = 0

        while start < len(tokens):
            end = min(start + self.chunk_size, len(tokens))
            chunk_tokens = tokens[start:end]
            chunk_text = self._encoding.decode(chunk_tokens)

            metadata = {
                "title": title,
                "chunk_index": index,
                "total_tokens": len(chunk_tokens),
            }
            if category:
                metadata["category"] = category

            chunks.append(
                Chunk(
                    text=chunk_text,
                    index=index,
                    policy_document_id=policy_document_id,
                    organization_id=organization_id,
                    metadata=metadata,
                )
            )

            # Move forward by (chunk_size - overlap) tokens
            start += self.chunk_size - self.overlap
            index += 1

        logger.info(
            "Chunked document %s into %d chunks (chunk_size=%d, overlap=%d)",
            policy_document_id,
            len(chunks),
            self.chunk_size,
            self.overlap,
        )
        return chunks

