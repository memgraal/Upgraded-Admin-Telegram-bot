import asyncio
import random

from dataclasses import dataclass

from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from database.captcha_logs import CaptchaLogs, CaptchaStatus
from database.managers import (
    CaptchaLogsManager,
    UserManager,
    GroupManager,
)
from filters.is_captcha_enabled import IsCaptchaEnabled
from routers import group_messages


CAPTCHA_TIMEOUT = 30


# =========================================================
# CAPTCHA
# =========================================================

def generate_captcha() -> tuple[str, int]:

    operation = random.choice(["+", "-"])

    if operation == "+":

        first = random.randint(1, 10)
        second = random.randint(1, 10)

        answer = first + second

    elif operation == "-":

        first = random.randint(1, 10)
        second = random.randint(1, first)

        answer = first - second

    question = f"{first} {operation} {second} = ?"

    return question, answer


# =========================================================
# STATE MODEL
# =========================================================

@dataclass
class CaptchaState:

    task: asyncio.Task | None

    user_message_id: int | None

    captcha_message_id: int | None

    answer: int

    lock: asyncio.Lock


# (chat_id, user_id) -> CaptchaState
active_captcha: dict[tuple[int, int], CaptchaState] = {}


# =========================================================
# CLEANUP
# =========================================================

async def cleanup_captcha(
    chat_id: int,
    user_id: int,
):
    key = (chat_id, user_id)

    state = active_captcha.pop(key, None)

    if not state:
        return

    if state.task and not state.task.done():
        state.task.cancel()


# =========================================================
# EDITED MESSAGE
# =========================================================

@group_messages.edited_message()
async def handle_group_edited_message(message: Message):

    key = (
        message.chat.id,
        message.from_user.id,
    )

    if key not in active_captcha:
        return

    try:
        await message.delete()
    except Exception:
        pass


# =========================================================
# CAPTCHA HANDLER
# =========================================================

@group_messages.message(IsCaptchaEnabled())
async def captcha_handler(
    message: Message,
    session: AsyncSession,
):

    chat_id = message.chat.id
    user_id = message.from_user.id

    key = (chat_id, user_id)


    # =====================================================
    # У ПОЛЬЗОВАТЕЛЯ УЖЕ ЕСТЬ КАПЧА
    # =====================================================

    if key in active_captcha:

        state = active_captcha[key]

        async with state.lock:

            user_answer = (message.text or "").strip()


            # -------------------------------------------------
            # Удаляем ответ пользователя
            # -------------------------------------------------

            try:
                await message.delete()
            except Exception:
                pass


            # -------------------------------------------------
            # Пытаемся преобразовать ответ в число
            # -------------------------------------------------

            try:
                answer = int(user_answer)

            except (ValueError, TypeError):

                answer = None


            # -------------------------------------------------
            # Неправильный ответ
            # -------------------------------------------------

            if answer != state.answer:
                return


            # =================================================
            # CAPTCHA SOLVED
            # =================================================

            user_message_id = state.user_message_id
            captcha_message_id = state.captcha_message_id


            # -------------------------------------------------
            # Удаляем state и останавливаем timeout
            # -------------------------------------------------

            await cleanup_captcha(
                chat_id,
                user_id,
            )


            # -------------------------------------------------
            # Удаляем исходное сообщение пользователя
            # -------------------------------------------------

            if user_message_id:

                try:
                    await message.bot.delete_message(
                        chat_id,
                        user_message_id,
                    )

                except Exception:
                    pass


            # -------------------------------------------------
            # Удаляем сообщение с капчей
            # -------------------------------------------------

            if captcha_message_id:

                try:
                    await message.bot.delete_message(
                        chat_id,
                        captcha_message_id,
                    )

                except Exception:
                    pass


            # =================================================
            # DATABASE
            # =================================================

            user = await UserManager(session).get(
                telegram_user_id=user_id,
            )

            group = await GroupManager(session).get(
                chat_id=chat_id,
            )


            if not user or not group:
                return


            await CaptchaLogsManager(session).create(
                CaptchaLogs(
                    group_id=group.id,
                    user_id=user.id,
                    status=CaptchaStatus.SOLVED,
                )
            )


            await session.commit()

        return


    # =====================================================
    # ПЕРВОЕ СООБЩЕНИЕ -> СОЗДАЁМ КАПЧУ
    # =====================================================

    question, answer = generate_captcha()


    # -----------------------------------------------------
    # Отправляем капчу reply на сообщение пользователя
    # -----------------------------------------------------

    captcha_message = await message.answer(
        "👋 Подтвердите, что вы не бот\n\n"
        f"🧮 Решите пример:\n\n"
        f"<b>{question}</b>\n\n"
        f"⏳ У вас {CAPTCHA_TIMEOUT} секунд",
        parse_mode="HTML",
        reply_to_message_id=message.message_id,
    )


    captcha_message_id = captcha_message.message_id

    user_message_id = message.message_id


    # =====================================================
    # TIMEOUT
    # =====================================================

    async def timeout():

        try:

            await asyncio.sleep(CAPTCHA_TIMEOUT)


            state = active_captcha.get(key)

            if not state:
                return


            active_captcha.pop(key, None)


            # -------------------------------------------------
            # Удаляем исходное сообщение пользователя
            # -------------------------------------------------

            try:

                await message.bot.delete_message(
                    chat_id,
                    user_message_id,
                )

            except Exception:
                pass


            # -------------------------------------------------
            # Удаляем сообщение с капчей
            # -------------------------------------------------

            try:

                await message.bot.delete_message(
                    chat_id,
                    captcha_message_id,
                )

            except Exception:
                pass


        except asyncio.CancelledError:

            pass


    task = asyncio.create_task(timeout())


    # =====================================================
    # SAVE STATE
    # =====================================================

    active_captcha[key] = CaptchaState(

        task=task,

        user_message_id=user_message_id,

        captcha_message_id=captcha_message_id,

        answer=answer,

        lock=asyncio.Lock(),
    )
