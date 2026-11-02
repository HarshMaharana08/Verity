from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    PrimaryKeyConstraint,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.schema import conv

from verity.models.base import DatabaseBase


class ExtractionReview(DatabaseBase):
    __tablename__ = "extractionReviews"

    __table_args__ = (
        PrimaryKeyConstraint(
            "reviewId",
            name="primaryKeyExtractionReviews",
        ),
        UniqueConstraint(
            "extractionId",
            "revisionNumber",
            name="uniqueExtractionReviewRevision",
        ),
        CheckConstraint(
            '"revisionNumber" >= 1',
            name=conv("positiveExtractionReviewRevision"),
        ),
        CheckConstraint(
            "\"reviewStatus\" IN ('draft', 'approved')",
            name=conv("validExtractionReviewStatus"),
        ),
        CheckConstraint(
            'jsonb_typeof("fieldDecisions") = \'object\'',
            name=conv("reviewFieldDecisionsIsObject"),
        ),
        CheckConstraint(
            'jsonb_typeof("clarificationResponses") = \'object\'',
            name=conv("reviewClarificationsIsObject"),
        ),
        CheckConstraint(
            'jsonb_typeof("assessmentSnapshot") = \'object\'',
            name=conv("reviewAssessmentIsObject"),
        ),
    )

    reviewId: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    extractionId: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "incidentExtractions.extractionId",
            name="foreignKeyReviewExtraction",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )

    revisionNumber: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    reviewStatus: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default=text("'draft'"),
    )

    reviewerLabel: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    assessmentVersion: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    assessmentSnapshot: Mapped[dict[str, object]] = mapped_column(
        JSONB(none_as_null=True),
        nullable=False,
    )

    fieldDecisions: Mapped[dict[str, object]] = mapped_column(
        JSONB(none_as_null=True),
        nullable=False,
    )

    clarificationResponses: Mapped[
        dict[str, object]
    ] = mapped_column(
        JSONB(none_as_null=True),
        nullable=False,
    )

    reviewNote: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    createdAt: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )