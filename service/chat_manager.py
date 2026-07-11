"""
Менеджер для работы с режимом от первого лица (POV).

В текущей архитектуре бот хранит локацию пользователя в `users_chats`
(один активный чат на пользователя). Поэтому для POV мы сохраняем последнюю
локацию перед отключением от чатов и можем восстановить её.
"""

from datetime import datetime
from typing import Dict, List

from service.db_engine import db
<<<<<<< Updated upstream
=======
from config import USER_ID
>>>>>>> Stashed changes


async def save_user_chats_before_first_person(user_id: int) -> List[int]:
    chat_id = await db.select([db.UserToChat.chat_id]).where(db.UserToChat.user_id == user_id).gino.scalar()
    if not chat_id:
        return []
    await db.UserChatHistory.create(
        user_id=user_id,
        chat_id=chat_id,
        joined_at=datetime.now(),
        left_at=datetime.now(),
        is_restored=False,
    )
    return [chat_id]


async def restore_user_to_chats(user_id: int) -> List[int]:
    records = await (
        db.UserChatHistory.query.where(
            (db.UserChatHistory.user_id == user_id) & (db.UserChatHistory.is_restored == False)
        )
        .order_by(db.UserChatHistory.left_at.asc())
        .gino.all()
    )
    if not records:
        return []

    # Последняя локация (куда "вернуть" пользователя в системе перемещения)
    last_record = max(records, key=lambda r: r.left_at or datetime.min)

    from service.utils import move_user
    await move_user(user_id, last_record.chat_id)

    restored_chat_ids: List[int] = []
    for record in records:
        await record.update(is_restored=True).apply()
        restored_chat_ids.append(record.chat_id)

    return restored_chat_ids


async def clear_user_chat_history(user_id: int, only_restored: bool = True):
    q = db.UserChatHistory.delete.where(db.UserChatHistory.user_id == user_id)
    if only_restored:
        q = q.where(db.UserChatHistory.is_restored == True)
    await q.gino.status()


async def get_user_chat_history(user_id: int) -> List[Dict]:
    records = (
        await db.UserChatHistory.query.where(db.UserChatHistory.user_id == user_id)
        .order_by(db.UserChatHistory.left_at.desc())
        .gino.all()
    )
    return [
        {"chat_id": r.chat_id, "chat_name": str(r.chat_id), "left_at": r.left_at, "restored": r.is_restored}
        for r in records
    ]
<<<<<<< Updated upstream
=======


async def force_pov_on(user_id: int, reason: str | None = None):
    """
    Принудительно включает POV-режим пользователю (используется административным
    инструментом "POV режим" и дебафами карты экспедитора с pov_effect).
    Пока режим не снят через force_pov_off(), пользователь не может выключить его сам.
    """
    from loader import bot
    from service.utils import remove_user_from_all_chats

    mode = await db.FirstPersonMode.query.where(db.FirstPersonMode.user_id == user_id).gino.first()
    if not (mode and mode.is_active):
        await save_user_chats_before_first_person(user_id)
        await remove_user_from_all_chats(user_id)
    if mode:
        await mode.update(is_active=True, blackout_mode=True, blackout_reason=reason).apply()
    else:
        await db.FirstPersonMode.create(user_id=user_id, is_active=True, blackout_mode=True, blackout_reason=reason)

    try:
        text = "⚫ Администрация принудительно перевела вас в режим от первого лица.\n"
        text += f"Причина: {reason}\n\n" if reason else "\n"
        text += f"Общайтесь через юзербота (Сирена): https://vk.com/id{USER_ID}"
        await bot.api.messages.send(user_id=user_id, message=text, random_id=0, is_notification=True)
    except Exception:
        pass


async def force_pov_off(user_id: int) -> bool:
    """Снимает принудительный POV-режим у пользователя (если он был включен принудительно)"""
    from loader import bot

    mode = await db.FirstPersonMode.query.where(db.FirstPersonMode.user_id == user_id).gino.first()
    if not mode or not mode.blackout_mode:
        return False
    await mode.update(is_active=False, blackout_mode=False, blackout_reason=None).apply()
    await restore_user_to_chats(user_id)
    await clear_user_chat_history(user_id, only_restored=True)
    try:
        await bot.api.messages.send(
            user_id=user_id,
            message="✅ Принудительный режим от первого лица снят администрацией.",
            random_id=0,
            is_notification=True,
        )
    except Exception:
        pass
    return True
>>>>>>> Stashed changes
