import re
import asyncio
from io import BytesIO
from typing import Callable, Awaitable, Dict, Any

import numpy as np
import cv2
from PIL import Image
import pytesseract

from aiogram import BaseMiddleware
from aiogram.types import Message
from aiogram.enums import ChatType

from constants.group_constants import GroupType
from bot import qr_detector
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
    return bool(bbox is not None and data)


def extract_text_tesseract(image_bytes: bytes) -> str:
    """OCR через Tesseract"""
    image = Image.open(BytesIO(image_bytes))

    # lang можно расширить при необходимости
    text = pytesseract.image_to_string(image, lang="rus+eng")
    return text


class BanwordsMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any],
    ) -> Any:

        if not isinstance(event, Message):
            print("BanwordsMiddleware: событие не Message, пропускаем")
            return await handler(event, data)

        if event.chat.type == ChatType.CHANNEL or event.sender_chat is not None:
            print("BanwordsMiddleware: канал сделал пост или коммент от имени канала, пропускаем")
            return

        session = data.get("session")
        if not session:
            print("BanwordsMiddleware: нет сессии в данных, пропускаем")
            return await handler(event, data)

        group = await GroupManager(session).get(chat_id=event.chat.id)
        if not group or group.subscription_type != GroupType.PAID:
            print("BanwordsMiddleware: группа не подписанна, пропускаем")
            return

        group_settings = await GroupSettingsManager(session).get(
            group_id=group.id,
        )

        banwords_result = await GroupBanwordsManager(session).search(
            group_id=group.id
        )

        if not banwords_result.items:
            print("BanwordsMiddleware: нет слов для проверки, пропускаем")
            return await handler(event, data)

        banwords = [bw.word.lower() for bw in banwords_result.items]
        print(f"BanwordsMiddleware: проверяем сообщение {event.message_id} в группе {event.chat.id} на слова {banwords}")
        # =====================
        # 1️⃣ Проверка текста
        # =====================
        text = event.text or event.caption
        if text:
            print("Text:", text)
            words = normalize(text)
            if any(bw in words for bw in banwords):
                await event.delete()
                return
        print("Текстовая проверка пройдена")
        # =====================
        # 2️⃣ Проверка фото
        # =====================
        if event.photo and group_settings.photo_check_enabled:
            print("Photo check enabled")
            try:
                photo = event.photo[-1]
                file = await event.bot.get_file(photo.file_id)
                file_stream = await event.bot.download_file(file.file_path)
                image_bytes = file_stream.read()
                print("Image downloaded, size:", len(image_bytes))
                # 🔥 2.1 QR
                has_qr = await asyncio.to_thread(detect_qr, image_bytes)
                if has_qr:
                    print("QR detected")
                    await event.delete()
                    return
                # 🔥 2.2 OCR (Tesseract)
                extracted_text = await asyncio.to_thread(
                    extract_text_tesseract,
                    image_bytes,
                )
                print("Text extracted:", extracted_text)

                words = normalize(extracted_text)
                if any(bw in words for bw in banwords):
                    await event.delete()
                    return

            except Exception as e:
                print("Image processing failed:", e)

        return await handler(event, data)
