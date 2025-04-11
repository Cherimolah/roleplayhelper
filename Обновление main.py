 "Обновление main.py"

from vkbottle.bot import Bot
from config import VK_TOKEN
from database import Database
from expeditor.handlers import ExpEditorHandlers

bot = Bot(token=VK_TOKEN)
db = Database()

# Существующие обработчики...

# Регистрация обработчиков Карты Экспедитора
expeditor_handlers = ExpEditorHandlers(bot, db)
expeditor_handlers.register_handlers()

bot.run_forever()