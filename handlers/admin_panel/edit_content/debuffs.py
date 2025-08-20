from vkbottle.bot import Message
from vkbottle import Keyboard, Text, KeyboardButtonColor
from vkbottle.dispatch.rules.base import PayloadRule, PayloadMapRule
from vkbottle.dispatch.rules.abc import OrRule

from loader import bot, states
from service.custom_rules import StateRule, AdminRule, NumericRule, JudgeRule
from service.states import Admin
from service.db_engine import db
from service import keyboards
from service.utils import send_content_page, allow_edit_content, parse_period, FormatDataException
from service.serializers import info_debuff_type, info_debuff_attribute, info_debuff_time, info_debuff_action_time


@bot.on.private_message(StateRule(f"{Admin.SELECT_ACTION}_StateDebuff"), PayloadRule({"StateDebuff": "add"}), OrRule(JudgeRule(), AdminRule()))
async def create_quest(m: Message):
    item = await db.StateDebuff.create()
    states.set(m.from_id, f"{Admin.DEBUFF_NAME}*{item.id}")
    await m.answer("Напишите название дебафа", keyboard=Keyboard())


@bot.on.private_message(StateRule(Admin.DEBUFF_NAME), OrRule(JudgeRule(), AdminRule()))
@allow_edit_content('StateDebuff', state=Admin.DEBUFF_TYPE)
async def debuff_name(m: Message, item_id: int, editing_content: bool):
    await db.StateDebuff.update.values(name=m.text).where(db.StateDebuff.id == item_id).gino.status()
    if not editing_content:
        reply, keyboard = await info_debuff_type()
        await m.answer(reply, keyboard=keyboard)


@bot.on.private_message(StateRule(Admin.DEBUFF_TYPE), PayloadMapRule({"debuff_type_id": int}), OrRule(JudgeRule(), AdminRule()))
@allow_edit_content('StateDebuff', state=Admin.DEBUFF_ATTRIBUTE)
async def debuff_type(m: Message, item_id: int, editing_content: bool):
    await db.StateDebuff.update.values(type_id=m.payload['debuff_type_id']).where(db.StateDebuff.id == item_id).gino.status()
    if not editing_content:
        reply, keyboard = await info_debuff_attribute()
        await m.answer(reply, keyboard=keyboard)


@bot.on.private_message(StateRule(Admin.DEBUFF_ATTRIBUTE), PayloadMapRule({"debuff_attribute_id": int}), OrRule(JudgeRule(), AdminRule()))
@allow_edit_content('StateDebuff', state=Admin.DEBUFF_PENALTY,
                    text='Укажите штраф, который будет выдаваться к этой характеристике (!! со знаком минус)', keyboard=Keyboard())
async def debuff_attribute(m: Message, item_id: int, editing_content: bool):
    await db.StateDebuff.update.values(attribute_id=m.payload['debuff_attribute_id']).where(db.StateDebuff.id == item_id).gino.status()


@bot.on.private_message(StateRule(Admin.DEBUFF_PENALTY), NumericRule(min_number=-200, max_number=200), OrRule(JudgeRule(), AdminRule()))
@allow_edit_content('StateDebuff', state=Admin.DEBUFF_ACTION_TIME,)
async def debuff_penalty(m: Message, value: int, item_id: int, editing_content: bool):
    await db.StateDebuff.update.values(penalty=value).where(db.StateDebuff.id == item_id).gino.status()
    if not editing_content:
        reply, keyboard = await info_debuff_action_time()
        await m.answer(reply, keyboard=keyboard)


@bot.on.private_message(StateRule(Admin.DEBUFF_ACTION_TIME), PayloadRule({'debuff_action_time': 'null'}), OrRule(JudgeRule(), AdminRule()))
@allow_edit_content('StateDebuff', state=Admin.DEBUFF_TIME)
async def set_debuf_action_time_null(m: Message, item_id, editing_content):
    if not editing_content:
        reply, keyboard = await info_debuff_time()
        await m.answer(reply, keyboard=keyboard)


@bot.on.private_message(StateRule(Admin.DEBUFF_ACTION_TIME), NumericRule(), OrRule(JudgeRule(), AdminRule()))
@allow_edit_content('StateDebuff', state=Admin.DEBUFF_TIME)
async def set_debuf_action_time_null(m: Message, item_id, editing_content, value):
    await db.StateDebuff.update.values(action_time=value).where(db.StateDebuff.id == item_id).gino.status()
    if not editing_content:
        reply, keyboard = await info_debuff_time()
        await m.answer(reply, keyboard=keyboard)


@bot.on.private_message(StateRule(Admin.DEBUFF_TIME), PayloadRule({'debuff_time': 'infinity'}), OrRule(JudgeRule(), AdminRule()))
@allow_edit_content('StateDebuff', text='Дебаф успешно создан', end=True)
async def set_infinity_debuff_time(m: Message, item_id, editing_content):
    pass


@bot.on.private_message(StateRule(Admin.DEBUFF_TIME), OrRule(JudgeRule(), AdminRule()))
@allow_edit_content('StateDebuff', text='Дебаф успешно создан', end=True)
async def set_infinity_debuff_time(m: Message, item_id, editing_content):
    try:
        seconds = parse_period(m.text)
    except:
        raise FormatDataException('Неправильный формат записи периода')
    if not seconds:
        raise FormatDataException('Не указано время')
    await db.StateDebuff.update.values(time_use=seconds).where(db.StateDebuff.id == item_id).gino.status()


@bot.on.private_message(StateRule(f"{Admin.SELECT_ACTION}_StateDebuff"), PayloadRule({"StateDebuff": "delete"}), OrRule(JudgeRule(), AdminRule()))
async def select_delete_quest(m: Message):
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
    item_id = await db.select([db.StateDebuff.id]).order_by(db.StateDebuff.id.asc()).offset(value - 1).limit(1).gino.scalar()
    await db.StateDebuff.delete.where(db.StateDebuff.id == item_id).gino.status()
    items = await db.select([db.Item.id, db.Item.bonus]).gino.all()
    for item_id, item_bonus in items:
        for i, bonus in enumerate(item_bonus):
            if bonus.get('type') == 'state' and bonus.get('action') in ('add', 'delete') and bonus.get('debuff_id') == item_bonus:
                item_bonus.pop(i)
                await db.Item.update.values(bonus=item_bonus).where(db.Item.id == item_id).gino.status()
                break
    states.set(m.peer_id, f"{Admin.SELECT_ACTION}_StateDebuff")
    await m.answer("Дебаф успешно удален", keyboard=keyboards.gen_type_change_content("StateDebuff"))
    await send_content_page(m, "StateDebuff", 1)
