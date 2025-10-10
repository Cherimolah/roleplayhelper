"""
Модуль для работы с экшен-режимом в чатах.
Экшен-режим позволяет судье управлять очередностью ходов участников в специальном режиме.
"""

from vkbottle.bot import MessageEvent, Message
from vkbottle.dispatch.rules.base import PayloadMapRule, PayloadRule
from vkbottle import GroupEventType, Keyboard, KeyboardButtonColor, Text, VKAPIError
from vkbottle_types.objects import MessagesForward
from sqlalchemy import and_

from loader import bot, states
from service.custom_rules import JudgeRule, UserFree, JudgeFree, StateRule
from service.db_engine import db
from service.states import Judge
from handlers.questions import start
from service.utils import get_mention_from_message, filter_users_expeditors, parse_period
from service import keyboards


async def send_users_in_action_mode(m: Message | MessageEvent, chat_id: int):
    """
    Отправляет список пользователей в экшен-режиме и клавиатуру управления.

    Args:
        m: Сообщение или событие от пользователя
        chat_id: ID чата для экшен-режима
    """
    # Получаем ID экшен-режима для указанного чата
    action_mode_id = await db.select([db.ActionMode.id]).where(db.ActionMode.chat_id == chat_id).gino.scalar()

    # Формируем сообщение с инструкциями
    reply = ('Отправьте ссылки/сообщения/упоминания пользователей, которых хотите добавить в экшен режим\n'
             'Они должны находиться в нужном чате и иметь карту экспедитора!\n'
             'Когда будет готово нажмите кнопку запуска экшен-режима\n\n'
             'Игроки добавленные в экшен-режим:\n')

    # Получаем данные о пользователях в экшен-режиме
    users_data = await db.select([db.Form.user_id, db.Form.name]).select_from(
        db.UsersToActionMode.join(db.User, db.UsersToActionMode.user_id == db.User.user_id).join(db.Form,
                                                                                                 db.User.user_id == db.Form.user_id)
    ).where(db.UsersToActionMode.action_mode_id == action_mode_id).order_by(db.User.user_id.asc()).gino.all()

    user_ids = [x[0] for x in users_data]
    user_names = [x[1] for x in users_data]
    users = await bot.api.users.get(user_ids=user_ids)

    # Добавляем информацию о каждом пользователе в сообщение
    for i in range(len(users)):
        reply += f'{i + 1}. [id{user_ids[i]}|{user_names[i]} / {users[i].first_name} {users[i].last_name}]\n'

    # Создаем клавиатуру управления экшен-режимом
    keyboard = Keyboard().add(
        Text('Запустить экшен-режим', {'action_mode': 'start'}), KeyboardButtonColor.POSITIVE
    ).row().add(
        Text('Удалить участников', {'action_mode': 'delete_users'}), KeyboardButtonColor.NEGATIVE
    )

    # Отправляем сообщение в зависимости от типа входящего сообщения
    if isinstance(m, Message):
        await m.answer(reply, keyboard=keyboard)
    else:
        await bot.api.messages.send(peer_id=m.user_id, message=reply, keyboard=keyboard)


@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent,
                  PayloadMapRule({'action_mode_request_id': int, 'action_mode': 'decline'}), JudgeRule(), UserFree(),
                  JudgeFree())
async def decline_action_mode(m: MessageEvent):
    """
    Обрабатывает отклонение запроса на создание экшен-режима.

    Args:
        m: Событие сообщения с payload
    """
    request_id = m.payload['action_mode_request_id']
    request = await db.ActionModeRequest.get(request_id)

    # Проверяем актуальность запроса
    if not request:
        await m.show_snackbar('Запрос уже неактуален')
        return

    # Получаем ID чата и устанавливаем состояние для указания причины отказа
    chat_id = await db.select([db.ActionModeRequest.chat_id]).where(db.ActionModeRequest.id == request_id).gino.scalar()
    states.set(m.user_id, f'{Judge.REASON_DECLINE}*{chat_id}')
    await m.edit_message('Укажите причину отказа экшен-режима', keyboard=Keyboard().get_json())


