from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from uuid import UUID
from app.models.paper import PaperStatus


class PaperCreate(BaseModel):
    title: Optional[str] = Field(None, max_length=500)
    doi: Optional[str] = Field(None, max_length=100)


class PaperUploadResponse(BaseModel):
    id: UUID
    status: PaperStatus
    message: str


class PaperResponse(BaseModel):
    id: UUID
    project_id: UUID
    title: Optional[str]
    authors: Optional[List[str]]
    abstract: Optional[str]
    doi: Optional[str]
    year: Optional[int]
    journal: Optional[str]
    status: PaperStatus
    error_message: Optional[str]
    original_filename: Optional[str]
    has_analysis: bool = False
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PaperListResponse(BaseModel):
    papers: List[PaperResponse]
    total: int
    analyzed: int
    processing: int
    failed: int
