from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from app.database import get_db
from app.models.user import User
from app.models.project import Project
from app.models.paper import Paper, PaperStatus
from app.schemas.project import ProjectCreate, ProjectUpdate, ProjectResponse, ProjectListResponse
from app.utils.auth import get_current_user


router = APIRouter(prefix="/projects", tags=["Projects"])


@router.get("", response_model=ProjectListResponse)
async def list_projects(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all projects for the current user."""
    # Get projects with paper counts
    result = await db.execute(
        select(Project)
        .where(Project.user_id == current_user.id)
        .options(selectinload(Project.papers))
        .order_by(Project.updated_at.desc())
    )
    projects = result.scalars().all()

    # Build response with counts
    project_responses = []
    for project in projects:
        paper_count = len(project.papers)
        analyzed_count = sum(1 for p in project.papers if p.status == PaperStatus.ANALYZED)
        project_responses.append(
            ProjectResponse(
                id=project.id,
                name=project.name,
                description=project.description,
                research_topic=project.research_topic,
                paper_count=paper_count,
                analyzed_count=analyzed_count,
                created_at=project.created_at,
                updated_at=project.updated_at,
            )
        )

    return ProjectListResponse(projects=project_responses, total=len(project_responses))


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    project_data: ProjectCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new project."""
    project = Project(
        user_id=current_user.id,
        name=project_data.name,
        description=project_data.description,
        research_topic=project_data.research_topic,
    )

    db.add(project)
    await db.commit()
    await db.refresh(project)

    return ProjectResponse(
        id=project.id,
        name=project.name,
        description=project.description,
        research_topic=project.research_topic,
        paper_count=0,
        analyzed_count=0,
        created_at=project.created_at,
        updated_at=project.updated_at,
    )


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a specific project by ID."""
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

    paper_count = len(project.papers)
    analyzed_count = sum(1 for p in project.papers if p.status == PaperStatus.ANALYZED)

    return ProjectResponse(
        id=project.id,
        name=project.name,
        description=project.description,
        research_topic=project.research_topic,
        paper_count=paper_count,
        analyzed_count=analyzed_count,
        created_at=project.created_at,
        updated_at=project.updated_at,
    )


@router.put("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: UUID,
    project_data: ProjectUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a project."""
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

    # Update fields if provided
    if project_data.name is not None:
        project.name = project_data.name
    if project_data.description is not None:
        project.description = project_data.description
    if project_data.research_topic is not None:
        project.research_topic = project_data.research_topic

    await db.commit()
    await db.refresh(project)

    paper_count = len(project.papers)
    analyzed_count = sum(1 for p in project.papers if p.status == PaperStatus.ANALYZED)

    return ProjectResponse(
        id=project.id,
        name=project.name,
        description=project.description,
        research_topic=project.research_topic,
        paper_count=paper_count,
        analyzed_count=analyzed_count,
        created_at=project.created_at,
        updated_at=project.updated_at,
    )


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a project and all its papers."""
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == current_user.id)
    )
    project = result.scalar_one_or_none()

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    await db.delete(project)
    await db.commit()
