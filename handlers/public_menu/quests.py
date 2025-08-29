import asyncio
import datetime
from typing import Union, List, Tuple

from vkbottle.bot import Message, MessageEvent
from vkbottle import Keyboard, KeyboardButtonColor, Callback, Text, GroupEventType
from vkbottle.dispatch.rules.base import PayloadRule, PayloadMapRule
from sqlalchemy import and_, func, or_, not_

from loader import bot
from service.custom_rules import StateRule
from service.states import Menu
from service.db_engine import db
from service.utils import get_current_form_id, parse_cooldown, quest_over, calculate_time, serialize_target_reward, count_daughter_params
from service.middleware import states
from config import ADMINS, OWNER, DATETIME_FORMAT


async def get_available_target_ids(quest: db.Quest, user_id: int) -> List[int]:
    if not quest.target_ids:
        return []
    form = await db.select([*db.Form]).where(db.Form.user_id == user_id).gino.first()
    libido_level, subordination_level = await count_daughter_params(user_id)
    allowed_target_ids = []
    for target_id in quest.target_ids:
        target = await db.AdditionalTarget.get(target_id)
        if target.for_all_users:
            allowed_target_ids.append(target_id)
            continue
        if target.fraction_reputation and target.reputation:
            reputation = await db.select([db.UserToFraction.reputation]).where(
                and_(db.UserToFraction.fraction_id == target.fraction_reputation, db.UserToFraction.user_id == user_id)
            ).gino.scalar()
            if reputation >= target.reputation:
                allowed_target_ids.append(target_id)
                continue
        if target.fraction and target.fraction == form.fraction_id:
            allowed_target_ids.append(target_id)
            continue
        if target.profession and target.profession == form.profession:
            allowed_target_ids.append(target_id)
            continue
        if target.daughter_params and form.status == 2:
            libido, subordination, word = target.daughter_params
            if word and (libido_level >= libido or subordination_level >= subordination):  # ИЛИ
                allowed_target_ids.append(target_id)
                continue
            if not word and (libido_level >= libido and subordination_level >= subordination):  # И
                allowed_target_ids.append(target_id)
                continue
        if target.forms and form.id in target.forms:
            allowed_target_ids.append(target_id)
            continue
    return allowed_target_ids


async def view_quest(quest: db.Quest, user_id: int, quest_active: bool = False) -> Tuple[str, Keyboard]:
    #  targets_active - чтобы сделать описание квестов, которые активны у чувака
    starts = quest.start_at.strftime(DATETIME_FORMAT)
    form_id = await get_current_form_id(user_id)
    if quest.closed_at:
        ends = quest.closed_at.strftime(DATETIME_FORMAT)
    else:
        ends = 'нет'
    reply = (f"Название: {quest.name}\n"
             f"Начало: {starts}\n"
             f"Завершение: {ends}\n"
             f"Время на выполнение: {parse_cooldown(quest.execution_time) or 'бессрочно'}\n"
             f"Награда: {await serialize_target_reward(quest.reward)}\n"
             f"Описание: {quest.description}")
    if not quest_active:
        target_ids = await get_available_target_ids(quest, user_id)
    else:
        active_targets = set(await db.select([db.QuestToForm.active_targets]).where(db.QuestToForm.form_id == form_id).gino.scalar())
        completed_targets = set()
        for target_id in active_targets:
            completed_targets = {x[0] for x in await db.select([db.ReadyTarget.target_id]).where(
                or_(and_(db.ReadyTarget.target_id == target_id, db.ReadyTarget.form_id == form_id,
                         db.ReadyTarget.is_checked.is_(True), db.ReadyTarget.is_claimed.is_(True)),
                    and_(db.ReadyTarget.target_id == target_id, db.ReadyTarget.form_id == form_id,
                         db.ReadyTarget.is_checked.is_(False), db.ReadyTarget.is_claimed.is_(False))
                    )
            ).gino.all()}
        target_ids = list(active_targets - completed_targets)
    if target_ids:
        reply += '\n\nДоп. цели:\n'
        for i, target_id in enumerate(target_ids):
            target = await db.AdditionalTarget.get(target_id)
            reply += (f'{i + 1}. {target.name}\n'
                      f'Описание: {target.description}\n'
                      f'Награда: {(await serialize_target_reward(target.reward_info))}')
    starts_at = await db.select([db.QuestToForm.quest_start]).where(db.QuestToForm.form_id == form_id).gino.scalar()
    if quest_active:
        execution_time = calculate_time(quest, starts_at)
        reply = ("У вас активирован квест:\n\n" + reply + f"\n\n"f"Остаётся на исполнение: {parse_cooldown(execution_time) if execution_time else 'бессрочно'}")
    keyboard = Keyboard()
    quest_ready = await db.select([db.ReadyQuest.id]).where(
        or_(and_(db.ReadyQuest.quest_id == quest.id, db.ReadyQuest.form_id == form_id,
                 db.ReadyQuest.is_checked.is_(True), db.ReadyQuest.is_claimed.is_(True)),
            and_(db.ReadyQuest.quest_id == quest.id, db.ReadyQuest.form_id == form_id,
                 db.ReadyQuest.is_checked.is_(False), db.ReadyQuest.is_claimed.is_(False)))
    ).gino.scalar()
    if not quest_ready:
        keyboard.add(
            Text(f"Завершить выполнение квеста", {"quest": "ready"}), KeyboardButtonColor.PRIMARY
        ).row()
    for i in range(len(target_ids)):
        keyboard.add(
            Text(f'Завершить доп. цель №{i + 1}', {"target_ready": target_ids[i]})
        ).row()
    keyboard.add(
        Text("Назад", {"menu": "quests and daylics"}), KeyboardButtonColor.NEGATIVE
    )
    return reply, keyboard


