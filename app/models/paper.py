import uuid
import json
from datetime import datetime
from enum import Enum
from sqlalchemy import String, Text, DateTime, ForeignKey, Integer, TypeDecorator
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class PaperStatus(str, Enum):
    UPLOADING = "uploading"
    PROCESSING = "processing"
    EXTRACTING = "extracting"
    ANALYZING = "analyzing"
    ANALYZED = "analyzed"
    FAILED = "failed"


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


class Paper(Base):
    __tablename__ = "papers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )

    # Paper metadata
    title: Mapped[str] = mapped_column(String(500), nullable=True)
    authors = mapped_column(JSONType, nullable=True)  # List stored as JSON
    abstract: Mapped[str] = mapped_column(Text, nullable=True)
    doi: Mapped[str] = mapped_column(String(100), nullable=True, index=True)
    year: Mapped[int] = mapped_column(Integer, nullable=True)
    journal: Mapped[str] = mapped_column(String(500), nullable=True)

    # Content
    full_text: Mapped[str] = mapped_column(Text, nullable=True)
    pdf_path: Mapped[str] = mapped_column(String(500), nullable=True)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=True)

    # Processing status
    status: Mapped[str] = mapped_column(String(20), default=PaperStatus.UPLOADING.value, nullable=False)
    error_message: Mapped[str] = mapped_column(Text, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relationships
    project = relationship("Project", back_populates="papers")
    analysis = relationship("PaperAnalysis", back_populates="paper", uselist=False, cascade="all, delete-orphan")
    embeddings = relationship("PaperEmbedding", back_populates="paper", cascade="all, delete-orphan")
    recommendations = relationship("PaperRecommendation", back_populates="paper", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Paper {self.title or self.id}>"
