from vkbottle.bot import Message, MessageEvent
from vkbottle.dispatch.rules.base import PayloadRule, PayloadMapRule
from vkbottle import Keyboard, Callback, KeyboardButtonColor, GroupEventType, Text
from sqlalchemy import func, and_, not_

from loader import bot
from service.utils import allow_edit_content, send_content_page, parse_ids, FormatDataException
from service.serializers import info_target_reward, parse_reward, info_quest_penalty
from service.middleware import states
from service.db_engine import db
from service.custom_rules import StateRule, AdminRule, NumericRule
from service.states import Admin
import service.keyboards as keyboards


@bot.on.private_message(StateRule(f"{Admin.SELECT_ACTION}_DaughterQuest"), PayloadRule({"DaughterQuest": "add"}), AdminRule())
async def create_quest(m: Message):
    quest = await db.DaughterQuest.create()
    states.set(m.from_id, f"{Admin.DAUGHTER_QUEST_NAME}*{quest.id}")
    await m.answer("Напишите название квеста", keyboard=Keyboard())


@bot.on.private_message(StateRule(Admin.DAUGHTER_QUEST_NAME), AdminRule())
@allow_edit_content('DaughterQuest', text='Имя успешно установлено. Укажите описание квеста:', state=Admin.DAUGHTER_QUEST_DESCRIPTION)
async def daughter_quest_name(m: Message, item_id: int, editing_content: bool):
    await db.DaughterQuest.update.values(name=m.text).where(db.DaughterQuest.id == item_id).gino.status()


@bot.on.private_message(StateRule(Admin.DAUGHTER_QUEST_DESCRIPTION), AdminRule())
@allow_edit_content('DaughterQuest', state=Admin.DAUGHTER_QUEST_FORM_ID)
async def daughter_quest_description(m: Message, item_id: int, editing_content: bool):
    await db.DaughterQuest.update.values(description=m.text).where(db.DaughterQuest.id == item_id).gino.status()
    if not editing_content:
        reply, keyboard = await show_daughters_page(1)
        await m.answer(reply, keyboard=keyboard)


async def show_daughters_page(page: int = 1) -> tuple[str, Keyboard]:
    used_form_id = [x[0] for x in await db.select([db.DaughterQuest.to_form_id]).where(not_(db.DaughterQuest.to_form_id.is_(None))).gino.all()]
    data = await db.select([db.Form.user_id, db.Form.name]).where(and_(db.Form.status == 2, db.Form.id.notin_(used_form_id))).order_by(
        db.Form.id.asc()).offset((page - 1) * 15).limit(15).gino.all()
    user_ids = [x[0] for x in data]
    users = await bot.api.users.get(user_ids=user_ids)
    user_names = [f'{x.first_name} {x.last_name}' for x in users]
    reply = ('Укажите дочь для которой будет установлен квест\n'
             'Можно прислать ссылку, пересланное сообщение или номер по порядку отсюда\n\n'
             'Список дочерей, у которых нет квестов:\n\n')
    for i in range(len(data)):
        reply += f'{(page - 1) * 15 + i + 1}. [id{users[i].id}|{data[i][1]} / {user_names[i]}]\n'
    count = await db.select([func.count(db.Form.id)]).where(and_(db.Form.status == 2, db.Form.id.notin_(used_form_id))).gino.scalar()
    keyboard = Keyboard(inline=True)
    if count > 15:
        if page > 1:
            keyboard.add(Callback('<-', {"daughters_page": page - 1}), KeyboardButtonColor.PRIMARY)
        if count > page * 15:
            keyboard.add(Callback("->", {"daughters_page": page + 1}), KeyboardButtonColor.PRIMARY)
        keyboard.row()
    keyboard.add(Text('Не выдавать дочери', {"daughter_quest_for_none": True}), KeyboardButtonColor.SECONDARY)
    return reply, keyboard


@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent, PayloadMapRule({"daughters_page": int}), AdminRule())
async def daughters_page(e: MessageEvent):
    page = e.payload['daughters_page']
    reply, keyboard = await show_daughters_page(page)
    await e.edit_message(reply, keyboard=keyboard.get_json())


@bot.on.private_message(StateRule(Admin.DAUGHTER_QUEST_FORM_ID), PayloadRule({"daughter_quest_for_none": True}), AdminRule())
@allow_edit_content('DaughterQuest', state=Admin.DAUGHTER_QUEST_REWARD)
async def daughter_quest_without_form_id(m: Message, item_id: int, editing_content: bool):
    await db.DaughterQuest.update.values(to_form_id=None).where(db.DaughterQuest.id == item_id).gino.status()
    if not editing_content:
        await m.answer((await info_target_reward())[0])


