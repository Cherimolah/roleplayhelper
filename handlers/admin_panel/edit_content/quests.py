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
from service.utils import parse_period, send_content_page, allow_edit_content, FormatDataException
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
        raise FormatDataException("Неправильный формат даты время")
    if day < datetime.datetime.now():
        raise FormatDataException("Укажите время в будущем")
    end_at = await db.select([db.Quest.closed_at]).where(db.Quest.id == quest_id).gino.scalar()
    if end_at and day >= end_at:
        raise FormatDataException("Начало квеста позже, чем его начало")
    await db.Quest.update.values(start_at=day).where(db.Quest.id == quest_id).gino.status()


@bot.on.private_message(StateRule(Admin.QUEST_END_DATE), PayloadRule({"quest_always": True}), AdminRule())
@allow_edit_content("Quest", state=Admin.QUEST_EXECUTION_TIME, text="Время окончание квеста установлено. Теперь напишите время, которое будет даваться "
                   "на выполнение квеста. Например: 2 дня 1 час 32 сек", keyboard=Keyboard().add(
        Text("Бессрочно", {"quest_forever": True})
    ))
async def set_quest_always(m: Message):
    quest_id = int(states.get(m.peer_id).split("*")[1])
    await db.Quest.update.values(closed_at=None).where(db.Quest.id == quest_id).gino.status()


@bot.on.private_message(StateRule(Admin.QUEST_END_DATE), AdminRule())
@allow_edit_content("Quest", state=Admin.QUEST_EXECUTION_TIME, text="Время окончание квеста установлено. Теперь напишите время, которое будет даваться "
                   "на выполнение квеста. Например: 2 дня 1 час 32 сек", keyboard=Keyboard().add(
        Text("Бессрочно", {"quest_forever": True})
    ))
async def end_date_quest(m: Message):
    quest_id = int(states.get(m.peer_id).split("*")[1])
    try:
        day = datetime.datetime.strptime(m.text, DATETIME_FORMAT)
    except:
        raise FormatDataException("Неправильный формат даты время")
    if day < datetime.datetime.now():
        raise FormatDataException("Укажите время в будущем")
    start_date = await db.select([db.Quest.start_at]).where(db.Quest.id == quest_id).gino.scalar()
    if start_date >= day:
        raise FormatDataException("Квест заканчивается раньше, чем начинается. Не логично, как-то что ли")
    await db.Quest.update.values(closed_at=day).where(db.Quest.id == quest_id).gino.status()


@bot.on.private_message(StateRule(Admin.QUEST_EXECUTION_TIME), PayloadMapRule({"quest_forever": bool}), AdminRule())
@allow_edit_content("Quest", state=Admin.QUEST_FRACTION)
async def quest_forever(m: Message):
    quest_id = int(states.get(m.peer_id).split("*")[1])
    await db.Quest.update.values(execution_time=None).where(db.Quest.id == quest_id).gino.status()
    fractions = [x[0] for x in await db.select([db.Fraction.name]).order_by(db.Fraction.id.asc()).gino.all()]
    reply = "Теперь укажи номер фракции, к которой будет бонус к репутации:\n\n"
    for i, name in enumerate(fractions):
        reply += f"{i + 1}. {name}\n"
    await m.answer(reply, keyboard=keyboards.without_fraction_bonus)


@bot.on.private_message(StateRule(Admin.QUEST_EXECUTION_TIME), AdminRule())
@allow_edit_content("Quest", state=Admin.QUEST_FRACTION)
async def quest_expiration_time(m: Message):
    quest_id = int(states.get(m.peer_id).split("*")[1])
    seconds = parse_period(m.text)
    if not seconds:
        raise FormatDataException("Формат периода неверный")
    start_at, end_at = await db.select([db.Quest.start_at, db.Quest.closed_at]).where(db.Quest.id == quest_id).gino.first()
    if seconds > (end_at - start_at).total_seconds():
        raise FormatDataException("Время на выполнение квеста больше, чем время жизни квеста")
    await db.Quest.update.values(execution_time=seconds).where(db.Quest.id == quest_id).gino.scalar()
    fractions = [x[0] for x in await db.select([db.Fraction.name]).order_by(db.Fraction.id.asc()).gino.all()]
    reply = "Теперь укажи номер фракции, к которой будет бонус к репутации:\n\n"
    for i, name in enumerate(fractions):
        reply += f"{i + 1}. {name}\n"
    await m.answer(reply, keyboard=keyboards.without_fraction_bonus)


@bot.on.private_message(StateRule(Admin.QUEST_FRACTION), PayloadRule({"withot_fraction_bonus": True}), AdminRule())
@allow_edit_content("Quest", text="Квест успешно создан без бонуса к репутации", end=True)
async def save_daylic_without_bonus(m: Message):
    quest_id = int(states.get(m.from_id).split("*")[-1])
    await db.Quest.update.values(fraction_id=None, reputation=0).where(db.Quest.id == quest_id).gino.status()


@bot.on.private_message(StateRule(Admin.QUEST_FRACTION), NumericRule(), AdminRule())
@allow_edit_content("Quest", text="Номер фракции установлен теперь укажи бонус к репутации числом",
                    state=Admin.QUEST_REPUTATION)
async def set_daylic_fraction(m: Message, value: int):
    quest_id = int(states.get(m.from_id).split("*")[-1])
    fractions = [x[0] for x in await db.select([db.Fraction.id]).order_by(db.Fraction.id.asc()).gino.all()]
    if value > len(fractions):
        raise FormatDataException("Номер фракции слишком большой")
    fraction_id = fractions[value - 1]
    await db.Quest.update.values(fraction_id=fraction_id).where(db.Quest.id == quest_id).gino.status()


@bot.on.private_message(StateRule(Admin.QUEST_REPUTATION), AdminRule())
@allow_edit_content("Quest", text="Квест успешно создан с бонусом к репутации", end=True)
async def save_daylic_with_bonus(m: Message):
    try:
        value = int(m.text)
    except ValueError:
        raise FormatDataException("Необходимо ввести целое число")

    quest_id = int(states.get(m.from_id).split("*")[-1])
    fraction_id = await db.select([db.Quest.fraction_id]).where(db.Quest.id == quest_id).gino.scalar()
    if not fraction_id and value != 0:
        raise FormatDataException("Бонус к репутации может быть установлен только, когда есть фракция\n"
                                  "Установите сначала фракцию, потом бонус к репутации\n\n"
                                  "Введите 0, чтобы выйти из режима редактирования репутации")

    if not -200 <= value <= 200:
        raise FormatDataException("Диапазон значений [-200; 200]")
    await db.Quest.update.values(reputation=value).where(db.Quest.id == quest_id).gino.status()


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
