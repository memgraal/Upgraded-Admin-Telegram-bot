from aiogram.filters import BaseFilter
from aiogram.types import Message

from database.managers import GroupSettingsManager, GroupManager


class IsCaptchaIsOn(BaseFilter):
    async def __call__(self, message: Message, session) -> bool:

        group = await GroupManager(session).get(
            chat_id=message.chat.id,
        )

        _settings = await GroupSettingsManager(session).get(
            group_id=group.id,
        )

        return _settings.captcha_enabled
