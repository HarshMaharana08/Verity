from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    PrimaryKeyConstraint,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from verity.models.base import DatabaseBase


class RcaEvidenceRequest(DatabaseBase):
    __tablename__ = "rcaEvidenceRequests"

    __table_args__ = (
        PrimaryKeyConstraint(
            "evidenceRequestId",
            name="primaryKeyRcaEvidenceRequests",
        ),
        Index(
            "indexRcaEvidenceRequestsByReview",
            "rcaReviewId",
            "createdAt",
        ),
    )

    evidenceRequestId: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    rcaReviewId: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "rcaReviews.rcaReviewId",
            name="foreignKeyRcaEvidenceRequestReview",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )

    hypothesisId: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    requestText: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    rationale: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    requestedByLabel: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    createdAt: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )