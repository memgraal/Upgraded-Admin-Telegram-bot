from aiogram import Router

from filters.chat_type import ChatTypeFilter


dm_router = Router(name="dm_router")
dm_router.message.filter(
    ChatTypeFilter("private")
)


on_bot_added_to_group_router = Router(name="on_bot_added_to_group_router")
on_bot_added_to_group_router.message.filter(
    ChatTypeFilter(("group", "supergroup"))
)


update_users_rights = Router(name="update_users_rights")
update_users_rights.message.filter(
    ChatTypeFilter(("group", "supergroup"))
)
