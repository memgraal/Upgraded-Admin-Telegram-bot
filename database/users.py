from sqlalchemy import BigInteger, String
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship,
)

from database.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[BigInteger] = mapped_column(
        BigInteger,
        primary_key=True,
    )

    username: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
    )

    telegram_user_id: Mapped[BigInteger] = mapped_column(
        BigInteger,
        unique=True,
        nullable=False,
    )

    groups = relationship(
        "UserGroup",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    captcha_logs = relationship(
        "CaptchaLogs",
        back_populates="user",
        cascade="all, delete-orphan",
    )
