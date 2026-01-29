from aiogram import types
from aiogram.filters import CommandStart
from sqlalchemy.ext.asyncio import AsyncSession

import constants.text_constants
import keyboards.dm_keyboards
from routers import dm_router


@dm_router.message(CommandStart())
async def start(message: types.Message, session: AsyncSession):

    await message.answer(
        constants.text_constants.START_GEREETING_TEXT,
        reply_markup=keyboards.dm_keyboards.start_menu_keyboard(),
    )
