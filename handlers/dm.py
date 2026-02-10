from aiogram import types, Bot, F
from aiogram.filters import CommandStart, Command
from aiogram.types import CallbackQuery
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

import constants.text_constants
from constants.group_constants import GroupType
from database.groups import Banwords, Group
from database.promocodes import Promocode
from database.managers import (
    GroupSettingsManager,
    GroupBanwordsManager,
)
import keyboards.dm_keyboards
from bot import admin_user_id
from states import DMFSM
from routers import dm_router
from utils import (
    check_group_access,
    open_settings_menu,
    validate_promo_code,
    activate_group_subscription,
    redraw_banwords_menu,
    generate_promocode,
)


# =========================
# START
# =========================
@dm_router.message(CommandStart())
async def start(
    message: types.Message,
    bot: Bot,
    state: FSMContext,
    session: AsyncSession,
):
    await cmd_clear(message, bot)

    await state.clear()
    await state.set_state(DMFSM.browsing_groups)

    await message.answer(
        constants.text_constants.START_GEREETING_TEXT,
        reply_markup=await keyboards.dm_keyboards.start_menu_keyboard(),
    )

    loading_msg = await message.answer(
        "🔄 Загружаю ваши группы…",
        reply_markup=keyboards.dm_keyboards.loading_keyboard(),
    )

    keyboard = await keyboards.dm_keyboards.get_paginated_kb(
        session=session,
        telegram_user_id=message.from_user.id,
        page=0,
    )

    if not keyboard:
        await loading_msg.edit_text("📭 Пока у тебя нет групп")
        return

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
@dm_router.callback_query(
    keyboards.dm_keyboards.PageCallback.filter(),
    DMFSM.browsing_groups
)
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
@dm_router.callback_query(
    keyboards.dm_keyboards.GroupData.filter(),
    DMFSM.browsing_groups,
)
async def open_group(
    callback: CallbackQuery,
    callback_data: keyboards.dm_keyboards.GroupData,
    state: FSMContext,
    session: AsyncSession,
):
    await state.set_state(DMFSM.group_settings)

    group_id = callback_data.group_id
    await state.update_data(group_id=group_id)

    has_access = await check_group_access(session=session, group_id=group_id)

    if not has_access:
        await callback.message.edit_text(
            "🔒 Эта группа на платной подписке.\n\nВыберите способ оплаты:",
            reply_markup=keyboards.dm_keyboards.payment_keyboard(),
        )
        await callback.answer()
        return

    await open_settings_menu(
        callback=callback,
        session=session,
        group_id=group_id,
    )


# =========================
# BACK TO GROUPS
# =========================
@dm_router.callback_query(F.data.in_(("promo:back", "groups:back")))
async def back_to_groups(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
):
    await state.clear()
    await state.set_state(DMFSM.browsing_groups)

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


# =========================
# PROMO FLOW
# =========================
@dm_router.callback_query(F.data == "promo:start", DMFSM.group_settings)
async def promo_start(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    bot: Bot,
):
    data = await state.get_data()
    group_id = data.get("group_id")

    if not group_id:
        await callback.answer()
        return

    group = await session.get(Group, group_id)
    if group and group.subscription_type == GroupType.PAID:
        await callback.answer("Подписка уже активна")
        return

    await state.set_state(DMFSM.waiting_for_promo)
    await callback.message.answer("✍️ Введите промокод:")
    await callback.answer()


@dm_router.message(DMFSM.waiting_for_promo)
async def promo_entered(
    message: types.Message,
    state: FSMContext,
    session: AsyncSession,
):
    promo = message.text.strip()
    data = await state.get_data()
    group_id = data.get("group_id")

    if not group_id:
        await message.answer("❌ Ошибка состояния")
        await state.clear()
        await state.set_state(DMFSM.browsing_groups)
        return

    ok, error = await validate_promo_code(
        session=session,
        promo=promo,
        group_id=group_id,
    )
    if not ok:
        await message.answer(error)
        return

    activated = await activate_group_subscription(
        session=session,
        group_id=group_id,
        promo=promo,
    )
    if not activated:
        await message.answer("❌ Промокод уже использован")
        return

    await message.answer("✅ Доступ получен")
    await open_settings_menu(
        message=message,
        session=session,
        group_id=group_id,
    )
    await state.set_state(DMFSM.group_settings)


# =========================
# STARS FLOW
# =========================
@dm_router.callback_query(F.data == "promo:stars", DMFSM.group_settings)
async def stars_start(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
):
    data = await state.get_data()
    group_id = data.get("group_id")

    if not group_id:
        await callback.answer()
        return

    group = await session.get(Group, group_id)
    if group and group.subscription_type == GroupType.PAID:
        await callback.answer("ℹ️ Подписка уже активна")
        return

    await state.set_state(DMFSM.waiting_for_stars)

    await callback.message.edit_text(
        "⭐️ Выберите срок подписки:",
        reply_markup=keyboards.dm_keyboards.stars_duration_keyboard(group_id),
    )
    await callback.answer()


