import asyncio
from typing import Dict, Tuple

from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from routers import group_messages
from keyboards.group_keyboards import captcha_keyboard
from database.managers import (
    CaptchaLogsManager,
    UserManager,
    GroupManager,
    GroupSettingsManager,
    GroupBanwordsManager,
)
from database.managers import UserGroupManager
from database.users_groups import UserGroup
from constants.group_constants import GroupUserRole
from database.captcha_logs import CaptchaLogs
from constants.captcha_constants import CaptchaStatus
from filters.if_any_banwords import IfAnyBanwords
from filters.is_captcha_needed import IsCaptchaNeeded
from filters.is_group_payed import IsGroupPayed
from filters.is_captcha_is_on import IsCaptchaIsOn
from filters.is_not_channel_post import IsMessageNotChannelPost
from utils import CaptchaCallbackData, extract_text_from_photo, safe_delete


CAPTCHA_TIMEOUT = 30

pending_captcha: Dict[Tuple[int, int], dict] = {}


@group_messages.message(
    IsGroupPayed(),
    IsCaptchaIsOn(),
    IsCaptchaNeeded(),
    IsMessageNotChannelPost(),
)
async def captcha_message_handler(
    message: Message,
    session: AsyncSession,
):
    chat_id = message.chat.id
    user_id = message.from_user.id
    key = (chat_id, user_id)

    # 1) Ищем пользователя
    user = await UserManager(session).get(telegram_user_id=user_id)

    # 2) Если нет — создаём
    if not user:
        user = await UserManager(session).create(
            telegram_user_id=user_id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
            last_name=message.from_user.last_name,
        )

    if key in pending_captcha:
        await safe_delete(message)
        return

    captcha_msg = await message.reply(
        "👋 Подтвердите, что вы не бот\n"
        "⏳ У вас 30 секунд",
        reply_markup=captcha_keyboard(
            CaptchaCallbackData(
                chat_id=chat_id,
                telegram_user_id=user_id,
            )
        ),
    )

    async def timeout():
        try:
            await asyncio.sleep(CAPTCHA_TIMEOUT)
        except asyncio.CancelledError:
            return

        if key in pending_captcha:
            pending_captcha.pop(key, None)
            await safe_delete(captcha_msg)
            await safe_delete(message)

    pending_captcha[key] = {
        "task": asyncio.create_task(timeout()),
        "captcha_msg_id": captcha_msg.message_id,
    }


@group_messages.callback_query(CaptchaCallbackData.filter())
async def captcha_confirm(
    callback: CallbackQuery,
    callback_data: CaptchaCallbackData,
    session: AsyncSession,
):
    if callback.from_user.id != callback_data.telegram_user_id:
        await callback.answer("❌ Это не для вас", show_alert=True)
        return

    key = (callback_data.chat_id, callback_data.telegram_user_id)

    captcha_data = pending_captcha.pop(key, None)
    if captcha_data:
        captcha_data['task'].cancel()

    await safe_delete(callback.message)

    # --- 1) User
    user = await UserManager(session).get(
        telegram_user_id=callback.from_user.id,
    )

    if not user:
        user = await UserManager(session).create(
            telegram_user_id=callback.from_user.id,
            username=callback.from_user.username,
            first_name=callback.from_user.first_name,
            last_name=callback.from_user.last_name,
        )

    # --- 2) Group
    group = await GroupManager(session).get(
        chat_id=callback_data.chat_id,
    )

    # --- 3) Captcha log
    await CaptchaLogsManager(session).create(
        CaptchaLogs(
            user_id=user.id,
            group_id=group.id,
            status=CaptchaStatus.SOLVED,
        )
    )

    user_group = await UserGroupManager(session).get(
        user_id=user.id,
        group_id=group.id,
    )

    if not user_group:
        await UserGroupManager(session).create(
            UserGroup(
                user_id=user.id,
                group_id=group.id,
                role=GroupUserRole.MEMBER,
            )
        )

    await callback.answer("✅ Теперь можно писать")


def contains_banword(text: str, banwords) -> bool:
    text = text.lower()
    return any(bw.word.lower() in text for bw in banwords)


@group_messages.message(
    IsGroupPayed(),
    IsMessageNotChannelPost(),
    IfAnyBanwords(),
)
async def banwords_message_handler(
    message: Message,
    session: AsyncSession,
):
    group = await GroupManager(session).get(
        chat_id=message.chat.id,
    )

    settings = await GroupSettingsManager(session).get(
        group_id=group.id,
    )

    banwords = await GroupBanwordsManager(session).search(
        group_id=group.id,
    )

    if not banwords or not settings:
        return

    # 1️⃣ Обычный текст
    if message.text:
        if contains_banword(message.text, banwords.items):
            await message.delete()
            return

    # 2️⃣ Фото
    if settings.photo_check_enabled and message.photo:
        photo = message.photo[-1]  # самое большое разрешение

        # 2.1 Фото с подписью
        if message.caption:
            if contains_banword(message.caption, banwords.items):
                await message.delete()
                return

        else:
            text_from_image = await extract_text_from_photo(
                photo=photo,
                bot=message.bot,
            )

            if text_from_image and contains_banword(
                text_from_image,
                banwords.items,
            ):
                await message.delete()
                return
