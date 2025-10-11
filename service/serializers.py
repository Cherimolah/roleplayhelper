"""
В этом модуле хранятся функции сериализации контента из базы данных
Использование см. в README

Можно посмотреть внизу на словарь fields_content , чтобы понять какая функция для какого поля используется
"""
from typing import Optional, Union, List, Dict, Callable
import datetime
import json
from collections import Counter

from vkbottle import Keyboard, Text, KeyboardButtonColor, Callback
from sqlalchemy import func, and_

from service.db_engine import db
from service import keyboards
from config import DATETIME_FORMAT
from loader import bot
from service.states import Admin, Registration


class Field:
    """
    Класс Field это основной класс, который используется для столбцов базы данных

    name: название на русском, которое будет выводится при выводе объекта
    state: необходимое состояние, которое установится при редактировании этого поля
    info_func: асинхронная функция, без аргументов, которая будет возвращать tuple[str, Keyboard()] - текст описания
    того, что должно быть в значении этого поля и клавиатура
    Например, нужно выбрать необходимую фракцию. Функция вытягивает из базы все фракции и вовзвращает в тексте строкой,
    также возвращает клавиатуру с кнопкой "Без фракции", если это поле необязательно
    serialize_func: асинхронная функция, принимающая один аргумент - значение поля из базы данных, возвращает строку -
    сериализованное поле. Например, предмет имеет тип "Одноразовый", но значение в базе "1" (айди типа одноразовый).
    Функция будет принимать айди типа, находить название типа в баз данных и возвращать читаемое название
    """

    def __init__(self, name: str, state: str, info_func: Callable = None, serialize_func: Callable = None):
        self.name = name
        self.state = state
        self.info_func = info_func
        self.serialize_func = serialize_func


class RelatedTable(Field):
    """
    Класс используемый для сериализации поля, как и Field

    Отличие в том, что функция serialize_func при сериализации объекта будет принимать вместо значения поля - айди объекта
    Используется, когда нужно сериализовать вместе с объектом дополнительно некоторые связанные объекты.
    Например при сериализации расы, будет полезно вывести пользователю все бонусы, которые она даёт.
    """
    pass


fields = (Field("Имя", Registration.PERSONAL_NAME), Field("Должность", Registration.PROFESSION),
          Field("Биологический возраст", Registration.AGE), Field("Рост", Registration.HEIGHT),
          Field("Вес", Registration.WEIGHT), Field("Физиологические особенности", Registration.FEATURES),
          Field("Биография", Registration.BIO), Field("Характер", Registration.CHARACTER),
          Field("Мотивы нахождения на Space-station", Registration.MOTIVES),
          Field("Сексуальная ориентация", Registration.ORIENTATION),
          Field("Фетиши", Registration.FETISHES), Field("Табу", Registration.TABOO),
          Field("Визуальный портрет", Registration.PHOTO), Field("Фракция", Registration.FRACTION))

fields_admin = (Field("Имя", Registration.PERSONAL_NAME), Field("Должность", Registration.PROFESSION),
                Field("Биологический возраст", Registration.AGE), Field("Рост", Registration.HEIGHT),
                Field("Вес", Registration.WEIGHT), Field("Физиологические особенности", Registration.FEATURES),
                Field("Биография", Registration.BIO), Field("Характер", Registration.CHARACTER),
                Field("Мотивы нахождения на Space-station", Registration.MOTIVES),
                Field("Сексуальная ориентация", Registration.ORIENTATION),
                Field("Фетиши", Registration.FETISHES), Field("Табу", Registration.TABOO),
                Field("Визуальный портрет", Registration.PHOTO), Field("Каюта", Admin.EDIT_CABIN),
                Field("Класс каюты", Admin.EDIT_CLASS_CABIN), Field("Заморозка", Admin.EDIT_FREEZE),
                Field("Статус", Admin.EDIT_STATUS), Field("Фракция", Admin.EDIT_FRACTION),
                Field('Уровень подчинения', Admin.EDIT_LEVEL_SUBORDINATION),
                Field('Уровень либидо', Admin.EDIT_LEVEL_LIBIDO))


class FormatDataException(Exception):
    """
    Исключение связанное с неправильным вводом данных. Это исключение обрабатывается в utils.allow_edit_content()
    Когда пользователь ввел неверные данные необходимо вызвать исключение, тогда отправится сообщение о недопустимом
    формате данных
    """
    pass


# Уровни репутации во фракции
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

