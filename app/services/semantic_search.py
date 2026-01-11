from uuid import UUID
from typing import List
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.models.paper import Paper, PaperStatus
from app.models.analysis import PaperEmbedding
from app.schemas.analysis import SearchResult


async def search_papers_by_query(
    db: AsyncSession,
    project_id: UUID,
    query: str,
    limit: int = 10,
) -> List[SearchResult]:
    """
    Search papers in a project by semantic similarity.

    For now, this uses simple text matching. In production, you would:
    1. Generate an embedding for the query using OpenAI/Claude
    2. Use pgvector to find similar embeddings
    """

    # Get all analyzed papers in the project
    result = await db.execute(
        select(Paper)
        .where(
            Paper.project_id == project_id,
            Paper.status == PaperStatus.ANALYZED,
        )
        .options(selectinload(Paper.analysis))
    )
    papers = result.scalars().all()

    # Simple text-based search (can be replaced with vector search)
    query_lower = query.lower()
    query_terms = query_lower.split()

    search_results = []
    for paper in papers:
        # Calculate relevance score based on term frequency
        searchable_text = " ".join(filter(None, [
            paper.title or "",
            paper.abstract or "",
            paper.analysis.importance if paper.analysis else "",
            paper.analysis.novelty if paper.analysis else "",
            paper.analysis.methodology if paper.analysis else "",
        ])).lower()

        # Count matching terms
        matches = sum(1 for term in query_terms if term in searchable_text)
        if matches == 0:
            continue

        relevance = matches / len(query_terms)

        # Find best matching snippet
        matched_chunk = ""
        for text_source in [paper.abstract, paper.analysis.importance if paper.analysis else None]:
            if text_source:
                for term in query_terms:
                    if term in text_source.lower():
                        # Extract context around the match
                        idx = text_source.lower().find(term)
                        start = max(0, idx - 100)
                        end = min(len(text_source), idx + 100)
                        matched_chunk = "..." + text_source[start:end] + "..."
                        break
                if matched_chunk:
                    break

        search_results.append(SearchResult(
            paper_id=paper.id,
            title=paper.title,
            abstract=paper.abstract[:300] + "..." if paper.abstract and len(paper.abstract) > 300 else paper.abstract,
            relevance_score=relevance,
            matched_chunk=matched_chunk or (paper.abstract[:200] if paper.abstract else ""),
        ))

    # Sort by relevance and limit
    search_results.sort(key=lambda x: x.relevance_score, reverse=True)
    return search_results[:limit]


async def generate_embeddings_for_paper(
    db: AsyncSession,
    paper_id: UUID,
    text_chunks: List[str],
    embeddings: List[List[float]],
):
    """
    Store embeddings for a paper.

    In production, you would:
    1. Chunk the paper text into smaller segments
    2. Generate embeddings using OpenAI's ada-002 or similar
    3. Store in pgvector for efficient similarity search
    """
    # Clear existing embeddings
    await db.execute(
        PaperEmbedding.__table__.delete().where(PaperEmbedding.paper_id == paper_id)
    )

    # Store new embeddings
    for i, (chunk, embedding) in enumerate(zip(text_chunks, embeddings)):
        paper_embedding = PaperEmbedding(
            paper_id=paper_id,
            chunk_text=chunk,
            chunk_index=i,
            embedding=embedding,
        )
        db.add(paper_embedding)

    await db.commit()


async def vector_search(
    db: AsyncSession,
    project_id: UUID,
    query_embedding: List[float],
    limit: int = 10,
) -> List[SearchResult]:
    """
    Perform vector similarity search using pgvector.

    This requires:
    1. The pgvector extension enabled
    2. Embeddings stored for papers
    3. A query embedding generated from the search query
    """
    # SQL query using pgvector's cosine distance
    sql = text("""
        SELECT
            pe.paper_id,
            p.title,
            p.abstract,
            pe.chunk_text,
            1 - (pe.embedding <=> :query_embedding) as similarity
        FROM paper_embeddings pe
        JOIN papers p ON p.id = pe.paper_id
        WHERE p.project_id = :project_id
        ORDER BY pe.embedding <=> :query_embedding
        LIMIT :limit
    """)

    result = await db.execute(
        sql,
        {
            "query_embedding": str(query_embedding),
            "project_id": str(project_id),
            "limit": limit,
        }
    )

    rows = result.fetchall()
    return [
        SearchResult(
            paper_id=row.paper_id,
            title=row.title,
            abstract=row.abstract[:300] + "..." if row.abstract and len(row.abstract) > 300 else row.abstract,
            relevance_score=float(row.similarity),
            matched_chunk=row.chunk_text,
        )
        for row in rows
    ]
