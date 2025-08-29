from vkbottle.bot import Message, MessageEvent
from vkbottle.dispatch.rules.base import PayloadRule, PayloadMapRule
from vkbottle import Keyboard, Callback, KeyboardButtonColor, GroupEventType, Text
from sqlalchemy import and_

from loader import bot, states
from service.db_engine import db
from service.custom_rules import StateRule, JudgeRule, NumericRule
from service.states import Judge, Menu
from service.utils import get_mention_from_message, filter_users_expeditors, get_current_turn
from service import keyboards
from handlers.questions import start


@bot.on.private_message(StateRule(Judge.PANEL), PayloadRule({'judge_action': 'add_users_active'}), JudgeRule())
async def select_add_users_active_action_mode(m: Message):
    states.set(m.from_id, Judge.ADD_USERS_ACTIVE)
    await m.answer('Укажите ссылки/сообщения/упоминания каких пользователей хотите добавить в экшен-режим',
                   keyboard=Keyboard())


@bot.on.private_message(StateRule(Judge.ADD_USERS_ACTIVE), JudgeRule())
async def add_active_action_mode_users(m: Message):
    user_ids = await get_mention_from_message(m, many_users=True)
    action_mode_id, chat_id = await db.select([db.ActionMode.id, db.ActionMode.chat_id]).where(db.ActionMode.judge_id == m.from_id).gino.first()
    user_ids = await filter_users_expeditors(user_ids, chat_id)
    added_users = []
    for user_id in user_ids:
        exited = await db.select([db.UsersToActionMode.exited]).where(and_(db.UsersToActionMode.user_id == user_id, db.UsersToActionMode.action_mode_id == action_mode_id)).gino.scalar()
        if exited:
            await db.UsersToActionMode.update.values(exited=False).where(and_(db.UsersToActionMode.user_id == user_id, db.UsersToActionMode.action_mode_id == action_mode_id)).gino.status()
        else:
            await db.UsersToActionMode.create(action_mode_id=action_mode_id, user_id=user_id)
        added_users.append(user_id)
    users_data = await db.select([db.Form.user_id, db.Form.name]).where(db.Form.user_id.in_(added_users)).gino.all()
    users = await bot.api.users.get(user_ids=[x[0] for x in users_data])
    reply = 'Добавленные пользователи:\n\n'
    for i in range(len(users_data)):
        reply += f'{i + 1}. [id{users[i].id}|{users_data[i][1]} / {users[i].first_name} {users[i].last_name}]\n'
    states.set(m.from_id, Judge.PANEL)
    await m.answer(reply, keyboard=keyboards.action_mode_panel)


@bot.on.private_message(StateRule(Judge.PANEL), PayloadRule({'judge_action': 'delete_users_active'}), JudgeRule())
async def select_add_users_active_action_mode(m: Message):
    states.set(m.from_id, Judge.DELETE_USERS_ACTIVE)
    action_mode_id = await db.select([db.ActionMode.id]).where(db.ActionMode.judge_id == m.from_id).gino.scalar()
    user_ids = [x[0] for x in await db.select([db.UsersToActionMode.user_id]).where(db.UsersToActionMode.action_mode_id == action_mode_id).gino.all()]
    users_data = await db.select([db.Form.user_id, db.Form.name]).where(db.Form.user_id.in_(user_ids)).order_by(db.Form.user_id.asc()).gino.all()
    users = await bot.api.users.get(user_ids=[x[0] for x in users_data])
    reply = 'Укажите номера пользователей, кого хотите удалить из экшен режима:\n\n'
    for i in range(len(users_data)):
        reply += f'{i + 1}. [id{users_data[i][0]}|{users_data[i][1]} / {users[i].first_name} {users[i].last_name}]\n'
    await m.answer(reply, keyboard=Keyboard())


@bot.on.private_message(StateRule(Judge.DELETE_USERS_ACTIVE), JudgeRule())
async def delete_users_activa_action_mode(m: Message):
    try:
        numbers = list(map(int, m.text.replace(' ', '').split(',')))
    except:
        await m.answer('Неправильный формат')
        return
    action_mode_id = await db.select([db.ActionMode.id]).where(db.ActionMode.judge_id == m.from_id).gino.scalar()
    user_ids = [x[0] for x in await db.select([db.UsersToActionMode.user_id]).where(db.UsersToActionMode.action_mode_id == action_mode_id).order_by(db.UsersToActionMode.user_id.asc()).gino.all()]
    exited = []
    for number in numbers:
        try:
            participate = await db.select([db.UsersToActionMode.participate]).where(and_(db.UsersToActionMode.action_mode_id == action_mode_id, db.UsersToActionMode.user_id == user_ids[number - 1])).gino.scalar()
            if not participate:  # Если типка добавили, но цикл не обновился и сразу хотят удалить, его можно делитнуть
                await db.UsersToActionMode.delete.where(and_(db.UsersToActionMode.action_mode_id == action_mode_id, db.UsersToActionMode.user_id == user_ids[number - 1])).gino.status()
            else:
                await db.UsersToActionMode.update.values(exited=True).where(and_(db.UsersToActionMode.action_mode_id == action_mode_id, db.UsersToActionMode.user_id == user_ids[number - 1])).gino.status()
            exited.append(user_ids[number - 1])
        except IndexError:
            pass
    users_data = await db.select([db.Form.user_id, db.Form.name]).where(db.Form.user_id.in_(exited)).gino.all()
    users = await bot.api.users.get(user_ids=[x[0] for x in users_data])
    reply = 'Эти игроки будут удалены из экшен-режима:\n\n'
    for i in range(len(users)):
        reply += f'{i + 1}. [id{users_data[i][0]}|{users_data[i][1]} / {users[i].first_name} {users[i].last_name}]\n'
    states.set(m.from_id, Judge.PANEL)
    await m.answer(reply, keyboard=keyboards.action_mode_panel)


