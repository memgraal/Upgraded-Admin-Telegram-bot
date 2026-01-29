import os

from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder
import dotenv


dotenv.load_dotenv()


def start_menu_keyboard() -> InlineKeyboardMarkup:
    _builder = InlineKeyboardBuilder()

    _builder.add(
        InlineKeyboardButton(
            text="⚙️ Подключить группу",
            url=str(os.getenv("BOT_INVITING_LINK")),
        ),
    )

    return _builder.as_markup()
