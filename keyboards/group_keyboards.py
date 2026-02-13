from aiogram.types import (
    InlineKeyboardButton,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

from utils import CaptchaCallbackData


def captcha_keyboard(chat_id, user_id):
    _builder = InlineKeyboardBuilder()

    _builder.add(
        InlineKeyboardButton(
            text="Я не бот💛",
            callback_data=CaptchaCallbackData(
                chat_id=chat_id,
                telegram_user_id=user_id,
            ).pack(),
        ),
    )

    return _builder.as_markup()
