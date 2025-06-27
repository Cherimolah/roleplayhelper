from typing import Optional, Union, List, Dict, Callable
import datetime
import json

from vkbottle import Keyboard, Text, KeyboardButtonColor, Callback
from sqlalchemy import func

from service.db_engine import db
from service import keyboards
from config import DATETIME_FORMAT
from loader import bot
from service.states import Admin, Registration


class Field:

    def __init__(self, name: str, state: str, info_func: Callable = None, serialize_func: Callable = None):
        self.name = name
        self.state = state
        self.info_func = info_func
        self.serialize_func = serialize_func


fields = (Field("Имя", Registration.PERSONAL_NAME), Field("Должность", Registration.PROFESSION),
          Field("Биологический возраст", Registration.AGE), Field("Рост", Registration.HEIGHT),
          Field("Вес", Registration.WEIGHT), Field("Физиологические особенности", Registration.FEATURES),
          Field("Биография", Registration.BIO), Field("Характер", Registration.CHARACTER),
          Field("Мотиы нахождения на Space-station", Registration.MOTIVES),
          Field("Сексуальная ориентация", Registration.ORIENTATION),
          Field("Фетиши", Registration.FETISHES), Field("Табу", Registration.TABOO),
          Field("Визуальный портрет", Registration.PHOTO), Field("Фракция", Registration.FRACTION))

fields_admin = (Field("Имя", Registration.PERSONAL_NAME), Field("Должность", Registration.PROFESSION),
                Field("Биологический возраст", Registration.AGE), Field("Рост", Registration.HEIGHT),
                Field("Вес", Registration.WEIGHT), Field("Физиологические особенности", Registration.FEATURES),
                Field("Биография", Registration.BIO), Field("Характер", Registration.CHARACTER),
                Field("Мотиы нахождения на Space-station", Registration.MOTIVES),
                Field("Сексуальная ориентация", Registration.ORIENTATION),
                Field("Фетиши", Registration.FETISHES), Field("Табу", Registration.TABOO),
                Field("Визуальный портрет", Registration.PHOTO), Field("Каюта", Admin.EDIT_CABIN),
                Field("Класс каюты", Admin.EDIT_CLASS_CABIN), Field("Заморозка", Admin.EDIT_FREEZE),
                Field("Статус", Admin.EDIT_STATUS), Field("Фракция", Admin.EDIT_FRACTION),
                Field('Уровень подчинения', Admin.EDIT_LEVEL_SUBORDINATION),
                Field('Уровень либидо', Admin.EDIT_LEVEL_LIBIDO))


class FormatDataException(Exception):
    pass


fraction_levels = {
    100: "Лидер фракции",
    90: "Верный(-ая) соратник(-ца)",
    75: "Единомышленник(-ца)",
    50: "Надëжный деловой партнëр",
    25: "Достойный(-ая) уважения",
    10: "Имеющий(-ая) потенциал",
    -9: "Простой обыватель",
    -24: "Неприятный собеседник",
    -49: "Отвратительная личность",
    -74: "Идеологический противник",
    -89: "Политический соперник",
    -99: "Враг фракции",
    -100: "Еретик и террорист"
}


def parse_reputation(rep_level: int) -> str:
    for level, name in fraction_levels.items():
        if rep_level >= level:
            return name
    return 'Не опознаный уровень'


def parse_orientation(number: int) -> str:
    if number == 0:
        return "гетеро"
    if number == 1:
        return "би"
    if number == 2:
        return "гомо"


