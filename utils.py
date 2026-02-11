from datetime import datetime, timezone
import random
import string

from aiogram import Bot
from aiogram.types import CallbackQuery, Message
from aiogram.filters.callback_data import CallbackData
from sqlalchemy.ext.asyncio import AsyncSession
from dateutil.relativedelta import relativedelta

from bot import bot
from database.managers import (
    GroupManager,
    GroupBanwordsManager,
    PromocodeManager,
)
from database.groups import GroupType, Group
import keyboards.dm_keyboards


class CaptchaCallbackData(CallbackData, prefix="captcha"):
    chat_id: int
    telegram_user_id: int


async def get_chat_admins(chat_id):
    return await bot.get_chat_administrators(chat_id)


async def get_group_name(*, session, group_id: int) -> str:
    group = await GroupManager(session).get(id=group_id)

    if group is None:
        return "❌ Группа не найдена"
    try:
        chat = await bot.get_chat(chat_id=group.chat_id)
    except Exception:
        return "❌ Не удалось получить информацию о группе"
    return chat.title


async def check_group_access(
    session: AsyncSession,
    group_id: int,
) -> bool:
    group = await session.get(Group, group_id)

    if not group:
        return False

    return group.subscription_type == GroupType.PAID


async def open_settings_menu(
    *,
    session,
    group_id: int,
    callback: CallbackQuery | None = None,
    message: Message | None = None,
):
    keyboard = await keyboards.dm_keyboards.settings_keyboard(
        session=session,
        group_id=group_id,
    )

    if callback:
        await callback.message.edit_reply_markup(
            reply_markup=keyboard,
        )
        await callback.answer()
        return

    if message:
        await message.answer(
            "⚙️ Настройки группы",
            reply_markup=keyboard,
        )


async def validate_promo_code(
    *,
    session,
    promo: str,
    group_id: int,
) -> tuple[bool, str | None]:
    promo_obj = await PromocodeManager(session).get(
        code=promo.strip().lower(),
    )

    if not promo_obj:
        return False, "❌ Промокод не найден"

    if promo_obj.group_id is not None:
        return False, "❌ Этот промокод уже был использован"

    if not promo_obj.is_active:
        return False, "❌ Промокод неактивен"

    return True, None


async def activate_group_subscription(
    *,
    session: AsyncSession,
    group_id: int,
    promo: str | None = None,
    months: int = 1,
) -> bool:
    group = await session.get(Group, group_id)
    if not group:
        return False

    now = datetime.now(timezone.utc)

    # ========================
    # 🎟 ПРОМОКОД
    # ========================
    if promo:
        promo_obj = await PromocodeManager(session).get(
            code=promo.strip().lower(),
        )

        if (
            not promo_obj
            or promo_obj.group_id is not None
            or not promo_obj.is_active
        ):
            return False

        await PromocodeManager(session).update(
            promo_obj,
            is_active=False,
            group_id=group_id,
            activated_at=now,
        )

    # ========================
    # ⭐️ STARS / ОБЩАЯ ЛОГИКА
    # ========================
    paid_until = group.paid_until or now

    # если подписка истекла — считаем от текущего времени
    if paid_until < now:
        paid_until = now

    await GroupManager(session).update(
        group,
        subscription_type=GroupType.PAID,
        paid_until=paid_until + relativedelta(months=months),
    )

    return True


async def redraw_banwords_menu(
    *,
    bot: Bot,
    session: AsyncSession,
    chat_id: int,
    message_id: int,
    group_id: int,
):
    pagination = await GroupBanwordsManager(session).search(group_id=group_id)
    words = pagination.items

    text = "🚫 <b>Бан-слова</b>\n\n"
    text += "\n".join(f"• {w.word}" for w in words) if words else "Список пуст"

    await bot.edit_message_text(
        chat_id=chat_id,
        message_id=message_id,
        text=text,
        reply_markup=await keyboards.dm_keyboards.banwords_keyboard(
            session,
            group_id,
        ),
        parse_mode='HTML'
    )


async def safe_delete(message: Message):
    try:
        await message.delete()
    except Exception:
        pass


def generate_promocode(length: int = 12, chunks: int = 3, sep: str = "-"):
    alphabet = string.ascii_uppercase + string.digits
    code = "".join(random.choice(alphabet) for _ in range(length))
    if chunks:
        return sep.join([code[i:i+4] for i in range(0, length, 4)])
    return code
