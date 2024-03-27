"""
Загружает все переменные окружения из файла .env
"""
import os
from dotenv import load_dotenv


load_dotenv()


BOT_TOKEN = os.environ.get("BOT_TOKEN").split(";")
USER_TOKENS = os.environ.get("USER_TOKENS").split(";")

USER = os.environ.get("PG_USER")
HOST = os.environ.get("HOST")
PASSWORD = os.environ.get("PASSWORD")
DATABASE = os.environ.get("DATABASE")

OWNER = int(os.environ.get("OWNER"))
ADMINS = list(map(int, os.environ.get("ADMINS").split(";")))

DATETIME_FORMAT = os.environ.get("DATETIME_FORMAT")
