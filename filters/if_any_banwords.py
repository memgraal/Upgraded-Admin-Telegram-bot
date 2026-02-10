from aiogram.filters import BaseFilter
from aiogram.types import Message

from database.managers import GroupBanwordsManager, GroupManager


class IfAnyBanwords(BaseFilter):
    async def __call__(self, message: Message, session) -> bool:

        group = await GroupManager(session).get(
            chat_id=message.chat.id,
        )

        banwords = await GroupBanwordsManager(session).search(
            group_id=group.id,
        )

        return bool(banwords.items)
