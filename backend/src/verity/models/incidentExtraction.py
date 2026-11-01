from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    PrimaryKeyConstraint,
    String,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.schema import conv

from verity.models.base import DatabaseBase


class IncidentExtractionRecord(DatabaseBase):
    __tablename__ = "incidentExtractions"

    __table_args__ = (
        PrimaryKeyConstraint(
            "extractionId",
            name="primaryKeyIncidentExtractions",
        ),
        CheckConstraint(
            'jsonb_typeof("extractedData") = \'object\'',
            name=conv("incidentExtractionDataIsObject"),
        ),
        CheckConstraint(
            '"sourceTextSha256" ~ \'^[0-9a-f]{64}$\'',
            name=conv("validExtractionSourceTextSha256"),
        ),
        Index(
            "indexExtractionsBySourceJobAndCreatedAt",
            "sourceProcessingJobId",
            "createdAt",
        ),
    )

    extractionId: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    sourceProcessingJobId: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "documentProcessingJobs.jobId",
            name="foreignKeyExtractionSourceProcessingJob",
            ondelete="RESTRICT",
        ),
        nullable=False,
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

    extractedData: Mapped[dict[str, object]] = mapped_column(
        JSONB,
        nullable=False,
    )

    createdAt: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )