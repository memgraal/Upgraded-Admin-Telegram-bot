from aiogram.filters import BaseFilter
from aiogram.types import Message


class IsMessageNotChannelPost(BaseFilter):
    async def __call__(self, message: Message) -> bool:
        # канал-пост
        if message.sender_chat:
            return False

        # сервисные сообщения
        if (
            message.new_chat_members
            or message.left_chat_member
            or message.pinned_message
            or message.new_chat_title
            or message.new_chat_photo
        ):
            return False

        # пересланные сообщения
        if message.forward_from or message.forward_from_chat:
            return False

        return True
