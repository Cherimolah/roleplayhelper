import asyncio
import datetime
from typing import Union

from vkbottle.bot import Message, MessageEvent
from vkbottle import Keyboard, KeyboardButtonColor, Callback, Text, GroupEventType
from vkbottle.dispatch.rules.base import PayloadRule, PayloadMapRule
from sqlalchemy import and_, func, or_, not_

from loader import bot
from service.custom_rules import StateRule
from service.states import Menu
from service.db_engine import db
from service.utils import get_current_form_id, parse_cooldown, quest_over, calculate_time
from service import keyboards
from service.middleware import states
from config import ADMINS, OWNER, DATETIME_FORMAT


async def view_quest(quest: db.Quest) -> str:
    starts = quest.start_at.strftime(DATETIME_FORMAT)
    if quest.closed_at:
        ends = quest.closed_at.strftime(DATETIME_FORMAT)
    else:
        ends = 'нет'
    reply = (f"Название: {quest.name}\n"
             f"Начало: {starts}\n"
             f"Завершение: {ends}\n"
             f"Время на выполнение: {parse_cooldown(quest.execution_time) or 'бессрочно'}\n"
             f"Награда: {quest.reward}\n"
             f"Описание: {quest.description}\n")
    if quest.fraction_id:
        fraction = await db.select([db.Fraction.name]).where(db.Fraction.id == quest.fraction_id).gino.scalar()
        reply += f"\nБонус к фракции: {fraction}\nБонус к репутации: {quest.reputation}"
    else:
        reply += "\n\nБез бонуса к репутации"
    return reply


async def send_quest_page(m: Union[Message, MessageEvent], page: int):
    if isinstance(m, Message):
        user_id = m.from_id
    else:
        user_id = m.user_id
    form_id = await get_current_form_id(user_id)
    ready = await db.select([db.ReadyQuest.id]).where(
        and_(db.ReadyQuest.form_id == form_id, db.ReadyQuest.is_checked.is_(False))
    ).gino.scalar()
    if ready:
        await m.answer("Новые квесты можно будет выполнить после проверки администрацией ваших отчётов")
        return
    completed_qusts = [x[0] for x in
                    await db.select([db.ReadyQuest.quest_id]).where(
                        and_(db.ReadyQuest.form_id == form_id, db.ReadyQuest.is_claimed.is_(True))).gino.all()]
    active_quest, starts_at = await db.select([db.Form.active_quest, db.Form.quest_start]).where(db.Form.id == form_id).gino.first()
    if active_quest:
        quest = await db.Quest.get(active_quest)
        execution_time = calculate_time(quest, starts_at) or 'бессрочно'
        reply = "У вас активирован квест:\n\n" + await view_quest(quest) + (f"\n\n"
                                                                            f"Остаётся на исполнение: {parse_cooldown(execution_time) or 'бессрочно'}")
        await m.answer(reply, keyboard=Keyboard().add(
                Text("Отправить отчёт", {"quest": "ready"}), KeyboardButtonColor.PRIMARY
            ).row().add(
            Text("Назад", {"menu": "quests and daylics"}), KeyboardButtonColor.NEGATIVE
        ))
        return
    profession_id, fraction_id = await db.select([db.Form.profession, db.Form.fraction_id]).where(db.Form.id == form_id).gino.first()
    restricted_quests = [x[0] for x in await db.select([db.Quest.id]).where(
        and_(db.Quest.allowed_forms != [], not_(db.Quest.allowed_forms.is_(None)), not_(db.Quest.allowed_forms.op('@>')([form_id])))
    ).gino.all()]
    restricted_quests += [x[0] for x in await db.select([db.Quest.id]).where(
        and_(not_(db.Quest.allowed_fraction.is_(None)), db.Quest.allowed_fraction != fraction_id)
    ).gino.all()]
    restricted_quests += [x[0] for x in await db.select([db.Quest.id]).where(
        and_(not_(db.Quest.allowed_profession.is_(None)), db.Quest.allowed_profession != profession_id)
    ).gino.all()]
    quest = await (
        db.select([*db.Quest])
        .where(and_(db.Quest.id.notin_(completed_qusts),
                    or_(db.Quest.closed_at > datetime.datetime.now(), db.Quest.closed_at.is_(None)),
                    db.Quest.id.notin_(restricted_quests))).limit(
            1).offset(page - 1).gino.first())
    count = await db.select([func.count(db.Quest.id)]).where(
        and_(db.Quest.id.notin_(completed_qusts),
             or_(db.Quest.closed_at > datetime.datetime.now(), db.Quest.closed_at.is_(None)),
             db.Quest.id.notin_(restricted_quests))
    ).gino.scalar()
    if not quest:
        await m.answer("На данный момент нет доступных квестов")
        return
    if isinstance(m, Message):
        await m.answer("Доступные квесты:", keyboard=Keyboard().add(
            Text("Назад", {"menu": "quests and daylics"}), KeyboardButtonColor.NEGATIVE
        ))
    reply = f"Квест №{page}\n\n" + await view_quest(quest)
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
        await m.answer(reply, keyboard=keyboard)
    else:
        await m.edit_message(reply, keyboard=keyboard.get_json())


