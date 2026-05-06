import asyncio
from dataclasses import dataclass

from aiogram.types import Message, CallbackQuery
from aiogram.filters.callback_data import CallbackData
from sqlalchemy.ext.asyncio import AsyncSession

from database.captcha_logs import CaptchaLogs, CaptchaStatus
from database.managers import (
    CaptchaLogsManager,
    UserManager,
    GroupManager,
)
from filters.is_captcha_enabled import IsCaptchaEnabled
from keyboards.group_keyboards import captcha_keyboard
from routers import group_messages


CAPTCHA_TIMEOUT = 30


# =========================================================
# CALLBACK DATA
# =========================================================
class CaptchaCallbackData(CallbackData, prefix="captcha"):
    chat_id: int
    telegram_user_id: int


# =========================================================
# STATE MODEL
# =========================================================
@dataclass
class CaptchaState:
    task: asyncio.Task | None
    user_message_id: int | None
    captcha_message_id: int | None
    lock: asyncio.Lock


# (chat_id, user_id) -> CaptchaState
active_captcha: dict[tuple[int, int], CaptchaState] = {}


# =========================================================
# CLEANUP (как в старом коде)
# =========================================================
async def cleanup_captcha(bot, chat_id: int, user_id: int):
    key = (chat_id, user_id)

    state = active_captcha.pop(key, None)
    if not state:
        return

    if state.task and not state.task.done():
        state.task.cancel()


# =========================================================
# HANDLERS
# =========================================================
@group_messages.edited_message()
async def handle_group_edited_message(message: Message):
    pass


@group_messages.message(~IsCaptchaEnabled())
async def handle_group_message(message: Message):
    pass


# =========================================================
# SEND CAPTCHA
# =========================================================
@group_messages.message(IsCaptchaEnabled())
async def captcha_send(message: Message, session: AsyncSession):

    chat_id = message.chat.id
    user_id = message.from_user.id
    key = (chat_id, user_id)

    if key not in active_captcha:
        active_captcha[key] = CaptchaState(
            task=None,
            user_message_id=None,
            captcha_message_id=None,
            lock=asyncio.Lock(),
        )

    state = active_captcha[key]

    async with state.lock:

        if state.task:
            await message.delete()
            return

        user_message_id = message.message_id

        captcha_msg = await message.answer(
            "👋 Подтвердите, что вы не бот\n"
            "⏳ У вас 30 секунд",
            reply_markup=captcha_keyboard(chat_id, user_id),
            reply_to_message_id=user_message_id,
        )

        captcha_message_id = captcha_msg.message_id
        bot = message.bot   # snapshot

        # ⭐ ВАЖНО — timeout удаляет напрямую (как старый код)
        async def timeout():
            try:
                await asyncio.sleep(CAPTCHA_TIMEOUT)

                active_captcha.pop(key, None)

                try:
                    await bot.delete_message(chat_id, captcha_message_id)
                except Exception:
                    pass

                try:
                    await bot.delete_message(chat_id, user_message_id)
                except Exception:
                    pass

            except asyncio.CancelledError:
                pass

        task = asyncio.create_task(timeout())

        state.task = task
        state.user_message_id = user_message_id
        state.captcha_message_id = captcha_message_id


# =========================================================
# CONFIRM CAPTCHA
# =========================================================
@group_messages.callback_query(CaptchaCallbackData.filter())
async def captcha_confirm(
    callback: CallbackQuery,
    callback_data: CaptchaCallbackData,
    session: AsyncSession,
):
    if callback.from_user.id != callback_data.telegram_user_id:
        await callback.answer("❌ Это не для вас", show_alert=True)
        return

    chat_id = callback_data.chat_id
    user_id = callback_data.telegram_user_id
    key = (chat_id, user_id)

    # ✅ получаем state ДО cleanup
    state = active_captcha.get(key)

    # ✅ удаляем ТОЛЬКО сообщение капчи
    if state and state.captcha_message_id:
        try:
            await callback.bot.delete_message(chat_id, state.captcha_message_id)
        except Exception:
            pass

    # ✅ теперь чистим timeout / state
    await cleanup_captcha(callback.bot, chat_id, user_id)

    user = await UserManager(session).get(
        telegram_user_id=user_id,
    )

    group = await GroupManager(session).get(
        chat_id=chat_id,
    )

    if not user or not group:
        await callback.answer("❌ Ошибка данных")
        return

    await CaptchaLogsManager(session).create(
        CaptchaLogs(
            group_id=group.id,
            user_id=user.id,
            status=CaptchaStatus.SOLVED,
        )
    )

    await session.commit()

    await callback.answer("✅ Теперь можно писать")

