from sqlalchemy import ForeignKey, Enum, UniqueConstraint
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship,
)

from database.base import Base
from constants.group_constants import GroupUserRole


class UserGroup(Base):
    __tablename__ = "user_groups"

    __table_args__ = (
        UniqueConstraint("user_id", "group_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    group_id: Mapped[int] = mapped_column(
        ForeignKey("groups.id", ondelete="CASCADE"),
        nullable=False,
    )

    role: Mapped[GroupUserRole] = mapped_column(
        Enum(
            GroupUserRole,
            name="group_user_role_enum",
        ),
        nullable=False,
        default=GroupUserRole.MEMBER,
    )

    user = relationship("User", back_populates="groups")
    group = relationship("Group", back_populates="users")
