from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    String,
    ForeignKey,
    UniqueConstraint,
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

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
    )

    chat_id: Mapped[int] = mapped_column(
        BigInteger,
        unique=True,
        nullable=False,
        index=True,
    )

    subscription_type: Mapped[GroupType] = mapped_column(
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
        server_default=func.now(),
        nullable=False,
    )

    # 🔥 ВАЖНО — 1 к 1
    settings: Mapped["GroupSettings"] = relationship(
        "GroupSettings",
        back_populates="group",
        uselist=False,
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    banwords: Mapped[list["Banwords"]] = relationship(
        "Banwords",
        back_populates="group",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    users: Mapped[list["UserGroup"]] = relationship(
        "UserGroup",
        back_populates="group",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    captcha_logs: Mapped[list["CaptchaLogs"]] = relationship(
        "CaptchaLogs",
        back_populates="group",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    promocodes: Mapped[list["Promocode"]] = relationship(
        "Promocode",
        back_populates="group",
        cascade="save-update",
    )


class GroupSettings(Base):
    __tablename__ = "group_settings"

    __table_args__ = (
        UniqueConstraint("group_id", name="uq_group_settings_group"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
    )

    group_id: Mapped[int] = mapped_column(
        ForeignKey("groups.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
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

    group: Mapped["Group"] = relationship(
        "Group",
        back_populates="settings",
    )


class Banwords(Base):
    __tablename__ = "banwords"

    __table_args__ = (
        UniqueConstraint("group_id", "word", name="uq_group_word"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
    )

    group_id: Mapped[int] = mapped_column(
        ForeignKey("groups.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    word: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    group: Mapped["Group"] = relationship(
        "Group",
        back_populates="banwords",
    )
