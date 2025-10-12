"""
Модуль для управления ежедневными заданиями (дейликами) в системе администратора.
Содержит обработчики для создания, настройки и удаления дейликов.
"""
from sqlalchemy.sql import True_
from sqlalchemy.testing import assert_warnings
from vkbottle.bot import Message
from vkbottle.dispatch.rules.base import PayloadRule, PayloadMapRule
from vkbottle import Keyboard

from loader import bot
from service.custom_rules import StateRule, AdminRule, NumericRule
from service.states import Admin
from service.middleware import states
from service.db_engine import db
from service.utils import send_content_page, allow_edit_content, FormatDataException
from service.serializers import info_daylic_chill
from service import keyboards


@bot.on.private_message(PayloadRule({"Daylic": "add"}), StateRule(f"{Admin.SELECT_ACTION}_Daylic"), AdminRule())
async def create_daylic(m: Message):
    """
    Создание нового дейлика.

    Args:
        m: Сообщение с payload {"Daylic": "add"}

    Действия:
        1. Создает запись дейлика в БД
        2. Устанавливает состояние для ввода названия
    """
    daylic = await db.Daylic.create()
    states.set(m.from_id, f"{Admin.DAYLIC_NAME}*{daylic.id}")
    await m.answer("Введите название еженедельного задания", keyboard=Keyboard())


@bot.on.private_message(StateRule(Admin.DAYLIC_NAME), AdminRule())
@allow_edit_content("Daylic", text="Укажите описание еженедельного задания", state=Admin.DAYLIC_DESCRIPTION)
async def set_name_daylic(m: Message, item_id: int, editing_content: bool):
    """
    Установка названия дейлика.

    Args:
        m: Сообщение с названием
        item_id: ID дейлика
        editing_content: Флаг редактирования
    """
    await db.Daylic.update.values(name=m.text).where(db.Daylic.id == item_id).gino.status()


@bot.on.private_message(StateRule(Admin.DAYLIC_DESCRIPTION), AdminRule())
@allow_edit_content("Daylic", text="Укажите награду за выполнение (количество валюты числом)",
                    state=Admin.DAYLIC_REWARD)
async def set_description_daylic(m: Message, item_id: int, editing_content: bool):
    """
    Установка описания дейлика.

    Args:
        m: Сообщение с описанием
        item_id: ID дейлика
        editing_content: Флаг редактирования
    """
    await db.Daylic.update.values(description=m.text).where(db.Daylic.id == item_id).gino.status()


@bot.on.private_message(StateRule(Admin.DAYLIC_REWARD), NumericRule(), AdminRule())
@allow_edit_content("Daylic", state=Admin.DAYLIC_PROFESSION)
async def set_daylic_reward(m: Message, value: int, item_id: int, editing_content: bool):
    """
    Установка награды за выполнение дейлика.

    Args:
        m: Сообщение с размером награды
        value: Числовое значение награды
        item_id: ID дейлика
        editing_content: Флаг редактирования

    Действия:
        Показывает список профессий для привязки
    """
    await db.Daylic.update.values(reward=value).where(db.Daylic.id == item_id).gino.status()
    if not editing_content:
        reply = 'Укажите к какой профессии будет создано еженедельное задание:\n\n'
        professions = [x[0] for x in await db.select([db.Profession.name]).order_by(db.Profession.id.asc()).gino.all()]
        for i, name in enumerate(professions):
            reply += f'{i + 1}. {name}\n'
        await m.answer(reply, keyboard=Keyboard())


@bot.on.private_message(StateRule(Admin.DAYLIC_PROFESSION), NumericRule(), AdminRule())
@allow_edit_content("Daylic", state=Admin.DAYLIC_FRACTION)
async def set_daylic_profession(m: Message, value: int, item_id: int, editing_content: bool):
    """
    Привязка дейлика к профессии.

    Args:
        m: Сообщение с номером профессии
        value: Номер профессии в списке
        item_id: ID дейлика
        editing_content: Флаг редактирования

    Действия:
        Показывает список фракций для установки бонуса репутации
    """
    profession_id = await db.select([db.Profession.id]).order_by(db.Profession.id).offset(value - 1).limit(
        1).gino.scalar()
    if not profession_id:
        raise FormatDataException("Профессия не найдена")
    await db.Daylic.update.values(profession_id=profession_id).where(db.Daylic.id == item_id).gino.status()
    fractions = [x[0] for x in await db.select([db.Fraction.name]).order_by(db.Fraction.id.asc()).gino.all()]
    reply = "Теперь укажи номер фракции, к которой будет бонус к репутации:\n\n"
    for i, name in enumerate(fractions):
        reply += f"{i + 1}. {name}\n"
    await m.answer(reply, keyboard=keyboards.without_fraction_bonus)


