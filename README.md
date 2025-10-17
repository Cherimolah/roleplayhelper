# Документация
Бот представляет собой систему менеджмента персонажами в многопользовательской текстовой ролевой игре.
Создан по заказу специально для сообщества VK: [ссылка](https://vk.com/erpamonguss)  

Поддерживаются такие фичи как: 
* Создание анкеты персонажа
* Просмотр анкет других пользователей
* Система квестов с доп. целями и ежедневными заданиями
* Система особых квестов для дочерей
* Магазин предметов
* Карта экспедитора и экшен-режим. 
* Мощная админ панель с CRUD перациями
контента

Обо всех механиках будет далее

**В проекте используется фреймворки [VKBottle](https://vkbottle.readthedocs.io/ru/latest/),
[Gino](https://python-gino.org/docs/en/1.0/tutorials/tutorial.html) 
(надстройка SQLAlchemy), [Alembic](https://alembic.sqlalchemy.org/en/latest/autogenerate.html) рекомендуется
их изучить перед доработкой проекта**

По всем вопросам можно обратиться к разработчику: [VK](https://vk.com/sigma_power), [TG](https://t.me/Cherimolah)

## Содержание
1. [Подготовка и запуск проекта](#подготовка-и-запуск-проекта)
2. Описание структуры проекта
3. Описание всех механик
   1. Регистрация пользователей
   2. Главное меню
   3. Админ-панель
   4. Экшен-режим
   5. Система чатов и перемещения
4. Используемые "фреймворки"
    1. Система стейтов
    2. CRUD с объектами контента
5. Структура кастомных данных

## Подготовка и запуск проекта
Описана будет установка на Linux (Ubuntu 24.04), для Windows действия аналогичны

Установите PostgreSQL, и создайте базу данных
```bash
sudo apt install postgresql
sudo -u postgres psql
>> CREATE DATABASE roleplayhelper;
>> ALTER USER postgres WITH PASSWORD 'new_password';
>> \q
```

Важно установить пакет `libpq-dev` для работы Alembic
```bash
sudo apt install libpq-dev
```

Склонируйте репозиторий, создайте окружение, установите зависимости
```bash
git clone git@github.com:Cherimolah/roleplayhelper.git
cd roleplayhelper
python3 -m venv venv
source venv/bin/activate
pip3 install -r requirements.txt
```
Скопируйте файл `.env_sample` под названием `.env` и заполните все переменные  
```bash
cp .env_sample .env
nano .env
```
**Переменную `HALL_CHAT_ID` пока можно не заполнять, её значение получим после запуска бота**

Запускаем бота, чтобы создать таблицы и получить `HALL_CHAT_ID`
```bash
python3 main.py
```
**После запуска отправляем боту сообщение `/chat_id`. В ответ придет число, вписываем его в `.env`**  

Бота останавливаем

Создайте окружение для Alembic
```bash
alembic init alembic
```
Откройте файл `alembic.ini` и укажите URL  базе данных
```bash
nano alembic.ini
# Найдите строку и замените:
sqlalchemy.url = postgres://postgres:PASSWORD@localhost/roleplayhelper
```
Откройте файл `alembic/env.py` и укажите объект метадаты базы данных
```
nano alembic/env.py

# В начало (где все импорты)
from service.db_engine import db
...
target_metadata = db  # Надо найти эту строчку
```

Для работы перезапуска бота по кнопке надо создать unit модуль systemd

Создайте запускаемый файл `startbot`
```bash
touch startbot
chmod +x startbot
nano startbot
```
Вписываем в файл код запуска
```bash
#!/bin/bash
cd /root/roleplayhelper  # Путь к папке
source venv/bin/activate
pip3 install -r requirements.txt
alembic revision --autogenerate --head head
alembic upgrade head
python3 main.py
```
Создаем файл модуля systemd
```bash
nano /etc/systemd/system/roleplayhelper.service
```
Вписываем конфиг модуля
```
[Unit]
Description=RolePlay Bot VK

[Service]
ExecStart=/bin/bash /root/roleplayhelper/startbot
KillMode=mixed

[Install]
WantedBy=multiuser.target
```
После этого можем запускать бота
```bash
systemctl restart roleplayhelper
```

Бот пришлет айди чата, его необходимо указать в файл `.env` и перезапустить бота командой
```bash
systemctl restart roleplayhelper
```
После этого пишем боту в личные сообщения `Начать`, проходим регистрацию, и принимаем свою анкету

Для создания миграций базы данных используйте этот код
```bash
alembic revision --autogenerate --head head
alembic upgrade head
```

## Описание структуры проекта