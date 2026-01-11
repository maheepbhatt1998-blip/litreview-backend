from uuid import UUID
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.database import get_db
from app.models.user import User
from app.models.project import Project
from app.models.paper import Paper, PaperStatus
from app.models.analysis import PaperAnalysis, ProjectInsight
from app.schemas.analysis import (
    AnalysisResponse,
    InsightCreate,
    InsightResponse,
    SearchQuery,
    SearchResult,
)
from app.utils.auth import get_current_user
from app.services.insight_generator import generate_project_insights_task
from app.services.semantic_search import search_papers_by_query


router = APIRouter(prefix="/analysis", tags=["Analysis"])


@router.get("/paper/{paper_id}", response_model=AnalysisResponse)
async def get_paper_analysis(
    paper_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get the AI analysis for a specific paper."""
    result = await db.execute(
        select(Paper)
        .where(Paper.id == paper_id)
        .options(selectinload(Paper.analysis), selectinload(Paper.project))
    )
    paper = result.scalar_one_or_none()

    if not paper:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Paper not found",
        )

    # Verify ownership through project
    if paper.project.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    if not paper.analysis:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Analysis not yet available. Paper may still be processing.",
        )

    return AnalysisResponse(
        id=paper.analysis.id,
        paper_id=paper.analysis.paper_id,
        importance=paper.analysis.importance,
        importance_score=paper.analysis.importance_score,
        novelty=paper.analysis.novelty,
        methodology=paper.analysis.methodology,
        results_summary=paper.analysis.results_summary,
        future_work=paper.analysis.future_work,
        key_findings=paper.analysis.key_findings,
        key_takeaways=paper.analysis.key_takeaways,
        conventional_methods=paper.analysis.conventional_methods,
        innovations=paper.analysis.innovations,
        created_at=paper.analysis.created_at,
        updated_at=paper.analysis.updated_at,
    )


@router.post("/project/{project_id}/insights", response_model=dict)
async def generate_insights(
    project_id: UUID,
    insight_request: InsightCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generate cross-paper insights for a project."""
    result = await db.execute(
        select(Project)
        .where(Project.id == project_id, Project.user_id == current_user.id)
        .options(selectinload(Project.papers))
    )
    project = result.scalar_one_or_none()

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    # Check if there are analyzed papers
    analyzed_papers = [p for p in project.papers if p.status == PaperStatus.ANALYZED]
    if len(analyzed_papers) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least 2 analyzed papers are required to generate insights.",
        )

    # Queue background processing
    paper_ids = [str(p.id) for p in analyzed_papers]
    if insight_request.paper_ids:
        paper_ids = [str(pid) for pid in insight_request.paper_ids]

    background_tasks.add_task(generate_project_insights_task, str(project_id), paper_ids)

    return {"message": "Insight generation started. Check back shortly."}


@router.get("/project/{project_id}/insights", response_model=List[InsightResponse])
async def get_project_insights(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get all insights for a project."""
    result = await db.execute(
        select(Project)
        .where(Project.id == project_id, Project.user_id == current_user.id)
        .options(selectinload(Project.insights))
    )
    project = result.scalar_one_or_none()

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    return [
        InsightResponse(
            id=insight.id,
            project_id=insight.project_id,
            insight_type=insight.insight_type,
            title=insight.title,
            content=insight.content,
            related_paper_ids=insight.related_paper_ids,
            created_at=insight.created_at,
        )
        for insight in project.insights
    ]


@router.delete("/project/{project_id}/insights", status_code=status.HTTP_204_NO_CONTENT)
async def clear_project_insights(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Clear all insights for a project."""
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == current_user.id)
    )
    project = result.scalar_one_or_none()

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    await db.execute(
        ProjectInsight.__table__.delete().where(ProjectInsight.project_id == project_id)
    )
    await db.commit()


@router.post("/project/{project_id}/search", response_model=List[SearchResult])
async def search_project_papers(
    project_id: UUID,
    search_query: SearchQuery,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Semantic search across papers in a project."""
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == current_user.id)
    )
    project = result.scalar_one_or_none()

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    # Perform semantic search
    results = await search_papers_by_query(
        db=db,
        project_id=project_id,
        query=search_query.query,
        limit=search_query.limit,
    )

    return results