@bot.on.private_message(StateRule(Judge.PANEL), PayloadRule({'judge_action': 'list_users'}), JudgeRule())
async def list_action_mode_users(m: Message):
    action_mode_id, chat_id = await db.select([db.ActionMode.id, db.ActionMode.chat_id]).where(db.ActionMode.judge_id == m.from_id).gino.first()
    users_actions = await db.select([*db.UsersToActionMode]).where(db.UsersToActionMode.action_mode_id == action_mode_id).gino.all()
    chat_name = (await bot.api.messages.get_conversations_by_id(peer_ids=[2000000000 + chat_id])).items[0].chat_settings.title
    reply = (f'Пользователи в экшен режиме чата «{chat_name}»\n'
             f'➕ - будут добавлены в следующем цикле\n'
             f'❌ - будут удалены в следующем цикле\n'
             f'🔵 - текущая очередь писать пост'
             f'В скобках указана текущая инициатива\n\n')
    users = await bot.api.users.get(user_ids=[x.user_id for x in users_actions])
    turn = await get_current_turn(action_mode_id)
    for i, user_action in enumerate(users_actions):
        name = await db.select([db.Form.name]).where(db.Form.user_id == users[i].id).gino.scalar()
        added = "➕" if not user_action.participate else ''
        deleted = "❌" if user_action.exited else ''
        if users[i].id == turn:
            current_turn = '🔵'
        else:
            current_turn = ''
        reply += f'{current_turn} {i + 1}. {added}{deleted} [id{users[i].id}|{name} / {users[i].first_name} {users[i].last_name}] ({user_action.initiative})\n'
    await m.answer(reply)


@bot.on.private_message(StateRule(Judge.PANEL), PayloadRule({'judge_action': 'pass_judge'}), JudgeRule())
@bot.on.private_message(StateRule(Judge.CONFIRM_PASS), PayloadRule({'pass_action_mode': 'cancel'}), JudgeRule())
async def select_user_to_pass_judge(m: Message):
    judge_ids = {x[0] for x in await db.select([db.User.user_id]).where(db.User.judge.is_(True)).order_by(db.User.user_id.asc()).gino.all()}
    active_judge_ids = {x[0] for x in await db.select([db.ActionMode.judge_id]).gino.all()}
    free_judge_ids = list(judge_ids - active_judge_ids)
    free_judge_ids.sort()
    names = [x[0] for x in await db.select([db.Form.name]).where(db.Form.user_id.in_(free_judge_ids)).order_by(db.Form.user_id.asc()).gino.all()]
    users = await bot.api.users.get(user_ids=free_judge_ids)
    reply = 'Укажите номер пользователя, которому вы хотите передать судейство:\n\n'
    for i in range(len(users)):
        reply += f'{i + 1}. [id{users[i].id}|{names[i]} / {users[i].first_name} {users[i].last_name}]\n'
    keyboard = Keyboard().add(
        Text('Назад', {'judge_action': 'back'}), KeyboardButtonColor.NEGATIVE
    )
    states.set(m.from_id, Judge.SELECT_USER_TO_PASS)
    await m.answer(reply, keyboard=keyboard)


@bot.on.private_message(StateRule(Judge.SELECT_USER_TO_PASS), PayloadRule({'judge_action': 'back'}), JudgeRule())
async def back_to_panel(m: Message):
    states.set(m.from_id, Judge.PANEL)
    await m.answer('Панель управления экшен-режимом', keyboard=keyboards.action_mode_panel)


@bot.on.private_message(StateRule(Judge.SELECT_USER_TO_PASS), NumericRule(), JudgeRule())
async def send_confirm_to_pass(m: Message, value: int):
    judge_ids = {x[0] for x in await db.select([db.User.user_id]).where(db.User.judge.is_(True)).order_by(
        db.User.user_id.asc()).gino.all()}
    active_judge_ids = {x[0] for x in await db.select([db.ActionMode.judge_id]).gino.all()}
    free_judge_ids = list(judge_ids - active_judge_ids)
    free_judge_ids.sort()
    if value > len(free_judge_ids):
        await m.answer('Номер слишком большой')
        return
    user_id = free_judge_ids[value - 1]
    name = await db.select([db.Form.name]).where(db.Form.user_id == user_id).gino.scalar()
    user = (await bot.api.users.get(user_ids=[user_id]))[0]
    reply = f'Вы действительно хотите передать судейство над экшен-режимом пользователю [id{user_id}|{name} / {user.first_name} {user.last_name}]?'
    action_mode_id = await db.select([db.ActionMode.id]).where(db.ActionMode.judge_id == m.from_id).gino.scalar()
    keyboard = Keyboard().add(
        Text('Подтвердить', {'pass_action_mode': action_mode_id, 'judge_id': user_id}), KeyboardButtonColor.POSITIVE
    ).row().add(
        Text('Отклонить', {'pass_action_mode': 'cancel'}), KeyboardButtonColor.NEGATIVE
    )
    states.set(m.from_id, Judge.CONFIRM_PASS)
    await m.answer(reply, keyboard=keyboard)


