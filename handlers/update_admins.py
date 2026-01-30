from aiogram.types import ChatMemberUpdated
from aiogram.enums import ChatMemberStatus
from sqlalchemy.ext.asyncio import AsyncSession

from routers import update_users_rights
from database.users_groups import UserGroup
from database.managers import GroupManager, UserManager, UserGroupManager
from constants.group_constants import GroupUserRole


@update_users_rights.chat_member()
async def update_admins_handler(
    event: ChatMemberUpdated,
    session: AsyncSession,
):
    group_manager = GroupManager(session)
    user_manager = UserManager(session)
    user_group_manager = UserGroupManager(session)

    old_status = event.old_chat_member.status
    new_status = event.new_chat_member.status

    tg_user = event.new_chat_member.user
    chat = event.chat

    if tg_user.is_bot:
        return

    # --- группа ---
    group, _ = await group_manager.get_or_create(
        chat_id=chat.id
    )

    # --- пользователь ---
    user, _ = await user_manager.get_or_create(
        telegram_user_id=tg_user.id,
        username=tg_user.username,
    )

    # --- связь пользователь–группа ---
    user_group = await user_group_manager.get(
        user_id=user.id,
        group_id=group.id,
    )

    # === ПОЛЬЗОВАТЕЛЬ ВЫШЕЛ / КИКНУТ ===
    if new_status in {
        ChatMemberStatus.LEFT,
        ChatMemberStatus.KICKED,
    }:
        if user_group:
            await user_group_manager.delete(user_group)

        await session.commit()
        return

    # === ЕСЛИ СВЯЗИ НЕТ — СОЗДАЁМ (по умолчанию MEMBER) ===
    if user_group is None:
        user_group = await user_group_manager.create(
            UserGroup(
                user_id=user.id,
                group_id=group.id,
                role=GroupUserRole.MEMBER,
            ),
        )

    # === НАЗНАЧИЛИ АДМИНОМ ===
    if (
        old_status in {
            ChatMemberStatus.MEMBER,
            ChatMemberStatus.RESTRICTED,
        }
        and new_status == ChatMemberStatus.ADMINISTRATOR
    ):
        if user_group.role != GroupUserRole.ADMIN:
            await user_group_manager.update(
                user_group,
                role=GroupUserRole.ADMIN,
            )

    # === СНЯЛИ АДМИНКУ ===
    elif (
        old_status == ChatMemberStatus.ADMINISTRATOR
        and new_status in {
            ChatMemberStatus.MEMBER,
            ChatMemberStatus.RESTRICTED,
        }
    ):
        if user_group.role != GroupUserRole.MEMBER:
            await user_group_manager.update(
                user_group,
                role=GroupUserRole.MEMBER,
            )

    await session.commit()
