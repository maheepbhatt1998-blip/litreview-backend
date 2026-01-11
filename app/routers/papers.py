import os
import uuid as uuid_module
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.database import get_db
from app.models.user import User
from app.models.project import Project
from app.models.paper import Paper, PaperStatus
from app.schemas.paper import PaperResponse, PaperListResponse, PaperUploadResponse
from app.schemas.analysis import RecommendationResponse
from app.utils.auth import get_current_user
from app.config import settings
from app.services.paper_processor import process_paper_task


router = APIRouter(prefix="/papers", tags=["Papers"])


async def verify_project_ownership(
    project_id: UUID, user_id: UUID, db: AsyncSession
) -> Project:
    """Verify that the project exists and belongs to the user."""
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == user_id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )
    return project


@router.get("/project/{project_id}", response_model=PaperListResponse)
async def list_papers(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all papers in a project."""
    await verify_project_ownership(project_id, current_user.id, db)

    result = await db.execute(
        select(Paper)
        .where(Paper.project_id == project_id)
        .options(selectinload(Paper.analysis))
        .order_by(Paper.created_at.desc())
    )
    papers = result.scalars().all()

    paper_responses = [
        PaperResponse(
            id=p.id,
            project_id=p.project_id,
            title=p.title,
            authors=p.authors,
            abstract=p.abstract,
            doi=p.doi,
            year=p.year,
            journal=p.journal,
            status=p.status,
            error_message=p.error_message,
            original_filename=p.original_filename,
            has_analysis=p.analysis is not None,
            created_at=p.created_at,
            updated_at=p.updated_at,
        )
        for p in papers
    ]

    analyzed = sum(1 for p in papers if p.status == PaperStatus.ANALYZED)
    processing = sum(1 for p in papers if p.status in [PaperStatus.PROCESSING, PaperStatus.EXTRACTING, PaperStatus.ANALYZING])
    failed = sum(1 for p in papers if p.status == PaperStatus.FAILED)

    return PaperListResponse(
        papers=paper_responses,
        total=len(papers),
        analyzed=analyzed,
        processing=processing,
        failed=failed,
    )


@router.post("/project/{project_id}/upload", response_model=PaperUploadResponse)
async def upload_paper(
    project_id: UUID,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Upload a PDF paper to a project."""
    await verify_project_ownership(project_id, current_user.id, db)

    # Validate file type
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF files are allowed",
        )

    # Check file size
    content = await file.read()
    if len(content) > settings.MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File size exceeds maximum limit of {settings.MAX_FILE_SIZE // (1024*1024)}MB",
        )

    # Save file
    file_id = str(uuid_module.uuid4())
    file_path = os.path.join(settings.UPLOAD_DIR, f"{file_id}.pdf")

    with open(file_path, "wb") as f:
        f.write(content)

    # Create paper record
    paper = Paper(
        project_id=project_id,
        pdf_path=file_path,
        original_filename=file.filename,
        status=PaperStatus.PROCESSING,
    )

    db.add(paper)
    await db.commit()
    await db.refresh(paper)

    # Queue background processing
    background_tasks.add_task(process_paper_task, str(paper.id))

    return PaperUploadResponse(
        id=paper.id,
        status=paper.status,
        message="Paper uploaded successfully. Processing will begin shortly.",
    )


@router.get("/{paper_id}", response_model=PaperResponse)
async def get_paper(
    paper_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a specific paper by ID."""
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

    return PaperResponse(
        id=paper.id,
        project_id=paper.project_id,
        title=paper.title,
        authors=paper.authors,
        abstract=paper.abstract,
        doi=paper.doi,
        year=paper.year,
        journal=paper.journal,
        status=paper.status,
        error_message=paper.error_message,
        original_filename=paper.original_filename,
        has_analysis=paper.analysis is not None,
        created_at=paper.created_at,
        updated_at=paper.updated_at,
    )


@router.delete("/{paper_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_paper(
    paper_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a paper."""
    result = await db.execute(
        select(Paper)
        .where(Paper.id == paper_id)
        .options(selectinload(Paper.project))
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

    # Delete PDF file if exists
    if paper.pdf_path and os.path.exists(paper.pdf_path):
        os.remove(paper.pdf_path)

    await db.delete(paper)
    await db.commit()


@router.post("/{paper_id}/reanalyze", response_model=PaperUploadResponse)
async def reanalyze_paper(
    paper_id: UUID,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Re-run analysis on a paper."""
    result = await db.execute(
        select(Paper)
        .where(Paper.id == paper_id)
        .options(selectinload(Paper.project))
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

    # Update status
    paper.status = PaperStatus.ANALYZING
    paper.error_message = None
    await db.commit()

    # Queue background processing
    background_tasks.add_task(process_paper_task, str(paper.id), reanalyze=True)

    return PaperUploadResponse(
        id=paper.id,
        status=paper.status,
        message="Re-analysis queued successfully.",
    )


@router.get("/{paper_id}/recommendations", response_model=list[RecommendationResponse])
async def get_paper_recommendations(
    paper_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get similar paper recommendations for a paper."""
    result = await db.execute(
        select(Paper)
        .where(Paper.id == paper_id)
        .options(selectinload(Paper.project), selectinload(Paper.recommendations))
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

    return [
        RecommendationResponse(
            id=rec.id,
            paper_id=rec.paper_id,
            recommended_title=rec.recommended_title,
            recommended_authors=rec.recommended_authors,
            recommended_abstract=rec.recommended_abstract,
            recommended_doi=rec.recommended_doi,
            recommended_url=rec.recommended_url,
            recommended_year=rec.recommended_year,
            similarity_score=rec.similarity_score,
            source=rec.source,
            relationship_type=rec.relationship_type,
            created_at=rec.created_at,
        )
        for rec in paper.recommendations
    ]
