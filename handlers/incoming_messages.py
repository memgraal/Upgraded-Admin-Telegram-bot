import asyncio

from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession
from database.captcha_logs import CaptchaLogs
from database.managers import CaptchaLogsManager
from aiogram.types import CallbackQuery
from database.captcha_logs import CaptchaStatus
from utils import CaptchaCallbackData

from database.managers import UserManager, GroupManager
from filters.is_captcha_enabled import IsCaptchaEnabled
from keyboards.group_keyboards import captcha_keyboard
from routers import group_messages


CAPTCHA_TIMEOUT = 30
pending_captcha: dict[tuple[int, int], asyncio.Task] = {}


@group_messages.edited_message()
async def handle_group_edited_message(message: Message):
    pass


@group_messages.message(
    ~IsCaptchaEnabled(),
)
async def handle_group_message(message: Message):
    print("captcha_log", 'тут')
    pass


@group_messages.message(IsCaptchaEnabled())
async def captcha_send(message: Message, session: AsyncSession):

    chat_id = message.chat.id
    user_id = message.from_user.id
    key = (chat_id, user_id)

    if key in pending_captcha:
        await message.delete()
        return

    user_message_id = message.message_id

    captcha_msg = await message.answer(
        "👋 Подтвердите, что вы не бот\n"
        "⏳ У вас 30 секунд",
        reply_markup=captcha_keyboard(chat_id, user_id),
        reply_to_message_id=user_message_id,
    )

    async def timeout():
        await asyncio.sleep(CAPTCHA_TIMEOUT)

        if key in pending_captcha:
            pending_captcha.pop(key, None)

            # удаляем сообщение бота
            try:
                await captcha_msg.delete()
            except Exception:
                pass

            # удаляем сообщение пользователя
            try:
                await message.bot.delete_message(chat_id, user_message_id)
            except Exception:
                pass

    task = asyncio.create_task(timeout())
    pending_captcha[key] = task


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

    task = pending_captcha.pop(key, None)
    if task:
        task.cancel()

    await callback.message.delete()

    user = await UserManager(session).get(
        telegram_user_id=callback_data.telegram_user_id,
    )

    group = await GroupManager(session).get(
        chat_id=callback_data.chat_id,
    )

    if not user:
        await callback.answer("❌ Пользователь не найден")
        return

    # создаём лог прохождения
    await CaptchaLogsManager(session).create(
        CaptchaLogs(
            group_id=group.id,
            user_id=user.id,
            status=CaptchaStatus.SOLVED,
        )
    )

    await session.commit()

    await callback.answer("✅ Теперь можно писать")