@dm_router.callback_query(
    F.data.startswith("stars:"),
    DMFSM.waiting_for_stars,
)
async def stars_invoice(
    callback: CallbackQuery,
    bot: Bot,
    state: FSMContext,
    session: AsyncSession,
):
    _, months, group_id = callback.data.split(":")
    group_id = int(group_id)

    group = await session.get(Group, group_id)
    if group and group.subscription_type == GroupType.PAID:
        await callback.answer("ℹ️ Подписка уже активна")
        await state.set_state(DMFSM.group_settings)
        return

    price = constants.text_constants.STARS_PRICES[int(months)]

    await bot.send_invoice(
        chat_id=callback.from_user.id,
        title="Подписка на группу",
        description=f"Доступ на {months} мес.",
        payload=f"group:{group_id}:{months}",
        currency="XTR",
        prices=[types.LabeledPrice(label="Подписка", amount=price)],
    )
    await callback.answer()


@dm_router.pre_checkout_query()
async def pre_checkout(pre_checkout_query: types.PreCheckoutQuery):
    await pre_checkout_query.answer(ok=True)


@dm_router.message(F.successful_payment)
async def successful_stars_payment(
    message: types.Message,
    session: AsyncSession,
    state: FSMContext,
):
    _, group_id, months = message.successful_payment.invoice_payload.split(":")
    group_id = int(group_id)
    months = int(months)

    activated = await activate_group_subscription(
        session=session,
        group_id=group_id,
        months=months,
    )
    if not activated:
        await message.answer("❌ Не удалось активировать подписку")
        return

    await message.answer(f"✅ Подписка активирована на {months} мес.")
    await open_settings_menu(
        message=message,
        session=session,
        group_id=group_id,
    )
    await state.set_state(DMFSM.group_settings)


# =========================
# SETTINGS
# =========================
@dm_router.callback_query(F.data.startswith("toggle:"), DMFSM.group_settings)
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
# BANWORDS
# =========================
@dm_router.callback_query(
    F.data.startswith("banwords:"),
    DMFSM.group_settings,
)
async def open_banwords(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
):
    await callback.answer()
    await state.set_state(DMFSM.banwords_menu)

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
        parse_mode="HTML",
    )

    await state.update_data(
        group_id=group_id,
        banwords_chat_id=callback.message.chat.id,
        banwords_message_id=callback.message.message_id,
    )
    await callback.answer()


@dm_router.callback_query(
    F.data.startswith("banwords:add:"),
    DMFSM.banwords_menu,
)
async def add_banword_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(DMFSM.banwords_add)
    await callback.message.answer("✍️ Введите слово для бана:")
    await callback.answer()


@dm_router.callback_query(
    F.data.startswith("banwords:back:"),
    DMFSM.banwords_menu,
)
async def banwords_back(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
):
    # вытаскиваем group_id из callback
    group_id = int(callback.data.split(":")[2])

    # возвращаем FSM в настройки группы
    await state.set_state(DMFSM.group_settings)

    # возвращаем меню настроек
    await open_settings_menu(
        callback=callback,
        session=session,
        group_id=group_id,
    )

    await callback.answer()


@dm_router.message(DMFSM.banwords_add)
async def add_banword_finish(
    message: types.Message,
    state: FSMContext,
    session: AsyncSession,
):
    data = await state.get_data()
    word = message.text.strip().lower()

    try:
        await GroupBanwordsManager(session).create(
            Banwords(group_id=data["group_id"], word=word)
        )
    except IntegrityError:
        await session.rollback()
        await message.answer("⚠️ Это слово уже есть")
        return

    await redraw_banwords_menu(
        bot=message.bot,
        session=session,
        chat_id=data["banwords_chat_id"],
        message_id=data["banwords_message_id"],
        group_id=data["group_id"],
    )
    await state.set_state(DMFSM.banwords_menu)


@dm_router.callback_query(
    F.data.startswith("banwords:del:"),
    DMFSM.banwords_menu,
)
async def delete_banword_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(DMFSM.banwords_delete)
    await callback.message.answer("✍️ Введите слово для удаления:")
    await callback.answer()


@dm_router.message(DMFSM.banwords_delete)
async def delete_banword_finish(
    message: types.Message,
    state: FSMContext,
    session: AsyncSession,
):
    data = await state.get_data()
    word = message.text.strip().lower()

    pagination = await GroupBanwordsManager(session).search(
        group_id=data["group_id"], word=word
    )
    if not pagination.items:
        await message.answer("❌ Слово не найдено")
        return

    for item in pagination.items:
        await GroupBanwordsManager(session).delete(item)

    await redraw_banwords_menu(
        bot=message.bot,
        session=session,
        chat_id=data["banwords_chat_id"],
        message_id=data["banwords_message_id"],
        group_id=data["group_id"],
    )
    await state.set_state(DMFSM.banwords_menu)


@dm_router.callback_query(lambda c: c.data == "give_promo")
async def give_promocode_handler(
    callback: CallbackQuery,
    session: AsyncSession,
):
    await callback.answer()

    if callback.from_user.id != admin_user_id:
        await callback.message.edit_text("❌ У вас нет доступа к этой кнопке.")
        return

    promo_code = None

    for _ in range(10):
        code = generate_promocode()

        promo = Promocode(
            code=code,
            is_active=True,
            group_id=None,
        )

        session.add(promo)

        try:
            await session.commit()
            promo_code = code
            break
        except IntegrityError:
            await session.rollback()
            continue

    if promo_code is None:
        await callback.message.answer(
            "❌ Не удалось сгенерировать уникальный промокод. Попробуйте снова."
        )
        return

    await callback.message.answer(
        f"🎉 Промокод создан:\n\n`{promo_code}`",
        parse_mode="Markdown"
    )
