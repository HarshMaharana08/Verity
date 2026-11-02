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
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.schema import conv

from verity.models.base import DatabaseBase


class RcaEvidenceResponse(DatabaseBase):
    __tablename__ = "rcaEvidenceResponses"

    __table_args__ = (
        PrimaryKeyConstraint(
            "evidenceResponseId",
            name="primaryKeyRcaEvidenceResponses",
        ),
        UniqueConstraint(
            "evidenceRequestId",
            "revisionNumber",
            name="uniqueRcaEvidenceResponseRevision",
        ),
        CheckConstraint(
            '"revisionNumber" >= 1',
            name=conv("positiveRcaEvidenceResponseRevision"),
        ),
        CheckConstraint(
            "\"responseStatus\" IN "
            "('pending', 'supplied', 'unavailable')",
            name=conv("validRcaEvidenceResponseStatus"),
        ),
    )

    evidenceResponseId: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    evidenceRequestId: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "rcaEvidenceRequests.evidenceRequestId",
            name="foreignKeyRcaEvidenceResponseRequest",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )

    revisionNumber: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    responseStatus: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    responseText: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    respondedByLabel: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    createdAt: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class RcaEvidenceResponseDocument(DatabaseBase):
    __tablename__ = "rcaEvidenceResponseDocuments"

    __table_args__ = (
        PrimaryKeyConstraint(
            "evidenceResponseId",
            "documentId",
            name="primaryKeyRcaEvidenceResponseDocuments",
        ),
        Index(
            "indexRcaEvidenceResponseDocumentsByDocument",
            "documentId",
        ),
    )

    evidenceResponseId: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "rcaEvidenceResponses.evidenceResponseId",
            name="foreignKeyRcaEvidenceDocumentResponse",
            ondelete="RESTRICT",
        ),
        primary_key=True,
    )

    documentId: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "investigationDocuments.documentId",
            name="foreignKeyRcaEvidenceDocumentSource",
            ondelete="RESTRICT",
        ),
        primary_key=True,
    )