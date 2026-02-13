import enum


class GroupType(enum.Enum):
    PAID = "paid"
    FREE = "free"


class GroupUserRole(enum.Enum):
    ADMIN = "admin"
    MEMBER = "member"
    OWNER = "owner"
