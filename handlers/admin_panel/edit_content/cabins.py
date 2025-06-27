from vkbottle.bot import Message
from vkbottle.dispatch.rules.base import PayloadRule
from vkbottle import Keyboard

import messages
import service.keyboards as keyboards
from loader import bot
from service.custom_rules import AdminRule, StateRule, NumericRule
from service.middleware import states
from service.states import Admin
from service.db_engine import db
from service.utils import send_content_page, allow_edit_content


@bot.on.private_message(StateRule(f"{Admin.SELECT_ACTION}_Cabins"), PayloadRule({"Cabins": "add"}), AdminRule())
async def create_new_cabin(m: Message):
    cabin = await db.Cabins.create()
    states.set(m.from_id, f"{Admin.NAME_CABIN}*{cabin.id}")
    await m.answer(messages.name_cabin, keyboard=Keyboard())


@bot.on.private_message(StateRule(Admin.NAME_CABIN), AdminRule())
@allow_edit_content("Cabins", text=messages.price_cabin, keyboard=Keyboard(), state=Admin.PRICE_CABIN)
async def set_name_cabin(m: Message, item_id: int, editing_content: bool):
    await db.Cabins.update.values(name=m.text).where(db.Cabins.id == item_id).gino.status()


@bot.on.private_message(StateRule(Admin.PRICE_CABIN), NumericRule(), AdminRule())
@allow_edit_content("Cabins",
                    text="Цена каюты установлена. Теперь укажите сколько будет слотов под обычный декор",
                    state=Admin.DECOR_SLOTS_CABINS)
async def set_price_cabin(m: Message, value: int, item_id: int, editing_content: bool):
    await db.Cabins.update.values(cost=value).where(db.Cabins.id == item_id).gino.status()


@bot.on.private_message(StateRule(Admin.DECOR_SLOTS_CABINS), AdminRule(), NumericRule())
@allow_edit_content("Cabins", state=Admin.FUNC_PRODUCTS_CABINS,
                    text="Количество слотов под обычный декор успешно записано. "
                         "Теперь укажите количество слотов для функциональных товаров")
async def set_decor_cabins(m: Message, value: int, item_id: int, editing_content: bool):
    await db.Cabins.update.values(decor_slots=value).where(db.Cabins.id == item_id).gino.status()


@bot.on.private_message(StateRule(Admin.FUNC_PRODUCTS_CABINS), AdminRule(), NumericRule())
@allow_edit_content("Cabins", state=f"{Admin.SELECT_ACTION}_Cabins", text=messages.cabin_added, end=True)
async def set_func_slots(m: Message, value: int, item_id: int, editing_content: bool):
    await db.Cabins.update.values(functional_slots=value).where(db.Cabins.id == item_id).gino.status()


@bot.on.private_message(StateRule(f"{Admin.SELECT_ACTION}_Cabins"), PayloadRule({"Cabins": "delete"}), AdminRule())
async def select_cabin_to_delete(m: Message):
    cabins = await db.select([db.Cabins.name, db.Cabins.cost]).order_by(db.Cabins.id.asc()).gino.all()
    if not cabins:
        return "Типы кают ещё не были созданы"
    reply = messages.cabin_type
    for i, cabin in enumerate(cabins):
        reply = f"{reply}{i+1}. {cabin.name} {cabin.cost}\n"
    states.set(m.from_id, Admin.ID_CABIN)
    await m.answer(reply, keyboard=Keyboard())


@bot.on.private_message(StateRule(Admin.ID_CABIN), NumericRule(), AdminRule())
async def delete_cabin(m: Message, value: int):
    cabin_id = await db.select([db.Cabins.id]).order_by(db.Cabins.id.asc()).offset(value-1).limit(1).gino.scalar()
    await db.Cabins.delete.where(db.Cabins.id == cabin_id).gino.status()
    states.set(m.from_id, f"{Admin.SELECT_ACTION}_Cabins")
    await m.answer(messages.cabin_deleted, keyboard=keyboards.gen_type_change_content("Cabins"))
    await send_content_page(m, "Cabins", 1)
