from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    PrimaryKeyConstraint,
    String,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.schema import conv

from verity.models.base import DatabaseBase


class RcaDraftRecord(DatabaseBase):
    __tablename__ = "rcaDrafts"

    __table_args__ = (
        PrimaryKeyConstraint(
            "rcaDraftId",
            name="primaryKeyRcaDrafts",
        ),
        UniqueConstraint(
            "rcaJobId",
            name="uniqueRcaDraftByJob",
        ),
        CheckConstraint(
            'jsonb_typeof("draftData") = \'object\'',
            name=conv("rcaDraftDataIsObject"),
        ),
        CheckConstraint(
            """(
                "draftData" #>> '{content,draftStatus}'
            ) IS NOT DISTINCT FROM 'draft'""",
            name=conv("rcaDraftContentIsDraft"),
        ),
    )

    rcaDraftId: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    rcaJobId: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "rcaJobs.rcaJobId",
            name="foreignKeyRcaDraftJob",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )

    schemaVersion: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    draftData: Mapped[dict[str, object]] = mapped_column(
        JSONB(none_as_null=True),
        nullable=False,
    )

    createdAt: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )