"""
Загружает ботов, загрузчиков медиа контента и полей для анкет
"""
import sys
from typing import List

from vkbottle.bot import Bot, BotLabeler
from vkbottle import API, CtxStorage
from loguru import logger
from vkbottle import PhotoMessageUploader, DocMessagesUploader, VideoUploader

from config import BOT_TOKEN, USER_TOKENS
from bot_extended import (APIExtended, RawBotEventViewExtended, BotMessageViewExtended, ErrorHandlerExtended,
                          RouterExtended, AioHTTPClientExtended)

states = CtxStorage()

bot = Bot(api=APIExtended(BOT_TOKEN, http_client=AioHTTPClientExtended()),
          labeler=BotLabeler(raw_event_view=RawBotEventViewExtended(),
                             message_view=BotMessageViewExtended()), error_handler=ErrorHandlerExtended(),
          router=RouterExtended())
bot.labeler.vbml_ignore_case = True
photo_message_uploader = PhotoMessageUploader(bot.api)
doc_messages_uploader = DocMessagesUploader(bot.api)
video_uploader = VideoUploader(bot.api)
logger.remove()
logger.add(sys.stderr, level="INFO")

users: List[API] = [API(x) for x in USER_TOKENS]
for user in users:
    user.API_VERSION = '5.134'
