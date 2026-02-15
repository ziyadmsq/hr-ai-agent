from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class DocumentResponse(BaseModel):
    id: UUID
    organization_id: UUID
    employee_id: Optional[UUID] = None
    document_type: str
    title: str
    file_path: Optional[str] = None
    generated_from_template: Optional[bool] = False
    created_at: datetime

    model_config = {"from_attributes": True}


class DocumentListResponse(BaseModel):
    items: list[DocumentResponse]
    total: int


class DocumentGenerateRequest(BaseModel):
    template_type: str  # contract, resignation_letter, experience_letter
    employee_id: Optional[UUID] = None
    parameters: Optional[dict] = None


class DocumentDownloadResponse(BaseModel):
    id: UUID
    title: str
    file_path: Optional[str] = None
    download_url: Optional[str] = None