@bot.on.private_message(StateRule(Admin.DAYLIC_FRACTION), PayloadRule({"withot_fraction_bonus": True}), AdminRule())
@allow_edit_content("Daylic", state=Admin.DAYLIC_CHILL)
async def save_daylic_without_bonus(m: Message, item_id: int, editing_content: bool):
    """
    Сохранение дейлика без бонуса к репутации.

    Args:
        m: Сообщение с payload
        item_id: ID дейлика
        editing_content: Флаг редактирования
    """
    await db.Daylic.update.values(fraction_id=None, reputation=0).where(db.Daylic.id == item_id).gino.status()
    if not editing_content:
        reply, keyboard = await info_daylic_chill()
        await m.answer(reply, keyboard=keyboard)


@bot.on.private_message(StateRule(Admin.DAYLIC_FRACTION), NumericRule(), AdminRule())
@allow_edit_content("Daylic", text="Номер фракции установлен теперь укажи бонус к репутации числом",
                    state=Admin.DAYLIC_REPUTATTION)
async def set_daylic_fraction(m: Message, value: int, item_id: int, editing_content: bool):
    """
    Привязка дейлика к фракции.

    Args:
        m: Сообщение с номером фракции
        value: Номер фракции в списке
        item_id: ID дейлика
        editing_content: Флаг редактирования
    """
    fractions = [x[0] for x in await db.select([db.Fraction.id]).order_by(db.Fraction.id.asc()).gino.all()]
    if value > len(fractions):
        raise FormatDataException("Номер фракции слишком большой")
    fraction_id = fractions[value - 1]
    await db.Daylic.update.values(fraction_id=fraction_id).where(db.Daylic.id == item_id).gino.status()


@bot.on.private_message(StateRule(Admin.DAYLIC_REPUTATTION), AdminRule())
@allow_edit_content("Daylic", state=Admin.DAYLIC_CHILL)
async def set_daylic_with_bonus(m: Message, item_id: int, editing_content: bool):
    """
    Установка бонуса к репутации за выполнение дейлика.

    Args:
        m: Сообщение с размером бонуса
        item_id: ID дейлика
        editing_content: Флаг редактирования
    """
    try:
        value = int(m.text)
    except ValueError:
        raise FormatDataException("Необходимо ввести целое число")

    fraction_id = await db.select([db.Daylic.fraction_id]).where(db.Daylic.id == item_id).gino.scalar()
    if not fraction_id and value != 0:
        raise FormatDataException("Бонус к репутации может быть установлен только, когда есть фракция\n"
                                  "Установите сначала фракцию, потом бонус к репутации\n\n"
                                  "Введите 0, чтобы выйти из режима редактирования репутации")

    if not -200 <= value <= 200:
        raise FormatDataException("Диапазон значений [-200; 200]")
    await db.Daylic.update.values(reputation=value).where(db.Daylic.id == item_id).gino.status()

    if not editing_content:
        reply, keyboard = await info_daylic_chill()
        await m.answer(reply, keyboard=keyboard)


@bot.on.private_message(StateRule(Admin.DAYLIC_CHILL), PayloadMapRule({'chill_daylic': bool}), AdminRule())
@allow_edit_content("Daylic", text='Еженедельник успешно создан', end=True)
async def set_daylic_chill(m: Message, item_id: int, editing_content: bool):
    value = m.payload['chill_daylic']
    await db.Daylic.update.values(chill=value).where(db.Daylic.id == item_id).gino.status()


@bot.on.private_message(StateRule(f"{Admin.SELECT_ACTION}_Daylic"), PayloadRule({"Daylic": "delete"}), AdminRule())
async def select_delete_daylic(m: Message):
    """
    Выбор дейлика для удаления.

    Args:
        m: Сообщение с payload {"Daylic": "delete"}

    Действия:
        Показывает список всех дейликов для выбора
    """
    daylics = (await db.select([db.Daylic.name, db.Daylic.reward, db.Profession.name])
               .select_from(db.Daylic.join(db.Profession, db.Daylic.profession_id == db.Profession.id))
               .order_by(db.Daylic.id.asc()).gino.all())
    if not daylics:
        return "Еженедельные задания ещё не созданы"
    reply = "Выберите еженедельник для удаления\n\n"
    for i, daylic in enumerate(daylics):
        reply = f"{reply}{i + 1}. {daylic[0]} ({daylic[2]}, {daylic[1]})\n"
    states.set(m.from_id, Admin.DAYLIC_SELECT_ID)
    await m.answer(reply)


@bot.on.private_message(StateRule(Admin.DAYLIC_SELECT_ID), NumericRule(), AdminRule())
async def delete_daylic(m: Message, value: int):
    """
    Удаление выбранного дейлика.

    Args:
        m: Сообщение с номером дейлика
        value: Номер дейлика в списке
    """
    daylic_id, daylic_name = await db.select([db.Daylic.id, db.Daylic.name]).order_by(db.Daylic.id.asc()).offset(
        value - 1).limit(1).gino.first()
    await db.Daylic.delete.where(db.Daylic.id == daylic_id).gino.status()
    states.set(m.from_id, f"{Admin.SELECT_ACTION}_Daylic")
    await m.answer(f"Еженедельник {daylic_name} удалён",
                   keyboard=keyboards.gen_type_change_content("Daylic"))
    await send_content_page(m, "Daylic", 1)