@bot.on.private_message(StateRule(Judge.REASON_DECLINE), JudgeRule())
async def send_reason_decline(m: Message):
    """
    Отправляет причину отказа в создании экшен-режима.

    Args:
        m: Сообщение с причиной отказа
    """
    chat_id = int(states.get(m.from_id).split('*')[1])

    # Получаем данные о запросе
    data = await db.select([db.ActionModeRequest.judge_id, db.ActionModeRequest.message_id]).where(
        db.ActionModeRequest.chat_id == chat_id).gino.all()
    chat_name = (await bot.api.messages.get_conversations_by_id(peer_ids=2000000000 + chat_id)).items[
        0].chat_settings.title
    name = await db.select([db.Form.name]).where(db.Form.user_id == m.from_id).gino.scalar()
    user = await m.get_user()

    # Уведомляем всех судей о причине отказа
    for judge_id, cmid in data:
        try:
            await bot.api.messages.send(peer_id=judge_id, forward=MessagesForward(
                peer_id=judge_id, conversation_message_ids=[cmid], is_reply=True
            ), message=f'Судья [id{m.from_id}|{name} / {user.first_name} {user.last_name}] отклонил создание экшен '
                       f'режима в чате «{chat_name}» по причине: «{m.text}»')
        except:
            await bot.api.messages.send(peer_id=judge_id,
                                        message=f'Судья [id{m.from_id}|{name} / {user.first_name} {user.last_name}] отклонил создание экшен '
                                                f'режима в чате «{chat_name}» по причине: «{m.text}»')

    # Удаляем запрос и уведомляем чат
    await db.ActionModeRequest.delete.where(db.ActionModeRequest.chat_id == chat_id).gino.status()
    keyboard = Keyboard().add(
        Text('Запросить экшен-режим', {'action_mode': 'create_request'}), KeyboardButtonColor.PRIMARY
    )
    await bot.api.messages.send(peer_id=2000000000 + chat_id,
                                message=f'Судья [id{m.from_id}|{name} / {user.first_name} {user.last_name}] отклонил создание экшен '
                                        f'режима в чате «{chat_name}» по причине: «{m.text}»', keyboard=keyboard)
    await start(m)


@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent,
                  PayloadMapRule({'action_mode_request_id': int, 'action_mode': 'confirm'}), JudgeRule(), UserFree(),
                  JudgeFree())
async def confirm_action_mode(m: MessageEvent):
    """
    Обрабатывает подтверждение запроса на создание экшен-режима.

    Args:
        m: Событие сообщения с payload
    """
    request_id = m.payload['action_mode_request_id']
    request = await db.ActionModeRequest.get(request_id)

    # Проверяем актуальность запроса
    if not request:
        await m.show_snackbar('Запрос уже неактуален')
        return

    # Проверяем права доступа бота в чате
    try:
        members = await bot.api.messages.get_conversation_members(peer_id=2000000000 + request.chat_id)
        user_ids = {x.member_id for x in members.items if x.member_id > 0}
        if m.user_id not in user_ids:
            await m.show_snackbar('Необходимо вступить в чат для принятия судейства')
            return
    except VKAPIError:
        await m.show_snackbar('Предоставьте боту права администратора в чате!')
        return

    # Получаем информацию о чате и судье
    chat_name = (await bot.api.messages.get_conversations_by_id(peer_ids=2000000000 + request.chat_id)).items[
        0].chat_settings.title
    data = await db.select([db.ActionModeRequest.judge_id, db.ActionModeRequest.message_id]).where(
        db.ActionModeRequest.chat_id == request.chat_id).gino.all()
    name = await db.select([db.Form.name]).where(db.Form.user_id == m.user_id).gino.scalar()
    user = (await bot.api.users.get(user_ids=[m.user_id]))[0]

    # Уведомляем всех судей о подтверждении
    for judge_id, cmid in data:
        try:
            await bot.api.messages.send(peer_id=judge_id, forward=MessagesForward(
                peer_id=judge_id, conversation_message_ids=[cmid], is_reply=True
            ), message=f'Судья [id{m.from_id}|{name} / {user.first_name} {user.last_name}] активировал экшен '
                       f'режим в чате «{chat_name}»')
        except:
            await bot.api.messages.send(peer_id=judge_id,
                                        message=f'Судья [id{m.user_id}|{name} / {user.first_name} {user.last_name}] активировал экшен '
                                                f'режима в чате «{chat_name}»')

    # Удаляем запрос и создаем экшен-режим
    await db.ActionModeRequest.delete.where(db.ActionModeRequest.chat_id == request.chat_id).gino.status()
    await bot.api.messages.send(peer_id=2000000000 + request.chat_id,
                                message=f'Судья [id{m.user_id}|{name} / {user.first_name} {user.last_name}] активировал экшен '
                                        f'режим в чате «{chat_name}»\n'
                                        f'Сейчас определится список игроков и очередность их ходов')

    # Устанавливаем состояние и создаем экшен-режим
    states.set(m.user_id, Judge.ADD_USERS)
    action_mode = await db.ActionMode.create(chat_id=request.chat_id, judge_id=m.user_id)
    await db.UsersToActionMode.create(action_mode_id=action_mode.id, user_id=request.from_id)

    await m.edit_message(f'Вы активировали экшен-режим в чате «{chat_name}»')
    await send_users_in_action_mode(m, action_mode.chat_id)