def parse_cooldown(cooldown: Optional[Union[int, float]]) -> Optional[str]:
    if not cooldown:
        return 'не установлено'
    days = int(cooldown // 86400)
    hours = int((cooldown - days * 86400) // 3600)
    minutes = int((cooldown - days * 86400 - hours * 3600) // 60)
    seconds = int(cooldown - days * 86400 - hours * 3600 - minutes * 60)
    return (f"{f'{days} дней' if days > 0 else ''} {f'{hours} часов' if hours > 0 else ''} "
            f"{f'{minutes} минут' if minutes > 0 else ''} {f'{seconds} секунд' if seconds > 0 else ''}")


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


async def info_fraction_daylic():
    reply = "Выбери номер фракции:\n\n"
    fractions = [x[0] for x in await db.select([db.Fraction.name]).order_by(db.Fraction.id.asc()).gino.all()]
    for i, name in enumerate(fractions):
        reply += f"{i + 1}. {name}"
    return reply, keyboards.without_fraction_bonus


async def serialize_fraction_daylic(fraction_id: int) -> str:
    name = await db.select([db.Fraction.name]).where(db.Fraction.id == fraction_id).gino.scalar()
    if not name:
        return "Без бонуса репутации к фракции"
    return name


async def info_quest_users_allowed():
    return ("Пришлите ссылки на пользователей, у которых будет доступен квест",
            Keyboard().add(Text('Без ограничений по игрокам', {"quest_for_all": True}),
                           KeyboardButtonColor.PRIMARY))


async def serialize_quest_users_allowed(form_ids: List[int]) -> str:
    if not form_ids:
        return 'не установлено'
    response = await db.select([db.Form.user_id, db.Form.name]).where(db.Form.id.in_(form_ids)).gino.all()
    user_ids: List[int] = [x[0] for x in response]
    users = await bot.api.users.get(user_ids=user_ids)
    names = [x[1] for x in response]
    reply = "\n\n"
    for i, name in enumerate(names):
        reply += f'{i + 1}. [id{users[i].id}|{users[i].first_name} {users[i].last_name} / {name}]\n'
    return reply


async def info_quest_fraction_allowed():
    fractions = [x[0] for x in await db.select([db.Fraction.name]).order_by(db.Fraction.id.asc()).gino.all()]
    reply = "Пришлите номер фракции у которой будет доступ к квесту\n\n"
    for i, name in enumerate(fractions):
        reply += f"{i + 1}. {name}\n"
    return (reply,
            Keyboard().add(Text('Без ограничения по фракциям', {"quest_for_all_fractions": True}),
                           KeyboardButtonColor.PRIMARY))


async def serialize_quest_fraction_allowed(fraction_id: int) -> str:
    if not fraction_id:
        return "нет ограничения"
    return await db.select([db.Fraction.name]).where(db.Fraction.id == fraction_id).gino.scalar()


async def info_quest_profession_allowed():
    professions = [x[0] for x in await db.select([db.Profession.name]).order_by(db.Profession.id.asc()).gino.all()]
    reply = "Пришлите номер профессии у которой будет доступ к квесту\n\n"
    for i, name in enumerate(professions):
        reply += f"{i + 1}. {name}\n"
    return (reply,
            Keyboard().add(Text('Без ограничения по профессиям', {"quest_for_all_professions": True}),
                           KeyboardButtonColor.PRIMARY))


async def serialize_quest_profession_allowed(profession_id: int) -> str:
    if not profession_id:
        return "нет ограничения"
    return await db.select([db.Profession.name]).where(db.Profession.id == profession_id).gino.scalar()


async def info_target_fraction_reputation():
    fractions = [x[0] for x in await db.select([db.Fraction.name]).order_by(db.Fraction.id.asc()).gino.all()]
    reply = "Пришлите номер фракции, по уровню репутации в которой будет доступ к доп. цели\n\n"
    for i, name in enumerate(fractions):
        reply += f"{i + 1}. {name}\n"
    return (reply,
            Keyboard().add(Text('Без выдачи по уровню репутации', {"target_reputation": False})))


async def serialize_target_fraction(fraction_id: int) -> str:
    if not fraction_id:
        return "не установлено"
    return await db.select([db.Fraction.name]).where(db.Fraction.id == fraction_id).gino.scalar()


async def info_target_fraction():
    fractions = [x[0] for x in await db.select([db.Fraction.name]).order_by(db.Fraction.id.asc()).gino.all()]
    reply = "Пришлите номер фракции у которой будет доступ к доп. цели\n\n"
    for i, name in enumerate(fractions):
        reply += f"{i + 1}. {name}\n"
    return (reply,
            Keyboard().add(Text('Без выдачи по фракции', {"target_fraction": False})))


async def info_target_profession_allowed():
    professions = [x[0] for x in await db.select([db.Profession.name]).order_by(db.Profession.id.asc()).gino.all()]
    reply = "Пришлите номер профессии у которой будет доступ к доп. цели\n\n"
    for i, name in enumerate(professions):
        reply += f"{i + 1}. {name}\n"
    return (reply,
            Keyboard().add(Text('Без выдачи по профессии', {"target_profession": False})))


async def serialize_target_profession_allowed(profession_id: int) -> str:
    if not profession_id:
        return "не установлено"
    return await db.select([db.Profession.name]).where(db.Profession.id == profession_id).gino.scalar()


async def info_target_daughter_params():
    return ('Укажите значения для необходимых параметров дочери.\n{Либидо} {и/или} {Подчинение}\n'
                         'Примеры:\n\n'
                         '10 и 15\n10 или 5\n\n', Keyboard().add(Text('Без выдачи по параметрам', {"target_params": False})))


async def serialize_target_daughter_params(params: List[int]):
    if not params:
        return 'не установлено'
    return f"либидо {params[0]} {'или' if params[1] else 'и'} подчинение {params[2]}"


async def info_target_users_allowed():
    return ("Пришлите ссылки на пользователей, у которых будет доступна доп. цель",
            Keyboard().add(Text('Без ограничений по игрокам', {"target_forms": False})))


async def serialize_target_reputation(reputation: int):
    if reputation is None:
        return "не установлено"
    return str(reputation)


async def info_quest_additional_targets():
    targets = [x[0] for x in
               await db.select([db.AdditionalTarget.name]).order_by(db.AdditionalTarget.id.asc()).gino.all()]
    reply = 'Укажите номера дополнительных целей через запятую:\n\n'
    if not targets:
        reply += 'Дополнительных целей на данный момент не создано'
    else:
        for i, target in enumerate(targets):
            reply += f"{i + 1}. {target}\n"
    return reply, Keyboard().add(Text('Без дополнительных целей', {"quest_without_targets": True}))


async def serialize_quest_additional_targets(target_ids: List[int]) -> str:
    if not target_ids:
        return 'Без дополнительных целей'
    else:
        names = [x[0] for x in await db.select([db.AdditionalTarget.name]).where(db.AdditionalTarget.id.in_(target_ids)).gino.all()]
        reply = "\n\n"
        for i, name in enumerate(names):
            reply += f"{i+1}. {name}\n"
        return reply


async def info_target_reward():
    reply = ('Возможные варианты награды:\n'
             'I. Бонус к репутации\n'
             'II. Награда валютой\n'
             'III. Изменение параметров\n\n'
             'Список фракций:\n')
    fractions = [x[0] for x in await db.select([db.Fraction.name]).order_by(db.Fraction.id.asc()).gino.all()]
    for i, fraction in enumerate(fractions):
        reply += f"{i + 1}. {fraction}\n"
    reply += ("\nЧтобы указать награду в виде бонуса к репутации необходимо написать команду «РЕП {номер фракции} "
              "{бонус}». Например:\nРЕП 1 10\n\n"
              "Чтобы указать награду в виде валюты необходимо написать команду «ВАЛ {бонус}». Например:\n"
              "ВАЛ 100\n\n"
              "Чтобы указать награду в виде изменения параметра необходимо написать команду «ПАР {либидо} {подчинение}». "
              "Например:\n ПАР -10 30\n\n❗️ Можно указать несколько вариантов через новую строку")
    return reply, None


async def info_quest_penalty():
    reply = ('Возможные варианты штрафа:\n'
             'I. Бонус к репутации\n'
             'II. Награда валютой\n'
             'III. Изменение параметров\n\n'
             'Список фракций:\n')
    fractions = [x[0] for x in await db.select([db.Fraction.name]).order_by(db.Fraction.id.asc()).gino.all()]
    for i, fraction in enumerate(fractions):
        reply += f"{i + 1}. {fraction}\n"
    reply += ("\nЧтобы указать штраф в виде уменьшения репутации необходимо написать команду «РЕП {номер фракции} "
              "{бонус}». Например:\nРЕП 1 -10\n\n"
              "Чтобы указать штраф в виде валюты необходимо написать команду «ВАЛ {бонус}». Например:\n"
              "ВАЛ -100\n\n"
              "Чтобы указать штраф в виде изменения параметра необходимо написать команду «ПАР {либидо} {подчинение}». "
              "Например:\nПАР -10 30\n\n❗️ Можно указать несколько вариантов через новую строку")
    keyboard = Keyboard().add(Text('Без штрафа', {"without_penalty": True}), KeyboardButtonColor.SECONDARY)
    return reply, keyboard


async def parse_reward(text: str) -> List[Dict]:
    data = []
    for line in text.split("\n"):
        line = line.lower()
        if line.startswith('реп'):
            try:
                fraction_id, reputation_bonus = map(int, line.split()[1:])
            except:
                raise FormatDataException('Неверно указаны параметры')
            fraction_id = await db.select([db.Fraction.id]).order_by(db.Fraction.id.asc()).offset(
                fraction_id - 1).limit(1).gino.scalar()
            if not fraction_id:
                raise FormatDataException('Неправильный номер фракции')
            data.append({
                'type': 'fraction_bonus',
                'fraction_id': fraction_id,
                'reputation_bonus': reputation_bonus
            })
        elif line.startswith('вал'):
            try:
                _, bonus = line.split()
                bonus = int(bonus)
            except:
                raise FormatDataException('Неверно указаны параметры')
            data.append({
                'type': 'value_bonus',
                'bonus': bonus
            })
        elif line.startswith('пар'):
            try:
                _, libido, subordination = line.split()
                libido = int(libido)
                subordination = int(subordination)
            except:
                raise FormatDataException('Неверно указаны параметры')
            data.append({
                'type': 'daughter_params',
                'libido': libido,
                'subordination': subordination
            })
        else:
            raise FormatDataException('Недоступный вариант награды')
    return data


async def serialize_target_reward(data):
    if not data:
        return 'не задано'
    reply = ""
    if isinstance(data, str):
        data = json.loads(data)
    for reward in data:
        if reward['type'] == 'fraction_bonus':
            fraction = await db.select([db.Fraction.name]).where(db.Fraction.id == reward['fraction_id']).gino.scalar()
            bonus = f"{'+' if reward['reputation_bonus'] >= 0 else ''}{reward['reputation_bonus']}"
            reply += f'Бонус к репутации {bonus} во фракции «{fraction}»'
        elif reward['type'] == 'value_bonus':
            reply += str(reward['bonus']) + ' валюты'
        elif reward['type'] == 'daughter_params':
            reply += f'Изменение либидо на {"+" if reward["libido"] > 0 else ""}{reward["libido"]}, изменение подчинение на {"+" if reward["subordination"] > 0 else ""}{reward["subordination"]}'
        reply += ", "
    return reply[:-2]


async def info_target_for_all_users():
    return "Доп. цель будет доступна для всех?", Keyboard().add(Text('Доступна для всех', {"target_for_all": True})).row().add(Text('Указать фильтры', {"target_for_all": False}))


async def serialize_target_for_all_users(for_all_users: bool):
    if not for_all_users:
        return "нет"
    return 'да'


async def info_quest_strict_mode():
    return ('Укажите режим квеста\nВ строгом режиме отчет по основному квесту можно '
                                  'будет выполнить толко после принятия всех отчётов по доп. целям',
            Keyboard().add(Text('Строгий', {"quest_strict": True})).add(Text('Не строгий', {"quest_strict": True})))


async def serialize_strict_mode(strict: bool):
    return 'да' if strict else 'нет'


async def info_daughter_quest_form_id():
    data = await db.select([db.Form.user_id, db.Form.name]).where(db.Form.status == 2).order_by(
        db.Form.id.asc()).limit(15).gino.all()
    user_ids = [x[0] for x in data]
    users = await bot.api.users.get(user_ids=user_ids)
    user_names = [f'{x.first_name} {x.last_name}' for x in users]
    reply = ('Укажите дочь для которой будет установлен квест\n'
             'Можно прислать ссылку, пересланное сообщение или номер по порядку отсюда\n\n'
             'Список дочерей:\n\n')
    for i in range(len(data)):
        reply += f'{i + 1}. [id{users[i].id}|{data[i][1]} / {user_names[i]}]\n'
    count = await db.select([func.count(db.Form.id)]).where(db.Form.status == 2).gino.scalar()
    keyboard = Keyboard(inline=True)
    if count > 15:
        keyboard.add(Callback("->", {"daughters_page": 2}), KeyboardButtonColor.PRIMARY).row()
    keyboard.add(Text('Не выдавать дочери', {"daughter_quest_for_none": True}), KeyboardButtonColor.SECONDARY)
    return reply, keyboard


async def serialize_daughter_quest_form_id(form_id: int):
    if not form_id:
        return 'Ни для кого'
    name, user_id = await db.select([db.Form.name, db.Form.user_id]).where(db.Form.id == form_id).gino.first()
    user = (await bot.api.users.get(user_ids=user_id))[0]
    return f'[id{user_id}|{name} / {user.first_name} {user.last_name}]'


async def info_daughter_target_ids():
    data = await db.select([db.DaughterTarget.name, db.DaughterTarget.params]).order_by(
        db.DaughterTarget.id.asc()).limit(15).gino.all()
    if not data:
        reply = 'На данный момент не создано доп. целей'
        return reply, None
    reply = '{номер}. {название} / {либидо} {правило} {подчинение}\n\n'
    count = await db.select([func.count(db.DaughterTarget.id)]).gino.scalar()
    for i in range(len(data)):
        name, params = data[i]
        reply += f'{i + 1}. {name} / {params[0]} {"и" if params[1] == 0 else "или"} {params[2]}\n'
    keyboard = Keyboard(inline=True)
    if count > 15:
        keyboard.add(Callback("->", {"daughter_targets": 2}), KeyboardButtonColor.PRIMARY)
        keyboard.row()
    keyboard.add(Text('Без доп. целей', {"without_targets": True}), KeyboardButtonColor.SECONDARY)
    return reply, keyboard


async def serialize_daughter_target_ids(target_ids: list[int]):
    if not target_ids:
        return 'Без доп. целей'
    reply = "\n"
    for i, target_id in enumerate(target_ids):
        name, params = await db.select([db.DaughterTarget.name, db.DaughterTarget.params]).where(db.DaughterTarget.id == target_id).gino.first()
        reply += f'{i + 1}. {name} / {params[0]} {"и" if params[1] == 0 else "или"} {params[2]}\n'
    return reply


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
            Field("Профессия", Admin.DAYLIC_PROFESSION, professions, profession_serialize),
            Field("Фракция", Admin.DAYLIC_FRACTION, info_fraction_daylic, serialize_fraction_daylic),
            Field("Бонус к репутации", Admin.DAYLIC_REPUTATTION)
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
            Field("Начало", Admin.QUEST_START_DATE, info_date, parse_datetime_async),
            Field("Конец", Admin.QUEST_END_DATE, info_end_quest, parse_datetime_async),
            Field("Даётся на выполнение", Admin.QUEST_EXECUTION_TIME, info_cooldown_quest, parse_cooldown_async),
            Field("Фракция", Admin.QUEST_FRACTION_ALLOWED, info_fraction_daylic, serialize_fraction_daylic),
            Field("Для профессии", Admin.QUEST_PROFESSION_ALLOWED, info_quest_profession_allowed, serialize_quest_profession_allowed),
            Field("Для игроков", Admin.QUEST_USERS_ALLOWED, info_quest_users_allowed, serialize_quest_users_allowed),
            Field('Доп. цели', Admin.QUEST_ADDITIONAL_TARGETS, info_quest_additional_targets, serialize_quest_additional_targets),
            Field("Награда", Admin.QUEST_REWARD, info_target_reward, serialize_target_reward),
            Field('Штраф', Admin.QUEST_PENALTY, info_quest_penalty, serialize_target_reward)
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
            Field("Фото", Admin.PHOTO_FRACTION),
            Field('Мультпиликатор дочери', Admin.FRACTION_MULTIPLIER)
        ],
        "name": "Фракция"
    },
    'AdditionalTarget': {
        "fields": [
            Field('Название', Admin.TARGET_NAME),
            Field('Описание', Admin.TARGET_DESCRIPTION),
            Field('Значение репутации во фракции', Admin.TARGET_FRACTION_REPUTATION, info_target_fraction_reputation, serialize_target_fraction),
            Field('Необходимый уровень репутации', Admin.TARGET_REPUTATION, serialize_func=serialize_target_reputation),
            Field('Для фракции', Admin.TARGET_FRACTION, info_target_fraction, serialize_target_fraction),
            Field('Для профессии', Admin.TARGET_PROFESSION, info_target_profession_allowed, serialize_target_profession_allowed),
            Field('С параметрами дочери', Admin.TARGET_DAUGHTER_PARAMS, info_target_daughter_params, serialize_target_daughter_params),
            Field('Для пользователей', Admin.TARGET_FORMS, info_target_users_allowed, serialize_quest_users_allowed),
            Field('Награда', Admin.TARGET_REWARD, info_target_reward, serialize_target_reward),
            Field('Для всех пользователей', Admin.TARGET_FOR_ALL_USERS, info_target_for_all_users, serialize_target_for_all_users)
        ],
        "name": "Доп. цель"
    },
    'DaughterQuest': {
        'name': 'Квесты для дочерей',
        'fields': [
            Field('Название', Admin.DAUGHTER_QUEST_NAME),
            Field('Описание', Admin.DAUGHTER_QUEST_DESCRIPTION),
            Field('Для кого', Admin.DAUGHTER_QUEST_FORM_ID, info_daughter_quest_form_id, serialize_daughter_quest_form_id),
            Field('Награда', Admin.DAUGHTER_QUEST_REWARD, info_target_reward, serialize_target_reward),
            Field('Штраф', Admin.DAUGHTER_QUEST_PENALTY, info_quest_penalty, serialize_target_reward),
            Field('Доп. цели', Admin.DAUGHTER_QUEST_TARGET_IDS, info_daughter_target_ids, serialize_daughter_target_ids)
        ]
    },
    'DaughterTarget': {
        'name': 'Доп. цели для дочерей',
        'fields': [
            Field('Название', Admin.DAUGHTER_TARGET_NAME),
            Field('Описание', Admin.DAUGHTER_TARGET_DESCRIPTION),
            Field('Награда', Admin.DAUGHTER_TARGET_REWARD, info_target_reward, serialize_target_reward),
            Field('Параметры дочери', Admin.DAUGHTER_TARGET_PARAMS, info_target_daughter_params, serialize_target_daughter_params)
        ]
    }
}