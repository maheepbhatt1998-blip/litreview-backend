import uuid
import json
from datetime import datetime
from sqlalchemy import String, Text, DateTime, ForeignKey, Integer, Float, TypeDecorator
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


# Custom type for JSON storage (works with SQLite)
class JSONType(TypeDecorator):
    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None:
            return json.dumps(value)
        return None

    def process_result_value(self, value, dialect):
        if value is not None:
            return json.loads(value)
        return None


class PaperAnalysis(Base):
    __tablename__ = "paper_analyses"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    paper_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("papers.id", ondelete="CASCADE"), unique=True, nullable=False
    )

    # Analysis sections
    importance: Mapped[str] = mapped_column(Text, nullable=True)
    importance_score: Mapped[int] = mapped_column(Integer, nullable=True)  # 1-10
    novelty: Mapped[str] = mapped_column(Text, nullable=True)
    methodology: Mapped[str] = mapped_column(Text, nullable=True)
    results_summary: Mapped[str] = mapped_column(Text, nullable=True)
    future_work: Mapped[str] = mapped_column(Text, nullable=True)

    # Structured data (stored as JSON)
    key_findings = mapped_column(JSONType, nullable=True)
    key_takeaways = mapped_column(JSONType, nullable=True)
    conventional_methods = mapped_column(JSONType, nullable=True)
    innovations = mapped_column(JSONType, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relationships
    paper = relationship("Paper", back_populates="analysis")

    def __repr__(self):
        return f"<PaperAnalysis for {self.paper_id}>"


class PaperEmbedding(Base):
    __tablename__ = "paper_embeddings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    paper_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("papers.id", ondelete="CASCADE"), nullable=False
    )

    # Embedding data (stored as JSON text for SQLite compatibility)
    embedding = mapped_column(Text, nullable=True)  # JSON string of embedding vector
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    # Relationships
    paper = relationship("Paper", back_populates="embeddings")

    def __repr__(self):
        return f"<PaperEmbedding {self.paper_id}:{self.chunk_index}>"


class PaperRecommendation(Base):
    __tablename__ = "paper_recommendations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    paper_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("papers.id", ondelete="CASCADE"), nullable=False
    )

    # Recommended paper info
    recommended_title: Mapped[str] = mapped_column(String(500), nullable=False)
    recommended_authors = mapped_column(JSONType, nullable=True)  # List stored as JSON
    recommended_abstract: Mapped[str] = mapped_column(Text, nullable=True)
    recommended_doi: Mapped[str] = mapped_column(String(100), nullable=True)
    recommended_url: Mapped[str] = mapped_column(String(500), nullable=True)
    recommended_year: Mapped[int] = mapped_column(Integer, nullable=True)

    # Similarity info
    similarity_score: Mapped[float] = mapped_column(Float, nullable=True)
    source: Mapped[str] = mapped_column(String(50), nullable=False)  # 'semantic_scholar', 'internal'
    relationship_type: Mapped[str] = mapped_column(String(50), nullable=True)  # 'citation', 'reference', 'similar'

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    # Relationships
    paper = relationship("Paper", back_populates="recommendations")

    def __repr__(self):
        return f"<PaperRecommendation {self.recommended_title[:30]}...>"


class ProjectInsight(Base):
    __tablename__ = "project_insights"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )

    # Insight data
    insight_type: Mapped[str] = mapped_column(String(50), nullable=False)  # 'research_gap', 'trend', 'idea', 'comparison'
    title: Mapped[str] = mapped_column(String(500), nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    related_paper_ids = mapped_column(JSONType, nullable=True)  # List of UUIDs stored as JSON

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    # Relationships
    project = relationship("Project", back_populates="insights")

    def __repr__(self):
        return f"<ProjectInsight {self.insight_type}: {self.title}>"
