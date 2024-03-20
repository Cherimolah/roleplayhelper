from vkbottle.bot import Message
from vkbottle.dispatch.rules.base import PayloadRule
from vkbottle import Keyboard

from loader import bot
from service.custom_rules import AdminRule, StateRule, NumericRule
from service.states import Admin
from service.db_engine import db
from service.middleware import states
from service import keyboards


@bot.on.private_message(PayloadRule({"events": "add"}), StateRule(Admin.SELECT_ACTION), AdminRule())
async def create_event(m: Message):
    event = await db.Event.create()
    states.set(m.from_id, f"{Admin.EVENT_NAME}*{event.id}")
    await bot.write_msg(m.peer_id, "Введите название события", keyboard=Keyboard())


@bot.on.private_message(StateRule(Admin.EVENT_NAME, True), AdminRule())
async def set_name_event(m: Message):
    event_id = int(states.get(m.from_id).split("*")[-1])
    await db.Event.update.values(title=m.text).where(db.Event.id == event_id).gino.status()
    states.set(m.from_id, f"{Admin.EVENT_DESCRIPTION}*{event_id}")
    await bot.write_msg(m.peer_id, "Название установлено. Теперь введите описание события")


@bot.on.private_message(StateRule(Admin.EVENT_DESCRIPTION, True), AdminRule())
async def set_name_description(m: Message):
    event_id = int(states.get(m.from_id).split("*")[-1])
    await db.Event.update.values(description=m.text).where(db.Event.id == event_id).gino.status()
    states.set(m.from_id, f"{Admin.EVENT_MASK}*{event_id}")
    await bot.write_msg(m.peer_id, "Описание установлено. Создайте маску выполненного события.\n"
                                   "Например: {s} выполняет Убийство {o}\n"
                                   "Здесь {s} (субъект) - тот кто, выполняет действие\n"
                                   "{o} (объект) - тот, над кем выполняют действие\n")


@bot.on.private_message(StateRule(Admin.EVENT_MASK, True), AdminRule())
async def set_mask_event(m: Message):
    event_id = int(states.get(m.from_id).split("*")[-1])
    await db.Event.update.values(mask=m.text).where(db.Event.id == event_id).gino.status()
    states.set(m.from_id, Admin.SELECT_ACTION)
    event = await db.select([*db.Event]).where(db.Event.id == event_id).gino.first()
    await bot.write_msg(m.peer_id, f"Квест {event.title} успешно создан\n"
                                   f"Описание: {event.description}\n"
                                   f"Маска: {event.mask}", keyboard=keyboards.gen_type_change_content("events"))


@bot.on.private_message(StateRule(Admin.SELECT_ACTION), PayloadRule({"events": "delete"}), AdminRule())
async def select_event_delete(m: Message):
    events = await db.select([db.Event.title]).order_by(db.Event.id).gino.all()
    if not events:
        await bot.write_msg(m.peer_id, "Никаких событий ещё не было создано")
        return
    reply = "Выберите событие, которое хотите удалить:\n\n"
    for i, event in enumerate(events):
        reply = f"{reply}{i + 1}. {event.title}\n"
    states.set(m.from_id, Admin.EVENT_SELECT_ID)
    await bot.write_msg(m.peer_id, reply)


@bot.on.private_message(StateRule(Admin.EVENT_SELECT_ID), NumericRule(), AdminRule())
async def delete_event(m: Message, value: int):
    event_id, event_name = await db.select([db.Event.id, db.Event.title]).order_by(db.Event.id).offset(value - 1).gino.first()
    await db.Event.delete.where(db.Event.id == event_id).gino.status()
    states.set(m.from_id, Admin.SELECT_ACTION)
    await bot.write_msg(m.from_id, f"Событие {event_name} удалено",
                        keyboard=keyboards.gen_type_change_content("events"))
