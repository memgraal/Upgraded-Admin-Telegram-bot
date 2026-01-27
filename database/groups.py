from sqlalchemy import (
    BigInteger,
    DateTime,
    Enum,
    JSON,
    func,
)
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship,
)

from database.base import Base
from constants.group_constants import GroupType


class Group(Base):
    __tablename__ = "groups"

    id: Mapped[BigInteger] = mapped_column(
        BigInteger,
        primary_key=True,
    )

    chat_id: Mapped[BigInteger] = mapped_column(
        BigInteger,
        unique=True,
        nullable=False,
    )

    # !JSON: {banwords: List[], welcome_message: str | "", ...}
    settings: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )

    subscription_type: Mapped[GroupType] = mapped_column(
        # !type: paid | free
        Enum(
            GroupType,
            name="group_subscription_type_enum",
        ),
        nullable=False,
        default=GroupType.FREE,
    )

    paid_until: Mapped[DateTime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    created_at: Mapped[DateTime] = mapped_column(
        DateTime,
        server_default=func.now()
    )

    users = relationship(
        "UserGroup",
        back_populates="group",
        cascade="all, delete-orphan"
    )

    captcha_logs = relationship(
        "CaptchaLogs",
        back_populates="group",
        cascade="all, delete-orphan",
    )
