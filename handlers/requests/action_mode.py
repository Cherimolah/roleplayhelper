from vkbottle.bot import MessageEvent, Message
from vkbottle.dispatch.rules.base import PayloadMapRule, PayloadRule
from vkbottle import GroupEventType, Keyboard, KeyboardButtonColor, Text
from vkbottle_types.objects import MessagesForward

from loader import bot, states
from service.custom_rules import JudgeRule, UserFree, JudgeFree, StateRule
from service.db_engine import db
from service.states import Judge
from handlers.questions import start
from service.utils import get_mention_from_message


@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent, PayloadMapRule({'action_mode_request_id': int, 'action_mode': 'decline'}), JudgeRule(), UserFree(), JudgeFree())
async def decline_action_mode(m: MessageEvent):
    request_id = m.payload['action_mode_request_id']
    request = await db.ActionModeRequest.get(request_id)
    if not request:
        await m.show_snackbar('Запрос уже неактуален')
        return
    chat_id = await db.select([db.ActionModeRequest.chat_id]).where(db.ActionModeRequest.id == request_id).gino.scalar()
    states.set(m.user_id, f'{Judge.REASON_DECLINE}*{chat_id}')
    await m.edit_message('Укажите причину отказа экшен-режима', keyboard=Keyboard().get_json())


@bot.on.private_message(StateRule(Judge.REASON_DECLINE), JudgeRule())
async def send_reason_decline(m: Message):
    chat_id = int(states.get(m.from_id).split('*')[1])
    data = await db.select([db.ActionModeRequest.judge_id, db.ActionModeRequest.message_id]).where(db.ActionModeRequest.chat_id == chat_id).gino.all()
    chat_name = (await bot.api.messages.get_conversations_by_id(peer_ids=2000000000 + chat_id)).items[0].chat_settings.title
    name = await db.select([db.Form.name]).where(db.Form.user_id == m.from_id).gino.scalar()
    user = await m.get_user()
    for judge_id, cmid in data:
        try:
            await bot.api.messages.send(peer_id=judge_id, forward=MessagesForward(
                peer_id=judge_id, conversation_message_ids=[cmid], is_reply=True
            ), message=f'Судья [id{m.from_id}|{name} / {user.first_name} {user.last_name}] отклонил создание экшен '
                       f'режима в чате «{chat_name}» по причине: «{m.text}»')
        except:
            await bot.api.messages.send(peer_id=judge_id, message=f'Судья [id{m.from_id}|{name} / {user.first_name} {user.last_name}] отклонил создание экшен '
                       f'режима в чате «{chat_name}» по причине: «{m.text}»')
    await db.ActionModeRequest.delete.where(db.ActionModeRequest.chat_id == chat_id).gino.status()
    keyboard = Keyboard().add(
        Text('Запросить экшен-режим', {'action_mode': 'create_request'}), KeyboardButtonColor.PRIMARY
    )
    await bot.api.messages.send(peer_id=2000000000 + chat_id, message=f'Судья [id{m.from_id}|{name} / {user.first_name} {user.last_name}] отклонил создание экшен '
                       f'режима в чате «{chat_name}» по причине: «{m.text}»', keyboard=keyboard)
    await start(m)


@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent, PayloadMapRule({'action_mode_request_id': int, 'action_mode': 'confirm'}), JudgeRule(), UserFree(), JudgeFree())
async def confirm_action_mode(m: MessageEvent):
    request_id = m.payload['action_mode_request_id']
    request = await db.ActionModeRequest.get(request_id)
    if not request:
        await m.show_snackbar('Запрос уже неактуален')
        return
    chat_name = (await bot.api.messages.get_conversations_by_id(peer_ids=2000000000 + request.chat_id)).items[0].chat_settings.title
    data = await db.select([db.ActionModeRequest.judge_id, db.ActionModeRequest.message_id]).where(db.ActionModeRequest.chat_id == request.chat_id).gino.all()
    name = await db.select([db.Form.name]).where(db.Form.user_id == m.user_id).gino.scalar()
    user = (await bot.api.users.get(user_ids=[m.user_id]))[0]
    for judge_id, cmid in data:
        try:
            await bot.api.messages.send(peer_id=judge_id, forward=MessagesForward(
                peer_id=judge_id, conversation_message_ids=[cmid], is_reply=True
            ), message=f'Судья [id{m.from_id}|{name} / {user.first_name} {user.last_name}] активировал экшен '
                       f'режим в чате «{chat_name}»')
        except:
            await bot.api.messages.send(peer_id=judge_id, message=f'Судья [id{m.user_id}|{name} / {user.first_name} {user.last_name}] активировал экшен '
                       f'режима в чате «{chat_name}»')
    await db.ActionModeRequest.delete.where(db.ActionModeRequest.chat_id == request.chat_id).gino.status()
    await bot.api.messages.send(peer_id=2000000000 + request.chat_id,
                                message=f'Судья [id{m.user_id}|{name} / {user.first_name} {user.last_name}] активировал экшен '
                                       f'режим в чате «{chat_name}»\n'
                                       f'Сейчас определится список игроков и очередность их ходов')
    states.set(m.user_id, Judge.ADD_USERS)
    action_mode = await db.ActionMode.create(chat_id=request.chat_id, judge_id=m.user_id)
    await db.UsersToActionMode.create(action_mode_id=action_mode.id, user_id=request.from_id)
    keyboard = Keyboard().add(
        Text('Запустить экшен-режим', {'action_mode': 'start'}), KeyboardButtonColor.POSITIVE
    ).row().add(
        Text('Удалить участников', {'action_mode': 'delete_users'}), KeyboardButtonColor.NEGATIVE
    )
    reply = ('Отправьте ссылки/сообщения/упоминания пользователей, которых хотите добавить в экшен режим\n'
             'Они должны находиться в нужном чате и иметь карту экспедитора!\n'
             'Когда будет готово нажмите кнопку запуска экшен-режима\n\n'
             'Игроки добавленные в экшен-режим:\n')
    members = await bot.api.messages.get_conversation_members(peer_id=2000000000 + request.chat_id)
    user_ids = [x.member_id for x in members.items if x.member_id > 0]
    form_ids = [x[0] for x in await db.select([db.Form.id]).where(db.Form.user_id.in_(user_ids)).gino.all()]
    form_ids = [x[0] for x in await db.select([db.Expeditor.form_id]).where(db.Expeditor.form_id.in_(form_ids)).gino.all()]
    users_data = await db.select([db.Form.name, db.Form.user_id]).where(db.Form.id.in_(form_ids)).gino.all()
    users = await bot.api.users.get(user_ids=[x[1] for x in users_data])
    for i in range(len(users_data)):
        reply += f'{i + 1}. [id{users_data[i][1]}|{users_data[i][0]} / {users[i].first_name} {users[i].last_name}]\n'
    await m.edit_message(message=reply, keyboard=keyboard.get_json())


