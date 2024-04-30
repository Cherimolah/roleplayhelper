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
from service.utils import parse_period, send_content_page, allow_edit_content
from config import DATETIME_FORMAT


@bot.on.private_message(StateRule(f"{Admin.SELECT_ACTION}_Quest"), PayloadRule({"Quest": "add"}), AdminRule())
async def create_quest(m: Message):
    quest = await db.Quest.create()
    states.set(m.from_id, f"{Admin.QUEST_NAME}*{quest.id}")
    await m.answer("Напишите название квеста", keyboard=Keyboard())


@bot.on.private_message(StateRule(Admin.QUEST_NAME), AdminRule())
@allow_edit_content("Quest", state=Admin.QUEST_DESCRIPTION,
                    text="Название квеста установлено. Теперь пришлите описание квеста")
async def name_quest(m: Message):
    quest_id = int(states.get(m.peer_id).split("*")[1])
    await db.Quest.update.values(name=m.text).where(db.Quest.id == quest_id).gino.status()


@bot.on.private_message(StateRule(Admin.QUEST_DESCRIPTION), AdminRule())
@allow_edit_content("Quest", state=Admin.QUEST_REWARD,
                    text="Описание квеста записал. Теперь напишите награду за выполнение квеста")
async def description_quest(m: Message):
    quest_id = int(states.get(m.peer_id).split("*")[1])
    await db.Quest.update.values(description=m.text).where(db.Quest.id == quest_id).gino.status()


@bot.on.private_message(StateRule(Admin.QUEST_REWARD), NumericRule(), AdminRule())
@allow_edit_content("Quest", state=Admin.QUEST_START_DATE,
                    text="Награда за квест установлена. Укажите дату и время начала квеста в формате "
                         "ДД.ММ.ГГГГ чч:мм:сс")
async def reward_quest(m: Message, value: int):
    quest_id = int(states.get(m.peer_id).split("*")[1])
    await db.Quest.update.values(reward=value).where(db.Quest.id == quest_id).gino.status()


@bot.on.private_message(StateRule(Admin.QUEST_START_DATE), AdminRule())
@allow_edit_content("Quest", state=Admin.QUEST_END_DATE, text="Дата начала установлена. Укажите дату и время окончания квеста в формате "
                   "ДД.ММ.ГГГГ чч:мм:сс", keyboard=Keyboard().add(
        Text("Навсегда", {"quest_always": True})
    ))
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


@bot.on.private_message(StateRule(Admin.QUEST_END_DATE), PayloadMapRule({"quest_always": bool}), AdminRule())
@allow_edit_content("Quest", state=Admin.QUEST_EXECUTION_TIME, text="Время окончание квеста установлено. Теперь напишите время, которое будет даваться "
                   "на выполнение квеста. Например: 2 дня 1 час 32 сек", keyboard=Keyboard().add(
        Text("Бессрочно", {"quest_forever": True})
    ))
async def set_quest_always(m: Message):
    pass


@bot.on.private_message(StateRule(Admin.QUEST_END_DATE), AdminRule())
@allow_edit_content("Quest", state=Admin.QUEST_EXECUTION_TIME, text="Время окончание квеста установлено. Теперь напишите время, которое будет даваться "
                   "на выполнение квеста в секундах ", keyboard=Keyboard().add(
        Text("Бессрочно", {"quest_forever": True})
    ))
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


@bot.on.private_message(StateRule(Admin.QUEST_EXECUTION_TIME), PayloadMapRule({"quest_forever": bool}), AdminRule())
@allow_edit_content("Quest", state=Admin.SELECT_ACTION, text="Квест успешно создан",
                    keyboard=keyboards.gen_type_change_content("Quest"), end=True)
async def quest_forever(m: Message):
    pass


@bot.on.private_message(StateRule(Admin.QUEST_EXECUTION_TIME), AdminRule())
@allow_edit_content("Quest", state=Admin.SELECT_ACTION, text="Квест успешно создан",
                    keyboard=keyboards.gen_type_change_content("Quest"), end=True)
async def quest_expiration_time(m: Message):
    quest_id = int(states.get(m.peer_id).split("*")[1])
    seconds = parse_period(m)
    await db.Quest.update.values(execution_time=seconds).where(db.Quest.id == quest_id).gino.scalar()


@bot.on.private_message(StateRule(f"{Admin.SELECT_ACTION}_Quest"), PayloadRule({"Quest": "delete"}), AdminRule())
async def select_delete_quest(m: Message):
    quests = await db.select([db.Quest.name]).order_by(db.Quest.id.asc()).gino.all()
    if not quests:
        return "Квесты ещё не созданы"
    reply = "Выберите квест для удаления:\n\n"
    for i, quest in enumerate(quests):
        reply = f"{reply}{i + 1}. {quest.name}\n"
    states.set(m.peer_id, Admin.QUEST_DELETE)
    await m.answer(reply, keyboard=Keyboard())


@bot.on.private_message(StateRule(Admin.QUEST_DELETE), NumericRule(), AdminRule())
async def delete_quest(m: Message, value: int):
    quest_id = await db.select([db.Quest.id]).order_by(db.Quest.id.asc()).offset(value - 1).limit(1).gino.scalar()
    await db.ReadyQuest.delete.where(db.ReadyQuest.quest_id == quest_id).gino.status()
    await db.Quest.delete.where(db.Quest.id == quest_id).gino.status()
    states.set(m.peer_id, f"{Admin.SELECT_ACTION}_Quest")
    await m.answer("Квест успешно удалён", keyboard=keyboards.gen_type_change_content("Quest"))
    await send_content_page(m, "Quest", 1)
