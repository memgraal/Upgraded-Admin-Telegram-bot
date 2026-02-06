from sqlalchemy import (
    BigInteger,
    String,
    Boolean,
    ForeignKey,
)
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship,
)

from database.base import Base


class Promocode(Base):
    __tablename__ = "promocodes"

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
    )

    # сам промокод
    code: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        unique=True,
        index=True,
    )

    # группа, к которой он будет привязан ПОСЛЕ активации
    group_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("groups.id", ondelete="SET NULL"),
        nullable=True,
    )

    # активирован или нет
    is_active: Mapped[bool | None] = mapped_column(
        Boolean,
        nullable=True,
    )

    # ORM-связь (на будущее)
    group = relationship(
        "Group",
        back_populates="promocodes",
    )
