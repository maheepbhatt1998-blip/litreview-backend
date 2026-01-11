from pydantic import BaseModel, Field
from typing import Optional, List, Any
from datetime import datetime
from uuid import UUID


class AnalysisResponse(BaseModel):
    id: UUID
    paper_id: UUID
    importance: Optional[str]
    importance_score: Optional[int]
    novelty: Optional[str]
    methodology: Optional[str]
    results_summary: Optional[str]
    future_work: Optional[str]
    key_findings: Optional[dict]
    key_takeaways: Optional[List[str]]
    conventional_methods: Optional[List[str]]
    innovations: Optional[List[str]]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class RecommendationResponse(BaseModel):
    id: UUID
    paper_id: UUID
    recommended_title: str
    recommended_authors: Optional[List[str]]
    recommended_abstract: Optional[str]
    recommended_doi: Optional[str]
    recommended_url: Optional[str]
    recommended_year: Optional[int]
    similarity_score: Optional[float]
    source: str
    relationship_type: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class InsightCreate(BaseModel):
    paper_ids: Optional[List[UUID]] = None  # If None, use all papers in project


class InsightResponse(BaseModel):
    id: UUID
    project_id: UUID
    insight_type: str
    title: Optional[str]
    content: str
    related_paper_ids: Optional[List[UUID]]
    created_at: datetime

    class Config:
        from_attributes = True


class SearchQuery(BaseModel):
    query: str = Field(..., min_length=1, max_length=1000)
    limit: int = Field(10, ge=1, le=50)


class SearchResult(BaseModel):
    paper_id: UUID
    title: Optional[str]
    abstract: Optional[str]
    relevance_score: float
    matched_chunk: str
