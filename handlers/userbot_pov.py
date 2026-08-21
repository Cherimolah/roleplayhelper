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
import re

from vkbottle.bot import Message
from vkbottle.dispatch.rules.base import FromPeerRule

from loader import user_bot
from service.db_engine import db
from service.utils import forward_pov_message, forward_pov_message_to_judges, forward_stealth_action
from service.pov_effects import is_valid_pov_message


# ─── Хэндлер входящих сообщений пользователей в ЛС юзербота ─────────────────

STEALTH_ACTION_PATTERN = re.compile(
    r'^\s*\[\s*скрытно\s+'
    r'(?P<mentions>(?:\[id\d+\|[^\]]+\]\s*)+)'
    r'[«"](?P<description>.*?)[»"]\s*\]\s*$',
    re.IGNORECASE | re.DOTALL
)


@user_bot.on.private_message(blocking=False)
async def pov_userbot_message(m: Message):
    """
    Обрабатывает все входящие личные сообщения юзерботу.

    Команды скрытного действия ([скрытно ...] и [скрытность]) доступны ЛЮБОМУ
    зарегистрированному игроку, даже если он не находится в POV-режиме:
    на время обработки команды пользователь временно помечается как
    находящийся в POV (это нужно механике пересылки/проверок), а сразу после
    обработки помечается обратно — БЕЗ удаления его из чатов и без прочих
    побочных эффектов полноценного входа в POV (в отличие от enable_pov_mode).

    Обычные (не скрытные) сообщения пересылаются только для игроков, у
    которых POV-режим включён по-настоящему (через меню/админку).
    """
    # Пропускаем системные сообщения с пустым peer_id
    if not m.from_id or m.from_id < 0:
        return

    # Проверяем, находится ли пользователь в POV-режиме
    pov_mode = await db.select([db.User.pov_mode]).where(
        db.User.user_id == m.from_id).gino.scalar()

    text = m.text or ''

    stealth_match = STEALTH_ACTION_PATTERN.match(text)
    is_secrecy_tag = '[скрытность]' in text.lower()

    if not pov_mode and not stealth_match and not is_secrecy_tag:
        return  # Обычные сообщения не в POV-режиме хэндлер не обрабатывает

    # Для игрока, который не в POV, но использует команду скрытного действия —
    # временно включаем флаг pov_mode на время обработки (без чатов/уведомлений
    # полноценного enable_pov_mode), а затем возвращаем как было.
    temporary_pov = False
    if not pov_mode and (stealth_match or is_secrecy_tag):
        await db.User.update.values(pov_mode=True).where(db.User.user_id == m.from_id).gino.status()
        temporary_pov = True

    try:
        await _handle_pov_message(m, text, stealth_match, is_secrecy_tag, pov_mode)
    finally:
        if temporary_pov:
            await db.User.update.values(pov_mode=False).where(db.User.user_id == m.from_id).gino.status()


async def _handle_pov_message(m: Message, text: str, stealth_match, is_secrecy_tag: bool, was_pov: bool):
    """Основная логика обработки одного входящего сообщения юзерботу (вынесена из хэндлера,
    чтобы гарантированно снять временную метку POV через `finally` в вызывающем коде)."""
    # Полная механика скрытных действий:
    # [скрытно [id1|Игрок] [id2|Игрок] "описание действия"]
    if stealth_match:
        target_ids = [
            int(user_id) for user_id in re.findall(
                r'\[id(\d+)\|[^\]]+\]', stealth_match.group('mentions'), re.IGNORECASE
            )
        ]
        visible_text = stealth_match.group('description').strip()
        if not target_ids or not visible_text:
            await m.answer(
                'Формат скрытного действия:\n'
                '[скрытно [id123|Игрок] [id456|Игрок] "Описание действия"]'
            )
            return

        try:
            result = await forward_stealth_action(
                sender_id=m.from_id,
                target_ids=target_ids,
                visible_text=visible_text,
                original_text=text,
            )
        except ValueError as error:
            await m.answer(f'⚠ {error}')
            return

        reply = (
            '🔐 Скрытное действие отправлено судьям и в локацию.\n'
            f'Очищенную версию получили в POV: {result["clean_sent"]}.\n'
            f'Оригинал по успешной проверке восприятия: {result["original_sent"]}.'
        )
        if result['absent_targets']:
            reply += '\nНе в этой локации: ' + ', '.join(map(str, result['absent_targets'])) + '.'
        if result['without_map']:
            reply += '\nБез карты экспедитора (проверка пропущена): ' + ', '.join(
                map(str, result['without_map'])
            ) + '.'
        await m.answer(reply)
        return

    # Режим скрытности: текст видят только судьи
    if is_secrecy_tag:
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

    # Обычные (не скрытные) POV-сообщения пересылаются только тем, кто
    # по-настоящему находится в POV-режиме (не через временную метку).
    if not was_pov:
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
