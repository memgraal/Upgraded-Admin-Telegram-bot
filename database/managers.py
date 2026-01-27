from sqlalchemy_manager import AsynManager

from database.captcha_logs import CaptchaLogs
from database.groups import Group
from database.users import User
from database.users_groups import UserGroup


class UserManager(AsynManager[User]):
    pass


class GroupManager(AsynManager[Group]):
    pass


class CaptchaLogsManager(AsynManager[CaptchaLogs]):
    pass


class UserGroupManager(AsynManager[UserGroup]):
    pass
