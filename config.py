"""
Загружает все переменные окружения из файла .env
"""
import os
from dotenv import load_dotenv


load_dotenv()


BOT_TOKEN = os.environ.get("BOT_TOKEN").split(",")  # Токен бота VK API

USER = os.environ.get("PG_USER")  # Пользователь базы данных
HOST = os.environ.get("HOST")  # Хост для подключения к базе данных
PASSWORD = os.environ.get("PASSWORD")  # Пароль пользователя для базы данных
DATABASE = os.environ.get("DATABASE")  # Название базы данных

OWNER = int(os.environ.get("OWNER"))  # Айди страницы ВК владельца бота
ADMINS = list(map(int, os.environ.get("ADMINS").split(",")))  # Айдишники страниц ВК администраторов бота

DATETIME_FORMAT = os.environ.get("DATETIME_FORMAT")  # Формат представления дат

SYSTEMD_NAME = os.environ.get("SYSTEMD_NAME")  # Название службы systemd (см. использование в README)

USER_BOT_TOKEN = os.getenv('USER_BOT_TOKEN')  # Токен пользователя юзер-бота
USER_ID = int(os.getenv('USER_ID'))  # Айди пользователя юзер-бота
GROUP_ID = int(os.getenv('GROUP_ID'))  # Айди группы, к которой подключен бот

HALL_CHAT_ID = int(os.getenv('HALL_CHAT_ID'))  # Айди чата, который будет стартовым при регистрации пользователя
