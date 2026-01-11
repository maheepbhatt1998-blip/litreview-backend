import asyncio
from typing import List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import selectinload
from app.config import settings
from app.models.project import Project
from app.models.paper import Paper, PaperStatus
from app.models.analysis import PaperAnalysis, ProjectInsight
from app.services.claude_service import claude_service


# Determine if using SQLite
is_sqlite = settings.DATABASE_URL.startswith("sqlite")

# Create a separate engine for background tasks
if is_sqlite:
    background_engine = create_async_engine(
        settings.DATABASE_URL,
        connect_args={"check_same_thread": False},
    )
else:
    background_engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=True)

BackgroundSessionLocal = async_sessionmaker(
    background_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def generate_project_insights(project_id: str, paper_ids: List[str]):
    """Generate cross-paper insights for a project."""
    async with BackgroundSessionLocal() as db:
        try:
            # Get project
            result = await db.execute(
                select(Project).where(Project.id == project_id)
            )
            project = result.scalar_one_or_none()

            if not project:
                return

            # Get papers with their analyses
            result = await db.execute(
                select(Paper)
                .where(Paper.id.in_(paper_ids))
                .options(selectinload(Paper.analysis))
            )
            papers = result.scalars().all()

            # Build paper summaries for Claude
            paper_summaries = []
            for paper in papers:
                if paper.analysis:
                    paper_summaries.append({
                        "title": paper.title or "Unknown",
                        "year": paper.year,
                        "importance": paper.analysis.importance,
                        "methodology": paper.analysis.methodology,
                        "results_summary": paper.analysis.results_summary,
                        "novelty": paper.analysis.novelty,
                    })

            if len(paper_summaries) < 2:
                return

            # Generate insights with Claude
            insights_result = await claude_service.generate_project_insights(
                project_topic=project.research_topic,
                paper_summaries=paper_summaries,
            )

            # Clear existing insights
            existing = await db.execute(
                select(ProjectInsight).where(ProjectInsight.project_id == project_id)
            )
            for insight in existing.scalars():
                await db.delete(insight)

            # Save new insights
            related_ids = paper_ids

            for insight_type, insight_data in insights_result.items():
                if isinstance(insight_data, dict) and "content" in insight_data:
                    insight = ProjectInsight(
                        project_id=project_id,
                        insight_type=insight_type,
                        title=insight_data.get("title", insight_type.replace("_", " ").title()),
                        content=insight_data["content"],
                        related_paper_ids=related_ids,
                    )
                    db.add(insight)

            await db.commit()

        except Exception as e:
            print(f"Error generating insights: {str(e)}")


def generate_project_insights_task(project_id: str, paper_ids: List[str]):
    """Wrapper to run async insight generation in background task."""
    asyncio.run(generate_project_insights(project_id, paper_ids))
