import enum


class UserRole(enum.Enum):
    ADMIN = "admin"
    MEMBER = "member"


class UserStatus(enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    BANNED = "banned"
