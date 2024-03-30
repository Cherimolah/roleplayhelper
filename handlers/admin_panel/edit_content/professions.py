from vkbottle.bot import Message
from vkbottle.dispatch.rules.base import PayloadRule, PayloadMapRule
from vkbottle import Keyboard, Text, KeyboardButtonColor

import messages
import service.keyboards as keyboards
from loader import bot
from service.custom_rules import AdminRule, StateRule, NumericRule
from service.middleware import states
from service.states import Admin
from service.db_engine import db


@bot.on.private_message(StateRule(Admin.SELECT_ACTION), PayloadRule({"professions": "add"}), AdminRule())
async def select_action_profession(m: Message):
    profession = await db.Profession.create()
    states.set(m.from_id, f"{Admin.NAME_PROFESSION}*{profession.id}")
    await m.answer(messages.profession_name_add, keyboard=Keyboard())


@bot.on.private_message(StateRule(Admin.NAME_PROFESSION, True), AdminRule())
async def set_name_profession(m: Message):
    profession_id = int(states.get(m.from_id).split("*")[1])
    await db.Profession.update.values(name=m.text).where(db.Profession.id == profession_id).gino.status()
    states.set(m.from_id, f"{Admin.SALARY_PROFESSION}*{profession_id}")
    await m.answer(messages.profession_salary)


@bot.on.private_message(StateRule(Admin.SALARY_PROFESSION, True), NumericRule(), AdminRule())
async def set_salary_profession(m: Message):
    profession_id = int(states.get(m.from_id).split("*")[1])
    await db.Profession.update.values(salary=int(m.text)).where(db.Profession.id == profession_id).gino.status()
    states.set(m.from_id, f"{Admin.HIDDEN_PROFESSION}*{profession_id}")
    keyboard = Keyboard().add(
        Text("Обычная", {"service_profession": False}), KeyboardButtonColor.POSITIVE
    ).row().add(
        Text("Специальная", {"service_profession": True}), KeyboardButtonColor.NEGATIVE
    )
    await m.answer(messages.profession_special, keyboard=keyboard)


@bot.on.private_message(StateRule(Admin.HIDDEN_PROFESSION, True), PayloadMapRule({"service_profession": bool}), AdminRule())
async def set_special_profession(m: Message):
    profession_id = int(states.get(m.from_id).split("*")[1])
    await db.Profession.update.values(special=m.payload['service_profession']).where(db.Profession.id == profession_id).gino.status()
    states.set(m.from_id, Admin.SELECT_ACTION)
    await m.answer(messages.proffesion_added, keyboard=keyboards.gen_type_change_content("professions"))


@bot.on.private_message(StateRule(Admin.SELECT_ACTION), PayloadRule({"professions": "delete"}), AdminRule())
async def select_id_to_delete_profession(m: Message):
    reply = messages.professions_list
    professions = await db.select([db.Profession.name]).gino.all()
    for i, profession in enumerate(professions):
        reply = f"{reply}{i+1}. {profession.name}\n"
    states.set(m.from_id, Admin.ID_PROFESSION)
    await m.answer(reply)


@bot.on.private_message(StateRule(Admin.ID_PROFESSION), NumericRule(), AdminRule())
async def delete_profession(m: Message, value: int):
    profession_id = await db.select([db.Profession.id]).offset(value-1).limit(1).gino.scalar()
    await db.Profession.delete.where(db.Profession.id == profession_id).gino.status()
    states.set(m.from_id, Admin.SELECT_ACTION)
    await m.answer(messages.profession_deleted,
                        keyboard=keyboards.gen_type_change_content("professions"))