@bot.on.private_message(StateRule(Judge.ADD_USERS), PayloadRule({'action_mode': 'start'}), JudgeRule())
async def start_action_mode(m: Message):
    pass


@bot.on.private_message(StateRule(Judge.ADD_USERS), PayloadRule({'action_mode': 'delete_users'}), JudgeRule())
async def delete_users_from_action_mode(m: Message):
    pass


async def send_users_in_action_mode(m: Message, chat_id: int):
    action_mode_id = await db.select([db.ActionMode.id]).where(db.ActionMode.chat_id == chat_id).gino.scalar()
    user_ids = [x[0] for x in await db.select([db.UsersToActionMode.user_id]).where(db.UsersToActionMode.action_mode_id == action_mode_id).gino.all()]
    reply = ('Отправьте ссылки/сообщения/упоминания пользователей, которых хотите добавить в экшен режим\n'
             'Они должны находиться в нужном чате и иметь карту экспедитора!\n'
             'Когда будет готово нажмите кнопку запуска экшен-режима\n\n'
             'Игроки добавленные в экшен-режим:\n')
    user_names = [x[0] for x in await db.select([db.Form.name]).where(db.Form.user_id.in_(user_ids)).gino.all()]
    users = await bot.api.users.get(user_ids=user_ids)
    for i in range(len(users)):
        reply += f'{i + 1}. [id{user_ids[i]}|{user_names[i]} / {users[i].first_name} {users[i].last_name}]\n'
    keyboard = Keyboard().add(
        Text('Запустить экшен-режим', {'action_mode': 'start'}), KeyboardButtonColor.POSITIVE
    ).row().add(
        Text('Удалить участников', {'action_mode': 'delete_users'}), KeyboardButtonColor.NEGATIVE
    )
    await m.answer(reply, keyboard=keyboard)


@bot.on.private_message(StateRule(Judge.ADD_USERS), JudgeRule())
async def add_users_to_action_mode(m: Message):
    user_ids = set(await get_mention_from_message(m, many_users=True))
    if not user_ids:
        await m.answer('Пользователей не найдено')
        return
    chat_id = await db.select([db.ActionMode.chat_id]).where(db.ActionMode.judge_id == m.from_id).gino.scalar()
    action_mode_id = await db.select([db.ActionMode.id]).where(db.ActionMode.chat_id == chat_id).gino.scalar()
    members = await bot.api.messages.get_conversation_members(peer_id=2000000000 + chat_id)
    member_ids = {x.member_id for x in members.items if x.member_id > 0}
    user_ids = list(user_ids & member_ids)  # users in chat
    form_ids = [x[0] for x in await db.select([db.Form.id]).where(db.Form.user_id.in_(user_ids)).gino.all()]  # users have forms
    form_ids = [x[0] for x in await db.select([db.Expeditor.form_id]).where(db.Expeditor.form_id.in_(form_ids)).gino.all()]  # users have expeditor_map
    user_ids = [x[0] for x in await db.select([db.Form.user_id]).where(db.Form.id.in_(form_ids)).gino.all()]  # new users' ids after all filters
    for user_id in user_ids:
        await db.UsersToActionMode.create(action_mode_id=action_mode_id, user_id=user_id)
    reply = 'Добавлены пользователи:\n\n'
    users = await bot.api.users.get(user_ids=user_ids)
    user_names = [x[0] for x in await db.select([db.Form.name]).where(db.Form.user_id.in_(user_ids)).gino.all()]
    for i in range(len(users)):
        reply += f'{i + 1}. [id{user_ids[i]}|{user_names[i]} / {users[i].first_name} {users[i].last_name}]\n'
    await m.answer(reply)
    await send_users_in_action_mode(m, chat_id)
