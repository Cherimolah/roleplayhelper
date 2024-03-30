"""
Загружает ботов, загрузчиков медиа контента и полей для анкет
"""
import sys
from typing import List

from vkbottle.bot import Bot, BotLabeler
from vkbottle import API
from loguru import logger
from vkbottle import PhotoMessageUploader, DocMessagesUploader, VideoUploader

from config import BOT_TOKEN, USER_TOKENS
from service.middleware import Middleware
from service.states import Registration, Admin
from bot_extended import APIExtended, RawBotEventViewExtended, BotMessageViewExtended, ErrorHandlerExtended, RouterExtended


class Field:

    def __init__(self, name: str, state: str):
        self.name = name
        self.state = state


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

bot = Bot(api=APIExtended(BOT_TOKEN),
          labeler=BotLabeler(raw_event_view=RawBotEventViewExtended(),
                             message_view=BotMessageViewExtended()), error_handler=ErrorHandlerExtended(),
          router=RouterExtended())
bot.labeler.vbml_ignore_case = True
bot.labeler.message_view.register_middleware(Middleware)
photo_message_uploader = PhotoMessageUploader(bot.api)
doc_messages_uploader = DocMessagesUploader(bot.api)
video_uploader = VideoUploader(bot.api)
logger.remove()
logger.add(sys.stderr, level="INFO")

users: List[API] = [API(x) for x in USER_TOKENS]
