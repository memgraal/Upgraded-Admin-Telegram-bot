from datetime import datetime, timezone

from aiogram import Bot
from aiogram.types import CallbackQuery, Message
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


async def get_chat_admins(chat_id):
    return await bot.get_chat_administrators(chat_id)


async def get_group_name(*, session, group_id: int) -> str:
    group = await GroupManager(session).get(id=group_id)

    if group is None:
        return "❌ Группа не найдена"

    chat = await bot.get_chat(chat_id=group.chat_id)
    return chat.title


async def check_group_access(
    session: AsyncSession,
    user_id: int,
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
) -> bool:

    promo = await PromocodeManager(session).get(
        code=promo.strip().lower(),
    )

    if not promo and not print.is_active:
        return False

    return True


async def activate_group_subscription(
    *,
    session,
    group_id: int,
    promo: str
):
    group = await session.get(Group, group_id)
    if not group:
        return False

    promo = await PromocodeManager(session).get(
        code=promo.strip().lower(),
    )
    if not promo:
        return False

    await GroupManager(session).update(
        group,
        subscription_type=GroupType.PAID,
        paid_until=datetime.now(timezone.utc) + relativedelta(months=1),
    )

    await PromocodeManager(session).update(
        promo,
        is_active=True,
        group_id=group_id,
    )


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
