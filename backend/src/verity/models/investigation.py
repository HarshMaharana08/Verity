from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from verity.models.base import DatabaseBase


class Investigation(DatabaseBase):
    __tablename__ = "investigations"

    __table_args__ = (
        CheckConstraint(
            "length(trim(title)) > 0",
            name="title_not_blank",
        ),
    )

    investigationId: Mapped[UUID] = mapped_column(
        "investigation_id",
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        server_default="draft",
    )

    createdAt: Mapped[datetime] = mapped_column(
        "created_at",
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )