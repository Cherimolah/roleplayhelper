import asyncio
import datetime
import os
from typing import List, Tuple, Optional, Union
import re

from sqlalchemy import and_, func, or_
from vkbottle_types.objects import PhotosPhotoSizes
from vkbottle.bot import Message, MessageEvent
from aiohttp import ClientSession
import aiofiles
from vkbottle import Keyboard, Callback, KeyboardButtonColor

from service.db_engine import db
from loader import bot, photo_message_uploader
from service.states import Admin
from service.middleware import states
import messages


def get_max_size_url(sizes: List[PhotosPhotoSizes]) -> str:
    square = 0
    index = 0
    for i, size in enumerate(sizes):
        if size.height * size.width > square:
            square = size.height * size.width
            index = i
    return sizes[index].url


def parse_orientation(number: int) -> str:
    if number == 0:
        return "гетеро"
    if number == 1:
        return "би"
    if number == 2:
        return "гомо"


async def loads_form(user_id: int = None, is_request: bool = None, number: int = 1, form_id: int = None) -> Tuple[str, Optional[str]]:
    if form_id:
        form = await db.select([*db.Form]).where(db.Form.id == form_id).gino.first()
    else:
        if is_request:
            form = await db.select([*db.Form]).where(
                and_(db.Form.user_id == user_id, db.Form.is_request.is_(is_request))
            ).gino.first()
        else:
            form = await db.select([*db.Form]).where(
                or_(and_(db.Form.user_id == user_id, db.Form.is_request.is_(is_request)),
                    and_(db.Form.number == number, db.Form.user_id == user_id))
            ).gino.first()
    user = (await bot.api.users.get(user_id))[0]
    if form.profession:
        profession = await db.select([db.Profession.name]).where(db.Profession.id == form.profession).gino.scalar()
    else:
        profession = None
    reply = f"Анкета пользователя [id{user_id}|{user.first_name} {user.last_name}]:\n\n" \
            f"Имя персонажа: {form.name}\n" \
            f"Должность: {profession or 'Не установлена'}\n" \
            f"Биологический возраст: {form.age} Земных лет\n" \
            f"Рост: {form.height} см\n" \
            f"Вес: {form.weight} кг\n" \
            f"Физиологические особенности: {form.features}\n" \
            f"Биография: {form.bio or 'не указана'}\n" \
            f"Харарктер: {form.character or 'не указан'}\n" \
            f"Мотивы нахождения на Space station: {form.motives or 'не указаны'}\n" \
            f"Сексуальная ориентация: {parse_orientation(form.orientation)}\n" \
            f"Фетиши: {form.fetishes or 'не указаны'}\n" \
            f"Табу: {form.taboo or 'не указаны'}\n" \
            f"Каюта: {form.cabin or 'не присвоена'}\n" \
            f"Тип каюты: {await db.select([db.Cabins.name]).where(db.Cabins.id == form.cabin_type).gino.scalar() or 'Не указан'}\n" \
            f"Баланс: {form.balance}\n" \
            f"Статус: {await db.select([db.Status.name]).where(db.Status.id == form.status).gino.scalar()}\n" \
            f"{'Визуальный портрет:' if form.photo else ''}"
    return reply, form.photo


async def parse_user_id(m: Message, many_users=False) -> Union[int, List[int]]:
    if m.reply_message:
        return m.reply_message.from_id
    elif m.text.isdigit():
        return int(m.text)
    if m.fwd_messages:
        user_ids = [x.from_id for x in m.fwd_messages]
    else:
        user_ids = []
    mention_regex = re.compile(r"\[(?P<type>id|club|public)(?P<id>\d*)\|(?P<text>.+)\]")
    link_regex = re.compile(r"https:/(?P<type>/|/m.)vk.com/(?P<screen_name>\w*)")
    text = m.text.lower()
    screen_names: List[str] = [x[1] for x in re.findall(link_regex, text)]
    screen_names.extend(re.findall(mention_regex, text))
    if screen_names:
        for screen_name in screen_names:
            if screen_name.isdigit():
                user_ids.append(int(screen_name))
            else:
                obj = await bot.api.utils.resolve_screen_name(screen_name)
                if obj.type == obj.type.USER:
                    user_ids.append(obj.object_id)
                else:
                    user_ids.append(-obj.object_id)
    names = m.text.split("\n")
    for name in names:
        user_id = await db.select([db.User.user_id]).where(
                and_(func.lower(db.Form.name) == func.lower(name), db.Form.is_request.is_(False))
            ).gino.scalar()
        if user_id:
            user_ids.append(user_id)
    if user_ids:
        if not many_users:
            return user_ids[0]
        return user_ids


async def get_mention_from_message(m: Message, many_users=False):
    user_id = await parse_user_id(m, many_users)
    if not many_users:
        if user_id and await db.select([db.User.user_id]).where(db.User.user_id == user_id).gino.scalar():
            return user_id
    else:
        return user_id


async def reload_image(attachment, name: str, delete: bool = False):
    photo_url = get_max_size_url(attachment.photo.sizes)
    async with ClientSession() as session:
        response = await session.get(photo_url)
        async with aiofiles.open(name, mode="wb") as file:
            await file.write(await response.read())
    photo = await photo_message_uploader.upload(name)
    if delete:
        os.remove(name)
    return photo


async def send_mailing(sleep, message_id, mailing_id):
    await asyncio.sleep(sleep)
    user_ids = [x[0] for x in await db.select([db.User.user_id]).gino.all()]
    for i in range(0, len(user_ids), 100):
        await bot.api.messages.send(peer_ids=user_ids[i:i + 100], forward_messages=message_id, random_id=0)
    await db.Mailings.delete.where(db.Mailings.id == mailing_id).gino.status()


async def take_off_payments(form_id: int):
    while True:
        info = await db.select([db.Form.balance, db.Form.freeze]).where(db.Form.id == form_id).gino.first()
        if not info:
            break
        balance, freeze = info
        if not balance or balance < 0 or freeze:
            return
        last_payment = await db.select([db.Form.last_payment]).where(db.Form.id == form_id).gino.scalar()
        today = datetime.datetime.now()
        delta = today - last_payment
        user_id = await db.select([db.Form.user_id]).where(db.Form.id == form_id).gino.scalar()
        if delta.days >= 7:
            cabin_type = await db.select([db.Form.cabin_type]).where(db.Form.id == form_id).gino.scalar()
            if cabin_type:
                price = await db.select([db.Cabins.cost]).where(db.Cabins.id == cabin_type).gino.scalar()
                await db.Form.update.values(balance=db.Form.balance-price,
                                            last_payment=today-datetime.timedelta(seconds=20)).where(
                    db.Form.id == form_id
                ).gino.status()
                group_id = (await bot.api.groups.get_by_id())[0].id
                if (await bot.api.messages.is_messages_from_group_allowed(group_id, user_id=user_id)).is_allowed:
                    await bot.write_msg(user_id, f"Снята арендная плата в размере {price}\n"
                                                 f"Доступно на балансе: {balance-price}")
                await asyncio.sleep(604800)
        else:
            await asyncio.sleep(delta.seconds+10)


async def select_form(state: str, user_id: int, m: Message):
    names = [x[0] for x in await db.select([db.Form.name]).where(db.Form.user_id == user_id).gino.all()]
    user = (await bot.api.users.get(user_id))[0]
    reply = f"Укажите номер анкеты пользователя [id{user_id}|{user.first_name} {user.last_name}]\n\n"
    for i, name in enumerate(names):
        reply = f"{reply}{i + 1}. {name}\n"
    states.set(m.from_id, f"{Admin.SELECT_NUMBER_FORM}@{user_id}@{state}")
    await bot.write_msg(m.peer_id, reply)