@bot.on.private_message(StateRule(Judge.ADD_USERS), PayloadRule({'action_mode': 'start'}), JudgeRule())
@bot.on.private_message(StateRule(Judge.DELETE_USERS), PayloadRule({'action_mode': 'start'}), JudgeRule())
async def select_time_to_post(m: Message):
    """
    Запрашивает время на написание поста для экшен-режима.

    Args:
        m: Сообщение с командой запуска
    """
    reply = 'Укажите время на написание поста.\nФормат: 1 день 2 часа 3 минуты 4 секунды'
    keyboard = Keyboard().add(Text('Без ограничения', {'action_mode_time_post': 'null'}), KeyboardButtonColor.NEGATIVE)
    states.set(m.from_id, Judge.TIME_TO_POST)
    await m.answer(reply, keyboard=keyboard)


@bot.on.private_message(StateRule(Judge.TIME_TO_POST), PayloadRule({'action_mode_time_post': 'null'}), JudgeRule())
@bot.on.private_message(StateRule(Judge.TIME_TO_POST), JudgeRule())
async def start_action_mode(m: Message):
    """
    Запускает экшен-режим с указанными параметрами.

    Args:
        m: Сообщение с параметрами времени или без ограничений
    """
    chat_id, action_mode_id = await db.select([db.ActionMode.chat_id, db.ActionMode.id]).where(
        db.ActionMode.judge_id == m.from_id).gino.first()

    # Обрабатываем указанное время
    if not m.payload:
        try:
            seconds = parse_period(m.text)
        except:
            await m.answer('Неправльный формат периода')
            return
        if not seconds:
            await m.answer('Неправльный формат периода')
            return
        await db.ActionMode.update.values(time_to_post=seconds).where(db.ActionMode.id == action_mode_id).gino.status()

    # Запускаем экшен-режим
    await db.ActionMode.update.values(started=True).where(db.ActionMode.judge_id == m.from_id).gino.scalar()
    chat_name = (await bot.api.messages.get_conversations_by_id(peer_ids=[2000000000 + chat_id])).items[
        0].chat_settings.title
    await m.answer(f'Вы успешно запустили экшен-режим в чате «{chat_name}»\n')

    # Уведомляем участников чата
    judge_name = await db.select([db.Form.name]).where(db.Form.user_id == m.from_id).gino.scalar()
    judge = await m.get_user()
    await bot.api.messages.send(message=f'Судья [id{m.from_id}|{judge_name} / {judge.first_name} {judge.last_name}] '
                                        f'запустил экшен режим', peer_id=2000000000 + chat_id)

    # Ограничиваем права участников чата (read-only)
    members = await bot.api.messages.get_conversation_members(peer_id=2000000000 + chat_id)
    member_ids = {x.member_id for x in members.items if x.member_id > 0}
    member_ids.remove(judge.id)
    member_ids = list(member_ids)
    await bot.api.request('messages.changeConversationMemberRestrictions',
                          {'peer_id': 2000000000 + chat_id, 'member_ids': ','.join(list(map(str, member_ids))),
                           'action': 'ro'})

    await bot.api.messages.send(message='Сейчас очередь судьи писать свой пост', peer_id=2000000000 + chat_id)
    chat_name = (await bot.api.messages.get_conversations_by_id(peer_ids=[2000000000 + chat_id])).items[
        0].chat_settings.title
    reply = f'Вы находитесь в режиме управления экшен режима в чате «{chat_name}»'
    states.set(m.from_id, Judge.PANEL)
    await m.answer(reply, keyboard=keyboards.action_mode_panel)


