from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    String,
    ForeignKey,
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

    settings = relationship(
        "GroupSettings",
        back_populates="group",
        uselist=False,
        cascade="all, delete-orphan",
    )

    banwords = relationship(
        "Banwords",
        back_populates="group",
        cascade="all, delete-orphan",
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


class GroupSettings(Base):
    __tablename__ = "group_settings"

    id: Mapped[BigInteger] = mapped_column(
        BigInteger,
        primary_key=True,
    )

    group_id: Mapped[BigInteger] = mapped_column(
        ForeignKey("groups.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )

    captcha_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    photo_check_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    group = relationship(
        "Group",
        back_populates="settings",
    )


class Banwords(Base):
    __tablename__ = "banwords"

    id: Mapped[BigInteger] = mapped_column(
        BigInteger,
        primary_key=True,
    )

    group_id: Mapped[BigInteger] = mapped_column(
        ForeignKey("groups.id", ondelete="CASCADE"),
        nullable=False,
    )

    word: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    group = relationship(
        "Group",
        back_populates="banwords",
    )
