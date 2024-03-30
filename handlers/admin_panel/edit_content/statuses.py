from vkbottle.bot import Message
from vkbottle.dispatch.rules.base import PayloadRule
from vkbottle import Keyboard

import service.keyboards as keyboards
from loader import bot
from service.custom_rules import AdminRule, StateRule, NumericRule
from service.middleware import states
from service.states import Admin
from service.db_engine import db


@bot.on.private_message(StateRule(Admin.SELECT_ACTION), PayloadRule({"statuses": "add"}), AdminRule())
async def start_create_new_atatus(m: Message):
    status = await db.Status.create()
    states.set(m.from_id, f"{Admin.ENTER_NAME_STATUS}*{status.id}")
    await m.answer("Введите название статуса", keyboard=Keyboard())


@bot.on.private_message(StateRule(Admin.ENTER_NAME_STATUS, True), AdminRule())
async def new_status(m: Message):
    status_id = int(states.get(m.from_id).split("*")[1])
    await db.Status.update.values(name=m.text).where(db.Status.id == status_id).gino.status()
    states.set(m.from_id, Admin.SELECT_ACTION)
    await m.answer("Статус успешно создан", keyboard=keyboards.gen_type_change_content("statuses"))


@bot.on.private_message(StateRule(Admin.SELECT_ACTION), PayloadRule({"statuses": "delete"}), AdminRule())
async def select_status_to_delete(m: Message):
    statuses = await db.select([db.Status.name]).gino.all()
    reply = "Выберите статус для удаления: \n\n"
    for i, status in enumerate(statuses):
        reply = f"{reply}{i+1}. {status.name}\n"
    states.set(m.from_id, Admin.ID_STATUS)
    await m.answer(reply, keyboard=Keyboard())


@bot.on.private_message(StateRule(Admin.ID_STATUS), NumericRule(), AdminRule())
async def delete_status(m: Message, value: int = None):
    await db.Status.delete.where(db.Status.id == value).gino.status()
    states.set(m.from_id, Admin.SELECT_ACTION)
    await m.answer("Статус успешно удалён", keyboard=keyboards.gen_type_change_content("statuses"))