@bot.on.private_message(StateRule(Judge.ADD_USERS), PayloadRule({'action_mode': 'delete_users'}), JudgeRule())
async def delete_users(m: Message):
    """
    Показывает список пользователей для удаления из экшен-режима.

    Args:
        m: Сообщение с командой удаления пользователей
    """
    states.set(m.from_id, Judge.DELETE_USERS)
    reply = 'Укажите номера пользователей через запятую, кого хотите удалить из экшен режима:\n\n'

    # Получаем данные о пользователях в экшен-режиме
    action_mode_id = await db.select([db.ActionMode.id]).where(db.ActionMode.judge_id == m.from_id).gino.scalar()
    users_data = await db.select([db.Form.user_id, db.Form.name]).select_from(
        db.UsersToActionMode.join(db.User, db.UsersToActionMode.user_id == db.User.user_id).join(db.Form,
                                                                                                 db.User.user_id == db.Form.user_id)
    ).where(db.UsersToActionMode.action_mode_id == action_mode_id).order_by(db.User.user_id.asc()).gino.all()

    user_ids = [x[0] for x in users_data]
    user_names = [x[1] for x in users_data]
    users = await bot.api.users.get(user_ids=user_ids)

    # Формируем список пользователей
    for i, user_id in enumerate(user_ids):
        reply += f'{i + 1}. [id{user_id}|{user_names[i]} / {users[i].first_name} {users[i].last_name}]\n'

    keyboard = Keyboard().add(
        Text('Запустить экшен-режим', {'action_mode': 'start'}), KeyboardButtonColor.POSITIVE
    ).row().add(
        Text('Добавить пользователей', {'action_mode': 'add_users'}), KeyboardButtonColor.POSITIVE
    )
    await m.answer(reply, keyboard=keyboard)


@bot.on.private_message(StateRule(Judge.DELETE_USERS), PayloadRule({'action_mode': 'add_users'}), JudgeRule())
async def add_users(m: Message):
    """
    Переключает в режим добавления пользователей в экшен-режим.

    Args:
        m: Сообщение с командой добавления пользователей
    """
    states.set(m.from_id, Judge.ADD_USERS)
    chat_id = await db.select([db.ActionMode.chat_id]).where(db.ActionMode.judge_id == m.from_id).gino.scalar()
    await send_users_in_action_mode(m, chat_id)


@bot.on.private_message(StateRule(Judge.DELETE_USERS), JudgeRule())
async def delete_users_from_action_mode(m: Message):
    """
    Удаляет пользователей из экшен-режима по указанным номерам.

    Args:
        m: Сообщение с номерами пользователей для удаления
    """
    action_mode_id = await db.select([db.ActionMode.id]).where(db.ActionMode.judge_id == m.from_id).gino.scalar()
    user_ids = [x[0] for x in await db.select([db.UsersToActionMode.user_id]).where(
        db.UsersToActionMode.action_mode_id == action_mode_id).order_by(db.UsersToActionMode.user_id.asc()).order_by(
        db.UsersToActionMode.user_id.asc()).gino.all()]

    try:
        numbers = list(map(int, m.text.replace(' ', '').split(',')))
    except:
        await m.answer('Неправильный формат!')
        return

    # Удаляем пользователей по указанным номерам
    for i in numbers:
        try:
            await db.UsersToActionMode.delete.where(and_(db.UsersToActionMode.action_mode_id == action_mode_id,
                                                         db.UsersToActionMode.user_id == user_ids[i - 1])).gino.status()
        except IndexError:
            pass  # Пропускаем некорректные номера

    await delete_users(m)


@bot.on.private_message(StateRule(Judge.ADD_USERS), JudgeRule())
async def add_users_to_action_mode(m: Message):
    """
    Добавляет пользователей в экшен-режим по упоминаниям в сообщении.

    Args:
        m: Сообщение с упоминаниями пользователей
    """
    user_ids = await get_mention_from_message(m, many_users=True)
    if not user_ids:
        await m.answer('Пользователей не найдено')
        return

    # Фильтруем пользователей с картой экспедитора
    chat_id = await db.select([db.ActionMode.chat_id]).where(db.ActionMode.judge_id == m.from_id).gino.scalar()
    action_mode_id = await db.select([db.ActionMode.id]).where(db.ActionMode.chat_id == chat_id).gino.scalar()
    user_ids = await filter_users_expeditors(user_ids, chat_id)

    # Добавляем пользователей в экшен-режим
    for user_id in user_ids:
        await db.UsersToActionMode.create(action_mode_id=action_mode_id, user_id=user_id)

    # Формируем отчет о добавленных пользователях
    reply = 'Добавлены пользователи:\n\n'
    users_data = await db.select([db.Form.user_id, db.Form.name]).where(db.Form.user_id.in_(user_ids)).gino.all()
    users = await bot.api.users.get(user_ids=[x[0] for x in users_data])
    for i in range(len(users_data)):
        reply += f'{i + 1}. [id{users[i].id}|{users_data[i][1]} / {users[i].first_name} {users[i].last_name}]\n'

    await m.answer(reply)
    await send_users_in_action_mode(m, chat_id)
