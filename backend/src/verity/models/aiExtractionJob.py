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
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.schema import conv

from verity.models.base import DatabaseBase


class AiExtractionJob(DatabaseBase):
    __tablename__ = "aiExtractionJobs"

    __table_args__ = (
        PrimaryKeyConstraint(
            "aiJobId",
            name="primaryKeyAiExtractionJobs",
        ),
        CheckConstraint(
            "\"status\" IN "
            "('queued', 'processing', 'succeeded', 'failed')",
            name=conv("validAiExtractionJobStatus"),
        ),
        CheckConstraint(
            '"attemptCount" >= 0',
            name=conv("nonnegativeAiJobAttemptCount"),
        ),
        CheckConstraint(
            '"sourceTextSha256" ~ \'^[0-9a-f]{64}$\'',
            name=conv("validAiJobSourceTextSha256"),
        ),
        CheckConstraint(
            """(
                "status" = 'succeeded'
                AND "extractionId" IS NOT NULL
            ) OR (
                "status" <> 'succeeded'
                AND "extractionId" IS NULL
            )""",
            name=conv("consistentAiJobResult"),
        ),
        UniqueConstraint(
            "extractionId",
            name="uniqueAiJobExtractionResult",
        ),
        Index(
            "indexAiJobsByStatusAndAvailableAt",
            "status",
            "availableAt",
        ),
        Index(
            "indexAiJobsBySourceJob",
            "sourceProcessingJobId",
        ),
        Index(
            "uniqueActiveAiJobBySourceJob",
            "sourceProcessingJobId",
            unique=True,
            postgresql_where=text(
                "\"status\" IN ('queued', 'processing')"
            ),
        ),
    )

    aiJobId: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    sourceProcessingJobId: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "documentProcessingJobs.jobId",
            name="foreignKeyAiJobSourceProcessingJob",
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

    availableAt: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    leaseToken: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        nullable=True,
    )

    leaseExpiresAt: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    providerName: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    modelName: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )

    promptVersion: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    schemaVersion: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    sourceTextSha256: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    extractionId: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "incidentExtractions.extractionId",
            name="foreignKeyAiJobExtractionResult",
            ondelete="RESTRICT",
        ),
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

    errorCode: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    errorMessage: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )