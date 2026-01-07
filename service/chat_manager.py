"""
Менеджер для работы с чатами пользователей в режиме от первого лица
"""

from datetime import datetime
from typing import List, Optional
from loader import db

async def save_user_chats_before_first_person(user_id: int):
    """
    Сохраняет информацию о всех чатах пользователя перед переходом в режим от первого лица
    """
    # Получаем текущие чаты пользователя
    user = await db.User.query.where(db.User.vk_id == user_id).gino.first()
    if not user:
        return []
    
    # Получаем все чаты, в которых состоит пользователь
    user_chats = await db.ChatMember.query.where(
        db.ChatMember.user_id == user_id
    ).gino.all()
    
    saved_chats = []
    for chat_member in user_chats:
        # Сохраняем в историю
        history_record = await db.UserChatHistory.create(
            user_id=user_id,
            chat_id=chat_member.chat_id,
            joined_at=chat_member.joined_at if hasattr(chat_member, 'joined_at') else datetime.now(),
            left_at=datetime.now()
        )
        saved_chats.append(chat_member.chat_id)
    
    return saved_chats

async def restore_user_to_chats(user_id: int) -> List[int]:
    """
    Восстанавливает пользователя во все чаты, из которых он был удален
    """
    # Получаем сохраненную историю чатов
    history_records = await db.UserChatHistory.query.where(
        (db.UserChatHistory.user_id == user_id) &
        (db.UserChatHistory.is_restored == False)
    ).gino.all()
    
    restored_chats = []
    
    for record in history_records:
        try:
            # Проверяем, существует ли еще чат
            chat = await db.Chat.query.where(db.Chat.id == record.chat_id).gino.first()
            if not chat:
                continue
            
            # Проверяем, не состоит ли пользователь уже в чате
            existing_member = await db.ChatMember.query.where(
                (db.ChatMember.user_id == user_id) &
                (db.ChatMember.chat_id == record.chat_id)
            ).gino.first()
            
            if not existing_member:
                # Добавляем пользователя в чат через VK API
                # Это зависит от вашей реализации системы чатов
                await add_user_to_chat_vk(user_id, chat.chat_id)
                
                # Создаем запись в ChatMember
                await db.ChatMember.create(
                    user_id=user_id,
                    chat_id=record.chat_id,
                    joined_at=datetime.now()
                )
            
            # Помечаем как восстановленный
            await record.update(is_restored=True).apply()
            restored_chats.append(record.chat_id)
            
        except Exception as e:
            print(f"Ошибка при восстановлении пользователя {user_id} в чат {record.chat_id}: {e}")
            continue
    
    return restored_chats

async def add_user_to_chat_vk(user_id: int, chat_vk_id: int):
    """
    Добавляет пользователя в чат через VK API
    Нужно интегрировать с вашей системой юзер-бота
    """
    # Здесь используйте вашу существующую логику добавления в чаты
    # Например:
    from loader import bot
    
    try:
        # Для приватных чатов (бесед)
        if chat_vk_id > 2000000000:
            chat_id = chat_vk_id - 2000000000
            await bot.api.messages.add_chat_user(
                chat_id=chat_id,
                user_id=user_id
            )
        # Для публичных чатов (сообществ)
        else:
            await bot.api.messages.allow_messages_from_group(
                group_id=abs(chat_vk_id),
                user_id=user_id
            )
    except Exception as e:
        print(f"Ошибка VK API при добавлении в чат: {e}")
        raise

async def clear_user_chat_history(user_id: int):
    """
    Очищает историю чатов пользователя (после полного восстановления)
    """
    await db.UserChatHistory.delete.where(
        db.UserChatHistory.user_id == user_id
    ).gino.status()

async def get_user_chat_history(user_id: int) -> List[Dict]:
    """
    Получает историю чатов пользователя
    """
    records = await db.UserChatHistory.query.where(
        db.UserChatHistory.user_id == user_id
    ).order_by(db.UserChatHistory.left_at.desc()).gino.all()
    
    result = []
    for record in records:
        chat = await db.Chat.query.where(db.Chat.id == record.chat_id).gino.first()
        result.append({
            'chat_id': record.chat_id,
            'chat_name': chat.name if chat else 'Неизвестный чат',
            'left_at': record.left_at,
            'restored': record.is_restored
        })
    
    return result
