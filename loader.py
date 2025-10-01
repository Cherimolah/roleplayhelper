"""
Загружает ботов, загрузчиков медиа контента и полей для анкет
"""
import sys

from vkbottle.bot import Bot, BotLabeler
from vkbottle import CtxStorage, User
from loguru import logger
from vkbottle import PhotoMessageUploader, DocMessagesUploader, VideoUploader

from config import BOT_TOKEN, USER_BOT_TOKEN
from bot_extended import (APIExtended, RawBotEventViewExtended,
                          RouterExtended, AioHTTPClientExtended, BotMessageViewExtended)

states = CtxStorage()

bot = Bot(api=APIExtended(BOT_TOKEN, http_client=AioHTTPClientExtended()),
          labeler=BotLabeler(raw_event_view=RawBotEventViewExtended(), message_view=BotMessageViewExtended()),
          router=RouterExtended())
bot.labeler.vbml_ignore_case = True
photo_message_uploader = PhotoMessageUploader(bot.api)
doc_messages_uploader = DocMessagesUploader(bot.api)
video_uploader = VideoUploader(bot.api)
logger.remove()
logger.add(sys.stderr, level="INFO")
bot.api.API_URL = 'https://api.vk.ru/method/'

user_bot = User(USER_BOT_TOKEN)
