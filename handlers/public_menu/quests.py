import asyncio
import datetime
from typing import Union

from vkbottle.bot import Message, MessageEvent
from vkbottle import Keyboard, KeyboardButtonColor, Callback, Text, GroupEventType
from vkbottle.dispatch.rules.base import PayloadRule, PayloadMapRule
from sqlalchemy import and_, func, or_

from loader import bot
from service.custom_rules import StateRule
from service.states import Menu
from service.db_engine import db
from service.utils import get_current_form_id, parse_cooldown, quest_over
from service import keyboards
from service.middleware import states
from config import ADMINS, OWNER


async def send_quest_page(m: Union[Message, MessageEvent], page: int):
    if isinstance(m, Message):
        user_id = m.from_id
    else:
        user_id = m.user_id
    form_id = await get_current_form_id(user_id)
    ready_quests = [x[0] for x in
                    await db.select([db.ReadyQuest.quest_id]).where(db.ReadyQuest.form_id == form_id).gino.all()]
    active_quest = await db.select([db.Form.active_quest]).where(db.Form.id == form_id).gino.scalar()
    if active_quest:
        ready_quests.append(active_quest)
    quest = await (
        db.select([*db.Quest])
        .where(and_(db.Quest.id.notin_(ready_quests),
                    or_(db.Quest.closed_at > datetime.datetime.now(), db.Quest.closed_at.is_(None)))).limit(
            1).offset(page - 1).gino.first())
    count = await db.select([func.count(db.Quest.id)]).where(and_(db.Quest.id.notin_(ready_quests),
                    or_(db.Quest.closed_at > datetime.datetime.now(), db.Quest.closed_at.is_(None)))
    ).gino.scalar()
    if not quest:
        await bot.write_msg(m.peer_id, "На данный момент нет доступных квестов", keyboard=await keyboards.main_menu(m.from_id))
        return
    sex = (await bot.api.users.get(user_id, fields=["sex"]))[0].sex
    quest_ready = Keyboard()
    if active_quest:
        quest_ready.add(
            Text(f"Я выполнил{'а' if sex == sex.female else ''} квест!", {"quest": "ready"}), KeyboardButtonColor.PRIMARY
        ).row()
    quest_ready.add(
        Text("Назад", {"menu": "quests and daylics"}), KeyboardButtonColor.NEGATIVE
    )
    if isinstance(m, Message):
        await bot.write_msg(m.peer_id, "Доступные квесты:", keyboard=quest_ready)
    if not quest.closed_at:
        if quest.execution_time:
            execution_time = parse_cooldown(quest.execution_time)
        else:
            execution_time = "Бессрочно"
    else:
        if not quest.execution_time:
            if datetime.datetime.now() < quest.start_at:
                execution_time = "До конца срока квеста"
            else:
                execution_time = parse_cooldown((quest.closed_at - datetime.datetime.now()).total_seconds())
        else:
            nearest = min(quest.closed_at.timestamp(), datetime.datetime.now().timestamp())
            execution_time = parse_cooldown(nearest - datetime.datetime.now().timestamp())
    reply = f"Квест №{page}: {quest.name}\n" \
            f"{quest.description}\n" \
            f"Нагарада: {quest.reward}\n" \
            f"Время на выполнение: " \
            f"{execution_time}\n"
    delta = None
    if quest.start_at > datetime.datetime.now():
        delta: datetime.timedelta = quest.start_at - datetime.datetime.now()
        active = False
    elif quest.closed_at:
        delta: datetime.timedelta = quest.closed_at - datetime.datetime.now()
        active = True
    if delta:
        total_seconds = delta.total_seconds()
        days = int(total_seconds / 86400)
        hours = int((total_seconds - days * 86400) / 3600)
        minutes = int((total_seconds - days * 86400 - hours * 3600) / 60)
        seconds = int(total_seconds - days * 86400 - hours * 3600 - minutes * 60)
        reply += f"{'Закончится через' if active else 'Начнётся через'} {days} дней {hours} часов {minutes} минут " \
                 f"{seconds} секунд\n\n"
    states.set(m.peer_id, Menu.SHOW_QUESTS)
    keyboard = Keyboard(inline=True)
    if count > 1 and page > 1:
        keyboard.add(Callback("<-", {"quests_page": page - 1}), KeyboardButtonColor.PRIMARY)
    if page < count:
        keyboard.add(Callback("->", {"quests_page": page + 1}), KeyboardButtonColor.PRIMARY)
    if not active_quest:
        if quest.start_at < datetime.datetime.now():
            if keyboard.buttons:
                keyboard.row()
            keyboard.add(Callback("Беру", {"quest_take": quest.id}), KeyboardButtonColor.POSITIVE)
    if isinstance(m, Message):
        await bot.write_msg(m.peer_id, reply, keyboard=keyboard)
    else:
        await bot.change_msg(m, reply, keyboard=keyboard)


@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent, PayloadMapRule({"quest_take": int}))
async def take_quest(m: MessageEvent):
    form_id = await get_current_form_id(m.user_id)
    quest_id = m.payload['quest_take']
    await db.Form.update.values(active_quest=quest_id).where(db.Form.id == form_id).gino.status()
    quest = await db.select([*db.Quest]).where(db.Quest.id == quest_id).gino.first()
    cooldown = None
    execution_time = ""
    if not quest.closed_at:
        if quest.execution_time:
            cooldown = quest.execution_time
        else:
            execution_time = "Бессрочно"
    else:
        if not quest.execution_time:
            if datetime.datetime.now() < quest.start_at:
                execution_time = "До конца срока квеста"
            else:
                cooldown = (quest.closed_at - datetime.datetime.now()).total_seconds()
        else:
            nearest = min(quest.closed_at.timestamp(), datetime.datetime.now().timestamp())
            cooldown = nearest - datetime.datetime.now().timestamp()
    reply = f"Вы взяли на выполнение квест: {quest.name}\n" \
            f"{quest.description}\n" \
            f"Нагарада: {quest.reward}\n" \
            f"Время на выполнение: {execution_time or parse_cooldown(cooldown)}\n"
    delta = None
    if quest.start_at > datetime.datetime.now():
        delta: datetime.timedelta = quest.start_at - datetime.datetime.now()
        active = False
    elif quest.closed_at:
        delta: datetime.timedelta = quest.closed_at - datetime.datetime.now()
        active = True
    if delta:
        total_seconds = delta.total_seconds()
        days = int(total_seconds / 86400)
        hours = int((total_seconds - days * 86400) / 3600)
        minutes = int((total_seconds - days * 86400 - hours * 3600) / 60)
        seconds = int(total_seconds - days * 86400 - hours * 3600 - minutes * 60)
        reply += f"{'Закончится через' if active else 'Начнётся через'} {days} дней {hours} часов {minutes} минут " \
                 f"{seconds} секунд\n\n"
    await bot.change_msg(m, reply)
    sex = (await bot.api.users.get(m.user_id, fields=["sex"]))[0].sex
    keyboard = Keyboard().add(
        Text(f"Я выполнил{'а' if sex == sex.female else ''} квест!", {"quest": "ready"}), KeyboardButtonColor.PRIMARY
    ).row().add(
        Text("Назад", {"menu": "quests and daylics"}), KeyboardButtonColor.NEGATIVE
    )
    if cooldown:
        asyncio.get_event_loop().create_task(quest_over(cooldown, form_id, quest_id))
    await bot.write_msg(m.peer_id, "После завершения квеста нажмите на кнопку завершения. Вы можете выйти и вернутся "
                                   "во вкладку квесты", keyboard=keyboard)


@bot.on.private_message(StateRule(Menu.MAIN), PayloadRule({"menu": "quests"}))
@bot.on.private_message(StateRule(Menu.SELECT_READY_QUEST), PayloadRule({"menu": "quests"}))
async def quest_menu(m: Message):
    await send_quest_page(m, 1)


@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent, PayloadMapRule({"quests_page": int}))
async def new_page_quest(m: MessageEvent):
    await send_quest_page(m, m.payload["quests_page"])


@bot.on.private_message(StateRule(Menu.SHOW_QUESTS), PayloadRule({"quest": "ready"}))
async def select_ready_quest(m: Message):
    form_id = await get_current_form_id(m.from_id)
    quest_id = await db.select([db.Form.active_quest]).where(db.Form.id == form_id).gino.scalar()
    if not quest_id:
        await bot.write_msg(m.peer_id, "У вас сейчас нет квеста на выполнении. Похоже вы брали когда-то его, "
                                       "но не выполнили")
        return
    name = await db.select([db.Form.name]).where(db.Form.id == form_id).gino.scalar()
    quest = await db.select([*db.Quest]).where(db.Quest.id == quest_id).gino.first()
    request = await db.ReadyQuest.create(quest_id=quest.id, form_id=form_id)
    await db.Form.update.values(active_quest=None).where(db.Form.id == form_id).gino.status()
    keyboard = Keyboard(inline=True).add(
        Callback("Выдать награду", {"quest_ready": True, "request_id": request.id}),
        KeyboardButtonColor.PRIMARY
    ).add(
        Callback("Отклонить", {"quest_ready": False, "request_id": request.id}),
        KeyboardButtonColor.NEGATIVE
    )
    await bot.write_msg(ADMINS + [OWNER], f"[id{m.from_id}|{name}] выполнил квест {quest.name}",
                        keyboard=keyboard)
    states.set(m.from_id, Menu.MAIN)
    await bot.write_msg(m.peer_id, "Поздравляем с завершением квеста. Ваш запрос отправлен администрации, после "
                                   "проверки вам придёт награда!", keyboard=await keyboards.main_menu(m.from_id))



