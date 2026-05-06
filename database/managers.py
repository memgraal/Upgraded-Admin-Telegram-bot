from sqlalchemy_manager.managers import AsyncManager

from database.captcha_logs import CaptchaLogs
from database.groups import Group, GroupSettings, Banwords
from database.users import User
from database.users_groups import UserGroup
from database.promocodes import Promocode
from database.paginators import (
    UserGroupPaginator,
    BanwordsPaginator,
)


class UserManager(AsyncManager[User]):
    pass


class GroupManager(AsyncManager[Group]):
    pass


class CaptchaLogsManager(AsyncManager[CaptchaLogs]):
    pass


class UserGroupManager(AsyncManager[UserGroup]):
    paginator_class = UserGroupPaginator


class GroupSettingsManager(AsyncManager[GroupSettings]):
    pass


class GroupBanwordsManager(AsyncManager[Banwords]):
    paginator_class = BanwordsPaginator


class PromocodeManager(AsyncManager[Promocode]):
    pass
