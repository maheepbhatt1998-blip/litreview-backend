import httpx
from typing import Optional, List, Dict, Any
from app.config import settings


class SemanticScholarService:
    """Service for interacting with Semantic Scholar API."""

    BASE_URL = "https://api.semanticscholar.org/graph/v1"

    def __init__(self):
        self.headers = {}
        if settings.SEMANTIC_SCHOLAR_API_KEY:
            self.headers["x-api-key"] = settings.SEMANTIC_SCHOLAR_API_KEY

    async def search_papers(
        self,
        query: str,
        limit: int = 10,
        fields: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Search for papers by query string."""
        if fields is None:
            fields = [
                "paperId", "title", "abstract", "authors",
                "year", "citationCount", "url", "externalIds"
            ]

        params = {
            "query": query,
            "limit": min(limit, 100),
            "fields": ",".join(fields),
        }

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.BASE_URL}/paper/search",
                params=params,
                headers=self.headers,
                timeout=30.0,
            )

            if response.status_code == 200:
                data = response.json()
                return data.get("data", [])
            else:
                return []

    async def get_paper_by_doi(
        self,
        doi: str,
        fields: Optional[List[str]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Get paper details by DOI."""
        if fields is None:
            fields = [
                "paperId", "title", "abstract", "authors",
                "year", "citationCount", "url", "externalIds",
                "references", "citations"
            ]

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.BASE_URL}/paper/DOI:{doi}",
                params={"fields": ",".join(fields)},
                headers=self.headers,
                timeout=30.0,
            )

            if response.status_code == 200:
                return response.json()
            else:
                return None

    async def get_paper_recommendations(
        self,
        paper_id: str,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Get paper recommendations based on a paper ID."""
        fields = [
            "paperId", "title", "abstract", "authors",
            "year", "citationCount", "url", "externalIds"
        ]

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.BASE_URL}/paper/{paper_id}/recommendations",
                params={
                    "fields": ",".join(fields),
                    "limit": min(limit, 100),
                },
                headers=self.headers,
                timeout=30.0,
            )

            if response.status_code == 200:
                data = response.json()
                return data.get("recommendedPapers", [])
            else:
                return []

    async def get_citations(
        self,
        paper_id: str,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Get papers that cite the given paper."""
        fields = [
            "paperId", "title", "abstract", "authors",
            "year", "url", "externalIds"
        ]

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.BASE_URL}/paper/{paper_id}/citations",
                params={
                    "fields": ",".join([f"citingPaper.{f}" for f in fields]),
                    "limit": min(limit, 100),
                },
                headers=self.headers,
                timeout=30.0,
            )

            if response.status_code == 200:
                data = response.json()
                return [item.get("citingPaper", {}) for item in data.get("data", [])]
            else:
                return []

    async def get_references(
        self,
        paper_id: str,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Get papers referenced by the given paper."""
        fields = [
            "paperId", "title", "abstract", "authors",
            "year", "url", "externalIds"
        ]

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.BASE_URL}/paper/{paper_id}/references",
                params={
                    "fields": ",".join([f"citedPaper.{f}" for f in fields]),
                    "limit": min(limit, 100),
                },
                headers=self.headers,
                timeout=30.0,
            )

            if response.status_code == 200:
                data = response.json()
                return [item.get("citedPaper", {}) for item in data.get("data", [])]
            else:
                return []

    async def find_similar_papers(
        self,
        title: str,
        abstract: Optional[str] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Find similar papers based on title and abstract."""
        # Build search query from title and key abstract terms
        query = title
        if abstract:
            # Add first few significant words from abstract
            words = abstract.split()[:20]
            query = f"{title} {' '.join(words)}"

        return await self.search_papers(query, limit=limit)


def format_recommendation(paper: Dict[str, Any], source: str, relationship: str) -> Dict[str, Any]:
    """Format a Semantic Scholar paper as a recommendation."""
    authors = paper.get("authors", [])
    author_names = [a.get("name", "") for a in authors] if authors else None

    external_ids = paper.get("externalIds", {}) or {}
    doi = external_ids.get("DOI")

    url = paper.get("url")
    if not url and doi:
        url = f"https://doi.org/{doi}"

    return {
        "recommended_title": paper.get("title", "Unknown"),
        "recommended_authors": author_names,
        "recommended_abstract": paper.get("abstract"),
        "recommended_doi": doi,
        "recommended_url": url,
        "recommended_year": paper.get("year"),
        "similarity_score": None,  # Semantic Scholar doesn't provide similarity scores
        "source": source,
        "relationship_type": relationship,
    }


# Singleton instance
semantic_scholar = SemanticScholarService()