@bot.on.private_message(StateRule(Admin.DAUGHTER_QUEST_FORM_ID), AdminRule())
@allow_edit_content('DaughterQuest', state=Admin.DAUGHTER_QUEST_REWARD)
async def daughter_quest_form_id(m: Message, item_id: int, editing_content: bool):
    used_form_id = [x[0] for x in await db.select([db.DaughterQuest.to_form_id]).where(not_(db.DaughterQuest.to_form_id.is_(None))).gino.all()]
    if m.text.isdigit():
        number = int(m.text)
        user_id = await db.select([db.Form.user_id]).where(and_(db.Form.status == 2, db.Form.id.notin_(used_form_id))).order_by(db.Form.id.asc()).offset(number-1).limit(1).gino.scalar()
        if not user_id:
            raise FormatDataException('Не найдено анкеты по порядковому номеру')
    else:
        users = await parse_ids(m)
        if not users:
            raise FormatDataException('Не найдено пользователя')
        if len(users) > 1:
            raise FormatDataException('Квест можно установить только для одной дочери')
        user_id = users[0]
    status, form_id = await db.select([db.Form.status, db.Form.id]).where(db.Form.user_id == user_id).gino.first()
    if status != 2:
        raise FormatDataException('У пользователя отсутствует статус дочь')
    if form_id in used_form_id:
        quest_name = await db.select([db.DaughterQuest.name]).where(db.DaughterQuest.to_form_id == form_id).gino.scalar()
        raise FormatDataException(f'Для этой дочери установлен квест «{quest_name}»')
    await db.DaughterQuest.update.values(to_form_id=form_id).where(db.DaughterQuest.id == item_id).gino.status()
    if not editing_content:
        await m.answer((await info_target_reward())[0])


@bot.on.private_message(StateRule(Admin.DAUGHTER_QUEST_REWARD), AdminRule())
@allow_edit_content('DaughterQuest', state=Admin.DAUGHTER_QUEST_PENALTY)
async def daughter_quest_reward(m: Message, item_id: int, editing_content: bool):
    data = await parse_reward(m.text)
    await db.DaughterQuest.update.values(reward=data).where(db.DaughterQuest.id == item_id).gino.status()
    if not editing_content:
        reply, keyboard = await info_quest_penalty()
        await m.answer(reply, keyboard=keyboard)


@bot.on.private_message(StateRule(Admin.DAUGHTER_QUEST_PENALTY), PayloadRule({"without_penalty": True}), AdminRule())
@allow_edit_content('DaughterQuest', state=Admin.DAUGHTER_QUEST_TARGET_IDS)
async def daughter_penalty(m: Message, item_id: int, editing_content: bool):
    await db.DaughterQuest.update.values(penalty=None).where(db.DaughterQuest.id == item_id).gino.status()
    if not editing_content:
        reply = ('Укажите доп. цели, через запятую, которые будут появляться по мере нарастания параметров.\n\n'
                 'Например: 1, 2, 3')
        await m.answer(reply, keyboard=Keyboard())
        reply, keyboard = await show_daughter_target_page(1)
        await m.answer(reply, keyboard=keyboard)


@bot.on.private_message(StateRule(Admin.DAUGHTER_QUEST_PENALTY), AdminRule())
@allow_edit_content('DaughterQuest', state=Admin.DAUGHTER_QUEST_TARGET_IDS)
async def daughter_penalty(m: Message, item_id: int, editing_content: bool):
    data = await parse_reward(m.text)
    await db.DaughterQuest.update.values(penalty=data).where(db.DaughterQuest.id == item_id).gino.status()
    if not editing_content:
        reply = ('Укажите доп. цели, через запятую, которые будут появляться по мере нарастания параметров.\n\n'
                 'Например: 1, 2, 3')
        await m.answer(reply, keyboard=Keyboard())
        reply, keyboard = await show_daughter_target_page(1)
        await m.answer(reply, keyboard=keyboard)


