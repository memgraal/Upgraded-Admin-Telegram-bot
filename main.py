import asyncio

from bot import (
    bot,
    dp,
    engine,
    session_maker,
)
import database.base
import handlers.dm
import middlewares.db_connection


async def start():
    async with engine.begin() as conn:
        await conn.run_sync(
            database.base.Base.metadata.create_all,
        )

    dp.update.middleware(
        middlewares.db_connection.DbSessionMiddleware(
            session_pool=session_maker,
        )
    )

    dp.include_routers(
        handlers.dm.dm_router,
    )

    try:
        await dp.start_polling(bot)
    finally:
        await engine.dispose()


asyncio.run(start())
