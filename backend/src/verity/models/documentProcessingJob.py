from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    PrimaryKeyConstraint,
    String,
    Text,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.schema import conv

from verity.models.base import DatabaseBase


class DocumentProcessingJob(DatabaseBase):
    __tablename__ = "documentProcessingJobs"

    __table_args__ = (
        PrimaryKeyConstraint(
            "jobId",
            name="primaryKeyDocumentProcessingJobs",
        ),
        CheckConstraint(
            "\"status\" IN "
            "('queued', 'processing', 'succeeded', 'failed')",
            name=conv("validDocumentProcessingJobStatus"),
        ),
        CheckConstraint(
            '"attemptCount" >= 0',
            name=conv("nonnegativeDocumentJobAttemptCount"),
        ),
        Index(
            "indexDocumentJobsByStatusAndCreatedAt",
            "status",
            "createdAt",
        ),
        Index(
            "indexDocumentJobsByDocument",
            "documentId",
        ),
        Index(
            "uniqueActiveDocumentProcessingJob",
            "documentId",
            unique=True,
            postgresql_where=text(
                "\"status\" IN ('queued', 'processing')"
            ),
        ),
    )

    jobId: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    documentId: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "investigationDocuments.documentId",
            name="foreignKeyProcessingJobDocument",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default=text("'queued'"),
    )

    attemptCount: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
    )

    leaseToken: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        nullable=True,
    )

    leaseExpiresAt: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    createdAt: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    startedAt: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    completedAt: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    extractedText: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    errorMessage: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )