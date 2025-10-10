"""
Модуль для обработки запросов на вступление в чаты (локации).
Управляет перемещением пользователей между чатами.
"""

from vkbottle.bot import MessageEvent
from vkbottle import GroupEventType
from vkbottle.dispatch.rules.base import PayloadMapRule
from vkbottle_types.objects import MessagesForward
from sqlalchemy import and_

from loader import bot
from service.db_engine import db
from service.utils import move_user, create_mention


@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent,
                  PayloadMapRule({'chat_action': 'accept', 'request_id': int}))
async def accept_request_location(m: MessageEvent):
    """
    Принимает запрос на вступление в чат (локацию).

    Args:
        m: Событие сообщения с принятием запроса
    """
    request_id = m.payload['request_id']
    request = await db.ChatRequest.get(request_id)

    # Проверяем актуальность запроса
    if not request:
        await m.show_snackbar('Запрос неактуален')
        return

    # Перемещаем пользователя в чат
    await move_user(request.user_id, request.chat_id)

    # Получаем данные о запросе для уведомления администраторов
    messages_data = await db.select([db.ChatRequest.admin_id, db.ChatRequest.message_id]).where(
        and_(db.ChatRequest.chat_id == request.chat_id, db.ChatRequest.user_id == request.user_id)
    ).gino.all()

    # Формируем упоминания и информацию о чате
    mention = await create_mention(m.user_id)
    chat_name = (await bot.api.messages.get_conversations_by_id(peer_ids=[request.chat_id + 2000000000])).items[0].chat_settings.title
    user = await create_mention(request.user_id)

    # Уведомляем администраторов о принятии запроса
    for admin_id, message_id in messages_data:
        try:
            await bot.api.messages.delete(cmids=[message_id], peer_id=admin_id, delete_for_all=True)
            await bot.api.messages.send(peer_id=admin_id,
                                        message=f'✅ Пользователь {mention} принял запрос на вступление '
                                                f'в чат «{chat_name}» пользователя {user}')
        except:
            await bot.api.messages.send(peer_id=admin_id,
                                        message=f'✅ Пользователь {mention} принял запрос на вступление '
                                                f'в чат «{chat_name}» пользователя {user}',
                                        forward=MessagesForward(
                                            peer_id=admin_id,
                                            conversation_message_ids=[message_id],
                                            is_reply=True
                                        ).json())

    # Удаляем запрос и уведомляем пользователя
    await db.ChatRequest.delete.where(
        and_(db.ChatRequest.chat_id == request.chat_id, db.ChatRequest.user_id == request.user_id)
    ).gino.status()
    await bot.api.messages.send(peer_id=request.user_id,
                                message=f'✅ Ваш запрос на вступление в чат «{chat_name}» одобрен\n')
    await m.show_snackbar('Запрос успешно принят')


@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent,
                  PayloadMapRule({'chat_action': 'decline', 'request_id': int}))
async def decline_request_location(m: MessageEvent):
    """
    Отклоняет запрос на вступление в чат (локацию).

    Args:
        m: Событие сообщения с отклонением запроса
    """
    request_id = m.payload['request_id']
    request = await db.ChatRequest.get(request_id)

    # Проверяем актуальность запроса
    if not request:
        await m.show_snackbar('Запрос неактуален')
        return

    # Получаем данные о запросе для уведомления администраторов
    messages_data = await db.select([db.ChatRequest.admin_id, db.ChatRequest.message_id]).where(
        and_(db.ChatRequest.chat_id == request.chat_id, db.ChatRequest.user_id == request.user_id)
    ).gino.all()

    # Формируем упоминания и информацию о чате
    mention = await create_mention(m.user_id)
    chat_name = (await bot.api.messages.get_conversations_by_id(peer_ids=[request.chat_id + 2000000000])).items[
        0].chat_settings.title
    user = await create_mention(request.user_id)

    # Уведомляем администраторов об отклонении запроса
    for admin_id, message_id in messages_data:
        try:
            await bot.api.messages.delete(cmids=[message_id], peer_id=admin_id, delete_for_all=True)
            await bot.api.messages.send(peer_id=admin_id,
                                        message=f'❌Пользователь {mention} отклонил запрос на вступление '
                                                f'в чат «{chat_name}» пользователя {user}')
        except:
            await bot.api.messages.send(peer_id=admin_id,
                                        message=f'❌ Пользователь {mention} отклонил запрос на вступление '
                                                f'в чат «{chat_name}» пользователя {user}',
                                        forward=MessagesForward(
                                            peer_id=admin_id,
                                            conversation_message_ids=[message_id],
                                            is_reply=True
                                        ).json())

    # Удаляем запрос и уведомляем пользователя
    await db.ChatRequest.delete.where(
        and_(db.ChatRequest.chat_id == request.chat_id, db.ChatRequest.user_id == request.user_id)
    ).gino.status()
    await bot.api.messages.send(peer_id=request.user_id,
                                message=f'❌ Ваш запрос на вступление в чат «{chat_name}» отклонен\n')
    await m.show_snackbar('Запрос успешно отклонен')
