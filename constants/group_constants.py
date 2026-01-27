import enum


class GroupType(enum.Enum):
    PAID = "paid"
    FREE = "free"


class GroupUserRole(enum.Enum):
    ADMIN = "admin"
    CREATOR = "creator"
    MEMBER = "member"
