from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from bot import engine
from queues.admin_queue import group_admins_queue
from database.managers import GroupManager, UserManager, GroupSettingsManager
from database.groups import GroupSettings
from database.users_groups import UserGroup
from constants.group_constants import GroupUserRole
import utils


Session = async_sessionmaker(engine, expire_on_commit=False)


async def group_admins_worker(bot):
    while True:
        chat_id = await group_admins_queue.get()

        async with Session() as session:
            try:
                group_manager = GroupManager(session)
                user_manager = UserManager(session)

                # 1️⃣ Получаем или создаём группу
                group, created = await group_manager.get_or_create(
                    chat_id=chat_id
                )

                # 2️⃣ Если группа новая — создаём настройки
                if created:
                    await GroupSettingsManager(session).create(
                        GroupSettings(
                            group_id=group.id,
                        )
                    )

                # 3️⃣ Получаем актуальных админов Telegram
                admins = await utils.get_chat_admins(chat_id)

                db_admin_ids = set()

                for admin in admins:
                    tg_user = admin.user

                    if tg_user.is_bot:
                        continue

                    # 4️⃣ Создаём или получаем пользователя с username
                    user, created_user = await user_manager.get_or_create(
                        telegram_user_id=tg_user.id,
                        username=tg_user.username,
                    )

                    if not created_user and user.username != tg_user.username:
                        user.username = tg_user.username

                    db_admin_ids.add(user.id)

                # 5️⃣ Получаем ВСЕ связи user_group для этой группы
                result = await session.execute(
                    select(UserGroup).where(
                        UserGroup.group_id == group.id
                    )
                )
                existing_relations = result.scalars().all()

                existing_by_user = {
                    rel.user_id: rel
                    for rel in existing_relations
                }

                # 6️⃣ Обновляем / создаём ADMIN
                for user_id in db_admin_ids:
                    if user_id in existing_by_user:
                        rel = existing_by_user[user_id]
                        if rel.role != GroupUserRole.ADMIN:
                            rel.role = GroupUserRole.ADMIN
                    else:
                        session.add(
                            UserGroup(
                                user_id=user_id,
                                group_id=group.id,
                                role=GroupUserRole.ADMIN,
                            )
                        )

                # 7️⃣ Понижаем тех, кто больше не админ
                for rel in existing_relations:
                    if (
                        rel.user_id not in db_admin_ids
                        and rel.role == GroupUserRole.ADMIN
                    ):
                        rel.role = GroupUserRole.MEMBER

                await session.commit()

            except IntegrityError:
                await session.rollback()

            except Exception:
                await session.rollback()
                raise

            finally:
                group_admins_queue.task_done()
