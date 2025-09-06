import asyncio

from vkbottle.bot import Message
from vkbottle.dispatch.rules.base import VBMLRule, PayloadRule
from vkbottle import VKAPIError, Keyboard, Text, KeyboardButtonColor

from loader import bot, states, user_bot
from service.custom_rules import AdminRule, StateRule, UserFree, NumericRule, FromUserRule
from service.db_engine import db
from service.states import Admin
from service import keyboards
from handlers.questions import start
from config import USER_ID, GROUP_ID


@bot.on.chat_message(AdminRule(), VBMLRule('/настройки'), UserFree())
@bot.on.private_message(StateRule(Admin.CHAT_SELECT_TYPE), PayloadRule({'set_chat_type': 'back'}))
@bot.on.private_message(StateRule(Admin.CHAT_SET_VISIBLE_MESSAGES_COUNT), PayloadRule({'set_visible_messages_count': 'back'}))
@bot.on.private_message(StateRule(Admin.CHAT_SET_VISIBLE_MESSAGES_COUNT), PayloadRule({'set_visible_messages_count': 'back'}))
@bot.on.private_message(StateRule(Admin.CHAT_ADD_PROFESSION), PayloadRule({'add_available_professions': 'back'}))
@bot.on.private_message(StateRule(Admin.CHAT_DELETE_PROFESSION), PayloadRule({'delete_available_professions': 'back'}))
async def chat_settings(m: Message):
    if m.peer_id > 2000000000:
        registered = await db.select([db.Chat.chat_id]).where(db.Chat.chat_id == m.chat_id).gino.scalar()
        if not registered:
            try:
                members = (await bot.api.messages.get_conversation_members(peer_id=m.peer_id)).items
                member_ids = [x.member_id for x in members if x.member_id > 0]
            except VKAPIError:
                await m.answer('Предоставьте боту права администратора!')
                return
            try:
                await bot.api.messages.get_invite_link(peer_id=m.peer_id)
            except VKAPIError:
                await m.answer('Предоставьте доступ к ссылке на чат для админов / всех пользователей')
                return
            await bot.api.request('messages.changeConversationMemberRestrictions',
                              {'peer_id': m.peer_id, 'member_ids': ','.join(list(map(str, member_ids))), 'action': 'ro'})
            await db.Chat.create(chat_id=m.chat_id)
        chat_id = m.chat_id
        await db.User.update.values(state=f'{Admin.CHAT_SETTINGS}*{chat_id}').where(db.User.user_id == m.from_id).gino.status()
        await m.answer('Перейдите в личные сообщения для настройки этого чата')
    else:
        _, chat_id = states.get(m.from_id).split('*')
        chat_id = int(chat_id)
        states.set(m.from_id, f'{Admin.CHAT_SETTINGS}*{chat_id}')
    chat = await db.select([*db.Chat]).where(db.Chat.chat_id == chat_id).gino.first()
    names = [x[0] for x in await db.select([db.Profession.name]).select_from(
        db.ChatToProfessions.join(db.Profession, db.ChatToProfessions.profession_id == db.Profession.id)
    ).where(db.ChatToProfessions.chat_id == chat_id).gino.all()]
    chat_name = (await bot.api.messages.get_conversations_by_id(peer_ids=[2000000000 + chat_id])).items[0].chat_settings.title
    reply = (f'Текущие настройки чата «{chat_name}»:\n'
             f'Тип чата: {"открытый" if not chat.is_private else "закрытый"}\n'
             f'Количество видимых сообщений в ссылке: {chat.visible_messages}\n'
             f'Доступные профессии: {", ".join(names)}\n')
    await bot.api.messages.send(peer_id=m.from_id, message=reply, keyboard=keyboards.chat_settings_panel)


@bot.on.private_message(PayloadRule({'chat_settings': 'chat_type'}), StateRule(Admin.CHAT_SETTINGS), AdminRule())
async def change_chat_type(m: Message):
    reply = 'Выберите тип чата, который хотите установить:'
    keyboard = Keyboard().add(
        Text('Приватный', {'set_chat_type': 'private'}), KeyboardButtonColor.PRIMARY
    ).row().add(
        Text('Публичный', {'set_chat_type': 'group'}), KeyboardButtonColor.PRIMARY
    ).row().add(
        Text('Назад', {'set_chat_type': 'back'}), KeyboardButtonColor.NEGATIVE
    )
    _, chat_id = states.get(m.from_id).split('*')
    states.set(m.from_id, f"{Admin.CHAT_SELECT_TYPE}*{chat_id}")
    await m.answer(reply, keyboard=keyboard)


@bot.on.private_message(PayloadRule({'set_chat_type': 'private'}), StateRule(Admin.CHAT_SELECT_TYPE), AdminRule())
@bot.on.private_message(PayloadRule({'set_chat_type': 'group'}), StateRule(Admin.CHAT_SELECT_TYPE), AdminRule())
async def set_chat_type(m: Message):
    type_chat = m.payload['set_chat_type']
    is_private = type_chat == 'private'
    _, chat_id = states.get(m.from_id).split('*')
    chat_id = int(chat_id)
    if is_private:
        user_chat_id = await db.select([db.Chat.user_chat_id]).where(db.Chat.chat_id == chat_id).gino.scalar()
        if not user_chat_id:
            members = (await bot.api.messages.get_conversation_members(peer_id=m.peer_id)).items
            member_ids = {x.member_id for x in members if x.member_id > 0}
            if USER_ID not in member_ids:
                await m.answer('Необходимо добавить аккаунт юзер-бота в этот чат!')
                return
            await m.answer('Проверяется связь и возможность добавлять пользователей....')
            message = (await bot.api.messages.send(message=f'/приват {chat_id}', peer_id=chat_id + 2000000000))[0]
            await asyncio.sleep(3)
            await bot.api.messages.delete(cmids=[message.conversation_message_id], peer_id=chat_id + 2000000000, delete_for_all=True)
            user_chat_id = await db.select([db.Chat.user_chat_id]).where(db.Chat.chat_id == chat_id).gino.scalar()
            if not user_chat_id:
                await m.answer('Не удалось установить связь между аккаунтом и ботом. Возможно юзер-бот не имеет права приглашать пользователей')
                return
    await db.Chat.update.values(is_private=is_private).where(db.Chat.chat_id == chat_id).gino.status()
    await m.answer('Значение успешно установлено')
    await chat_settings(m)


@user_bot.on.chat_message(FromUserRule(GROUP_ID), text='/приват <chat_id:int>')
async def connect_private_chat(m: Message, chat_id: int):
    can_invite = (await user_bot.api.messages.get_conversations_by_id(peer_ids=[m.peer_id])).items[0].chat_settings.acl.can_invite
    if not can_invite:
        return
    await db.Chat.update.values(user_chat_id=m.chat_id).where(db.Chat.chat_id == chat_id).gino.status()


@bot.on.private_message(PayloadRule({'chat_settings': 'visible_messages_count'}), StateRule(Admin.CHAT_SETTINGS), AdminRule())
async def send_info_visible_messages_count(m: Message):
    _, chat_id = states.get(m.from_id).split('*')
    states.set(m.from_id, f'{Admin.CHAT_SET_VISIBLE_MESSAGES_COUNT}*{chat_id}')
    keyboard = Keyboard().add(
        Text('Назад', {'set_visible_messages_count': 'back'}), KeyboardButtonColor.NEGATIVE
    )
    await m.answer('Напишите количество сообщений, которые будут видны при заходе в чат по ссылке (от 0 до 1000).',
                   keyboard=keyboard)


@bot.on.private_message(StateRule(Admin.CHAT_SET_VISIBLE_MESSAGES_COUNT), NumericRule(max_number=1000, min_number=0), AdminRule())
async def set_visible_messages_count(m: Message, value: int):
    _, chat_id = states.get(m.from_id).split('*')
    chat_id = int(chat_id)
    await db.Chat.update.values(visible_messages=value).where(db.Chat.chat_id == chat_id).gino.status()
    await m.answer('Значение успешно установлено')
    await chat_settings(m)


@bot.on.private_message(StateRule(Admin.CHAT_SETTINGS), PayloadRule({'chat_settings': 'add_available_professions'}), AdminRule())
async def show_available_professions(m: Message):
    _, chat_id = states.get(m.from_id).split('*')
    chat_id = int(chat_id)
    active_profession_ids = [x[0] for x in await db.select([db.ChatToProfessions.profession_id]).where(db.ChatToProfessions.chat_id == chat_id).gino.all()]
    names = [x[0] for x in await db.select([db.Profession.name]).where(db.Profession.id.notin_(active_profession_ids)).order_by(db.Profession.id.asc()).gino.all()]
    reply = 'Укажите номер профессии, к которой хотите открыть доступ:\n\n'
    for i, name in enumerate(names):
        reply += f'{i + 1}. {name}\n'
    keyboard = Keyboard().add(
        Text('Назад', {'add_available_professions': 'back'}), KeyboardButtonColor.NEGATIVE
    )
    states.set(m.from_id, f"{Admin.CHAT_ADD_PROFESSION}*{chat_id}")
    await m.answer(reply, keyboard=keyboard)


@bot.on.private_message(StateRule(Admin.CHAT_ADD_PROFESSION), NumericRule(), AdminRule())
async def open_profession(m: Message, value: int):
    _, chat_id = states.get(m.from_id).split('*')
    chat_id = int(chat_id)
    active_profession_ids = [x[0] for x in await db.select([db.ChatToProfessions.profession_id]).where(db.ChatToProfessions.chat_id == chat_id).gino.all()]
    profession_id = await db.select([db.Profession.id]).where(db.Profession.id.notin_(active_profession_ids)).order_by(db.Profession.id.asc()).offset(value - 1).limit(1).gino.scalar()
    if not profession_id:
        await m.answer('Неверный номер')
        return
    await db.ChatToProfessions.create(chat_id=chat_id, profession_id=profession_id)
    await m.answer('Значение успешно установлено')
    await chat_settings(m)


@bot.on.private_message(StateRule(Admin.CHAT_SETTINGS), PayloadRule({'chat_settings': 'delete_available_professions'}), AdminRule())
async def select_delete_profession(m: Message):
    _, chat_id = states.get(m.from_id).split('*')
    chat_id = int(chat_id)
    names = [x[0] for x in await db.select([db.Profession.name]).select_from(
        db.ChatToProfessions.join(db.Profession, db.ChatToProfessions.profession_id == db.Profession.id)
    ).where(db.ChatToProfessions.chat_id == chat_id).order_by(db.ChatToProfessions.id.asc()).gino.all()]
    reply = 'Выберите профессию, к которой хотите запретить доступ:\n\n'
    for i, name in enumerate(names):
        reply += f'{i + 1}. {name}\n'
    keyboard = Keyboard().add(
        Text('Назад', {'delete_available_professions': 'back'}), KeyboardButtonColor.NEGATIVE
    )
    states.set(m.from_id, f"{Admin.CHAT_DELETE_PROFESSION}*{chat_id}")
    await m.answer(reply, keyboard=keyboard)


@bot.on.private_message(StateRule(Admin.CHAT_DELETE_PROFESSION), NumericRule(), AdminRule())
async def delete_profession(m: Message, value: int):
    _, chat_id = states.get(m.from_id).split('*')
    chat_id = int(chat_id)
    row_id = await db.select([db.ChatToProfessions.id]).where(db.ChatToProfessions.chat_id == chat_id).order_by(db.ChatToProfessions.id.asc()).offset(value - 1).limit(1).gino.scalar()
    if not row_id:
        await m.answer('Неверный номер')
        return
    await db.ChatToProfessions.delete.where(db.ChatToProfessions.id == row_id).gino.status()
    await m.answer('Значение успешно установлено')
    await chat_settings(m)


@bot.on.private_message(StateRule(Admin.CHAT_SETTINGS), PayloadRule({'chat_settings': 'save'}), AdminRule())
async def save_profession(m: Message):
    await start(m)


@bot.on.chat_message(FromUserRule(USER_ID), text='/каюта <cabin_number:int>')
async def set_cabin_number(m: Message, cabin_number: int):
    user_id = await db.select([db.Form.user_id]).where(db.Form.cabin == cabin_number).gino.scalar()
    exist = await db.select([db.Chat.chat_id]).where(db.Chat.cabin_user_id == user_id).gino.scalar()
    if exist:
        await db.Chat.update.values(chat_id=m.chat_id).where(db.Chat.cabin_user_id == user_id).gino.scalar()
    else:
        await db.Chat.create(chat_id=m.chat_id, cabin_user_id=user_id, visible_messages=10, is_private=True)
    message = (await bot.api.messages.send(message=f'/приват {m.chat_id}', peer_id=m.peer_id))[0]
    await asyncio.sleep(2)
    await bot.api.messages.delete(cmids=[message.conversation_message_id], peer_id=m.peer_id, delete_for_all=True)
