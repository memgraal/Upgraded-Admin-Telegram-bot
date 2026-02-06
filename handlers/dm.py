from aiogram import types, Bot, F
from aiogram.filters import CommandStart, Command
from aiogram.types import CallbackQuery
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

import constants.text_constants
from database.groups import Banwords
from database.managers import (
    GroupSettingsManager,
    GroupBanwordsManager
)
import keyboards.dm_keyboards
from states import GroupFSM, BanwordsFSM
from routers import dm_router
from utils import (
    check_group_access,
    open_settings_menu,
    validate_promo_code,
    activate_group_subscription,
    redraw_banwords_menu,
)


# =========================
# START
# =========================
@dm_router.message(CommandStart())
async def start(message: types.Message, bot: Bot, session: AsyncSession):
    await cmd_clear(message, bot)

    # 1️⃣ Приветствие + кнопка "Подключить группу"
    await message.answer(
        constants.text_constants.START_GEREETING_TEXT,
        reply_markup=await keyboards.dm_keyboards.start_menu_keyboard(),
    )

    # 2️⃣ Сообщение-заглушка
    loading_msg = await message.answer(
        "🔄 Загружаю ваши группы…",
        reply_markup=keyboards.dm_keyboards.loading_keyboard(),
    )

    # 3️⃣ Получаем группы
    keyboard = await keyboards.dm_keyboards.get_paginated_kb(
        session=session,
        telegram_user_id=message.from_user.id,
        page=0,
    )

    # 4️⃣ Заменяем заглушку списком групп
    await loading_msg.edit_text(
        constants.text_constants.USER_GROUPS_TEXT,
        reply_markup=keyboard,
    )


# =========================
# CLEAR CHAT
# =========================
@dm_router.message(Command("clear"))
async def cmd_clear(message: types.Message, bot: Bot):
    chat_id = message.chat.id
    msg_id = message.message_id - 1

    MAX_ERRORS = 5
    MAX_ITER = 250

    errors = 0
    iterations = 0

    while msg_id > 0 and iterations < MAX_ITER:
        try:
            await bot.delete_message(chat_id, msg_id)
            errors = 0
        except TelegramBadRequest:
            errors += 1
            if errors >= MAX_ERRORS:
                break

        msg_id -= 1
        iterations += 1


# =========================
# PAGINATION
# =========================
@dm_router.callback_query(keyboards.dm_keyboards.PageCallback.filter())
async def paginate_user_groups(
    callback: CallbackQuery,
    callback_data: keyboards.dm_keyboards.PageCallback,
    session: AsyncSession,
):
    await callback.message.edit_reply_markup(
        reply_markup=await keyboards.dm_keyboards.get_paginated_kb(
            session=session,
            telegram_user_id=callback.from_user.id,
            page=callback_data.page,
        )
    )
    await callback.answer()


# =========================
# OPEN GROUP
# =========================
@dm_router.callback_query(keyboards.dm_keyboards.GroupData.filter())
async def open_group(
    callback: CallbackQuery,
    callback_data: keyboards.dm_keyboards.GroupData,
    state: FSMContext,
    session: AsyncSession,
):
    group_id = callback_data.group_id
    await state.update_data(group_id=group_id)

    has_access = await check_group_access(
        session=session,
        user_id=callback.from_user.id,
        group_id=group_id,
    )

    if not has_access:
        await callback.message.edit_text(
            "🔒 Эта группа на платной подписке.\n\n"
            "Введите промокод для получения доступа:",
            reply_markup=keyboards.dm_keyboards.payment_keyboard(),
        )
        await callback.answer()
        return

    await open_settings_menu(
        callback=callback,
        session=session,
        group_id=group_id,
    )


@dm_router.callback_query(F.data == "promo:back")
async def promo_back(
    callback: CallbackQuery,
    session: AsyncSession,
):
    keyboard = await keyboards.dm_keyboards.get_paginated_kb(
        session=session,
        telegram_user_id=callback.from_user.id,
        page=0,
    )

    await callback.message.edit_text(
        constants.text_constants.USER_GROUPS_TEXT,
        reply_markup=keyboard,
    )

    await callback.answer()


@dm_router.callback_query(F.data == "groups:back")
async def back_to_groups(
    callback: CallbackQuery,
    session: AsyncSession,
):
    keyboard = await keyboards.dm_keyboards.get_paginated_kb(
        session=session,
        telegram_user_id=callback.from_user.id,
        page=0,  # всегда первая страница
    )

    await callback.message.edit_text(
        constants.text_constants.USER_GROUPS_TEXT,
        reply_markup=keyboard,
    )

    await callback.answer()


# =========================
# PROMO FLOW
# =========================
@dm_router.callback_query(F.data == "promo:start")
async def promo_start(
    callback: CallbackQuery,
    state: FSMContext,
):
    await state.set_state(GroupFSM.waiting_for_promo)

    await callback.message.answer("✍️ Введите промокод:")
    await callback.answer()


