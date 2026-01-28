from aiogram.types import Message
from aiogram.filters import BaseFilter


class ChatTypeFilter(BaseFilter):
    def __init__(self, chat_type: str | tuple[str, ...]):
        self.chat_types = (
            {chat_type} if isinstance(chat_type, str) else set(chat_type)
        )

    async def __call__(self, message: Message) -> bool:
        return message.chat.type in self.chat_types
