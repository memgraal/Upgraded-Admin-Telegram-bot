import os

from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.filters.callback_data import CallbackData
import dotenv

from constants.group_constants import GroupUserRole
from database.managers import (
    GroupBanwordsManager,
    UserGroupManager,
    UserManager,
    GroupSettingsManager,
)
from utils import get_group_name


dotenv.load_dotenv()


class PageCallback(CallbackData, prefix="page"):
    page: int


class GroupData(CallbackData, prefix="group"):
    group_id: int


async def start_menu_keyboard() -> InlineKeyboardMarkup:
    _builder = InlineKeyboardBuilder()

    _builder.add(
        InlineKeyboardButton(
            text="⚙️ Подключить группу",
            url=str(os.getenv("BOT_INVITING_LINK")),
        ),
    )

    return _builder.as_markup()


async def get_paginated_kb(
    session,
    telegram_user_id: int,
    page: int = 0,
):
    builder = InlineKeyboardBuilder()

    user_manager = UserManager(session)
    user_group_manager = UserGroupManager(session)

    user = await user_manager.get(telegram_user_id=telegram_user_id)

    pagination = await user_group_manager.search(
        user_id=user.id,
        role=GroupUserRole.ADMIN,
        page=page + 1,
    )

    groups = pagination.items

    for group in groups:
        builder.row(
            InlineKeyboardButton(
                text=await get_group_name(
                    session=session,
                    group_id=group.group_id,
                ),
                callback_data=GroupData(group_id=group.group_id).pack(),
            )
        )

    nav = []

    if pagination.has_prev:
        nav.append(
            InlineKeyboardButton(
                text="⬅️",
                callback_data=PageCallback(page=page - 1).pack(),
            )
        )

    if pagination.has_next:
        nav.append(
            InlineKeyboardButton(
                text="➡️",
                callback_data=PageCallback(page=page + 1).pack(),
            )
        )

    if nav:
        builder.row(*nav)

    return builder.as_markup()


def loading_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⏳ Загружается…", callback_data="noop")]
        ]
    )


def payment_keyboard():
    builder = InlineKeyboardBuilder()

    builder.button(
        text="💳 Оплата промокодом",
        callback_data="promo:start",
    )

    builder.button(
        text="⬅️ Назад",
        callback_data="promo:back",
    )

    builder.adjust(1)
    return builder.as_markup()


async def settings_keyboard(session, group_id: int):

    settings = await GroupSettingsManager(session).get(
        group_id=group_id
    )

    builder = InlineKeyboardBuilder()

    builder.button(
        text=f"🧩 Капча: {'ON' if settings.captcha_enabled else 'OFF'}",
        callback_data=f"toggle:captcha:{group_id}",
    )

    builder.button(
        text=f"""
        📸 Фото-проверка: {'ON' if settings.photo_check_enabled else 'OFF'}
        """,
        callback_data=f"toggle:photo:{group_id}",
    )

    builder.button(
        text="🚫 Бан-слова",
        callback_data=f"banwords:{group_id}",
    )

    builder.button(
        text="⬅️ Назад к группам",
        callback_data="groups:back",
    )

    builder.adjust(1)
    return builder.as_markup()


async def banwords_keyboard(session, group_id: int):
    builder = InlineKeyboardBuilder()

    pagination = await GroupBanwordsManager(session).search(group_id=group_id)
    words = pagination.items

    builder.button(
        text="➕ Добавить слово",
        callback_data=f"banwords:add:{group_id}",
    )

    if words:  # ✅ теперь это реальный список
        builder.button(
            text="➖ Удалить слово",
            callback_data=f"banwords:del:{group_id}",
        )

    builder.button(
        text="⬅️ Назад",
        callback_data=f"banwords:back:{group_id}",
    )

    builder.adjust(1)
    return builder.as_markup()
