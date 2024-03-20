import os

BOT_TOKEN = os.environ.get("BOT_TOKEN").split(";")
USER_TOKENS = os.environ.get("USER_TOKEN").split(";")
PASSWORD = os.environ.get("PG_PASSWORD")
OWNER = 671385770
ADMINS = [32650977]


USER = "postgres"
DATABASE = "role_play"
HOST = "localhost"

DATETIME_FORMAT = "%d.%m.%Y %H:%M:%S"