async def show_daughter_target_page(page: int = 1) -> tuple[str, Keyboard | None]:
    data = await db.select([db.DaughterTarget.name, db.DaughterTarget.params]).order_by(db.DaughterTarget.id.asc()).offset((page - 1) * 15).limit(15).gino.all()
    if not data:
        reply = 'На данный момент не создано доп. целей'
        return reply, Keyboard(inline=True).add(Text('Без доп. целей', {"without_targets": True}), KeyboardButtonColor.SECONDARY)
    reply = '{номер}. {название} / {либидо} {правило} {подчинение}\n\n'
    count = await db.select([func.count(db.DaughterTarget.id)]).gino.scalar()
    for i in range(len(data)):
        name, params = data[i]
        if not params:  # В базе могут быть не до конца созданные доп. цели
            continue
        reply += f'{(page - 1) * 15 + i + 1}. {name} / {params[0]} {"и" if params[1] == 0 else "или"} {params[2]}\n'
    keyboard = Keyboard(inline=True)
    if count > 15:
        if page > 1:
            keyboard.add(Callback("<-", {"daughter_targets": page - 1}), KeyboardButtonColor.PRIMARY)
        if count > page * 15:
            keyboard.add(Callback("->", {"daughter_targets": page + 1}), KeyboardButtonColor.PRIMARY)
        if page > 1 or count > page * 15:
            keyboard.row()
    keyboard.add(Text('Без доп. целей', {"without_targets": True}), KeyboardButtonColor.SECONDARY)
    return reply, keyboard


@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent, PayloadMapRule({"daughter_targets": int}), AdminRule())
async def daughter_targets_page(m: MessageEvent):
    page = m.payload['daughter_targets']
    reply, keyboard = await show_daughter_target_page(page)
    await m.edit_message(reply, keyboard=keyboard.get_json())


@bot.on.private_message(StateRule(Admin.DAUGHTER_QUEST_TARGET_IDS), PayloadRule({"without_targets": True}), AdminRule())
@allow_edit_content('DaughterQuest', end=True, text='Квест для дочери успешно создан')
async def daughter_target_ids(m: Message, item_id: int, editing_content: bool):
    await db.DaughterQuest.update.values(target_ids=[]).where(db.DaughterQuest.id == item_id).gino.status()


@bot.on.private_message(StateRule(Admin.DAUGHTER_QUEST_TARGET_IDS), AdminRule())
@allow_edit_content('DaughterQuest', end=True, text='Квест для дочери успешно создан')
async def daughter_target_ids(m: Message, item_id: int, editing_content: bool):
    text = m.text.replace(" ", '')
    try:
        target_numbers = list(map(int, text.split(",")))
    except:
        raise FormatDataException('Неверно указан формат чисел')
    count = await db.select([func.count(db.DaughterTarget.id)]).gino.scalar()
    for n in target_numbers:
        if n <= 0 or n > count:
            raise FormatDataException(f'Номера должны быть от 1 до {count}')
    target_ids_all = [x[0] for x in await db.select([db.DaughterTarget.id]).order_by(db.DaughterTarget.id.asc()).gino.all()]
    target_ids = [target_ids_all[n - 1] for n in target_numbers]
    await db.DaughterQuest.update.values(target_ids=target_ids).where(db.DaughterQuest.id == item_id).gino.status()


@bot.on.private_message(StateRule(f"{Admin.SELECT_ACTION}_DaughterQuest"), PayloadRule({"DaughterQuest": "delete"}), AdminRule())
async def select_delete_quest(m: Message):
    quests = await db.select([db.DaughterQuest.name]).order_by(db.DaughterQuest.id.asc()).gino.all()
    if not quests:
        return "Квесты ещё не созданы"
    reply = "Выберите квест для удаления:\n\n"
    for i, quest in enumerate(quests):
        reply = f"{reply}{i + 1}. {quest.name}\n"
    states.set(m.peer_id, Admin.DAUGHTER_QUEST_DELETE)
    await m.answer(reply, keyboard=Keyboard())


@bot.on.private_message(StateRule(Admin.DAUGHTER_QUEST_DELETE), NumericRule(), AdminRule())
async def delete_quest(m: Message, value: int):
    quest_id = await db.select([db.DaughterQuest.id]).order_by(db.DaughterQuest.id.asc()).offset(value - 1).limit(1).gino.scalar()
    await db.DaughterQuest.delete.where(db.DaughterQuest.id == quest_id).gino.status()
    states.set(m.peer_id, f"{Admin.SELECT_ACTION}_DaughterQuest")
    await m.answer("Квест успешно удалён", keyboard=keyboards.gen_type_change_content("DaughterQuest"))
    await send_content_page(m, "DaughterQuest", 1)

