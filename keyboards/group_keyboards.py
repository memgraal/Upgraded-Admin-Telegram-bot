from aiogram.types import (
    InlineKeyboardButton,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

from utils import CaptchaCallbackData


def captcha_keyboard(callback_credantionals: CaptchaCallbackData):
    _builder = InlineKeyboardBuilder()

    _builder.add(
        InlineKeyboardButton(
            text="Я не бот💛",
            callback_data=callback_credantionals.pack(),
        ),
    )

    return _builder.as_markup()
