from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_current_tenant, get_db
from app.models.document import Document
from app.models.user import User
from app.schemas.documents import (
    DocumentDownloadResponse,
    DocumentGenerateRequest,
    DocumentListResponse,
    DocumentResponse,
)

router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("", response_model=DocumentListResponse)
async def list_documents(
    current_user: User = Depends(get_current_user),
    org_id: UUID = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """List documents for the current user."""
    query = select(Document).where(Document.organization_id == org_id)

    # Non-admin users only see their own documents
    if current_user.role not in ("admin", "hr_manager"):
        if current_user.employee_id:
            query = query.where(
                (Document.employee_id == current_user.employee_id)
                | (Document.employee_id.is_(None))
            )
        else:
            query = query.where(Document.employee_id.is_(None))

    result = await db.execute(query)
    documents = result.scalars().all()
    return DocumentListResponse(items=documents, total=len(documents))


@router.get("/{document_id}/download", response_model=DocumentDownloadResponse)
async def download_document(
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    org_id: UUID = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Get download info for a document."""
    result = await db.execute(
        select(Document).where(
            Document.id == document_id, Document.organization_id == org_id
        )
    )
    document = result.scalar_one_or_none()
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document not found"
        )

    # Non-admin users can only download their own documents or org-wide ones
    if current_user.role not in ("admin", "hr_manager"):
        if document.employee_id and document.employee_id != current_user.employee_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this document",
            )

    return DocumentDownloadResponse(
        id=document.id,
        title=document.title,
        file_path=document.file_path,
        download_url=f"/api/v1/documents/{document.id}/file" if document.file_path else None,
    )


@router.post("/generate", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def generate_document(
    data: DocumentGenerateRequest,
    current_user: User = Depends(get_current_user),
    org_id: UUID = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Generate a document from a template (placeholder implementation)."""
    # Determine the employee for the document
    employee_id = data.employee_id
    if not employee_id and current_user.employee_id:
        employee_id = current_user.employee_id

    # Template title mapping
    template_titles = {
        "contract": "Employment Contract",
        "resignation_letter": "Resignation Letter",
        "experience_letter": "Experience Letter",
        "salary_certificate": "Salary Certificate",
        "noc": "No Objection Certificate",
    }
    title = template_titles.get(data.template_type, f"Generated {data.template_type}")

    # Placeholder: In production, this would render a real template
    document = Document(
        organization_id=org_id,
        employee_id=employee_id,
        document_type="letter",
        title=title,
        file_path=None,  # Placeholder — no actual file generated
        generated_from_template=True,
    )
    db.add(document)
    await db.flush()
    await db.refresh(document)
    return document

