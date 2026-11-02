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


class AiExtractionChunk(DatabaseBase):
    __tablename__ = "aiExtractionChunks"

    __table_args__ = (
        PrimaryKeyConstraint(
            "chunkId",
            name="primaryKeyAiExtractionChunks",
        ),
        UniqueConstraint(
            "aiJobId",
            "chunkIndex",
            name="uniqueAiJobChunkIndex",
        ),
        CheckConstraint(
            '"chunkIndex" >= 0',
            name=conv("nonnegativeAiChunkIndex"),
        ),
        CheckConstraint(
            '"startCharacter" >= 0 '
            'AND "endCharacter" > "startCharacter"',
            name=conv("validAiChunkCharacterRange"),
        ),
        CheckConstraint(
            '"attemptCount" >= 0',
            name=conv("nonnegativeAiChunkAttemptCount"),
        ),
        CheckConstraint(
            "\"status\" IN "
            "('queued', 'processing', 'succeeded', 'failed')",
            name=conv("validAiChunkStatus"),
        ),
        CheckConstraint(
            '"sourceTextSha256" ~ \'^[0-9a-f]{64}$\'',
            name=conv("validAiChunkSourceTextSha256"),
        ),
        CheckConstraint(
            """(
                "status" = 'succeeded'
                AND "extractedData" IS NOT NULL
            ) OR (
                "status" <> 'succeeded'
                AND "extractedData" IS NULL
            )""",
            name=conv("consistentAiChunkResult"),
        ),
        CheckConstraint(
            '"extractedData" IS NULL OR '
            'jsonb_typeof("extractedData") = \'object\'',
            name=conv("aiChunkDataIsObject"),
        ),
    )

    chunkId: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    aiJobId: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "aiExtractionJobs.aiJobId",
            name="foreignKeyAiChunkJob",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )

    chunkIndex: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    startCharacter: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    endCharacter: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    sourceTextSha256: Mapped[str] = mapped_column(
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

    extractedData: Mapped[dict[str, object] | None] = mapped_column(
        JSONB(none_as_null=True),
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

    createdAt: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    completedAt: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )