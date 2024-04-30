import asyncio
import datetime
import os
from typing import List, Tuple, Optional, Union, Dict
import re

from sqlalchemy import and_, func
from vkbottle_types.objects import PhotosPhotoSizes
from vkbottle.bot import Message, MessageEvent
import aiofiles
from vkbottle import Keyboard, Callback, KeyboardButtonColor, Text

from service.db_engine import db
from loader import bot, photo_message_uploader, fields, Field
import messages
from bot_extended import AioHTTPClientExtended
from service.middleware import states
import service.states
from service.states import Admin
import service.keyboards as keyboards
from config import DATETIME_FORMAT

mention_regex = re.compile(r"\[(?P<type>id|club|public)(?P<id>\d*)\|(?P<text>.+)\]")
link_regex = re.compile(r"https:/(?P<type>/|/m.)vk.com/(?P<screen_name>\w*)")

client = AioHTTPClientExtended()


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


async def loads_form(user_id: int = None, is_request: bool = None, form_id: int = None) -> Tuple[str, Optional[str]]:
    if form_id:
        form = await db.select([*db.Form]).where(db.Form.id == form_id).gino.first()
    elif is_request:
        form = await db.select([*db.Form]).where(and_(db.Form.is_request.is_(True), db.Form.user_id == user_id)).gino.first()
    else:
        form = await db.select([*db.Form]).where(db.Form.user_id == user_id).gino.first()
    user = (await bot.api.users.get(user_id))[0]
    if form.profession:
        profession = await db.select([db.Profession.name]).where(db.Profession.id == form.profession).gino.scalar()
    else:
        profession = None
    if form.fraction_id:
        fraction = await db.select([db.Fraction.name]).where(db.Fraction.id == form.fraction_id).gino.scalar()
    else:
        fraction = None
    reply = f"Анкета пользователя [id{user_id}|{user.first_name} {user.last_name}]:\n\n" \
            f"Имя персонажа: {form.name}\n" \
            f"Должность: {profession or 'не установлена'}\n" \
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
            f"Тип каюты: {await db.select([db.Cabins.name]).where(db.Cabins.id == form.cabin_type).gino.scalar() or 'не указан'}\n" \
            f"Баланс: {form.balance}\n" \
            f"Статус: {await db.select([db.Status.name]).where(db.Status.id == form.status).gino.scalar()}\n" \
            f"Фракция: {fraction or 'не установлена'}"
    return reply, form.photo


async def parse_ids(m: Message) -> List[int]:
    if m.reply_message:
        return [m.reply_message.from_id]
    if m.fwd_messages:
        return [x.from_id for x in m.fwd_messages]
    user_ids = []
    text = m.text.lower()
    screen_names: List[str] = [x[1] for x in re.findall(link_regex, text)]
    screen_names.extend([x[1] for x in re.findall(mention_regex, text)])
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
    return user_ids


async def get_mention_from_message(m: Message, many_users=False) -> Optional[Union[int, List[int]]]:
    user_ids = [x for x in await parse_ids(m) if x > 0]
    names = m.text.split("\n")
    for name in names:
        user_id = await db.select([db.Form.user_id]).where(
            and_(func.lower(db.Form.name) == name.lower(), db.Form.is_request.is_(False))
        ).gino.scalar()
        if user_id:
            user_ids.append(user_id)
    if many_users:
        return user_ids
    if len(user_ids) > 0:
        return user_ids[0]
    return None


async def reload_image(attachment, name: str, delete: bool = False):
    photo_url = get_max_size_url(attachment.photo.sizes)
    response = await client.request_content(photo_url)
    if not os.path.exists("/".join(name.split("/")[:-1])):
        os.mkdir("/".join(name.split("/")[:-1]))
    async with aiofiles.open(name, mode="wb") as file:
        await file.write(response)
    photo = await photo_message_uploader.upload(name)
    if delete:
        os.remove(name)
    return photo


async def send_mailing(sleep, message_id, mailing_id):
    await asyncio.sleep(sleep)
    user_ids = [x[0] for x in await db.select([db.User.user_id]).gino.all()]
    for i in range(0, len(user_ids), 100):
        await bot.api.messages.send(peer_ids=user_ids[i:i + 100], forward_messages=message_id, random_id=0, is_notification=True)
    await db.Mailings.delete.where(db.Mailings.id == mailing_id).gino.status()


async def take_off_payments(form_id: int):
    while True:
        info = await db.select([db.Form.balance, db.Form.freeze]).where(db.Form.id == form_id).gino.first()
        if not info:  # Анкета удалена
            return
        balance, freeze = info
        if not balance or balance < 0 or freeze:
            await asyncio.sleep(86400)  # Ждём сутки, вдруг появятся деньги или анкета разморозиться
            continue
        last_payment = await db.select([db.Form.last_payment]).where(db.Form.id == form_id).gino.scalar()
        today = datetime.datetime.now()
        delta = today - last_payment
        user_id = await db.select([db.Form.user_id]).where(db.Form.id == form_id).gino.scalar()
        if delta.days >= 7:
            cabin_type = await db.select([db.Form.cabin_type]).where(db.Form.id == form_id).gino.scalar()
            if cabin_type:
                price = await db.select([db.Cabins.cost]).where(db.Cabins.id == cabin_type).gino.scalar()
                func_price = sum([soft_divide(x[0], 10) for x in await db.select([db.Decor.price]).select_from(
                    db.UserDecor.join(db.Decor, db.UserDecor.decor_id == db.Decor.id)
                ).where(and_(db.UserDecor.user_id == user_id, db.Decor.is_func.is_(True))).gino.all()])
                price += func_price
                await db.Form.update.values(balance=db.Form.balance-price,
                                            last_payment=today-datetime.timedelta(seconds=20)).where(
                    db.Form.id == form_id
                ).gino.status()
                group_id = (await bot.api.groups.get_by_id())[0].id
                if (await bot.api.messages.is_messages_from_group_allowed(group_id, user_id=user_id)).is_allowed:
                    await bot.api.messages.send(user_id, f"Снята арендная плата в размере {price}\n"
                                                 f"Доступно на балансе: {balance-price}", is_notification=True)
                await asyncio.sleep(604800)  # Следующее списание через неделю
            else:
                await asyncio.sleep(86400)  # Каюта может быть не присвоена подождём сутки, вдруг появится
                continue
        else:
            # Ждём пока не пройдёт неделя до следующего списания
            next_payment = last_payment + datetime.timedelta(days=7)
            await asyncio.sleep(int((next_payment - today).total_seconds()) + 1)


async def send_page_users(m: Union[Message, MessageEvent], page: int = 1):
    users = await db.select([db.User.user_id, db.User.admin]).order_by(db.User.admin.desc()).order_by(db.User.user_id.asc()).offset((page-1)*15).limit(15).gino.all()
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
        await m.answer(reply, keyboard=keyboard)
    elif isinstance(m, MessageEvent):
        await m.edit_message(reply, keyboard=keyboard)


async def get_current_form_id(user_id: int) -> int:
    return await db.select([db.Form.id]).where(db.Form.user_id == user_id).gino.scalar()


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
    "минуты", "мин", "минут", "мин", "минута"
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
        await bot.api.messages.send(user_id, f"Время выполнения квеста «{name}» завершилось", is_notification=True)


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
                await bot.api.messages.send(user_id, "Вам доступно новое ежедневное задание!", is_notification=True)
        await asyncio.sleep(5)


async def show_fields_edit(user_id: int, new=True):
    if new:
        form = dict(await db.select([*db.Form]).where(db.Form.user_id == user_id).gino.first())
        params = {k: v for k, v in form.items() if k not in ("id", "is_request")}
        params['is_request'] = True
        await db.Form.create(**params)
        await db.User.update.values(editing_form=True).where(db.User.user_id == user_id).gino.status()
    await db.User.update.values(state=service.states.Menu.SELECT_FIELD_EDIT_NUMBER).where(db.User.user_id == user_id).gino.status()
    states.set(user_id, service.states.Menu.SELECT_FIELD_EDIT_NUMBER)
    reply = ("Выберите поле для редактирования. "
             "Когда закончите нажмите кнопку «Подтвердить изменения»\n\n")
    for i, field in enumerate(fields):
        reply += f"{i+1}. {field.name}\n"
    await bot.api.messages.send(message=reply, keyboard=keyboards.confirm_edit_form, peer_id=user_id)


async def page_content(table_name, page: int) -> Tuple[str, Optional[Keyboard]]:
    table = getattr(db, table_name)
    names = [x[0] for x in await db.select([table.name]).order_by(table.id.asc()).offset((page - 1) * 15).limit(15).gino.all()]
    count = await db.select([func.count(table.id)]).gino.scalar()
    if count % 15 == 0:
        pages = count // 15
    else:
        pages = count // 15 + 1
    keyboard = Keyboard(inline=True)
    if not names:
        return "На данный момент ничего не создано", keyboard
    reply = f"Отправьте число, для редактирования:\n\n"
    for i, name in enumerate(names):
        reply += f"{(page - 1) * 15 + i + 1}. {name}\n"
    if page > 1:
        keyboard.add(Callback("<-", {"content_page": page - 1, "content": table_name}), KeyboardButtonColor.SECONDARY)
    if page * 15 < count:
        keyboard.add(Callback("->", {"content_page": page + 1, "content": table_name}), KeyboardButtonColor.SECONDARY)
    if pages > 1:
        reply += f"\nСтраница {page}/{pages}\n\n"
    return reply, keyboard


async def send_content_page(m: Union[Message, MessageEvent], table_name: str, page: int):
    reply, keyboard = await page_content(table_name, page)
    if isinstance(m, Message):
        await m.answer(messages.select_action, keyboard=keyboards.gen_type_change_content(table_name))
        await m.answer(reply, keyboard=keyboard)
    else:
        await m.send_message(messages.select_action, keyboard=keyboards.gen_type_change_content(table_name))
        await m.send_message(reply, keyboard=keyboard)


def allow_edit_content(content_type: str, end: bool = False, text: str = None, state: str = None, keyboard = None):
    def decorator(function):
        async def wrapper(m: Message, value=None, form=None, *args, **kwargs):
            kwargs["m"] = m
            if value:
                kwargs["value"] = value
            if form:
                kwargs["form"] = form
            data = await function(**kwargs)
            item_id = int(states.get(m.from_id).split("*")[1])
            editing_content = await db.select([db.User.editing_content]).where(db.User.user_id == m.from_id).gino.scalar()
            if editing_content:
                await m.answer("Новое значение успешно установлено")
                await send_edit_item(m.from_id, item_id, content_type)
            else:
                states.set(m.from_id, f"{state}*{item_id}")
                if text:
                    await m.answer(text, keyboard=keyboard)
                if end:
                    await send_content_page(m, content_type, 1)
                    states.set(m.from_id, service.states.Admin.SELECT_ACTION + "_" + content_type)
            return data
        return wrapper
    return decorator


async def send_edit_item(user_id: int, item_id: int, item_type: str):
    await db.User.update.values(editing_content=True).where(db.User.user_id == user_id).gino.status()
    item = await db.select([*getattr(db, item_type)]).where(getattr(db, item_type).id == item_id).gino.first()
    reply = "Выберите поле для редактирования\n\n"
    attachment = None
    for i, data in enumerate(fields_content[item_type]['fields']):
        if data.name == "Фото":
            attachment = item[i+1]
        if not data.serialize_func:
            reply += f"{i+1}. {data.name}: {item[i + 1]}\n"
        else:
            reply += f"{i+1}. {data.name}: {await data.serialize_func(item[i + 1])}\n"
    keyboard = keyboards.get_edit_content(item_type)
    await db.User.update.values(state=f"{service.states.Admin.EDIT_CONTENT}_{item_type}*{item.id}").where(db.User.user_id == user_id).gino.status()
    states.set(user_id, f"{service.states.Admin.EDIT_CONTENT}_{item_type}*{item.id}")
    await bot.api.messages.send(message=reply, keyboard=keyboard.get_json(), peer_id=user_id, attachment=attachment)


async def profession_serialize(profession_id: int) -> str:
    return await db.select([db.Profession.name]).where(db.Profession.id == profession_id).gino.scalar()


async def professions():
    names = [x[0] for x in await db.select([db.Profession.name]).gino.all()]
    reply = "Список профессий:\n\n"
    for i, name in enumerate(names):
        reply += f"{i + 1}. {name}\n"
    return reply, None


async def type_professions():
    reply = "Варианты видимости профессии"
    keyboard = keyboards.select_type_profession
    return reply, keyboard


async def serialize_type_profession(special: bool) -> str:
    return "Специальная" if special else "Обычная"


async def parse_cooldown_async(cooldown):
    if not cooldown:
        return "Не указано"
    return parse_cooldown(cooldown)


async def info_cooldown():
    return "Укажите Кулдаун в формате \"1 час 2 минуты 3 секунды\"", None


async def info_cooldown_quest():
    return "Укажите Кулдаун в формате \"1 час 2 минуты 3 секунды\"", Keyboard().add(
        Text("Бессрочно", {"quest_forever": True})
    )


async def info_date():
    return "Укажите дату и время в формате ДД.ММ.ГГГГ чч:мм:сс", None


async def info_end_quest():
    return "Укажите дату и время в формате ДД.ММ.ГГГГ чч:мм:сс", Keyboard().add(
        Text("Бессрочно", {"quest_always": True})
    )


async def serialize_shop(service: bool):
    return "Услуга" if service else "Товар"


async def parse_datetime_async(datetime_: datetime.datetime) -> str:
    if not datetime_:
        return "Не указано"
    return datetime_.strftime(DATETIME_FORMAT)


async def info_photo():
    return "Пришлите фото", None


async def info_service_type():
    return "Выберите вариант размещения в магазине", Keyboard().add(
        Text("Услуга", {"service": True}), KeyboardButtonColor.PRIMARY
    ).row().add(
        Text("Товар", {"service": False}), KeyboardButtonColor.PRIMARY
    )


def soft_divide(num: int, den: int) -> int:
    if num % den == 0:
        return int(num // den)
    return int(num // den) + 1


async def info_is_func_decor():
    return "Выберите тип товара", keyboards.decor_vars


async def serialize_is_func_decor(is_func: bool):
    return "да" if is_func else "нет (декор)"


async def info_leader_fraction():
    return "Пришли ссылку или перешли сообщение нового лидера фракции", None


async def serialize_leader_fraction(leader_id: int) -> str:
    if not leader_id:
        return "Без лидера"
    name = await db.select([db.Form.name]).where(db.Form.user_id == leader_id).gino.scalar()
    user = (await bot.api.users.get(user_ids=leader_id))[0]
    return f"[id{leader_id}|{name} / {user.first_name} {user.last_name}]"


fields_content: Dict[str, Dict[str, List[Field]]] = {
    "Cabins": {
        "fields": [
            Field("Название", Admin.NAME_CABIN),
            Field("Стоимость", Admin.PRICE_CABIN),
            Field("Слотов под декор", Admin.DECOR_SLOTS_CABINS),
            Field("Слотов под функциональный товар", Admin.FUNC_PRODUCTS_CABINS)
        ],
        "name": "Тип каюты"
    },
    "Daylic": {
        "fields": [
            Field("Название", Admin.DAYLIC_NAME),
            Field("Описание", Admin.DAYLIC_DESCRIPTION),
            Field("Награда", Admin.DAYLIC_REWARD),
            Field("Кулдаун", Admin.DAYLIC_COOLDOWN, info_cooldown, parse_cooldown_async),
            Field("Профессия", Admin.DAYLIC_PROFESSION, professions, profession_serialize)
        ],
        "name": "Дейлик"
    },
    "Profession": {
        "fields": [
            Field("Название", Admin.NAME_PROFESSION),
            Field("Тип профессии", Admin.HIDDEN_PROFESSION, type_professions, serialize_type_profession),
            Field("Зарплата", Admin.SALARY_PROFESSION),
        ],
        "name": "Профессия"
    },
    "Quest": {
        "fields": [
            Field("Название", Admin.QUEST_NAME),
            Field("Описание", Admin.QUEST_DESCRIPTION),
            Field("Награда", Admin.QUEST_REWARD),
            Field("Начало", Admin.QUEST_START_DATE, info_date, parse_datetime_async),
            Field("Конец", Admin.QUEST_END_DATE, info_end_quest, parse_datetime_async),
            Field("Даётся на выполнение", Admin.QUEST_EXECUTION_TIME, info_cooldown_quest, parse_cooldown_async)
        ],
        "name": "Квест"
    },
    "Shop": {
        "fields": [
            Field("Название", Admin.NAME_PRODUCT),
            Field("Фото", Admin.ART_PRODUCT, info_photo),
            Field("Описание", Admin.DESCRIPTION_PRODUCT),
            Field("Цена", Admin.PRICE_PRODUCT),
            Field("Тип", Admin.SERVICE_PRODUCT, info_service_type, serialize_shop)
        ],
        "name": "Товар/Услуга"
    },
    "Status": {
        "fields": [
            Field("Название", Admin.ENTER_NAME_STATUS)
        ],
        "name": "Статус"
    },
    "Decor": {
        "fields": [
            Field("Название", Admin.NAME_DECOR),
            Field("Цена", Admin.PRICE_DECOR),
            Field("Функциональный", Admin.IS_FUNC_DECOR, info_is_func_decor, serialize_is_func_decor),
            Field("Фото", Admin.PHOTO_DECOR),
            Field("Описание", Admin.DESCRIPTION_DECOR)
        ],
        "name": "Декор"
    },
    "Fraction": {
        "fields": [
            Field("Название", Admin.NAME_FRACTION),
            Field("Описание", Admin.DESCRIPTION_FRACTION),
            Field("Лидер", Admin.LEADER_FRACTION, info_leader_fraction, serialize_leader_fraction),
            Field("Фото", Admin.PHOTO_FRACTION)
        ],
        "name": "Фракция"
    }
}


async def page_fractions(page: int) -> Tuple[str, Keyboard, str]:
    fraction = await db.select([*db.Fraction]).order_by(db.Fraction.id.desc()).offset(page - 1).limit(1).gino.first()
    if fraction.leader_id:
        leader_nick = await db.select([db.Form.name]).where(db.Form.user_id == fraction.leader_id).gino.scalar()
        leader = (await bot.api.users.get(user_id=fraction.leader_id))[0]
        leader_mention = f"[id{fraction.leader_id}|{leader_nick} / {leader.first_name} {leader.last_name}]"
    else:
        leader_mention = "Без лидера"
    reply = (f"Название: {fraction.name}\n"
             f"Описание: {fraction.description}\n"
             f"Текущий лидер: {leader_mention}")
    count = await db.select([func.count(db.Fraction.id)]).gino.scalar()
    kb = Keyboard(inline=True)
    if page > 1:
        kb.add(
            Callback("<-", {"fraction_page": page - 1}), KeyboardButtonColor.SECONDARY
        )
    if count > page:
        kb.add(
            Callback("->", {"fraction_page": page + 1}), KeyboardButtonColor.SECONDARY
        )
    if len(kb.buttons) > 0 and len(kb.buttons[0]) > 0:
        kb.row()
    kb.add(
        Callback("Вступить", {"fraction_select": fraction.id}), KeyboardButtonColor.POSITIVE
    )
    return reply, kb, fraction.photo
