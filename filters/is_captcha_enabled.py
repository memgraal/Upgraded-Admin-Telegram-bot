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
        if message.chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
            print("captcha_log", "не группа")
            return False

        # 2️⃣ Игнорируем сервисные сообщения (вступление ботов)
        if message.new_chat_members:
            if any(member.is_bot for member in message.new_chat_members):
                print("captcha_log", "добавление бота — пропускаем")
                return False

        if not message.from_user:
            return False

        # 3️⃣ Получаем группу
        group = await GroupManager(session).get(chat_id=message.chat.id)
        if not group:
            print("captcha_log", "группы нет в БД")
            return False

        # 4️⃣ Проверяем включена ли капча
        settings = await GroupSettingsManager(session).get(group_id=group.id)
        if not settings or not settings.captcha_enabled:
            print("captcha_log", "капча выключена")
            return False

        # 5️⃣ Получаем пользователя (может не существовать — это нормально)
        user = await UserManager(session).get(
            telegram_user_id=message.from_user.id
        )

        # 🔥 НОВЫЙ ПОЛЬЗОВАТЕЛЬ → нужна капча
        if not user:
            print("captcha_log", "новый пользователь — нужна капча")
            return True

        # 6️⃣ Получаем связь пользователь-группа
        user_group = await UserGroupManager(session).get(
            user_id=user.id,
            group_id=group.id,
        )

        # 🔥 Впервые пишет в этой группе → нужна капча
        if not user_group:
            print("captcha_log", "новый в группе — нужна капча")
            return True

        # 7️⃣ Админы не проходят капчу
        if user_group.role in (GroupUserRole.ADMIN, GroupUserRole.OWNER):
            print("captcha_log", "админ — капча не нужна")
            return False

        # 8️⃣ Уже решал капчу?
        captcha_log = await CaptchaLogsManager(session).get(
            group_id=group.id,
            user_id=user.id,
            status=CaptchaStatus.SOLVED,
        )

        if captcha_log:
            print("captcha_log", "уже проходил капчу")
            return False

        # 🔥 Обычный пользователь без решённой капчи
        print("captcha_log", "капча требуется")
        return True

