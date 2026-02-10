from aiogram.filters import BaseFilter
from aiogram.types import Message

from database.managers import GroupManager
from constants.group_constants import GroupType


class IsGroupPayed(BaseFilter):
    async def __call__(self, message: Message, session) -> bool:
        print("isGroupPayed CALLED")

        group = await GroupManager(session).get(
            chat_id=message.chat.id,
        )

        if group is None:
            return False

        else:
            return group.subscription_type == GroupType.PAID
