from sqlalchemy.ext.asyncio import async_sessionmaker

from bot import engine
from queues.admin_queue import group_admins_queue
from database.groups import GroupSettings
from database.managers import GroupManager, UserManager, UserGroupManager
from constants.group_constants import GroupUserRole
import utils


Session = async_sessionmaker(engine, expire_on_commit=False)


async def group_admins_worker(bot):
    # Первичное добавление админов с добавлением бота
    while True:
        chat_id = await group_admins_queue.get()

        async with Session() as session:
            try:
                group_manager = GroupManager(session)
                user_manager = UserManager(session)
                user_group_manager = UserGroupManager(session)

                # 1. Группа
                group, created = await group_manager.get_or_create(
                    chat_id=chat_id
                )

                if created:
                    session.add(
                        GroupSettings(
                            group_id=group.id,
                        )
                    )

                else:
                    # страховка, если группа старая
                    if group.settings is None:
                        session.add(
                            GroupSettings(
                                group_id=group.id,
                            )
                        )

                # 2. Админы чата
                admins = await utils.get_chat_admins(chat_id)

                for admin in admins:
                    tg_user = admin.user

                    if tg_user.is_bot:
                        continue

                    # 3. Пользователь
                    user, _ = await user_manager.get_or_create(
                        telegram_user_id=tg_user.id,
                        username=tg_user.username,
                    )

                    # 4. Связь пользователь–группа
                    await user_group_manager.get_or_create(
                        user_id=user.id,
                        group_id=group.id,
                        role=GroupUserRole.ADMIN,
                    )

                await session.commit()

            except Exception:
                await session.rollback()
                raise

            finally:
                group_admins_queue.task_done()
