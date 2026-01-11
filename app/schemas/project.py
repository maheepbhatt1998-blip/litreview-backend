from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from uuid import UUID


class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    research_topic: Optional[str] = Field(None, max_length=500)


class ProjectUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    research_topic: Optional[str] = Field(None, max_length=500)


class ProjectResponse(BaseModel):
    id: UUID
    name: str
    description: Optional[str]
    research_topic: Optional[str]
    paper_count: int = 0
    analyzed_count: int = 0
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ProjectListResponse(BaseModel):
    projects: List[ProjectResponse]
    total: int
