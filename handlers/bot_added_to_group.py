from aiogram.types import ChatMemberUpdated
from aiogram.enums import ChatMemberStatus

from routers import on_bot_added_to_group_router
from queues.admin_queue import group_admins_queue


@on_bot_added_to_group_router.my_chat_member()
async def bot_added_to_group(event: ChatMemberUpdated):
    old_status = event.old_chat_member.status
    new_status = event.new_chat_member.status

    if (
        old_status in {ChatMemberStatus.LEFT, ChatMemberStatus.KICKED}
        and
        new_status == ChatMemberStatus.ADMINISTRATOR
    ):
        await group_admins_queue.put(event.chat.id)
