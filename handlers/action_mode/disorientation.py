"""
Обработка эффекта дезориентации в экшен-режиме
"""

import random
from typing import List, Dict
from datetime import datetime
from loader import db

async def apply_disorientation_effects(action_mode_id: int, user_id: int) -> Dict:
    """
    Применяет эффекты дезориентации к экшен-режиму:
    1. Перемешивает порядок действий других игроков
    2. Гарантированно ставит дезориентированного игрока в конец
    3. Удаляет информацию об отправителях
    """
    result = {
        'original_order': [],
        'shuffled_order': [],
        'user_position': -1,
        'removed_senders': []
    }
    
    # Получаем текущий экшен-режим
    action_mode = await db.ActionMode.query.where(
        db.ActionMode.id == action_mode_id
    ).gino.first()
    
    if not action_mode:
        return result
    
    # Получаем всех участников
    participants = await db.ActionModeParticipant.query.where(
        db.ActionModeParticipant.action_mode_id == action_mode_id
    ).order_by(db.ActionModeParticipant.initiative.desc()).gino.all()
    
    # Сохраняем оригинальный порядок
    original_order = [p.user_id for p in participants]
    result['original_order'] = original_order
    
    # Находим дезориентированного игрока
    if user_id not in original_order:
        return result
    
    # Разделяем участников: дезориентированный и остальные
    disoriented_index = original_order.index(user_id)
    other_participants = [p for i, p in enumerate(participants) if i != disoriented_index]
    
    # Перемешиваем остальных участников
    random.shuffle(other_participants)
    
    # Собираем новый порядок: перемешанные другие + дезориентированный в конце
    new_order = [p.user_id for p in other_participants] + [user_id]
    result['shuffled_order'] = new_order
    result['user_position'] = len(new_order) - 1  # Позиция в конце
    
    # Обновляем инициативу для отражения нового порядка
    # Самому дезориентированному ставим минимальную инициативу
    for i, participant in enumerate(other_participants):
        new_initiative = 1000 - i * 10  # Убывающие значения для порядка
        await participant.update(initiative=new_initiative).apply()
    
    # Дезориентированному - самая низкая инициатива
    disoriented_participant = participants[disoriented_index]
    await disoriented_participant.update(initiative=0).apply()
    
    # Получаем информацию об удаленных отправителях
    for participant in participants:
        if participant.user_id != user_id:
            user = await db.User.query.where(db.User.vk_id == participant.user_id).gino.first()
            if user:
                result['removed_senders'].append({
                    'user_id': participant.user_id,
                    'name': f"{user.first_name} {user.last_name}"
                })
    
    return result

async def send_disoriented_action_mode_info(chat_id: int, user_id: int, action_mode_id: int):
    """
    Отправляет информацию об экшен-режиме с эффектом дезориентации
    """
    # Получаем эффекты дезориентации
    effects = await apply_disorientation_effects(action_mode_id, user_id)
    
    # Формируем сообщение
    message = "🌀 **ЭФФЕКТ ДЕЗОРИЕНТАЦИИ АКТИВИРОВАН**\n\n"
    message += "Восприятие реальности искажено:\n"
    message += "1. Порядок действий перемешан\n"
    message += "2. Вы действуете последним\n"
    message += "3. Источники звуков неопределенны\n\n"
    
    if effects['removed_senders']:
        message += "❓ Неопознанные источники:\n"
        for sender in effects['removed_senders']:
            message += f"   - Источник #{hash(sender['user_id']) % 1000:03d}\n"
    
    # Отправляем сообщение в чат экшен-режима
    from loader import bot
    await bot.api.messages.send(
        peer_id=chat_id,
        message=message,
        random_id=0
    )
    
    # Отправляем персональное сообщение дезориентированному игроку
    await bot.api.messages.send(
        user_id=user_id,
        message="🌀 Вы чувствуете сильную дезориентацию. Всё вокруг кажется перемешанным и неясным.\n"
               "Вы будете действовать последним, и не сможете определить, кто что делает.",
        random_id=0
    )

async def handle_disoriented_post(text: str, sender_id: int, receiver_id: int) -> str:
    """
    Обрабатывает пост для дезориентированного игрока
    """
    from service.text_processors import disorientation
    
    # Применяем дезориентацию к тексту
    processed_text = disorientation(text, remove_sender=True)
    
    # Добавляем заголовок с пометкой об искажении
    final_text = f"🌀 [ИСКАЖЕННЫЙ СИГНАЛ]\n\n{processed_text}\n\n"
    final_text += "⚠️ Восприятие может не соответствовать действительности"
    
    return final_text