sex_types = {
    1: 'Мужской',
    2: 'Женский',
    3: 'Другое'
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
    """
    Форматирует количество секунд в текст
    """
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
             'III. Изменение параметров\n'
             'IV. Предметы карты экспедитора\n'
             'V. Изменение характеристик\n\n'
             'Список фракций:\n')
    fractions = [x[0] for x in await db.select([db.Fraction.name]).order_by(db.Fraction.id.asc()).gino.all()]
    for i, fraction in enumerate(fractions):
        reply += f"{i + 1}. {fraction}\n"
    reply += '\nСписок характеристик:\n'
    attributes = [x[0] for x in await db.select([db.Attribute.name]).order_by(db.Attribute.id.asc()).gino.all()]
    for i, attribute in enumerate(attributes):
        reply += f"{i + 1}. {attribute}\n"
    reply += '\nПредметы Карты экспедитора:\n'
    items = [x[0] for x in await db.select([db.Item.name]).order_by(db.Item.id.asc()).gino.all()]
    for i, item in enumerate(items):
        reply += f"{i + 1}. {item}\n"
    reply += ("\nЧтобы указать награду в виде бонуса к репутации необходимо написать команду «РЕП {номер фракции} "
              "{бонус}». Например:\nРЕП 1 10\n\n"
              "Чтобы указать награду в виде валюты необходимо написать команду «ВАЛ {бонус}». Например:\n"
              "ВАЛ 100\n\n"
              "Чтобы указать награду в виде изменения параметра необходимо написать команду «ПАР {либидо} {подчинение}». "
              "Например:\nПАР -10 30\n\n"
              "Чтобы указать награду в виде предметов Карты экспедитора необходимо написать команду «ПРЕ» и перечислить "
              "номера со множителями через запятую\n"
              "Например:\n«ПРЕ 1, 2х4» задаёт награду 1 шт. предмета 1 и 4 шт. предмета 2\n\n"
              "Чтобы указать награду в виде изменения характеристик, необходимо написать команду «ХАР {номер} {изменение}». "
              "Например:\nХАР 1 +5\n\n"
              "❗️ Можно указать несколько вариантов через новую строку")
    return reply, None


