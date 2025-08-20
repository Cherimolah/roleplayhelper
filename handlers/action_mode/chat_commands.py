from vkbottle.bot import Message
from vkbottle.dispatch.rules.base import VBMLRule, PayloadRule
from vkbottle import Keyboard, Text, KeyboardButtonColor, Callback

from loader import bot
from service.custom_rules import AdminRule, ActionModeTurn
from service.db_engine import db
from service.utils import get_current_form_id, next_step
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
    chat_name = (await bot.api.messages.get_conversations_by_id(peer_ids=m.peer_id)).items[0].chat_settings.title
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
                                                       f'запрашивает включение экшен-режима в чате «{chat_name}»'))[0]
        await db.ActionModeRequest.update.values(message_id=message.conversation_message_id).where(db.ActionModeRequest.id == request.id).gino.status()
    await m.answer('Запрос на включение экшен-режима отправлен судьям', keyboard=Keyboard())


@bot.on.chat_message(ActionModeTurn())
async def user_post(m: Message, action_mode_id: int):
    # TODO: всякие калькуляции, проверки и т.д.
    await next_step(action_mode_id)
