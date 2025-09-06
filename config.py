"""
Загружает все переменные окружения из файла .env
"""
import os
from dotenv import load_dotenv


load_dotenv()


BOT_TOKEN = os.environ.get("BOT_TOKEN").split(",")
USER_TOKENS = os.environ.get("USER_TOKENS").split(",")

USER = os.environ.get("PG_USER")
HOST = os.environ.get("HOST")
PASSWORD = os.environ.get("PASSWORD")
DATABASE = os.environ.get("DATABASE")

OWNER = int(os.environ.get("OWNER"))
ADMINS = list(map(int, os.environ.get("ADMINS").split(",")))

DATETIME_FORMAT = os.environ.get("DATETIME_FORMAT")

SYSTEMD_NAME = os.environ.get("SYSTEMD_NAME")

CHAT_IDS = list(map(int, os.environ.get("CHAT_IDS").split(",")))

USER_BOT_TOKEN = os.getenv('USER_BOT_TOKEN')
USER_ID = int(os.getenv('USER_ID'))
GROUP_ID = int(os.getenv('GROUP_ID'))

HALL_CHAT_ID = int(os.getenv('HALL_CHAT_ID'))
