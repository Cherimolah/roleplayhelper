"""
Загружает ботов, загрузчиков медиа контента и полей для анкет
"""
import sys
from typing import List

from vkbottle.bot import Bot, MessageEvent, Message
from vkbottle.user import User
from loguru import logger
from vkbottle import PhotoMessageUploader, ConsistentTokenGenerator, DocMessagesUploader, VKAPIError, VideoUploader

from config import BOT_TOKEN, USER_TOKENS
from service.middleware import Middleware
from service.states import Registration, Admin


class SafeBot(Bot):

    async def write_msg(self, peer_ids, message: str = None, attachment: str = None, keyboard: str = None,
                        disable_mentions: bool = True):
        length = len(message) // 4096
        for i in range(0, len(message), 4096):
            await self.api.messages.send(peer_ids=peer_ids, message=message[i:i + 4096],
                                         attachment=attachment if i // 4096 == length else None,
                                         keyboard=keyboard if i // 4096 == length else None,
                                         disable_mentions=disable_mentions, random_id=0)

    async def edit_msg(self, message: Message, text: str = None, attachment: str = None, keyboard: str = None,
                       disable_mentions: bool = True, keep_forward: bool = True):
        try:
            await self.api.messages.edit(message.peer_id, text, attachment=attachment, keyboard=keyboard,
                                         disable_mentions=disable_mentions, keep_forward_messages=keep_forward,
                                         conversation_message_id=message.conversation_message_id)
        except VKAPIError:
            await self.write_msg(message.peer_id, text, attachment, keyboard, disable_mentions)

    async def change_msg(self, event: MessageEvent, text: str = None, attachment: str = None, keyboard: str = None,
                         disable_mentions: bool = True):
        try:
            await self.api.messages.edit(event.object.peer_id, text, attachment=attachment, keyboard=keyboard,
                                         disable_mentions=disable_mentions,
                                         conversation_message_id=event.object.conversation_message_id)
        except VKAPIError:
            await self.write_msg(event.object.peer_id, text, attachment, keyboard, disable_mentions)


class Field:

    def __init__(self, name: str, table: str):
        self.name = name
        self.table = table


fields = (Field("Имя", Registration.PERSONAL_NAME), Field("Должность", Registration.PROFESSION),
          Field("Биологический возраст", Registration.AGE), Field("Рост", Registration.HEIGHT),
          Field("Вес", Registration.WEIGHT), Field("Физиологические особенности", Registration.FEATURES),
          Field("Биография", Registration.BIO), Field("Характер", Registration.CHARACTER),
          Field("Мотиы нахождения на Space-station", Registration.MOTIVES),
          Field("Сексуальная ориентация", Registration.ORIENTATION),
          Field("Фетиши", Registration.FETISHES), Field("Табу", Registration.TABOO),
          Field("Визуальный портрет", Registration.PHOTO))

fields_admin = (Field("Имя", Registration.PERSONAL_NAME), Field("Должность", Registration.PROFESSION),
                Field("Биологический возраст", Registration.AGE), Field("Рост", Registration.HEIGHT),
                Field("Вес", Registration.WEIGHT), Field("Физиологические особенности", Registration.FEATURES),
                Field("Биография", Registration.BIO), Field("Характер", Registration.CHARACTER),
                Field("Мотиы нахождения на Space-station", Registration.MOTIVES),
                Field("Сексуальная ориентация", Registration.ORIENTATION),
                Field("Фетиши", Registration.FETISHES), Field("Табу", Registration.TABOO),
                Field("Визуальный портрет", Registration.PHOTO), Field("Каюта", Admin.EDIT_CABIN),
                Field("Класс каюты", Admin.EDIT_CLASS_CABIN), Field("Заморозка", Admin.EDIT_FREEZE),
                Field("Статус", Admin.EDIT_STATUS))

bot = SafeBot(ConsistentTokenGenerator(BOT_TOKEN))
bot.labeler.vbml_ignore_case = True
bot.labeler.message_view.register_middleware(Middleware)
photo_message_uploader = PhotoMessageUploader(bot.api)
doc_messages_uploader = DocMessagesUploader(bot.api)
video_uploader = VideoUploader(bot.api)
logger.remove()
logger.add(sys.stderr, level="INFO")

users: List[User] = [User(x) for x in USER_TOKENS]
