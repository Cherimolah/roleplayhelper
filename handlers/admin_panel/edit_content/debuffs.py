"""
Модуль для создания, удаления, редактирвоания дебафов
"""
from vkbottle.bot import Message
from vkbottle import Keyboard
from vkbottle.dispatch.rules.base import PayloadRule, PayloadMapRule
from vkbottle.dispatch.rules.abc import OrRule

from loader import bot, states
from service.custom_rules import StateRule, AdminRule, NumericRule, JudgeRule
from service.states import Admin
from service.db_engine import db
from service import keyboards
from service.utils import send_content_page, allow_edit_content, parse_period, FormatDataException
from service.serializers import info_debuff_type, info_debuff_attribute, info_debuff_time, info_debuff_action_time


@bot.on.private_message(StateRule(f"{Admin.SELECT_ACTION}_StateDebuff"), PayloadRule({"StateDebuff": "add"}),
                        OrRule(JudgeRule(), AdminRule()))
async def create_quest(m: Message):
    """
    Создание нового дебафа.

    Обрабатывает запрос на добавление нового дебафа. Создает запись в базе данных
    и переводит пользователя в состояние ввода названия дебафа.

    Args:
        m (Message): Входящее сообщение от пользователя
    """
    item = await db.StateDebuff.create()
    states.set(m.from_id, f"{Admin.DEBUFF_NAME}*{item.id}")
    await m.answer("Напишите название дебафа", keyboard=Keyboard())


@bot.on.private_message(StateRule(Admin.DEBUFF_NAME), OrRule(JudgeRule(), AdminRule()))
@allow_edit_content('StateDebuff', state=Admin.DEBUFF_TYPE)
async def debuff_name(m: Message, item_id: int, editing_content: bool):
    """
    Установка названия дебафа.

    Сохраняет название дебафа в базу данных и переводит пользователя
    к выбору типа дебафа.

    Args:
        m (Message): Входящее сообщение с названием дебафа
        item_id (int): ID дебафа в базе данных
        editing_content (bool): Флаг редактирования существующего контента
    """
    await db.StateDebuff.update.values(name=m.text).where(db.StateDebuff.id == item_id).gino.status()
    if not editing_content:
        reply, keyboard = await info_debuff_type()
        await m.answer(reply, keyboard=keyboard)


@bot.on.private_message(StateRule(Admin.DEBUFF_TYPE), PayloadMapRule({"debuff_type_id": int}),
                        OrRule(JudgeRule(), AdminRule()))
@allow_edit_content('StateDebuff', state=Admin.DEBUFF_ATTRIBUTE)
async def debuff_type(m: Message, item_id: int, editing_content: bool):
    """
    Установка типа дебафа.

    Сохраняет выбранный тип дебафа и переводит к выбору атрибута,
    на который влияет дебаф.

    Args:
        m (Message): Входящее сообщение с выбранным типом
        item_id (int): ID дебафа в базе данных
        editing_content (bool): Флаг редактирования существующего контента
    """
    await db.StateDebuff.update.values(type_id=m.payload['debuff_type_id']).where(
        db.StateDebuff.id == item_id).gino.status()
    if not editing_content:
        reply, keyboard = await info_debuff_attribute()
        await m.answer(reply, keyboard=keyboard)


@bot.on.private_message(StateRule(Admin.DEBUFF_ATTRIBUTE), PayloadMapRule({"debuff_attribute_id": int}),
                        OrRule(JudgeRule(), AdminRule()))
@allow_edit_content('StateDebuff', state=Admin.DEBUFF_PENALTY,
                    text='Укажите штраф, который будет выдаваться к этой характеристике (!! со знаком минус)',
                    keyboard=Keyboard())
async def debuff_attribute(m: Message, item_id: int, editing_content: bool):
    """
    Установка атрибута для дебафа.

    Сохраняет выбранный атрибут, на который будет влиять дебаф.

    Args:
        m (Message): Входящее сообщение с выбранным атрибутом
        item_id (int): ID дебафа в базе данных
        editing_content (bool): Флаг редактирования существующего контента
    """
    await db.StateDebuff.update.values(attribute_id=m.payload['debuff_attribute_id']).where(
        db.StateDebuff.id == item_id).gino.status()


@bot.on.private_message(StateRule(Admin.DEBUFF_PENALTY), NumericRule(min_number=-200, max_number=200),
                        OrRule(JudgeRule(), AdminRule()))
@allow_edit_content('StateDebuff', state=Admin.DEBUFF_ACTION_TIME, )
async def debuff_penalty(m: Message, value: int, item_id: int, editing_content: bool):
    """
    Установка значения штрафа для дебафа.

    Сохраняет числовое значение штрафа для выбранного атрибута.

    Args:
        m (Message): Входящее сообщение с значением штрафа
        value (int): Числовое значение штрафа
        item_id (int): ID дебафа в базе данных
        editing_content (bool): Флаг редактирования существующего контента
    """
    await db.StateDebuff.update.values(penalty=value).where(db.StateDebuff.id == item_id).gino.status()
    if not editing_content:
        reply, keyboard = await info_debuff_action_time()
        await m.answer(reply, keyboard=keyboard)


@bot.on.private_message(StateRule(Admin.DEBUFF_ACTION_TIME), PayloadRule({'debuff_action_time': 'null'}),
                        OrRule(JudgeRule(), AdminRule()))
@allow_edit_content('StateDebuff', state=Admin.DEBUFF_TIME)
async def set_debuf_action_time_null(m: Message, item_id, editing_content):
    """
    Установка нулевого времени действия дебафа.

    Обрабатывает выбор отсутствия времени действия для дебафа.

    Args:
        m (Message): Входящее сообщение
        item_id (int): ID дебафа в базе данных
        editing_content (bool): Флаг редактирования существующего контента
    """
    if not editing_content:
        reply, keyboard = await info_debuff_time()
        await m.answer(reply, keyboard=keyboard)


@bot.on.private_message(StateRule(Admin.DEBUFF_ACTION_TIME), NumericRule(), OrRule(JudgeRule(), AdminRule()))
@allow_edit_content('StateDebuff', state=Admin.DEBUFF_TIME)
async def set_debuf_action_time_null(m: Message, item_id, editing_content, value):
    """
    Установка времени действия дебафа.

    Сохраняет указанное время действия дебафа в секундах.

    Args:
        m (Message): Входящее сообщение с временем действия
        item_id (int): ID дебафа в базе данных
        editing_content (bool): Флаг редактирования существующего контента
        value (int): Время действия в секундах
    """
    await db.StateDebuff.update.values(action_time=value).where(db.StateDebuff.id == item_id).gino.status()
    if not editing_content:
        reply, keyboard = await info_debuff_time()
        await m.answer(reply, keyboard=keyboard)


@bot.on.private_message(StateRule(Admin.DEBUFF_TIME), PayloadRule({'debuff_time': 'infinity'}),
                        OrRule(JudgeRule(), AdminRule()))
@allow_edit_content('StateDebuff', text='Дебаф успешно создан', end=True)
async def set_infinity_debuff_time(m: Message, item_id, editing_content):
    """
    Установка бесконечного времени для дебафа.

    Обрабатывает выбор бесконечной длительности дебафа.

    Args:
        m (Message): Входящее сообщение
        item_id (int): ID дебафа в базе данных
        editing_content (bool): Флаг редактирования существующего контента
    """
    pass


@bot.on.private_message(StateRule(Admin.DEBUFF_TIME), OrRule(JudgeRule(), AdminRule()))
@allow_edit_content('StateDebuff', text='Дебаф успешно создан', end=True)
async def set_infinity_debuff_time(m: Message, item_id, editing_content):
    """
    Установка времени использования дебафа.

    Парсит текстовое представление времени и сохраняет в секундах.

    Args:
        m (Message): Входящее сообщение с текстовым представлением времени
        item_id (int): ID дебафа в базе данных
        editing_content (bool): Флаг редактирования существующего контента

    Raises:
        FormatDataException: Если формат времени неправильный или время не указано
    """
    try:
        seconds = parse_period(m.text)
    except:
        raise FormatDataException('Неправильный формат записи периода')
    if not seconds:
        raise FormatDataException('Не указано время')
    await db.StateDebuff.update.values(time_use=seconds).where(db.StateDebuff.id == item_id).gino.status()


@bot.on.private_message(StateRule(f"{Admin.SELECT_ACTION}_StateDebuff"), PayloadRule({"StateDebuff": "delete"}),
                        OrRule(JudgeRule(), AdminRule()))
async def select_delete_quest(m: Message):
    """
    Выбор дебафа для удаления.

    Показывает список всех дебафов для выбора того, который нужно удалить.

    Args:
        m (Message): Входящее сообщение

    Returns:
        str: Сообщение об отсутствии дебафов, если таковых нет
    """
    debuffs = await db.select([db.StateDebuff.name]).order_by(db.StateDebuff.id.asc()).gino.all()
    if not debuffs:
        return "Предметы ещё не созданы"
    reply = "Выберите предмет для удаления:\n\n"
    for i, item in enumerate(debuffs):
        reply = f"{reply}{i + 1}. {item.name}\n"
    states.set(m.peer_id, Admin.DEBUFF_DELETE)
    await m.answer(reply, keyboard=Keyboard())


@bot.on.private_message(StateRule(Admin.DEBUFF_DELETE), NumericRule(), OrRule(JudgeRule(), AdminRule()))
async def delete_quest(m: Message, value: int):
    """
    Удаление выбранного дебафа.

    Удаляет дебаф из базы данных и все его упоминания в связанных таблицах.

    Args:
        m (Message): Входящее сообщение с номером дебафа для удаления
        value (int): Номер дебафа в списке
    """
    item_id = await db.select([db.StateDebuff.id]).order_by(db.StateDebuff.id.asc()).offset(value - 1).limit(
        1).gino.scalar()
    await db.StateDebuff.delete.where(db.StateDebuff.id == item_id).gino.status()
    # Удаление упоминаний дебафа в предметах
    items = await db.select([db.Item.id, db.Item.bonus]).gino.all()
    for item_id, item_bonus in items:
        for i, bonus in enumerate(item_bonus):
            if bonus.get('type') == 'state' and bonus.get('action') in ('add', 'delete') and bonus.get(
                    'debuff_id') == item_bonus:
                item_bonus.pop(i)
                await db.Item.update.values(bonus=item_bonus).where(db.Item.id == item_id).gino.status()
                break
    # Удаление упоминаний дебафа в последствиях
    cons = await db.select([db.Consequence.id, db.Consequence.data]).gino.all()
    for con_id, data in cons:
        if data and data['type'] in ('add_debuff', 'delete_debuff') and data['debuff_id'] == item_id:
            await db.Consequence.delete.where(db.Consequence.id == con_id).gino.status()
    states.set(m.peer_id, f"{Admin.SELECT_ACTION}_StateDebuff")
    await m.answer("Дебаф успешно удален", keyboard=keyboards.gen_type_change_content("StateDebuff"))
    await send_content_page(m, "StateDebuff", 1)
