import asyncio
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from bot import bot, dp, engine, session_maker
import database.base
from handlers.dm import dm_router
from handlers.bot_added_to_group import on_bot_added_to_group_router
from handlers.update_admins import update_users_rights
from middlewares.db_connection import DbSessionMiddleware
from queues.workers import group_admins_worker
from payments_schedule.job import check_daily_payments


scheduler = AsyncIOScheduler(
    timezone=ZoneInfo("Europe/Moscow")
)


async def start():

    async with engine.begin() as conn:
        await conn.run_sync(database.base.Base.metadata.create_all)

    dp.update.middleware(DbSessionMiddleware(session_pool=session_maker))

    dp.include_routers(
        dm_router,
        on_bot_added_to_group_router,
        update_users_rights,
    )

    asyncio.create_task(group_admins_worker(bot))

    scheduler.add_job(
        check_daily_payments,
        trigger="cron",
        hour=9,
        minute=0,
        args=[session_maker],
    )

    scheduler.start()

    try:
        await dp.start_polling(bot)
    finally:
        scheduler.shutdown(wait=False)
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(start())
