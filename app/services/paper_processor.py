import asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from app.config import settings
from app.models.paper import Paper, PaperStatus
from app.models.analysis import PaperAnalysis, PaperRecommendation
from app.services.pdf_parser import parse_pdf
from app.services.claude_service import claude_service
from app.services.semantic_scholar import semantic_scholar, format_recommendation


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


async def process_paper(paper_id: str, reanalyze: bool = False):
    """Process a paper: extract text, analyze with Claude, get recommendations."""
    async with BackgroundSessionLocal() as db:
        try:
            # Get paper from database
            result = await db.execute(select(Paper).where(Paper.id == paper_id))
            paper = result.scalar_one_or_none()

            if not paper:
                return

            # Step 1: Extract text from PDF (skip if reanalyzing)
            if not reanalyze and paper.pdf_path:
                try:
                    paper.status = PaperStatus.EXTRACTING.value
                    await db.commit()

                    parsed = parse_pdf(paper.pdf_path)

                    paper.title = parsed.title or paper.title
                    paper.authors = parsed.authors
                    paper.abstract = parsed.abstract
                    paper.full_text = parsed.full_text
                    paper.doi = parsed.doi
                    paper.year = parsed.year

                    await db.commit()

                except Exception as e:
                    paper.status = PaperStatus.FAILED.value
                    paper.error_message = f"PDF extraction failed: {str(e)}"
                    await db.commit()
                    return

            # Step 2: Analyze with Claude
            try:
                paper.status = PaperStatus.ANALYZING.value
                await db.commit()

                # Check if we have text to analyze
                text_to_analyze = paper.full_text or paper.abstract or ""
                if len(text_to_analyze) < 100:
                    paper.status = PaperStatus.FAILED.value
                    paper.error_message = "Insufficient text extracted from PDF"
                    await db.commit()
                    return

                # Call Claude API
                analysis_result = await claude_service.analyze_paper(
                    title=paper.title,
                    abstract=paper.abstract,
                    full_text=text_to_analyze,
                )

                # Delete existing analysis if reanalyzing
                if reanalyze:
                    existing = await db.execute(
                        select(PaperAnalysis).where(PaperAnalysis.paper_id == paper.id)
                    )
                    existing_analysis = existing.scalar_one_or_none()
                    if existing_analysis:
                        await db.delete(existing_analysis)

                # Create analysis record
                analysis = PaperAnalysis(
                    paper_id=paper.id,
                    importance=analysis_result.get("importance"),
                    importance_score=analysis_result.get("importance_score"),
                    novelty=analysis_result.get("novelty"),
                    methodology=analysis_result.get("methodology"),
                    results_summary=analysis_result.get("results_summary"),
                    future_work=analysis_result.get("future_work"),
                    key_findings=analysis_result.get("key_findings"),
                    key_takeaways=analysis_result.get("key_takeaways"),
                    conventional_methods=analysis_result.get("conventional_methods"),
                    innovations=analysis_result.get("innovations"),
                )

                db.add(analysis)
                await db.commit()

            except Exception as e:
                paper.status = PaperStatus.FAILED.value
                paper.error_message = f"Analysis failed: {str(e)}"
                await db.commit()
                return

            # Step 3: Get recommendations from Semantic Scholar
            try:
                recommendations = []

                # Try to find by DOI first
                ss_paper = None
                if paper.doi:
                    ss_paper = await semantic_scholar.get_paper_by_doi(paper.doi)

                if ss_paper:
                    paper_id_ss = ss_paper.get("paperId")

                    # Get recommendations
                    recs = await semantic_scholar.get_paper_recommendations(paper_id_ss, limit=5)
                    for rec in recs:
                        recommendations.append(
                            format_recommendation(rec, "semantic_scholar", "similar")
                        )

                    # Get citations
                    citations = await semantic_scholar.get_citations(paper_id_ss, limit=5)
                    for cit in citations:
                        if cit:
                            recommendations.append(
                                format_recommendation(cit, "semantic_scholar", "citation")
                            )

                    # Get references
                    refs = await semantic_scholar.get_references(paper_id_ss, limit=5)
                    for ref in refs:
                        if ref:
                            recommendations.append(
                                format_recommendation(ref, "semantic_scholar", "reference")
                            )
                else:
                    # Fall back to search by title
                    similar = await semantic_scholar.find_similar_papers(
                        title=paper.title or "",
                        abstract=paper.abstract,
                        limit=10,
                    )
                    for sim in similar:
                        recommendations.append(
                            format_recommendation(sim, "semantic_scholar", "similar")
                        )

                # Delete existing recommendations if reanalyzing
                if reanalyze:
                    existing_recs = await db.execute(
                        select(PaperRecommendation).where(PaperRecommendation.paper_id == paper.id)
                    )
                    for rec in existing_recs.scalars():
                        await db.delete(rec)

                # Save recommendations
                for rec_data in recommendations[:15]:  # Limit to 15 recommendations
                    rec = PaperRecommendation(
                        paper_id=paper.id,
                        **rec_data,
                    )
                    db.add(rec)

                await db.commit()

            except Exception as e:
                # Non-fatal: recommendations failed but analysis succeeded
                print(f"Warning: Failed to get recommendations: {str(e)}")

            # Mark as complete
            paper.status = PaperStatus.ANALYZED.value
            paper.error_message = None
            await db.commit()

        except Exception as e:
            # Mark as failed
            try:
                result = await db.execute(select(Paper).where(Paper.id == paper_id))
                paper = result.scalar_one_or_none()
                if paper:
                    paper.status = PaperStatus.FAILED.value
                    paper.error_message = f"Processing failed: {str(e)}"
                    await db.commit()
            except Exception:
                pass


def process_paper_task(paper_id: str, reanalyze: bool = False):
    """Wrapper to run async process_paper in background task."""
    asyncio.run(process_paper(paper_id, reanalyze))