@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent, PayloadMapRule({"quest_take": int}))
async def take_quest(m: MessageEvent):
    form_id = await get_current_form_id(m.user_id)
    quest_id = m.payload['quest_take']
    now = datetime.datetime.now()
    await db.Form.update.values(active_quest=quest_id, quest_start=now).where(db.Form.id == form_id).gino.status()
    quest = await db.select([*db.Quest]).where(db.Quest.id == quest_id).gino.first()
    reply = await view_quest(quest) + (f"\n\nВы взяли этот квест на выполнение\n")
    await m.edit_message(reply)
    keyboard = Keyboard().add(
        Text(f"Отправить отчёт", {"quest": "ready"}), KeyboardButtonColor.PRIMARY
    ).row().add(
        Text("Назад", {"menu": "quests and daylics"}), KeyboardButtonColor.NEGATIVE
    )
    cooldown = calculate_time(quest, now)
    if cooldown:
        asyncio.get_event_loop().create_task(quest_over(cooldown, form_id, quest_id))
    await m.send_message("После завершения квеста нажмите на кнопку завершения. Вы можете выйти и вернутся "
                                   "во вкладку квесты", keyboard=keyboard.get_json())


@bot.on.private_message(StateRule(Menu.MAIN), PayloadRule({"menu": "quests"}))
@bot.on.private_message(StateRule(Menu.SELECT_READY_QUEST), PayloadRule({"menu": "quests"}))
async def quest_menu(m: Message):
    await send_quest_page(m, 1)


@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent, PayloadMapRule({"quests_page": int}))
async def new_page_quest(m: MessageEvent):
    await send_quest_page(m, m.payload["quests_page"])


@bot.on.private_message(StateRule(Menu.SHOW_QUESTS), PayloadRule({"quest": "ready"}))
async def send_ready_quest(m: Message):
    form_id = await get_current_form_id(m.from_id)
    quest_id = await db.select([db.Form.active_quest]).where(db.Form.id == form_id).gino.scalar()
    if not quest_id:
        await m.answer("У вас сейчас нет квеста на выполнении. Похоже вы брали когда-то его, "
                                       "но не выполнили")
        return
    exist = await db.select([db.ReadyQuest.id]).where(
        and_(db.ReadyQuest.form_id == form_id, db.ReadyQuest.is_checked.is_(False))).gino.scalar()
    if exist:
        await m.answer("Вы уже отправили запрос на проверку квеста")
        return
    name = await db.select([db.Form.name]).where(db.Form.id == form_id).gino.scalar()
    quest = await db.select([*db.Quest]).where(db.Quest.id == quest_id).gino.first()
    request = await db.ReadyQuest.create(quest_id=quest.id, form_id=form_id)
    await db.Form.update.values(active_quest=None, quest_start=None).where(db.Form.id == form_id).gino.status()
    keyboard = Keyboard(inline=True).add(
        Callback("Принять", {"quest_ready": True, "request_id": request.id}),
        KeyboardButtonColor.PRIMARY
    ).row().add(
        Callback("Отклонить", {"quest_ready": False, "request_id": request.id}),
        KeyboardButtonColor.NEGATIVE
    )
    await bot.api.messages.send(peer_ids=ADMINS + [OWNER], message=f"[id{m.from_id}|{name}] выполнил квест {quest.name}",
                        keyboard=keyboard)
    if m.peer_id > 2000000000:
        await m.answer("Поздравляем с завершением квеста. Ваш запрос отправлен администрации, после "
                       "проверки вам придёт награда!", keyboard=Keyboard())
        return
    states.set(m.from_id, Menu.MAIN)
    await m.answer("Поздравляем с завершением квеста. Ваш запрос отправлен администрации, после "
                                   "проверки вам придёт награда!", keyboard=await keyboards.main_menu(m.from_id))