@bot.on.private_message(StateRule(Judge.CONFIRM_PASS), PayloadMapRule({'pass_action_mode': int, 'judge_id': int}), JudgeRule())
async def pass_action_mode(m: Message):
    action_mode_id = m.payload['pass_action_mode']
    judge_id = m.payload['judge_id']
    busy = await db.select([db.ActionMode.chat_id]).where(db.ActionMode.judge_id == judge_id).gino.scalar()
    if busy:
        chat_name = (await bot.api.messages.get_conversations_by_id(peer_ids=[2000000000 + busy])).items[0].chat_settings.title
        await m.answer(f'Этот пользователь уже является судьей экшен-режима в чате «{chat_name}»')
        return
    await db.ActionMode.update.values(judge_id=judge_id).where(db.ActionMode.id == action_mode_id).gino.status()
    states.set(m.from_id, Menu.MAIN)
    await db.User.update.values(state=str(Judge.PANEL)).where(db.User.user_id == judge_id).gino.status()
    number_step = await db.select([db.ActionMode.number_step]).where(db.ActionMode.id == action_mode_id).gino.scalar()
    chat_id = await db.select([db.ActionMode.chat_id]).where(db.ActionMode.id == action_mode_id).gino.scalar()
    if number_step == 0:  # Ход судьи
        await bot.api.request('messages.changeConversationMemberRestrictions',
                          {'peer_id': 2000000000 + chat_id, 'member_ids': m.from_id, 'action': 'ro'})
        await bot.api.request('messages.changeConversationMemberRestrictions',
                              {'peer_id': 2000000000 + chat_id, 'member_ids': judge_id, 'action': 'rw'})
    name_new = await db.select([db.Form.name]).where(db.Form.user_id == judge_id).gino.scalar()
    user_new = (await bot.api.users.get(user_ids=[judge_id]))[0]
    await m.answer(f'Вы передали судейство экшен-режимом пользователю [id{judge_id}|{name_new} / {user_new.first_name} {user_new.last_name}]')
    await start(m)
    name = await db.select([db.Form.name]).where(db.Form.user_id == m.from_id).gino.scalar()
    user = (await bot.api.users.get(user_ids=[m.from_id]))[0]
    chat_name = (await bot.api.messages.get_conversations_by_id(peer_ids=[2000000000 + chat_id])).items[0].chat_settings.title
    link = (await bot.api.messages.get_invite_link(peer_id=2000000000 + chat_id, visible_message_count=1000)).link
    await bot.api.messages.send(peer_id=judge_id, message=f'Пользователь [id{m.from_id}|{name} / {user.first_name} {user.last_name}] '
                                                          f'передал вам судейство экшен-режима в чате «{chat_name}»\n'
                                                          f'Ссылка на чат: {link}',
                                keyboard=keyboards.action_mode_panel)


@bot.on.private_message(StateRule(Judge.PANEL), PayloadRule({'judge_action': 'finish_action_mode'}), JudgeRule())
async def finish_action_mode(m: Message):
    reply = ('Вы действительно хотите завершить экшен-режим?\n'
             'После подтверждения это действие нельзя будет отменить')
    keyboard = Keyboard(inline=True).add(
        Callback('Подтвердить', {'judge_action': 'confirm_finish_action_mode'}), KeyboardButtonColor.POSITIVE
    ).row().add(
        Callback('Отклонить', {'judge_action': 'decline_finish_action_mode'}), KeyboardButtonColor.NEGATIVE
    )
    await m.answer(reply, keyboard=keyboard)


@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent, PayloadRule({'judge_action': 'decline_finish_action_mode'}))
async def decline_finish_action_mode(m: MessageEvent):
    await m.edit_message('Отклонено завершение экшен-режима')


@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent, PayloadRule({'judge_action': 'confirm_finish_action_mode'}), JudgeRule())
async def confirm_finish_action_mode(m: MessageEvent):
    action_mode_id = await db.select([db.ActionMode.id]).where(db.ActionMode.judge_id == m.user_id).gino.scalar()
    await db.ActionMode.update.values(finished=True).where(db.ActionMode.id == action_mode_id).gino.status()
    await m.edit_message('Экшен режим будет остановлен после проверки игрока', keyboard=Keyboard().get_json())
    await bot.api.messages.send(peer_id=m.user_id, message='Функции бота будут доступны после окончательного завершения экшен режима')

