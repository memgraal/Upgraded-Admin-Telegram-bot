import re
import asyncio
from io import BytesIO
from typing import Callable, Awaitable, Dict, Any

import numpy as np
import cv2
from PIL import Image

from aiogram import BaseMiddleware
from aiogram.types import Message
from aiogram.enums import ChatType

from constants.group_constants import GroupType
from bot import qr_detector, reader
from database.managers import (
    GroupBanwordsManager,
    GroupManager,
    GroupSettingsManager,
)


def normalize(text: str) -> list[str]:
    return re.findall(r"[a-zа-яё0-9]+", text.lower())


def detect_qr(image_bytes: bytes) -> bool:
    """Проверяет, есть ли QR-код на изображении"""
    np_array = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(np_array, cv2.IMREAD_COLOR)

    data, bbox, _ = qr_detector.detectAndDecode(img)

    if bbox is not None and data:
        return True
    return False


class BanwordsMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any],
    ) -> Any:

        if not isinstance(event, Message):
            return await handler(event, data)

        if (
            event.chat.type == ChatType.CHANNEL
            or event.sender_chat is not None
        ):
            return

        session = data.get("session")
        if not session:
            return await handler(event, data)

        group = await GroupManager(session).get(chat_id=event.chat.id)

        if not group or group.subscription_type != GroupType.PAID:
            return

        group_settings = await GroupSettingsManager(session).get(
            group_id=group.id,
        )

        banwords_result = await GroupBanwordsManager(session).search(
            group_id=group.id
        )

        if not banwords_result.items:
            return await handler(event, data)

        banwords = [bw.word.lower() for bw in banwords_result.items]

        # =====================
        # 1️⃣ Проверка текста
        # =====================
        text = event.text or event.caption
        if text:
            words = normalize(text)
            if any(bw in words for bw in banwords):
                await event.delete()
                return

        # =====================
        # 2️⃣ Проверка фото
        # =====================
        if event.photo and group_settings.photo_check_enabled:
            try:
                photo = event.photo[-1]

                file = await event.bot.get_file(photo.file_id)
                file_stream = await event.bot.download_file(file.file_path)
                image_bytes = file_stream.read()

                # 🔥 2.1 Проверка QR (быстро)
                has_qr = await asyncio.to_thread(detect_qr, image_bytes)
                if has_qr:
                    await event.delete()
                    return

                # 🔥 2.2 OCR
                image = Image.open(BytesIO(image_bytes))

                result = await asyncio.to_thread(
                    reader.readtext,
                    image,
                    detail=0,
                    paragraph=True,
                )

                extracted_text = " ".join(result)
                words = normalize(extracted_text)

                if any(bw in words for bw in banwords):
                    await event.delete()
                    return

            except Exception as e:
                print("Image processing failed:", e)

        return await handler(event, data)
