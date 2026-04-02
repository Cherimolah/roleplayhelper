"""
Модуль отображения доступных локаций и чатов для пользователя.
"""

from vkbottle.bot import Message
from vkbottle.dispatch.rules.base import PayloadRule
from sqlalchemy import and_

from loader import bot
from service.custom_rules import StateRule
from service.states import Menu
from service.db_engine import db


@bot.on.private_message(StateRule(Menu.MAIN), PayloadRule({"menu": "locations"}))
async def show_locations(m: Message):
    """Отображение списка доступных локаций и чатов."""
    current_chat_id = await db.select([db.UserToChat.chat_id]).where(db.UserToChat.user_id == m.from_id).gino.scalar()

    # Формирование заголовка с учетом текущего местоположения
    if not current_chat_id:
        reply = ('Список доступных локаций:\n'
                 '🚪 - приватная комната\n\n')
    else:
        current_chat_name = (await bot.api.messages.get_conversations_by_id(
            peer_ids=[current_chat_id + 2000000000])).items[0].chat_settings.title
        reply = (f'Вы сейчас находитесь в чате «{current_chat_name}»\n\n'
                 'Список доступных локаций:\n'
                 '🚪 - приватная комната\n\n')

    # Получение списка доступных чатов
    chats_data = await db.select([db.Chat.chat_id, db.Chat.is_private]).where(
        and_(db.Chat.chat_id != current_chat_id, db.Chat.cabin_user_id.is_(None))).order_by(
        db.Chat.chat_id.asc()).gino.all()
    chat_ids = [x[0] for x in chats_data]
    peer_ids = [2000000000 + x for x in chat_ids]

    if not peer_ids:
        reply += 'Нет активных чатов'
    else:
        names = [x.chat_settings.title for x in (await bot.api.messages.get_conversations_by_id(
            peer_ids=peer_ids)).items]
        for i, row in enumerate(chats_data):
            chat_id, is_private = row
            reply += f'{i + 1}. {"🚪" if is_private else ""} «{names[i]}»\n'

    reply += '\nФормат чатов для кают: RP \"Среди Нас\" Каюта/Кельи № (номер каюты/кельи)'
    await m.answer(reply)