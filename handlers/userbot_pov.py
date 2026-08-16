"""
POV-пересылка через юзербота.

Когда игрок находится в pov_mode=True — все его сообщения в личку юзерботу
(Сирене) автоматически пересылаются другим игрокам в той же локации.

Если в тексте есть [скрытность] — сообщение идёт только судьям/администраторам
через forward_pov_message_to_judges.

Сообщения проверяются на минимальный объём (300 символов без пробелов) и антиспам.
Если сообщение слишком короткое — игрок получает предупреждение.
"""

import asyncio

from vkbottle.bot import Message
from vkbottle.dispatch.rules.base import FromPeerRule

from loader import user_bot
from service.db_engine import db
from service.utils import forward_pov_message, forward_pov_message_to_judges
from service.pov_effects import is_valid_pov_message


# ─── Хэндлер входящих сообщений пользователей в ЛС юзербота ─────────────────

@user_bot.on.private_message(blocking=False)
async def pov_userbot_message(m: Message):
    """
    Обрабатывает все входящие личные сообщения юзерботу.
    Если отправитель в POV-режиме — пересылает сообщение.
    Если не в POV — игнорирует (другие хэндлеры обработают).
    """
    # Пропускаем системные сообщения с пустым peer_id
    if not m.from_id or m.from_id < 0:
        return

    # Проверяем, находится ли пользователь в POV-режиме
    pov_mode = await db.select([db.User.pov_mode]).where(
        db.User.user_id == m.from_id).gino.scalar()

    if not pov_mode:
        return  # Не в POV — хэндлер не вмешивается

    text = m.text or ''

    # Режим скрытности: текст видят только судьи
    if '[скрытность]' in text.lower():
        # Убираем тег из текста
        clean_text = text.replace('[скрытность]', '').replace('[Скрытность]', '').strip()
        await forward_pov_message_to_judges(m.from_id, clean_text)
        try:
            await user_bot.api.messages.send(
                peer_id=m.from_id,
                message='🔐 Скрытное действие отправлено судьям.',
                random_id=0
            )
        except Exception:
            pass
        return

    # Обычное POV-сообщение — проверяем минимальный объём
    if not is_valid_pov_message(text):
        char_count = len(text.replace(' ', '').replace('\n', ''))
        try:
            await user_bot.api.messages.send(
                peer_id=m.from_id,
                message=(
                    f'⚠ Сообщение слишком короткое ({char_count} символов без пробелов).\n'
                    f'Для отправки в POV-режиме требуется не менее 300 символов.\n\n'
                    f'Также убедитесь, что сообщение не состоит из одних команд или '
                    f'повторяющихся слов.'
                ),
                random_id=0
            )
        except Exception:
            pass
        return

    # Собираем строку вложений (фотографии)
    attachments_str = ''
    if m.attachments:
        attaches = []
        for a in m.attachments:
            if hasattr(a, 'photo') and a.photo:
                attaches.append(f'photo{a.photo.owner_id}_{a.photo.id}')
            elif hasattr(a, 'doc') and a.doc:
                attaches.append(f'doc{a.doc.owner_id}_{a.doc.id}')
        attachments_str = ','.join(attaches)

    # Пересылаем сообщение игрокам в той же локации
    await forward_pov_message(m.from_id, text, attachments_str)
    await m.answer('✅ Ваше сообщение отправлено игрокам в этой локации')

    # Подтверждение отправителю (тихое — одно сообщение раз в сессию)
    # Не отправляем подтверждение каждый раз, чтобы не засорять диалог
