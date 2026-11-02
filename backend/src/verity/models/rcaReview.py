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
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.schema import conv

from verity.models.base import DatabaseBase


class RcaReview(DatabaseBase):
    __tablename__ = "rcaReviews"

    __table_args__ = (
        PrimaryKeyConstraint(
            "rcaReviewId",
            name="primaryKeyRcaReviews",
        ),
        UniqueConstraint(
            "rcaDraftId",
            "revisionNumber",
            name="uniqueRcaReviewRevision",
        ),
        CheckConstraint(
            '"revisionNumber" >= 1',
            name=conv("positiveRcaReviewRevision"),
        ),
        CheckConstraint(
            "\"reviewStatus\" IN ('draft', 'reviewed')",
            name=conv("validRcaReviewStatus"),
        ),
        CheckConstraint(
            'jsonb_typeof("hypothesisDecisions") = \'object\'',
            name=conv("rcaReviewDecisionsIsObject"),
        ),
        CheckConstraint(
            'jsonb_typeof("findingResponses") = \'object\'',
            name=conv("rcaReviewFindingResponsesIsObject"),
        ),
        CheckConstraint(
            'jsonb_typeof("assessmentSnapshot") = \'object\'',
            name=conv("rcaReviewAssessmentIsObject"),
        ),
    )

    rcaReviewId: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    rcaDraftId: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "rcaDrafts.rcaDraftId",
            name="foreignKeyRcaReviewDraft",
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

    hypothesisDecisions: Mapped[
        dict[str, object]
    ] = mapped_column(
        JSONB(none_as_null=True),
        nullable=False,
    )

    findingResponses: Mapped[dict[str, object]] = mapped_column(
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