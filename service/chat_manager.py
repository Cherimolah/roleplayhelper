"""
Менеджер для работы с режимом от первого лица (POV).

В текущей архитектуре бот хранит локацию пользователя в `users_chats`
(один активный чат на пользователя). Поэтому для POV мы сохраняем последнюю
локацию перед отключением от чатов и можем восстановить её.
"""

from datetime import datetime
from typing import Dict, List

from service.db_engine import db


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