async def send_page_users(m: Union[Message, MessageEvent], page: int = 1):
    users = await db.select([db.User.user_id, db.User.admin]).order_by(db.User.admin.desc()).offset((page-1)*15).limit(15).gino.all()
    user_ids = [x[0] for x in users]
    users_info = await bot.api.users.get(user_ids)
    reply = messages.list_users
    for i, user in enumerate(users):
        reply = f"{reply}{(page-1)*15 + i + 1}. {'👑' if user.admin == 2 else '🅰' if user.admin == 1 else ''}" \
                f" [id{user.user_id}|{users_info[i].first_name} {users_info[i].last_name}]\n"
    keyboard = None
    count_users = await db.func.count(db.User.user_id).gino.scalar()
    if count_users % 15 == 0:
        count_pages = count_users // 15
    else:
        count_pages = count_users // 15 + 1
    reply = f"{reply}\n\nСтраница {page}/{count_pages}"
    if page > 1 or page * 15 < count_users:
        keyboard = Keyboard(inline=True)
        if page > 1:
            keyboard.add(Callback("<-", {"users_list": page - 1}), KeyboardButtonColor.PRIMARY)
        if page * 15 < count_users:
            keyboard.add(Callback("->", {"users_list": page + 1}), KeyboardButtonColor.PRIMARY)
    if isinstance(m, Message):
        await bot.edit_msg(m, reply, keyboard=keyboard)
    elif isinstance(m, MessageEvent):
        await bot.change_msg(m, reply, keyboard=keyboard)

async def get_current_form_id(user_id: int) -> int:
    return await db.select([db.Form.id]).select_from(
        db.Form.join(db.User, and_(db.Form.user_id == db.User.user_id, db.Form.number == db.User.activated_form))
    ).where(db.Form.user_id == user_id).gino.scalar()


years = [
    "год", "года", "лет"
]
months = [
    "мес", "месяцев", "месяц", "месяца"
]
weeks = [
    "неделя", "недель", "недели"
]
days = [
    "день", "дня", "дней", "день"
]
hours = [
    "час", "часа", "часов"
]
minutes = [
    "минуты", "мин", "минут", "мин"
]
seconds = [
    "сек", "секунды", "сек", "секунда", "секунд", "секунду"
]



def parse_period(m: Message) -> Optional[int]:
    params = m.text.lower().split(" ")
    last_number = 0
    total = 0
    for index, param in enumerate(params):
        if index % 2 == 0:
            if not param.isdigit():
                return
            last_number = int(param)
        else:
            if param.isdigit():
                return
            if param in years:
                total += last_number * 31536000
            elif param in months:
                total += last_number * 2592000
            elif param in weeks:
                total += last_number * 604800
            elif param in days:
                total += last_number * 86400
            elif param in hours:
                total += last_number * 3600
            elif param in minutes:
                total += last_number * 60
            elif param in seconds:
                total += last_number
            last_number = 0
    return total


def parse_cooldown(cooldown: Optional[Union[int, float]]) -> Optional[str]:
    if not cooldown:
        return
    hours = int(cooldown // 3600)
    minutes = int((cooldown - hours * 3600) // 60)
    seconds = int(cooldown - hours * 3600 - minutes * 60)
    return f"{hours} час(-a, -ов) {minutes} минут {seconds} секунд"


async def quest_over(seconds, form_id, quest_id):
    if not seconds:
        return
    await asyncio.sleep(seconds)
    user_id, current_quest = await db.select([db.Form.user_id, db.Form.active_quest]).where(db.Form.id == form_id).gino.first()
    if current_quest == quest_id:
        name = await db.select([db.Quest.name]).where(db.Quest.id == current_quest).gino.scalar()
        await db.Form.update.values(active_quest=None).where(db.Form.id == form_id).gino.status()
        await bot.write_msg(user_id, f"Время выполнения квеста «{name}» завершилось")


async def send_daylics():
    while True:
        today = datetime.datetime.now()
        expected = datetime.datetime(today.year, today.month, today.day, 18, 0, 0)
        if today > expected:
            expected = expected + datetime.timedelta(days=1)
        await asyncio.sleep((expected-today).total_seconds())
        data = await db.select([db.Form.id, db.Form.user_id]).where(db.Form.deactivated_daylic < datetime.datetime.now()).gino.all()
        for form_id, user_id in data:
            profession_id = await db.select([db.Form.profession]).where(db.Form.id == form_id).gino.scalar()
            daylic = await db.select([db.Daylic.id]).where(db.Daylic.profession_id == profession_id).order_by(func.random()).gino.scalar()
            if daylic:
                await db.Form.update.values(activated_daylic=daylic).where(db.Form.id == form_id).gino.status()
                await bot.write_msg(user_id, "Вам доступно новое ежедневное задание!")
        await asyncio.sleep(5)
