from vkbottle.bot import Message
from vkbottle import Keyboard, Text, KeyboardButtonColor
from vkbottle.dispatch.rules.base import PayloadRule, PayloadMapRule, AttachmentTypeRule

from loader import bot, states
from service.custom_rules import StateRule, AdminRule, NumericRule
from service.states import Admin
from service.db_engine import db
from service import keyboards
from service.utils import send_content_page, allow_edit_content, FormatDataException, reload_image
from service.serializers import info_debuff_type, info_debuff_attribute


@bot.on.private_message(StateRule(f"{Admin.SELECT_ACTION}_StateDebuff"), PayloadRule({"StateDebuff": "add"}), AdminRule())
async def create_quest(m: Message):
    item = await db.StateDebuff.create()
    states.set(m.from_id, f"{Admin.DEBUFF_NAME}*{item.id}")
    await m.answer("Напишите название дебафа", keyboard=Keyboard())


@bot.on.private_message(StateRule(Admin.DEBUFF_NAME), AdminRule())
@allow_edit_content('StateDebuff', state=Admin.DEBUFF_TYPE)
async def debuff_name(m: Message, item_id: int, editing_content: bool):
    await db.StateDebuff.update.values(name=m.text).where(db.StateDebuff.id == item_id).gino.status()
    if not editing_content:
        reply, keyboard = await info_debuff_type()
        await m.answer(reply, keyboard=keyboard)


@bot.on.private_message(StateRule(Admin.DEBUFF_TYPE), PayloadMapRule({"debuff_type_id": int}), AdminRule())
@allow_edit_content('StateDebuff', state=Admin.DEBUFF_ATTRIBUTE)
async def debuff_type(m: Message, item_id: int, editing_content: bool):
    await db.StateDebuff.update.values(type_id=m.payload['debuff_type_id']).where(db.StateDebuff.id == item_id).gino.status()
    if not editing_content:
        reply, keyboard = await info_debuff_attribute()
        await m.answer(reply, keyboard=keyboard)


@bot.on.private_message(StateRule(Admin.DEBUFF_ATTRIBUTE), PayloadMapRule({"debuff_attribute_id": int}), AdminRule())
@allow_edit_content('StateDebuff', state=Admin.DEBUFF_PENALTY,
                    text='Укажите штраф, который будет выдаваться к этой характеристике (!! со знаком минус)', keyboard=Keyboard())
async def debuff_attribute(m: Message, item_id: int, editing_content: bool):
    await db.StateDebuff.update.values(attribute_id=m.payload['debuff_attribute_id']).where(db.StateDebuff.id == item_id).gino.status()


@bot.on.private_message(StateRule(Admin.DEBUFF_PENALTY), NumericRule(min_number=-200, max_number=200), AdminRule())
@allow_edit_content('StateDebuff', text='Дебаф успешно создан', end=True)
async def debuff_penalty(m: Message, value: int, item_id: int, editing_content: bool):
    await db.StateDebuff.update.values(penalty=value).where(db.StateDebuff.id == item_id).gino.status()


@bot.on.private_message(StateRule(f"{Admin.SELECT_ACTION}_StateDebuff"), PayloadRule({"StateDebuff": "delete"}), AdminRule())
async def select_delete_quest(m: Message):
    debuffs = await db.select([db.StateDebuff.name]).order_by(db.StateDebuff.id.asc()).gino.all()
    if not debuffs:
        return "Предметы ещё не созданы"
    reply = "Выберите предмет для удаления:\n\n"
    for i, item in enumerate(debuffs):
        reply = f"{reply}{i + 1}. {item.name}\n"
    states.set(m.peer_id, Admin.DEBUFF_DELETE)
    await m.answer(reply, keyboard=Keyboard())


@bot.on.private_message(StateRule(Admin.DEBUFF_DELETE), NumericRule(), AdminRule())
async def delete_quest(m: Message, value: int):
    item_id = await db.select([db.StateDebuff.id]).order_by(db.StateDebuff.id.asc()).offset(value - 1).limit(1).gino.scalar()
    await db.StateDebuff.delete.where(db.StateDebuff.id == item_id).gino.status()
    states.set(m.peer_id, f"{Admin.SELECT_ACTION}_StateDebuff")
    await m.answer("Дебаф успешно удален", keyboard=keyboards.gen_type_change_content("StateDebuff"))
    await send_content_page(m, "StateDebuff", 1)
