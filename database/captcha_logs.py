from sqlalchemy import (
    Index,
    Integer,
    ForeignKey,
    Enum,
    UniqueConstraint,
)
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship,
)

from database.base import Base
from constants.captcha_constants import CaptchaStatus


class CaptchaLogs(Base):
    __tablename__ = "captcha_logs"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    group_id: Mapped[int] = mapped_column(
        ForeignKey("groups.id", ondelete="CASCADE"),
        nullable=False,
    )

    status: Mapped[CaptchaStatus] = mapped_column(
        Enum(
            CaptchaStatus,
            name="captcha_status_enum",
        ),
        nullable=False,
        default=CaptchaStatus.PENDING,
    )

    # 🔒 1 пользователь — 1 капча в 1 группе
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "group_id",
            name="uq_captcha_user_group",
        ),
        Index("ix_captcha_user_id", "user_id"),
        Index("ix_captcha_group_id", "group_id"),
    )

    user = relationship(
        "User",
        back_populates="captcha_logs",
    )
    group = relationship(
        "Group",
        back_populates="captcha_logs",
    )
