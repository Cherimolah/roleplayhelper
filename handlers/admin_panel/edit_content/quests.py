import datetime

from vkbottle.bot import Message
from vkbottle.dispatch.rules.base import PayloadRule, PayloadMapRule
from vkbottle import Keyboard, Text

import service.keyboards as keyboards
from loader import bot
from service.custom_rules import AdminRule, StateRule, NumericRule
from service.middleware import states
from service.states import Admin
from service.db_engine import db
from service.utils import parse_period
from config import DATETIME_FORMAT


@bot.on.private_message(StateRule(Admin.SELECT_ACTION), PayloadRule({"quests": "add"}), AdminRule())
async def create_quest(m: Message):
    quest = await db.Quest.create()
    states.set(m.from_id, f"{Admin.QUEST_NAME}*{quest.id}")
    await m.answer("Напишите название квеста", keyboard=Keyboard())


@bot.on.private_message(StateRule(Admin.QUEST_NAME, True), AdminRule())
async def name_quest(m: Message):
    quest_id = int(states.get(m.peer_id).split("*")[1])
    await db.Quest.update.values(name=m.text).where(db.Quest.id == quest_id).gino.status()
    states.set(m.peer_id, f"{Admin.QUEST_DESCRIPTION}*{quest_id}")
    await m.answer("Название квеста установлено. Теперь пришлите описание квеста")


@bot.on.private_message(StateRule(Admin.QUEST_DESCRIPTION, True), AdminRule())
async def description_quest(m: Message):
    quest_id = int(states.get(m.peer_id).split("*")[1])
    await db.Quest.update.values(description=m.text).where(db.Quest.id == quest_id).gino.status()
    states.set(m.peer_id, f"{Admin.QUEST_REWARD}*{quest_id}")
    await m.answer("Описание квеста записал. Теперь напишите награду за выполнение квеста")

@bot.on.private_message(StateRule(Admin.QUEST_REWARD, True), NumericRule(), AdminRule())
async def reward_quest(m: Message, value: int):
    quest_id = int(states.get(m.peer_id).split("*")[1])
    await db.Quest.update.values(reward=value).where(db.Quest.id == quest_id).gino.status()
    states.set(m.peer_id, f"{Admin.QUEST_START_DATE}*{quest_id}")
    await m.answer("Награда за квест установлена. Укажите дату и время начала квеста в формате "
                                   "ДД.ММ.ГГГГ чч:мм:сс")


@bot.on.private_message(StateRule(Admin.QUEST_START_DATE, True), AdminRule())
async def start_date_quest(m: Message):
    quest_id = int(states.get(m.peer_id).split("*")[1])
    try:
        day = datetime.datetime.strptime(m.text, DATETIME_FORMAT)
    except:
        await m.answer("Неправильный формат даты время")
        return
    if day < datetime.datetime.now():
        await m.answer("Укажите время в будущем")
        return
    await db.Quest.update.values(start_at=day).where(db.Quest.id == quest_id).gino.status()
    states.set(m.peer_id, f"{Admin.QUEST_END_DATE}*{quest_id}")
    keyboard = Keyboard().add(
        Text("Навсегда", {"quest_always": quest_id})
    )
    await m.answer("Дата начала установлена. Укажите дату и время окончания квеста в формате "
                                   "ДД.ММ.ГГГГ чч:мм:сс", keyboard=keyboard)


@bot.on.private_message(StateRule(Admin.QUEST_END_DATE, True), PayloadMapRule({"quest_always": int}), AdminRule())
async def set_quest_always(m: Message):
    quest_id = int(states.get(m.peer_id).split("*")[1])
    states.set(m.peer_id, f"{Admin.QUEST_EXECUTION_TIME}*{quest_id}")
    keyboard = Keyboard().add(
        Text("Бессрочно", {"quest_forever": quest_id})
    )
    await m.answer("Время окончание квеста установлено. Теперь напишите время, которое будет даваться "
                                   "на выполнение квеста. Например: 2 дня 1 час 32 сек",
                        keyboard=keyboard)


@bot.on.private_message(StateRule(Admin.QUEST_END_DATE, True), AdminRule())
async def end_date_quest(m: Message):
    quest_id = int(states.get(m.peer_id).split("*")[1])
    try:
        day = datetime.datetime.strptime(m.text, DATETIME_FORMAT)
    except:
        await m.answer("Неправильный формат даты время")
        return
    if day < datetime.datetime.now():
        await m.answer("Укажите время в будущем")
        return
    start_date = await db.select([db.Quest.start_at]).where(db.Quest.id == quest_id).gino.scalar()
    if start_date >= day:
        await m.answer("Квест заканчивается раньше, чем начинается. Не логично, как-то что ли")
        return
    await db.Quest.update.values(closed_at=day).where(db.Quest.id == quest_id).gino.status()
    states.set(m.peer_id, f"{Admin.QUEST_EXECUTION_TIME}*{quest_id}")
    keyboard = Keyboard().add(
        Text("Бессрочно", {"quest_forever": quest_id})
    )
    await m.answer("Время окончание квеста установлено. Теперь напишите время, которое будет даваться "
                                   "на выполнение квеста в секундах ", keyboard=keyboard)


@bot.on.private_message(StateRule(Admin.QUEST_EXECUTION_TIME, True), PayloadMapRule({"quest_forever": int}), AdminRule())
async def quest_forever(m: Message):
    quest_id = int(states.get(m.peer_id).split("*")[1])
    states.set(m.peer_id, Admin.SELECT_ACTION)
    name = await db.select([db.Quest.name]).where(db.Quest.id == quest_id).gino.scalar()
    await m.answer(f"Квест «{name}» создан", keyboard=keyboards.gen_type_change_content("quests"))


@bot.on.private_message(StateRule(Admin.QUEST_EXECUTION_TIME, True), AdminRule())
async def quest_expiration_time(m: Message):
    quest_id = int(states.get(m.peer_id).split("*")[1])
    states.set(m.peer_id, Admin.SELECT_ACTION)
    seconds = parse_period(m)
    name = await db.select([db.Quest.name]).where(db.Quest.id == quest_id).gino.scalar()
    await db.Quest.update.values(execution_time=seconds).where(db.Quest.id == quest_id).gino.scalar()
    await m.answer(f"Квест «{name}» создан", keyboard=keyboards.gen_type_change_content("quests"))


@bot.on.private_message(StateRule(Admin.SELECT_ACTION), PayloadRule({"quests": "delete"}), AdminRule())
async def select_delete_quest(m: Message):
    quests = await db.select([db.Quest.name]).gino.all()
    reply = "Выберите квест для удаления:\n\n"
    for i, quest in enumerate(quests):
        reply = f"{reply}{i + 1}. {quest.name}\n"
    states.set(m.peer_id, Admin.QUEST_DELETE)
    await m.answer(reply, keyboard=Keyboard())


@bot.on.private_message(StateRule(Admin.QUEST_DELETE), NumericRule(), AdminRule())
async def delete_quest(m: Message, value: int):
    quest_id = await db.select([db.Quest.id]).offset(value - 1).limit(1).gino.scalar()
    await db.ReadyQuest.delete.where(db.ReadyQuest.quest_id == quest_id).gino.status()
    await db.Quest.delete.where(db.Quest.id == quest_id).gino.status()
    states.set(m.peer_id, Admin.SELECT_ACTION)
    await m.answer("Квест успешно удалён", keyboard=keyboards.gen_type_change_content("quests"))
