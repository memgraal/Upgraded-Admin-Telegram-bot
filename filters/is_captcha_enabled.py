from aiogram.filters import BaseFilter
from aiogram.types import Message
from aiogram.enums import ChatType
from sqlalchemy.ext.asyncio import AsyncSession

from constants.group_constants import GroupUserRole
from constants.captcha_constants import CaptchaStatus
from database.managers import (
    GroupSettingsManager,
    UserGroupManager,
    UserManager,
    GroupManager,
    CaptchaLogsManager,
)


class IsCaptchaEnabled(BaseFilter):
    async def __call__(
        self,
        message: Message,
        session: AsyncSession,
    ) -> bool:

        # 1️⃣ Только группы
        if message.chat.type not in (
            ChatType.GROUP,
            ChatType.SUPERGROUP,
        ):
            print("captcha_log", 'не группа')
            return False

        # 🔥 Игнорируем добавление бота
        if message.new_chat_members:
            if any(member.is_bot for member in message.new_chat_members):
                print("captcha_log", "добавление бота — пропускаем")
                return False

        # 3️⃣ Получаем группу
        group = await GroupManager(session).get(
            chat_id=message.chat.id
        )

        if not group:
            print("captcha_log", 'нет группы в бд')
            return False

        # 4️⃣ Проверяем настройки
        settings = await GroupSettingsManager(session).get(
            group_id=group.id
        )

        if not settings:
            print("captcha_log", 'нет настроек группы в бд')
            return False

        if not settings.captcha_enabled:
            print("captcha_log", 'капча не включена')
            return False

        # 5️⃣ Получаем пользователя
        if not message.from_user:
            return False

        user = await UserManager(session).get(
            telegram_user_id=message.from_user.id
        )

        if not user:
            return False

        user_group = await UserGroupManager(session).get(
            user_id=user.id,
            group_id=group.id,
        )

        if not user_group:
            return False

        if user_group.role in (
            GroupUserRole.ADMIN,
            GroupUserRole.OWNER,
        ):
            print("captcha_log", 'пользователь админ')
            return False

        captcha_log = await CaptchaLogsManager(session).get(
            group_id=group.id,
            user_id=user.id,
            status=CaptchaStatus.SOLVED,
        )

        if captcha_log:
            print("captcha_log", 'пользователь уже решал капчу')
            return False

        return True
