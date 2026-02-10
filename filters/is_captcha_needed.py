from aiogram.filters import BaseFilter
from aiogram.types import Message

from database.managers import (
    GroupManager,
    UserManager,
    CaptchaLogsManager,
)
from constants.captcha_constants import CaptchaStatus


class IsCaptchaNeeded(BaseFilter):
    async def __call__(self, message: Message, session) -> bool:
        if not message.from_user:
            return False

        group = await GroupManager(session).get(
            chat_id=message.chat.id,
        )
        if not group:
            return False

        user = await UserManager(session).get(
            telegram_user_id=message.from_user.id,
        )
        if not user:
            return True  # пользователя нет → капча нужна

        captcha = await CaptchaLogsManager(session).get(
            user_id=user.id,
            group_id=group.id,
        )

        if not captcha:
            return True

        return captcha.status != CaptchaStatus.SOLVED