@dm_router.message(GroupFSM.waiting_for_promo)
async def promo_entered(
    message: types.Message,
    state: FSMContext,
    session: AsyncSession,
):
    promo = message.text.strip()
    data = await state.get_data()
    group_id = data.get("group_id")

    if not group_id:
        await message.answer("❌ Ошибка состояния. Попробуйте заново.")
        await state.clear()
        return

    is_valid = await validate_promo_code(
        session=session,
        promo=promo,
        group_id=group_id,
    )

    if not is_valid:
        await message.answer("❌ Неверный промокод\nПопробуйте ещё раз:")
        return

    await activate_group_subscription(
        session=session,
        group_id=group_id,
        promo=promo,
    )

    await message.answer("✅ Доступ получен")

    await open_settings_menu(
        message=message,
        session=session,
        group_id=group_id,
    )

    await state.clear()


# =========================
# SETTINGS MENU
# =========================
@dm_router.callback_query(F.data.startswith("toggle:"))
async def toggle_group_setting(
    callback: CallbackQuery,
    session: AsyncSession,
):
    _, field, group_id = callback.data.split(":")
    group_id = int(group_id)

    settings = await GroupSettingsManager(session).get(group_id=group_id)

    if field == "captcha":
        settings.captcha_enabled = not settings.captcha_enabled

    elif field == "photo":
        settings.photo_check_enabled = not settings.photo_check_enabled

    else:
        await callback.answer("❌ Неизвестная настройка")
        return

    await session.commit()

    await open_settings_menu(
        callback=callback,
        session=session,
        group_id=group_id,
    )


# =========================
# Bandwords MENU
# =========================
@dm_router.callback_query(
    F.data.startswith("banwords:")
    & ~F.data.contains("add")
    & ~F.data.contains("del")
    & ~F.data.contains("back")
)
async def open_banwords(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
):
    _, group_id = callback.data.split(":")
    group_id = int(group_id)

    pagination = await GroupBanwordsManager(session).search(group_id=group_id)
    words = pagination.items

    text = "🚫 <b>Бан-слова</b>\n\n"
    text += "\n".join(f"• {w.word}" for w in words) if words else "Список пуст"

    await callback.message.edit_text(
        text,
        reply_markup=await keyboards.dm_keyboards.banwords_keyboard(
            session,
            group_id,
        ),
        parse_mode='HTML',
    )

    await state.update_data(
        banwords_chat_id=callback.message.chat.id,
        banwords_message_id=callback.message.message_id,
        group_id=group_id,
    )

    await callback.answer()


@dm_router.callback_query(F.data.startswith("banwords:back:"))
async def back_from_banwords(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
):
    group_id = int(callback.data.split(":")[2])

    # чистим состояние бан-слов
    await state.clear()

    # возвращаемся в настройки группы
    await open_settings_menu(
        callback=callback,
        session=session,
        group_id=group_id,
    )

    await callback.answer()


# Добавление банворда
@dm_router.callback_query(F.data.startswith("banwords:add:"))
async def add_banword_start(
    callback: CallbackQuery,
    state: FSMContext,
):
    group_id = int(callback.data.split(":")[2])

    await state.update_data(
        group_id=group_id,
        banwords_chat_id=callback.message.chat.id,
        banwords_message_id=callback.message.message_id,
    )

    await state.set_state(BanwordsFSM.waiting_for_add)

    await callback.message.answer("✍️ Введите слово для бана:")
    await callback.answer()


@dm_router.message(BanwordsFSM.waiting_for_add)
async def add_banword_finish(
    message: types.Message,
    state: FSMContext,
    session: AsyncSession,
):
    data = await state.get_data()
    word = message.text.strip().lower()

    try:
        await GroupBanwordsManager(session).create(
            Banwords(
                group_id=data["group_id"],
                word=word,
            )
        )
    except IntegrityError:
        await session.rollback()
        await message.answer("⚠️ Это слово уже есть в списке")
        return

    await redraw_banwords_menu(
        bot=message.bot,
        session=session,
        chat_id=data["banwords_chat_id"],
        message_id=data["banwords_message_id"],
        group_id=data["group_id"],
    )

    await state.clear()


# Удаление банворда
@dm_router.callback_query(F.data.startswith("banwords:del:"))
async def delete_banword_start(
    callback: CallbackQuery,
    state: FSMContext,
):
    group_id = int(callback.data.split(":")[2])

    await state.update_data(
        group_id=group_id,
        banwords_chat_id=callback.message.chat.id,
        banwords_message_id=callback.message.message_id,
    )

    await state.set_state(BanwordsFSM.waiting_for_delete)

    await callback.message.answer("✍️ Введите слово для удаления:")
    await callback.answer()


@dm_router.message(BanwordsFSM.waiting_for_delete)
async def delete_banword_finish(
    message: types.Message,
    state: FSMContext,
    session: AsyncSession,
):
    data = await state.get_data()
    word = message.text.strip().lower()

    pagination = await GroupBanwordsManager(session).search(
        group_id=data["group_id"],
        word=word,
    )
    items = pagination.items

    if not items:
        await message.answer("❌ Такое слово не найдено")
        return

    for item in items:
        await GroupBanwordsManager(session).delete(item)

    await redraw_banwords_menu(
        bot=message.bot,
        session=session,
        chat_id=data["banwords_chat_id"],
        message_id=data["banwords_message_id"],
        group_id=data["group_id"],
    )

    await state.clear()
