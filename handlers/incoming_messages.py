import asyncio
import logging
from typing import List
from typing import Dict, Tuple

import aiohttp
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
from utils import CaptchaCallbackData, safe_delete


logger = logging.getLogger(__name__)

API_URL = "http://qwertyx.dev-core.me/does_image_have_banwords"

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
    """
    Обработчик CAPTCHA для новых пользователей в группе.
    """
    chat_id = message.chat.id
    user_id = message.from_user.id
    key = (chat_id, user_id)

    # Ищем пользователя
    user = await UserManager(session).get(telegram_user_id=user_id)

    # Если нет — создаём
    if not user:
        user = await UserManager(session).create(
            telegram_user_id=user_id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
            last_name=message.from_user.last_name,
        )
        await session.commit()

    # Если уже есть активная CAPTCHA, удаляем сообщение
    if key in pending_captcha:
        await safe_delete(message)
        return

    try:
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
    except Exception as e:
        logger.error(f"Failed to send captcha message: {e}")
        return

    async def timeout():
        """Таймаут для CAPTCHA (30 секунд)."""
        try:
            await asyncio.sleep(CAPTCHA_TIMEOUT)
        except asyncio.CancelledError:
            return

        if key in pending_captcha:
            pending_captcha.pop(key, None)
            try:
                await safe_delete(captcha_msg)
                await safe_delete(message)
            except Exception as e:
                logger.warning(f"Failed to delete messages: {e}")

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
    """
    Обработчик подтверждения CAPTCHA.
    """
    if callback.from_user.id != callback_data.telegram_user_id:
        await callback.answer("❌ Это не для вас", show_alert=True)
        return

    key = (callback_data.chat_id, callback_data.telegram_user_id)

    # Отменяем таймаут
    captcha_data = pending_captcha.pop(key, None)
    if captcha_data:
        captcha_data['task'].cancel()

    try:
        await safe_delete(callback.message)
    except Exception as e:
        logger.warning(f"Failed to delete callback message: {e}")

    try:
        # Получаем/создаём пользователя
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

        # Получаем группу
        group = await GroupManager(session).get(
            chat_id=callback_data.chat_id,
        )

        if not group:
            logger.error(f"Group {callback_data.chat_id} not found")
            await callback.answer("❌ Ошибка: группа не найдена")
            return

        # Создаём лог CAPTCHA
        await CaptchaLogsManager(session).create(
            CaptchaLogs(
                user_id=user.id,
                group_id=group.id,
                status=CaptchaStatus.SOLVED,
            )
        )

        # Получаем/создаём связь пользователя с группой
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

        await session.commit()
        await callback.answer("✅ Теперь можно писать")

    except Exception as e:
        logger.error(f"Error in captcha_confirm: {e}")
        await session.rollback()
        await callback.answer("❌ Произошла ошибка")


def contains_banword(text: str, banwords: List[str]) -> bool:
    """
    Проверяет наличие банворда в тексте.
    
    Args:
        text: Текст для проверки
        banwords: Список банвордов (строк или объектов Banwords)
    
    Returns:
        True если найден хотя бы один банворд
    """
    if not text or not banwords:
        return False

    text_lower = text.lower()
    
    for word in banwords:
        # Если это объект Banwords, берём атрибут .word
        if hasattr(word, 'word'):
            banword_str = word.word.lower()
        else:
            # Если это уже строка
            banword_str = word.lower() if isinstance(word, str) else str(word).lower()
        
        if banword_str in text_lower:
            return True
    
    return False


async def check_image_for_banwords(
    photo,
    message: Message,
    banwords: List[str],
):
    """
    Проверяет изображение на наличие банвордов через API.
    Использует aiohttp для отправки multipart/form-data.
    
    Args:
        photo: Объект фото из сообщения
        message: Объект сообщения
        banwords: Список банвордов для проверки (СТРОКИ!)
    """
    try:
        # Скачиваем файл фото
        file = await message.bot.get_file(photo.file_id)
        file_stream = await message.bot.download_file(file.file_path)

        # Получаем байты изображения
        image_bytes = file_stream.read()

        # Формируем multipart/form-data
        form_data = aiohttp.FormData()
        form_data.add_field(
            'image',
            image_bytes,
            filename='image.png',
            content_type='image/png'
        )

        # Добавляем каждый банворд отдельным полем
        for banword in banwords:
            form_data.add_field('banwords', banword)

        try:
            # ✅ Используем aiohttp вместо requests_async
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    API_URL,
                    data=form_data,
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as response:
                    if response.status == 200:
                        # API возвращает bool
                        has_banwords = await response.json()

                        if has_banwords:
                            try:
                                await message.delete()
                                logger.info(
                                    f"Message {message.message_id} deleted: banwords found in image"
                                )
                            except Exception as e:
                                logger.warning(f"Failed to delete photo message: {e}")

                    elif response.status >= 500:
                        logger.error(
                            f"API server error {response.status}: {await response.text()}"
                        )
                    else:
                        logger.warning(
                            f"API returned status {response.status}: {await response.text()}"
                        )

        except asyncio.TimeoutError:
            logger.error(f"API request timeout for photo {photo.file_id}")
        except aiohttp.ClientError as e:
            logger.error(f"API connection error: {type(e).__name__}: {e}")
        except Exception as e:
            logger.error(f"API request error: {type(e).__name__}: {e}")

    except Exception as e:
        logger.error(f"Error checking image for banwords: {type(e).__name__}: {e}")


@group_messages.message(
    IsGroupPayed(),
    IsMessageNotChannelPost(),
    IfAnyBanwords(),
)
async def banwords_message_handler(
    message: Message,
    session: AsyncSession,
):
    """
    Обработчик проверки сообщений на банворды.
    Проверяет текст и фото с использованием локальной функции и API.
    """
    try:
        group = await GroupManager(session).get(
            chat_id=message.chat.id,
        )

        if not group:
            logger.warning(f"Group {message.chat.id} not found")
            return

        settings = await GroupSettingsManager(session).get(
            group_id=group.id,
        )

        banwords = await GroupBanwordsManager(session).search(
            group_id=group.id,
        )

        if not banwords or not settings:
            return

        # ✅ Правильно извлекаем список строк из объектов Banwords
        banword_list = [bw.word for bw in banwords.items] if banwords.items else []

        if not banword_list:
            return

        # ================================================
        # 1️⃣ Проверка обычного текста
        # ================================================
        if message.text:
            if contains_banword(message.text, banword_list):
                try:
                    await message.delete()
                    logger.info(f"Text message {message.message_id} deleted: banword found")
                except Exception as e:
                    logger.warning(f"Failed to delete text message: {e}")
                return

        # ================================================
        # 2️⃣ Проверка фото
        # ================================================
        if settings.photo_check_enabled and message.photo:
            photo = message.photo[-1]  # самое большое разрешение

            # 2.1 Фото с подписью
            if message.caption:
                if contains_banword(message.caption, banword_list):
                    try:
                        await message.delete()
                        logger.info(f"Photo message {message.message_id} with caption deleted: banword found")
                    except Exception as e:
                        logger.warning(f"Failed to delete photo message with caption: {e}")
                    return

            # 2.2 Фото без подписи ― отправляем на API OCR
            else:
                # ✅ ПЕРЕДАЁМ СПИСОК СТРОК!
                await check_image_for_banwords(
                    photo=photo,
                    message=message,
                    banwords=banword_list,
                )

    except Exception as e:
        logger.error(f"Error in banwords_message_handler: {e}")
