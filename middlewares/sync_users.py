from typing import Callable, Awaitable, Dict, Any

from aiogram import BaseMiddleware
from aiogram.types import Message
from aiogram.enums import ChatType

from database.users import User
from database.managers import (
    UserManager,
    UserGroupManager,
    GroupManager,
)


class SyncUsersMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any],
    ) -> Any:

        if not isinstance(event, Message):
            return await handler(event, data)

        if (
            event.chat.type == ChatType.CHANNEL
            or not event.from_user
        ):
            return

        session = data["session"]

        user = await UserManager(session).get(
            telegram_user_id=event.from_user.id
        )

        if not user:
            user = await UserManager(session).create(
                User(
                    telegram_user_id=event.from_user.id,
                    username=event.from_user.username,
                ),
            )

        group = await GroupManager(session).get(
            chat_id=event.chat.id,
        )

        if group:
            await UserGroupManager(session).get_or_create(
                user_id=user.id,
                group_id=group.id,
            )

        return await handler(event, data)
