from vkbottle.bot import Message
from vkbottle.dispatch.rules.base import PayloadRule, PayloadMapRule
from vkbottle import Keyboard

import messages
import service.keyboards as keyboards
from loader import bot
from service.custom_rules import AdminRule, StateRule, NumericRule
from service.middleware import states
from service.states import Admin
from service.db_engine import db
from service.utils import send_content_page, allow_edit_content


@bot.on.private_message(StateRule(f"{Admin.SELECT_ACTION}_Profession"), PayloadRule({"Profession": "add"}), AdminRule())
async def select_action_profession(m: Message):
    profession = await db.Profession.create()
    states.set(m.from_id, f"{Admin.NAME_PROFESSION}*{profession.id}")
    await m.answer(messages.profession_name_add, keyboard=Keyboard())


@bot.on.private_message(StateRule(Admin.NAME_PROFESSION), AdminRule())
@allow_edit_content("Profession", text=messages.profession_salary, state=Admin.SALARY_PROFESSION)
async def set_name_profession(m: Message, item_id: int, editing_content: bool):
    await db.Profession.update.values(name=m.text).where(db.Profession.id == item_id).gino.status()


@bot.on.private_message(StateRule(Admin.SALARY_PROFESSION), NumericRule(), AdminRule())
@allow_edit_content("Profession", text=messages.profession_special,
                    keyboard=keyboards.select_type_profession, state=Admin.HIDDEN_PROFESSION)
async def set_salary_profession(m: Message, value: int, item_id: int, editing_content: bool):
    await db.Profession.update.values(salary=value).where(db.Profession.id == item_id).gino.status()


@bot.on.private_message(StateRule(Admin.HIDDEN_PROFESSION), PayloadMapRule({"service_profession": bool}), AdminRule())
@allow_edit_content("Profession", text=messages.proffesion_added,
                    keyboard=keyboards.gen_type_change_content("Profession"), state=f"{Admin.SELECT_ACTION}_Profession",
                    end=True)
async def set_special_profession(m: Message, item_id: int, editing_content: bool):
    await db.Profession.update.values(special=m.payload['service_profession']).where(
        db.Profession.id == item_id).gino.status()


@bot.on.private_message(StateRule(f"{Admin.SELECT_ACTION}_Profession"), PayloadRule({"Profession": "delete"}),
                        AdminRule())
async def select_id_to_delete_profession(m: Message):
    reply = messages.professions_list
    professions = await db.select([db.Profession.name]).order_by(db.Profession.id.asc()).gino.all()
    if not professions:
        return "Профессии ещё не созданы"
    for i, profession in enumerate(professions):
        reply = f"{reply}{i + 1}. {profession.name}\n"
    states.set(m.from_id, Admin.ID_PROFESSION)
    await m.answer(reply)


@bot.on.private_message(StateRule(Admin.ID_PROFESSION), NumericRule(), AdminRule())
async def delete_profession(m: Message, value: int):
    profession_id = await db.select([db.Profession.id]).order_by(db.Profession.id.asc()).offset(value - 1).limit(1).gino.scalar()
    await db.Profession.delete.where(db.Profession.id == profession_id).gino.status()
    states.set(m.from_id, f"{Admin.SELECT_ACTION}_Profession")
    await m.answer(messages.profession_deleted,
                   keyboard=keyboards.gen_type_change_content("Profession"))
    await send_content_page(m, "Profession", 1)