async def info_quest_penalty():
    reply = ('Возможные варианты штрафа:\n'
             'I. Бонус к репутации\n'
             'II. Награда валютой\n'
             'III. Изменение параметров\n'
             'IV. Изменение характеристик\n'
             'Список фракций:\n')
    fractions = [x[0] for x in await db.select([db.Fraction.name]).order_by(db.Fraction.id.asc()).gino.all()]
    for i, fraction in enumerate(fractions):
        reply += f"{i + 1}. {fraction}\n"
    reply += '\nСписок характеристик:\n'
    attributes = [x[0] for x in await db.select([db.Attribute.name]).order_by(db.Attribute.id.asc()).gino.all()]
    for i, attribute in enumerate(attributes):
        reply += f"{i + 1}. {attribute}\n"
    reply += ("\nЧтобы указать штраф в виде уменьшения репутации необходимо написать команду «РЕП {номер фракции} "
              "{бонус}». Например:\nРЕП 1 -10\n\n"
              "Чтобы указать штраф в виде валюты необходимо написать команду «ВАЛ {бонус}». Например:\n"
              "ВАЛ -100\n\n"
              "Чтобы указать штраф в виде изменения параметра необходимо написать команду «ПАР {либидо} {подчинение}». "
              "Например:\nПАР -10 30\n\n"
              "Чтобы указать награду в виде изменения характеристик, необходимо написать команду «ХАР {номер} {изменение}». "
              "Например:\nХАР 1 +5\n\n"
              "❗️ Можно указать несколько вариантов через новую строку")
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
                raise FormatDataException('Неверно указаны параметры бонуса к репутации')
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
                raise FormatDataException('Неверно указаны параметры валюты')
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
                raise FormatDataException('Неверно указаны параметры либидо/подчинения')
            data.append({
                'type': 'daughter_params',
                'libido': libido,
                'subordination': subordination
            })
        elif line.startswith('пре'):
            try:
                line = line.replace(' ', '')
                line = line[3:]
                line = line.replace('х', 'x')  # Кириллицу на латинскую
                params = line.split(',')
            except:
                raise FormatDataException('Неправильно указаны параметры для выдачи предметов')
            item_ids = [x[0] for x in await db.select([db.Item.id]).order_by(db.Item.id.asc()).gino.all()]
            for param in params:
                if 'x' in param:
                    number, multiplier = map(int, param.split('x'))
                else:
                    number = int(param)
                    multiplier = 1
                exist = await db.select([db.Item.id]).order_by(db.Item.asc()).offset(number - 1).limit(1).gino.scalar()
                if not exist:
                    raise FormatDataException('Указан предмет, которого не существует')
                data.append({
                    'type': 'item',
                    'item_id': item_ids[number - 1],
                    'count': multiplier
                })
        elif line.startswith('хар'):
            try:
                _, attribute_id, value = line.split()
                attribute_id = int(attribute_id)
                value = int(value)
            except:
                raise FormatDataException('Неверно указаны параметры для изменения характеристик')
            attribute_id = await db.select([db.Attribute.id]).order_by(db.Attribute.id.asc()).offset(attribute_id - 1).limit(1).gino.scalar()
            if not attribute_id:
                raise FormatDataException('Указана несуществующая характеристика')
            data.append({
                'type': 'attribute',
                'attribute_id': attribute_id,
                'value': value
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
            reply += f'бонус к репутации {bonus} во фракции «{fraction}»'
        elif reward['type'] == 'value_bonus':
            reply += str(reward['bonus']) + ' валюты'
        elif reward['type'] == 'daughter_params':
            reply += f'{"+" if reward["libido"] > 0 else ""}{reward["libido"]} к Либидо, {"+" if reward["subordination"] > 0 else ""}{reward["subordination"]} к Подчинению'
        elif reward['type'] == 'item':
            name = await db.select([db.Item.name]).where(db.Item.id == reward['item_id']).gino.scalar()
            count = reward['count']
            reply += f'предмет  «{name}» ({count} шт.)'
        elif reward['type'] == 'attribute':
            name = await db.select([db.Attribute.name]).where(db.Attribute.id == reward['attribute_id']).gino.scalar()
            value = reward['value']
            reply += f'{"+" if value >= 0 else ""}{value} к {name}'
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


async def info_profession_bonus(profession_id: int):
    reply = 'Установленные бонусы сейчас:\n'
    attributes = await db.select([*db.Attribute]).gino.all()
    keyboard = Keyboard(inline=True)
    for i, attribute in enumerate(attributes):
        bonus = await db.select([db.ProfessionBonus.bonus]).where(
            and_(db.ProfessionBonus.profession_id == profession_id, db.ProfessionBonus.attribute_id == attribute.id)).gino.scalar()
        if not bonus:
            reply += f'{i + 1}. {attribute.name} +0\n'
        else:
            reply += f'{i + 1}. {attribute.name} {"+" if bonus >= 0 else ""}{bonus}\n'
        keyboard.add(Callback(attribute.name, {'profession_id': profession_id, 'attribute_id': attribute.id, 'action': 'select'}), KeyboardButtonColor.PRIMARY)
        if i % 2 == 1:
            keyboard.row()
    if len(keyboard.buttons[-1]) > 0:
        keyboard.row()
    keyboard.add(Text('Сохранить', {"profession_id": profession_id, 'action': 'save'}), KeyboardButtonColor.POSITIVE)
    return reply, keyboard


async def serialize_profession_bonus(profession_id: int):
    raw = await db.select([db.ProfessionBonus.attribute_id, db.ProfessionBonus.bonus]).where(db.ProfessionBonus.profession_id == profession_id).gino.all()
    if not raw:
        return 'Без бонусов'
    reply = '\n\n'
    for i, data in enumerate(raw):
        attribute_id, bonus = data
        attribute = await db.select([db.Attribute.name]).where(db.Attribute.id == attribute_id).gino.scalar()
        reply += f'{i + 1}. {attribute}: {"+" if bonus > 0 else ""}{bonus}\n'
    return reply


async def info_item_group():
    item_groups = await db.select([*db.ItemGroup]).gino.all()
    reply = 'Выберите группу предмета:\n'
    keyboard = Keyboard()
    for item_group in item_groups:
        keyboard.add(Text(item_group.name, {"item_group": item_group.id}), KeyboardButtonColor.PRIMARY).row()
    keyboard.buttons.pop(-1)
    return reply, keyboard


async def serialize_item_group(group_id: int):
    name = await db.select([db.ItemGroup.name]).where(db.ItemGroup.id == group_id).gino.scalar()
    return name


async def info_item_type():
    item_types = await db.select([*db.ItemType]).gino.all()
    reply = 'Выберите тип предмета'
    keyboard = Keyboard()
    for item_type in item_types:
        keyboard.add(Text(item_type.name, {"item_type": item_type.id}), KeyboardButtonColor.PRIMARY).row()
    keyboard.buttons.pop(-1)
    return reply, keyboard


async def serialize_item_type(type_id: int):
    name = await db.select([db.ItemType.name]).where(db.ItemType.id == type_id).gino.scalar()
    return name


async def info_item_bonus(item_id: int):
    item_bonus = await db.select([db.Item.bonus]).where(db.Item.id == item_id).gino.scalar()
    reply = 'Текущий бонус предмета:\n'
    reply += await serialize_item_bonus(item_bonus)
    keyboard = Keyboard(inline=True).add(
        Callback('Добавить бонус', {"item_id": item_id, "action": "add_bonus"}), KeyboardButtonColor.POSITIVE
    ).add(
        Callback('Удалить бонус', {"item_id": item_id, "action": "delete_bonus"}), KeyboardButtonColor.NEGATIVE
    ).row().add(
        Text('Сохранить', {"item_id": item_id, "action": "save_bonus"}), KeyboardButtonColor.POSITIVE
    )
    return reply, keyboard


async def serialize_item_bonus(data: list):
    if not data:
        return 'Без эффектов'
    reply = '\n\n'
    for i, bonus in enumerate(data):
        if bonus.get('type') == 'attribute':
            name = await db.select([db.Attribute.name]).where(db.Attribute.id == bonus['attribute_id']).gino.scalar()
            upgrade = bonus['bonus']
            reply += f'{i + 1}. Изменение характеристики «{name}» на {"+" if upgrade >= 0 else ""}{upgrade}\n'
        elif bonus.get('type') == 'state':
            if bonus.get('action') == 'add':
                debuff = await db.StateDebuff.get(bonus['debuff_id'])
                type_name = await db.select([db.DebuffType.name]).where(db.DebuffType.id == debuff.type_id).gino.scalar()
                attribute_name = await db.select([db.Attribute.name]).where(db.Attribute.id == debuff.attribute_id).gino.scalar()
                reply += (f'{i+1}. Добавление {type_name} «{debuff.name}» ({attribute_name} '
                          f'{"+" if debuff.penalty >= 0 else ""}{debuff.penalty})\n')
            elif bonus.get('action') == 'delete':
                debuff = await db.StateDebuff.get(bonus['debuff_id'])
                type_name = await db.select([db.DebuffType.name]).where(
                    db.DebuffType.id == debuff.type_id).gino.scalar()
                attribute_name = await db.select([db.Attribute.name]).where(
                    db.Attribute.id == debuff.attribute_id).gino.scalar()
                reply += (f'{i+1}. Удаление {type_name} «{debuff.name}» ({attribute_name} '
                          f'{"+" if debuff.penalty >= 0 else ""}{debuff.penalty})\n')
            elif bonus.get('action') == 'delete_type':
                type_name = await db.select([db.DebuffType.name]).where(db.DebuffType.id == bonus['type_id']).gino.scalar()
                reply += f'{i+1}. Удаление всех дебафов типа {type_name}\n'
            elif bonus.get('action') == 'delete_all':
                reply += f'{i+1}. Удаление всех дебафов\n'
        elif bonus.get('type') == 'sex_state':
            if bonus.get('attribute') == 'subordination':
                upgrade = bonus['bonus']
                reply += f'{i+1}. Изменение Подчинение на {"+" if upgrade >= 0 else ""}{upgrade}\n'
            elif bonus.get('attribute') == 'libido':
                upgrade = bonus['bonus']
                reply += f'{i+1}. Изменение Либидо на {"+" if upgrade >= 0 else ""}{upgrade}\n'
            elif bonus.get('action') == 'set_pregnant':
                reply += f'{i+1}. Установить статус Оплодотворение ({bonus["text"]})\n'
            elif bonus.get('action') == 'delete_pregnant':
                reply += f'{i+1}. Удалить статус оплодотворение\n'
    return reply


async def info_debuff_type():
    types = await db.select([*db.DebuffType]).order_by(db.DebuffType.id.asc()).gino.all()
    reply = 'Укажите тип дебафа:\n'
    keyboard = Keyboard()
    for i, types in enumerate(types):
        reply += f'{i + 1}. {types.name}\n'
        keyboard.add(Text(types.name, {"debuff_type_id": types.id}), KeyboardButtonColor.PRIMARY).row()
    keyboard.buttons.pop(-1)
    return reply, keyboard


async def serialize_debuff_type(type_id: int):
    name = await db.select([db.DebuffType.name]).where(db.DebuffType.id == type_id).gino.scalar()
    return name


async def info_debuff_attribute():
    attributes = await db.select([*db.Attribute]).order_by(db.Attribute.id.asc()).gino.all()
    reply = 'Укажите характеристику дебафа:\n'
    keyboard = Keyboard()
    for i, attribute in enumerate(attributes):
        reply += f'{i + 1}. {attribute.name}\n'
        keyboard.add(Text(attribute.name, {"debuff_attribute_id": attribute.id}), KeyboardButtonColor.PRIMARY).row()
    keyboard.buttons.pop(-1)
    return reply, keyboard


async def serialize_debuff_attribute(attribute_id: int):
    name = await db.select([db.Attribute.name]).where(db.Attribute.id == attribute_id).gino.scalar()
    return name


async def info_item_available_for_sale():
    reply = 'Выберите будет ли доступен предмет для продажи в магазине'
    return reply, keyboards.item_type


async def serialize_item_available_for_sale(type_id: int):
    if type_id == 0:
        return 'Нет'
    elif type_id == 1:
        return 'Да'


async def info_item_fraction():
    reply = 'Укажите для какой фракции будет доступен предмет для покупки\n\nСписок фракций:\n'
    fractions = [x[0] for x in await db.select([db.Fraction.name]).order_by(db.Fraction.id.asc()).gino.all()]
    for i, fraction in enumerate(fractions):
        reply += f'{i + 1}. {fraction}\n'
    keyboard = Keyboard().add(Text('Для всех фракций', {"item_for_all_fractions": True}), KeyboardButtonColor.SECONDARY)
    return reply, keyboard


async def info_item_photo():
    reply = 'Отправьте изображение для предмета'
    keyboard = Keyboard().add(Text('Без фото', {"item_without_photo": True}), KeyboardButtonColor.SECONDARY)
    return reply, keyboard


async def info_race_bonus(race_id: int):
    reply = 'Установленные бонусы сейчас:\n'
    attributes = await db.select([*db.Attribute]).gino.all()
    keyboard = Keyboard(inline=True)
    for i, attribute in enumerate(attributes):
        bonus = await db.select([db.RaceBonus.bonus]).where(
            and_(db.RaceBonus.race_id == race_id, db.RaceBonus.attribute_id == attribute.id)).gino.scalar()
        if not bonus:
            reply += f'{i + 1}. {attribute.name} +0\n'
        else:
            reply += f'{i + 1}. {attribute.name} {"+" if bonus >= 0 else ""}{bonus}\n'
        keyboard.add(Callback(attribute.name, {'race_id': race_id, 'attribute_id': attribute.id, 'action': 'select'}), KeyboardButtonColor.PRIMARY)
        if i % 2 == 1:
            keyboard.row()
    if len(keyboard.buttons[-1]) > 0:
        keyboard.row()
    keyboard.add(Text('Сохранить', {"race_id": race_id, 'action': 'save'}), KeyboardButtonColor.POSITIVE)
    return reply, keyboard


async def serialize_race_bonus(race_id: int):
    raw = await db.select([db.RaceBonus.attribute_id, db.RaceBonus.bonus]).where(db.RaceBonus.race_id == race_id).gino.all()
    if not raw:
        return 'Без бонусов'
    reply = ''
    for i, data in enumerate(raw):
        attribute_id, bonus = data
        attribute = await db.select([db.Attribute.name]).where(db.Attribute.id == attribute_id).gino.scalar()
        reply += f'{"+" if bonus > 0 else ""}{bonus} к {attribute}, '
    return reply[:-2]


async def info_expeditor_name() -> tuple[str, Keyboard | None]:
    return ('Нельзя установить имя для Карты Экспедитора. Оно подтягивается автоматически из анкеты пользователя\n\n'
            'Отправьте любое сообщение, чтобы выйти из режима редактирвоания'), None


async def serialize_expeditor_name(expeditor_id: int) -> str:
    form_id = await db.select([db.Expeditor.form_id]).where(db.Expeditor.id == expeditor_id).gino.scalar()
    name, user_id = await db.select([db.Form.name, db.Form.user_id]).where(db.Form.id == form_id).gino.first()
    user = (await bot.api.users.get(user_id))[0]
    return f'[id{user_id}|{name} / {user.first_name} {user.last_name}]'


async def info_expeditor_sex() -> tuple[str, Keyboard | None]:
    return 'Выберите пол:', keyboards.sex_types


async def serialize_expeditor_sex(value: int) -> str:
    return sex_types[value]


async def info_expeditor_race() -> tuple[str, Keyboard | None]:
    reply = 'Выберите расу:\n\n'
    races = [x[0] for x in await db.select([db.Race.name]).order_by(db.Race.id.asc()).gino.all()]
    for i, name in enumerate(races):
        reply += f'{i + 1}. {name}\n'
    return reply, None


async def serialize_expeditor_race(value: int) -> str:
    return await db.select([db.Race.name]).where(db.Race.id == value).gino.scalar()


async def info_expeditor_pregnant() -> tuple[str, Keyboard | None]:
    keyboard = Keyboard().add(
        Text('Удалить оплодотворение', {'delete_expeditor_pregnant': True}), KeyboardButtonColor.NEGATIVE
    )
    return 'Отправьте текст значения оплодотворения', keyboard


async def serialize_expeditor_pregnant(value: str | None) -> str:
    if not value:
        return 'Отстутствует'
    return value


async def info_expeditor_attributes(expeditor_id: int) -> tuple[str, Keyboard | None]:
    reply = 'Текущие показания характеристик:\n\n'
    reply += await serialize_expeditor_attributes(expeditor_id)
    data = await db.select([db.ExpeditorToAttributes.attribute_id, db.ExpeditorToAttributes.value]).where(db.ExpeditorToAttributes.expeditor_id == expeditor_id).order_by(db.ExpeditorToAttributes.attribute_id.asc()).gino.all()
    keyboard = Keyboard(inline=True)
    for attribute_id, value in data:
        attribute_name = await db.select([db.Attribute.name]).where(db.Attribute.id == attribute_id).gino.scalar()
        keyboard.add(
            Callback(attribute_name, {'expeditor_id': expeditor_id, 'attribute_id': attribute_id, 'action': 'select_attribute'}), KeyboardButtonColor.PRIMARY
        )
        if len(keyboard.buttons[-1]) >= 2:
            keyboard.row()
    if len(keyboard.buttons[-1]) > 0:
        keyboard.row()
    keyboard.add(Text('Сохранить', {'action': 'save_attribute'}), KeyboardButtonColor.POSITIVE)
    return reply, keyboard


async def serialize_expeditor_attributes(expeditor_id: int) -> str:
    data = await db.select([db.ExpeditorToAttributes.attribute_id, db.ExpeditorToAttributes.value]).where(db.ExpeditorToAttributes.expeditor_id == expeditor_id).order_by(db.ExpeditorToAttributes.attribute_id.asc()).gino.all()
    reply = '\n'
    for attribute_id, value in data:
        attribute_name = await db.select([db.Attribute.name]).where(db.Attribute.id == attribute_id).gino.scalar()
        reply += f'{attribute_name}: {value}\n'
    return reply[:-1]


async def info_expeditor_debuffs(expeditor_id: int) -> tuple[str, Keyboard | None]:
    reply = 'Текущие активные дебафы:\n\n'
    reply += await serialize_expeditor_debuffs(expeditor_id)
    keyboard = Keyboard(inline=True).add(
        Callback('Добавить дебаф', {'expeditor_id': expeditor_id, 'action': 'add_debuff'}), KeyboardButtonColor.PRIMARY
    ).row().add(
        Callback('Удалить дебаф', {'expeditor_id': expeditor_id, 'action': 'delete_debuff'}), KeyboardButtonColor.PRIMARY
    ).row().add(
        Text('Сохранить', {'action': 'save_debuffs'}), KeyboardButtonColor.POSITIVE
    )
    return reply, keyboard


async def serialize_expeditor_debuffs(expeditor_id: int) -> str:
    reply = '\n'
    debufs = [x[0] for x in await db.select([db.ExpeditorToDebuffs.debuff_id]).where(
        db.ExpeditorToDebuffs.expeditor_id == expeditor_id).gino.all()]
    if not debufs:
        reply += 'Дебафы отсутствуют'
    else:
        injuries = await db.select([*db.StateDebuff]).where(
            and_(db.StateDebuff.id.in_(debufs), db.StateDebuff.type_id == 1)).gino.all()
        if injuries:
            reply += 'Активные травмы:\n'
            for i, debuff_id in enumerate(debufs):
                debuff = await db.select([*db.StateDebuff]).where(db.StateDebuff.id == debuff_id).gino.first()
                if debuff.type_id == 1:
                    attribute = await db.select([db.Attribute.name]).where(
                        db.Attribute.id == debuff.attribute_id).gino.scalar()
                    reply += f'{i + 1}. {debuff.name} ({"+" if debuff.penalty >= 0 else ""}{debuff.penalty} к {attribute})\n'
        else:
            reply += 'Травмы отсутствуют\n'
        madness = await db.select([*db.StateDebuff]).where(
            and_(db.StateDebuff.id.in_(debufs), db.StateDebuff.type_id == 2)).gino.all()
        if madness:
            reply += 'Активные безумства:\n'
            for i, debuff_id in enumerate(debufs):
                debuff = await db.select([*db.StateDebuff]).where(db.StateDebuff.id == debuff_id).gino.scalar()
                if debuff.type_id == 2:
                    attribute = await db.select([db.Attribute.name]).where(
                        db.Attribute.id == debuff.attribute_id).gino.scalar()
                    reply += f'{i + 1}. {debuff.name} ({"+" if debuff.penalty >= 0 else ""}{debuff.penalty} к {attribute})\n'
        else:
            reply += 'Безумства отсутствуют'
    return reply


async def info_expeditor_items(expeditor_id: int) -> tuple[str, Keyboard | None]:
    reply = 'Текущие предметы в инвентаре:\n\n'
    reply += await serialize_expeditor_items(expeditor_id)
    keyboard = Keyboard(inline=True).add(
        Callback('Добавить предмет', {'expeditor_id': expeditor_id, 'action': 'add_item'}), KeyboardButtonColor.PRIMARY
    ).row().add(
        Callback('Удалить предмет', {'expeditor_id': expeditor_id, 'action': 'delete_item'}), KeyboardButtonColor.PRIMARY
    ).row().add(
        Text('Сохранить', {'action': 'save_items'}), KeyboardButtonColor.POSITIVE
    )
    return reply, keyboard


async def serialize_expeditor_items(expeditor_id: int) -> str:
    reply = '\n'
    inventory = [x[0] for x in await db.select([db.ExpeditorToItems.item_id]).where(
        db.ExpeditorToItems.expeditor_id == expeditor_id).gino.all()]
    if inventory:
        counts = dict(Counter(inventory))
        reply += 'Предметы в инвентаре:\n'
        item_ids = list(set(inventory))
        for i, item in enumerate(item_ids):
            name = await db.select([db.Item.name]).where(db.Item.id == item).gino.scalar()
            reply += f'{name}'
            if counts[item] > 1:
                reply += f' X{counts[item]}'
            reply += ', '
        reply = reply[:-2]
    else:
        reply += 'Инвентарь пуст'
    return reply


async def info_item_action_time():
    reply = 'Укажите количество циклов, которые будет действовать предмет'
    keyboard = Keyboard().add(Text('Без ограничения', {'item_action_time': 'null'}), KeyboardButtonColor.NEGATIVE)
    return reply, keyboard


async def info_item_time():
    reply = 'Укажите время действия предмета\nФормат: 1 день 2 часа 3 минуты 4 секунды'
    keyboard = Keyboard().add(Text('Бессрочно', {'item_time': 'infinity'}), KeyboardButtonColor.NEGATIVE)
    return reply, keyboard


async def serialize_item_time(seconds: int):
    if not seconds:
        return 'бессрочно'
    return parse_cooldown(seconds)


async def serialize_item_action_time(count_use: int):
    if not count_use:
        return 'без ограничения'
    return str(count_use)


async def info_debuff_action_time():
    reply = 'Укажите количество циклов, которые будет действовать предмет'
    keyboard = Keyboard().add(Text('Без ограничения', {'debuff_action_time': 'null'}), KeyboardButtonColor.NEGATIVE)
    return reply, keyboard


async def info_debuff_time():
    reply = 'Укажите время действия дебафф\nФормат: 1 день 2 часа 3 минуты 4 секунды'
    keyboard = Keyboard().add(Text('Бессрочно', {'debuff_time': 'infinity'}), KeyboardButtonColor.NEGATIVE)
    return reply, keyboard

# Словарь со всеми типами контента
# Ключом в словаре должна являться строка - название аттрибута объекта db (прямо как в Database.__init__() объявлен)
# По этому ключу будет получен класс таблицы из db
# Значение названия таблицы словарь с полем fields (обязательно) и name (необязательно)
# Значением ключа fields является list[Union[Field, RelatedTable]]
# Необходимо указывать поля Field строго в том порядке в котором они идут в базе данных
# Важно указывать поля RelatedTable в конце списка, чтобы не нарушать очередность полей Field
fields_content: Dict[str, Dict[str, List[Union[Field, RelatedTable]]]] = {
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
            RelatedTable('Бонусы к характеристикам', Admin.PROFESSION_BONUS, info_profession_bonus, serialize_profession_bonus)
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
            Field('Мультпиликатор либидо', Admin.FRACTION_LIBIDO),
            Field('Мультпиликатор подчинения', Admin.FRACTION_SUBORDINATION)
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
            Field('Параметры дочери', Admin.DAUGHTER_TARGET_PARAMS, info_target_daughter_params, serialize_target_daughter_params),
            Field('Штраф', Admin.DAUGHTER_TARGET_PENALTY, info_quest_penalty, serialize_target_reward)
        ]
    },
    'StateDebuff': {
        'name': "Дебафы",
        'fields': [
            Field('Название', Admin.DEBUFF_NAME),
            Field('Тип', Admin.DEBUFF_TYPE, info_debuff_type, serialize_debuff_type),
            Field('Характеристика', Admin.DEBUFF_ATTRIBUTE, info_debuff_attribute, serialize_debuff_attribute),
            Field('Штраф', Admin.DEBUFF_PENALTY),
            Field('Количество циклов действия (шт.)', Admin.DEBUFF_ACTION_TIME, info_debuff_action_time, serialize_item_action_time),
            Field('Время действия', Admin.DEBUFF_TIME, info_debuff_time, serialize_item_time)
        ]
    },
    'Item': {
        'name': 'Предметы для карты экспедитора',
        'fields': [
            Field('Название', Admin.ITEM_NAME),
            Field('Описание', Admin.ITEM_DESCRIPTION),
            Field('Группа', Admin.ITEM_GROUP, info_item_group, serialize_item_group),
            Field('Тип', Admin.ITEM_TYPE, info_item_type, serialize_item_type),
            Field('Количество использований', Admin.ITEM_COUNT_USE),
            Field('Доступно для продажи', Admin.ITEM_AVAILABLE_FOR_SALE, info_item_available_for_sale, serialize_item_available_for_sale),
            Field('Цена', Admin.ITEM_PRICE),
            Field('Для фракции', Admin.ITEM_FRACTION_ID, info_item_fraction, serialize_target_fraction),
            Field('Необходимый уровень репутации', Admin.ITEM_REPUTATION),
            Field('Фото', Admin.ITEM_PHOTO, info_item_photo),
            Field('Бонус', Admin.ITEM_BONUS, info_item_bonus, serialize_item_bonus),
            Field('Количество циклов действия (шт.)', Admin.ITEM_ACTION_TIME, info_item_action_time, serialize_item_action_time),
            Field('Время действия', Admin.ITEM_TIME, info_item_time, serialize_item_time)
        ]
    },
    'Race': {
        'name': 'Расы',
        'fields': [
            Field('Название', Admin.RACE_NAME),
            RelatedTable('Бонус к характеристикам', Admin.RACE_BONUS, info_race_bonus, serialize_race_bonus)
        ]
    },
    'Expeditor': {
        'name': 'Карты экспедитора',
        'fields': [
            RelatedTable('Имя', Admin.EXPEDITOR_NAME, info_expeditor_name, serialize_expeditor_name),
            Field('Пол', Admin.EXPEDITOR_SEX, info_expeditor_sex, serialize_expeditor_sex),
            Field('Раса', Admin.EXPEDITOR_RACE, info_expeditor_race, serialize_expeditor_race),
            Field('Оплодотворение', Admin.EXPEDITOR_PREGNANT, info_expeditor_pregnant, serialize_expeditor_pregnant),
            RelatedTable('Характеристики', Admin.EXPEDITOR_ATTRIBUTES, info_expeditor_attributes, serialize_expeditor_attributes),
            RelatedTable('Состояние (дебафы)', Admin.EXPEDITOR_DEBUFFS, info_expeditor_debuffs, serialize_expeditor_debuffs),
            RelatedTable('Инвентарь', Admin.EXPEDITOR_ITEMS, info_expeditor_items, serialize_expeditor_items)
        ]
    }
}
