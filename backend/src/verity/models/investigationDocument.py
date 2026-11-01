from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    PrimaryKeyConstraint,
    String,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.schema import conv

from verity.models.base import DatabaseBase


class InvestigationDocument(DatabaseBase):
    __tablename__ = "investigationDocuments"

    __table_args__ = (
        PrimaryKeyConstraint(
            "documentId",
            name="primaryKeyInvestigationDocuments",
        ),
        UniqueConstraint(
            "storageKey",
            name="uniqueDocumentStorageKey",
        ),
        CheckConstraint(
            '"fileSizeBytes" > 0',
            name=conv("positiveDocumentFileSize"),
        ),
        Index(
            "indexDocumentsByInvestigation",
            "investigationId",
        ),
    )

    documentId: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    investigationId: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "investigations.investigation_id",
            name="foreignKeyDocumentInvestigation",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )

    originalFileName: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    storageKey: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )

    mediaType: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    fileSizeBytes: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )

    sha256Digest: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    uploadedAt: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )