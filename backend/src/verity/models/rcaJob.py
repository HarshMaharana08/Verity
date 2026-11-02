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
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.schema import conv

from verity.models.base import DatabaseBase


class RcaJob(DatabaseBase):
    __tablename__ = "rcaJobs"

    __table_args__ = (
        PrimaryKeyConstraint(
            "rcaJobId",
            name="primaryKeyRcaJobs",
        ),
        CheckConstraint(
            "\"status\" IN "
            "('queued', 'processing', 'succeeded', 'failed')",
            name=conv("validRcaJobStatus"),
        ),
        CheckConstraint(
            '"attemptCount" >= 0',
            name=conv("nonnegativeRcaJobAttemptCount"),
        ),
        CheckConstraint(
            'jsonb_typeof("inputSnapshot") = \'object\'',
            name=conv("rcaJobInputSnapshotIsObject"),
        ),
        CheckConstraint(
            '"inputSha256" ~ \'^[0-9a-f]{64}$\'',
            name=conv("validRcaJobInputSha256"),
        ),
        Index(
            "indexRcaJobsByStatusAndAvailableAt",
            "status",
            "availableAt",
        ),
        Index(
            "indexRcaJobsBySourceReview",
            "sourceReviewId",
        ),
        Index(
            "uniqueActiveRcaJobBySourceReview",
            "sourceReviewId",
            unique=True,
            postgresql_where=text(
                "\"status\" IN ('queued', 'processing')"
            ),
        ),
    )

    rcaJobId: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    sourceReviewId: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "extractionReviews.reviewId",
            name="foreignKeyRcaJobSourceReview",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )

    inputSnapshot: Mapped[dict[str, object]] = mapped_column(
        JSONB(none_as_null=True),
        nullable=False,
    )

    inputSha256: Mapped[str] = mapped_column(
        String(64),
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

    workflowVersion: Mapped[str] = mapped_column(
        String(50),
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