async def send_quest_page(m: Union[Message, MessageEvent], page: int):
    if isinstance(m, Message):
        user_id = m.from_id
    else:
        user_id = m.user_id
    form_id = await get_current_form_id(user_id)
    taked_quests = [x[0] for x in await db.select([db.QuestHistory.quest_id]).where(db.QuestHistory.form_id == form_id).gino.all()]
    active_quest = await db.select([db.QuestToForm.quest_id]).where(db.QuestToForm.form_id == form_id).gino.scalar()
    if active_quest:
        quest = await db.Quest.get(active_quest)
        reply, keyboard = await view_quest(quest, user_id, True)
        states.set(m.from_id, Menu.SHOW_QUESTS)
        await m.answer(reply, keyboard=keyboard)
        return
    quest_request = await db.select([db.ReadyQuest.id]).where(
        and_(db.ReadyQuest.form_id == form_id, db.ReadyQuest.is_checked.is_(False))
    ).gino.scalar()
    target_request = await db.select([db.ReadyTarget.id]).where(
        and_(db.ReadyTarget.form_id == form_id, db.ReadyTarget.is_checked.is_(False))
    ).gino.scalar()
    if quest_request or target_request:
        await m.answer("Новые квесты можно будет выполнить после проверки администрацией всех ваших отчётов")
        return
    profession_id, fraction_id = await db.select([db.Form.profession, db.Form.fraction_id]).where(db.Form.id == form_id).gino.first()
    #  @> - пересечение массивов. Здесь проверка на то, что пользователя нет в вайт-листе
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
        .where(and_(db.Quest.id.notin_(taked_quests),
                    or_(db.Quest.closed_at > datetime.datetime.now(), db.Quest.closed_at.is_(None)),
                    db.Quest.id.notin_(restricted_quests))).limit(
            1).offset(page - 1).gino.first())
    count = await db.select([func.count(db.Quest.id)]).where(
        and_(db.Quest.id.notin_(taked_quests),
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
        reply = f"Квест №{page}\n\n" + (await view_quest(quest, m.from_id))[0]
    else:
        reply = f"Квест №{page}\n\n" + (await view_quest(quest, m.user_id))[0]
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
        await db.User.update.values(state=Menu.SHOW_QUESTS).where(db.User.user_id == user_id).gino.status()
        await m.edit_message(reply, keyboard=keyboard.get_json())


@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent, PayloadMapRule({"quest_take": int}))
async def take_quest(m: MessageEvent):
    form_id = await get_current_form_id(m.user_id)
    quest_id = m.payload['quest_take']
    now = datetime.datetime.now()
    quest = await db.Quest.get(quest_id)
    target_ids = await get_available_target_ids(quest, m.user_id)
    await db.QuestToForm.create(quest_id=quest_id, quest_start=now, active_targets=target_ids, form_id=form_id)
    reply = await view_quest(quest, m.user_id, True)
    await m.edit_message(reply[0])
    cooldown = calculate_time(quest, now)
    if cooldown:
        asyncio.get_event_loop().create_task(quest_over(cooldown, form_id, quest_id))
    if quest.closed_at:
        seconds = (quest.closed_at - datetime.datetime.now()).total_seconds()
        asyncio.get_event_loop().create_task(quest_over(seconds, form_id, quest_id))
    states.set(m.user_id, Menu.SHOW_QUESTS)
    await db.QuestHistory.create(quest_id=quest_id, form_id=form_id)
    await m.send_message("После завершения квеста нажмите на кнопку завершения. Вы можете выйти и вернутся "
                                   "во вкладку квесты", keyboard=reply[1].get_json())


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
    quest_id = await db.select([db.QuestToForm.quest_id]).where(db.QuestToForm.form_id == form_id).gino.scalar()
    if not quest_id:
        await m.answer("Время на выполнение квеста истекло!")
        return
    exist = await db.select([db.ReadyQuest.id]).where(
        and_(db.ReadyQuest.form_id == form_id, db.ReadyQuest.is_checked.is_(False), db.ReadyQuest.quest_id == quest_id)).gino.scalar()
    if exist:
        await m.answer("Вы уже отправили запрос на проверку квеста")
        return
    name = await db.select([db.Form.name]).where(db.Form.id == form_id).gino.scalar()
    quest = await db.select([*db.Quest]).where(db.Quest.id == quest_id).gino.first()
    request = await db.ReadyQuest.create(quest_id=quest.id, form_id=form_id)
    starts_at = await db.select([db.QuestToForm.quest_start]).where(db.QuestToForm.form_id == form_id).gino.scalar()
    await db.QuestToForm.update.values(is_paused=True, remained_time=calculate_time(quest, starts_at)).where(db.QuestToForm.form_id == form_id).gino.status()
    keyboard = Keyboard(inline=True).add(
        Callback("Принять", {"quest_ready": True, "request_id": request.id}),
        KeyboardButtonColor.PRIMARY
    ).row().add(
        Callback("Отклонить", {"quest_ready": False, "request_id": request.id}),
        KeyboardButtonColor.NEGATIVE
    )
    user = (await bot.api.users.get(user_id=m.from_id))[0]
    user_name = f"{user.first_name} {user.last_name}"
    await bot.api.messages.send(peer_ids=ADMINS + [OWNER], message=f"[id{m.from_id}|{name} / {user_name}] выполнил квест {quest.name}",
                        keyboard=keyboard)
    if m.peer_id > 2000000000:
        await m.answer("Поздравляем с завершением квеста. Ваш запрос отправлен администрации, после "
                       "проверки вам придёт награда!", keyboard=Keyboard())
        return
    await m.answer("Поздравляем с завершением квеста. Ваш запрос отправлен администрации, после "
                                   "проверки вам придёт награда!")
    reply, keyboard = await view_quest(quest, m.from_id, True)
    await m.answer(reply, keyboard=keyboard)


@bot.on.private_message(StateRule(Menu.SHOW_QUESTS), PayloadMapRule({"target_ready": int}))
async def target_ready(m: Message):
    form_id = await get_current_form_id(m.from_id)
    quest_id = await db.select([db.QuestToForm.quest_id]).where(db.QuestToForm.form_id == form_id).gino.scalar()
    if not quest_id:
        await m.answer("Время на выполнение квеста истекло!")
        return
    target_id = int(m.payload['target_ready'])
    exist = await db.select([db.ReadyTarget.id]).where(
        and_(db.ReadyTarget.form_id == form_id, db.ReadyTarget.is_checked.is_(False), db.ReadyTarget.target_id == target_id)).gino.scalar()
    if exist:
        await m.answer("Вы уже отправили запрос на проверку этой дополнительной цели")
        return
    name = await db.select([db.Form.name]).where(db.Form.id == form_id).gino.scalar()
    target = await db.AdditionalTarget.get(target_id)
    request = await db.ReadyTarget.create(target_id=target_id, form_id=form_id)
    keyboard = Keyboard(inline=True).add(
        Callback("Принять", {"target_accept": True, "request_id": request.id}),
        KeyboardButtonColor.PRIMARY
    ).row().add(
        Callback("Отклонить", {"target_accept": False, "request_id": request.id}),
        KeyboardButtonColor.NEGATIVE
    )
    user = (await bot.api.users.get(user_id=m.from_id))[0]
    user_name = f"{user.first_name} {user.last_name}"
    await bot.api.messages.send(peer_ids=ADMINS + [OWNER],
                                message=f"[id{m.from_id}|{name} / {user_name}] выполнил дополнительную цель {target.name}",
                                keyboard=keyboard)
    if m.peer_id > 2000000000:
        await m.answer("Поздравляем с завершением дополнительной цели. Ваш запрос отправлен администрации, после "
                       "проверки вам придёт награда!", keyboard=Keyboard())
        return
    await m.answer("Поздравляем с завершением дополнительной цели. Ваш запрос отправлен администрации, после "
                   "проверки вам придёт награда!")
    quest_id = await db.select([db.QuestToForm.quest_id]).where(db.QuestToForm.form_id == form_id).gino.scalar()
    quest = await db.Quest.get(quest_id)
    reply, keyboard = await view_quest(quest, m.from_id, True)
    await m.answer(reply, keyboard=keyboard)
