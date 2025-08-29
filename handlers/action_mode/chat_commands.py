from vkbottle.bot import Message
from vkbottle.dispatch.rules.base import VBMLRule, PayloadRule
from vkbottle import Keyboard, KeyboardButtonColor, Callback, VKAPIError
from sqlalchemy import and_

from loader import bot
from service.custom_rules import AdminRule, ActionModeTurn, JudgePostTurn
from service.db_engine import db
from service.utils import get_current_form_id, parse_actions, next_round
from service import keyboards


@bot.on.chat_message(VBMLRule('/клавиатура'), AdminRule())
async def send_keyboard(m: Message):
    await m.answer('Кнопка для запроса экшен-режима', keyboard=keyboards.request_action_mode)


@bot.on.chat_message(PayloadRule({'action_mode': 'create_request'}))
async def create_action_mode_request(m: Message):
    form_id = await get_current_form_id(m.from_id)
    expeditor_map = await db.select([db.Expeditor.id]).where(db.Expeditor.form_id == form_id).gino.scalar()
    if not expeditor_map:
        await m.answer('У вас нет созданной карты экспедитора!')
        return
    exist = await db.select([db.ActionModeRequest.id]).where(db.ActionModeRequest.chat_id == m.chat_id).gino.scalar()
    if exist:
        await m.answer('Уже существует запрос на экшен-режим в этом чате')
        return
    name = await db.select([db.Form.name]).where(db.Form.id == form_id).gino.scalar()
    user = await m.get_user()
    try:
        chat_name = (await bot.api.messages.get_conversations_by_id(peer_ids=m.peer_id)).items[0].chat_settings.title
    except VKAPIError:
        await m.answer('Предоставьте боту права администратора!')
        return
    try:
        link = (await bot.api.messages.get_invite_link(peer_id=m.peer_id, visible_messages_count=1000)).link
    except VKAPIError:
        await m.answer('Необходимо, чтобы создатель чата открыл видимость ссылки для приглашения')
        return
    judges = [x[0] for x in await db.select([db.User.user_id]).where(db.User.judge.is_(True)).gino.all()]
    for judge_id in judges:
        request = await db.ActionModeRequest.create(judge_id=judge_id, chat_id=m.chat_id, from_id=m.from_id)
        keyboard = Keyboard(inline=True).add(
            Callback('Принять', {'action_mode_request_id': request.id, 'action_mode': 'confirm'}), KeyboardButtonColor.POSITIVE
        ).row().add(
            Callback('Отклонить', {'action_mode_request_id': request.id, 'action_mode': 'decline'}), KeyboardButtonColor.NEGATIVE
        )
        message = (await bot.api.messages.send(peer_id=judge_id, keyboard=keyboard,
                                               message=f'Игрок [id{m.from_id}|{name} / {user.first_name} {user.last_name}] '
                                                       f'запрашивает включение экшен-режима в чате «{chat_name}»\n'
                                                       f'Ссылка на чат: {link}'))[0]
        await db.ActionModeRequest.update.values(message_id=message.conversation_message_id).where(db.ActionModeRequest.id == request.id).gino.status()
    await m.answer('Запрос на включение экшен-режима отправлен судьям', keyboard=Keyboard())


@bot.on.chat_message(ActionModeTurn())
async def user_post(m: Message, action_mode_id: int):
    form_id = await get_current_form_id(m.from_id)
    expeditor_id = await db.select([db.Expeditor.id]).where(db.Expeditor.form_id == form_id).gino.scalar()
    actions = await parse_actions(m.text.lower(), expeditor_id)
    if not actions:
        await m.answer('Вы не указали в своем посте действия в []')
        return
    await bot.api.request('messages.changeConversationMemberRestrictions',
                          {'peer_id': m.peer_id, 'member_ids': m.from_id, 'action': 'ro'})
    post_id = await db.select([db.Post.id]).where(and_(db.Post.user_id == m.from_id, db.Post.action_mode_id == action_mode_id)).order_by(db.Post.id.desc()).gino.scalar()
    for action in actions:
        await db.Action.create(data=action, post_id=post_id)
    await db.ActionMode.update.values(check_status=True).where(db.ActionMode.id == action_mode_id).gino.status()
    await m.answer('Ваш пост принят, ожидайте проверки судьи')
    judge_id = await db.select([db.ActionMode.judge_id]).where(db.ActionMode.id == action_mode_id).gino.scalar()
    name = await db.select([db.Form.name]).where(db.Form.user_id == m.from_id).gino.scalar()
    user = await m.get_user()
    reply = (f'Пользователь [id{m.from_id}|{name} / {user.first_name} {user.last_name}] написал свой пост.\n'
             f'Нажмите кнопку, чтобы начать проверку')
    keyboard = Keyboard(inline=True).add(
        Callback('Начать проверку', {'start_check': post_id}), KeyboardButtonColor.PRIMARY
    )
    forward = {'peer_id': m.peer_id, 'conversation_message_ids': [m.conversation_message_id], 'is_reply': False}
    await bot.api.messages.send(peer_id=judge_id, message=reply, keyboard=keyboard, forward=forward)


@bot.on.chat_message(JudgePostTurn())
async def judge_post_turn(m: Message, action_mode_id: int):
    await bot.api.request('messages.changeConversationMemberRestrictions',
                          {'peer_id': m.peer_id, 'member_ids': m.from_id, 'action': 'ro'})
    await next_round(action_mode_id)
