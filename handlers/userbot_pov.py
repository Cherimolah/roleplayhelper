"""
POV-пересылка через юзербота.

Когда игрок находится в pov_mode=True — все его сообщения в личку юзерботу
(Сирене) автоматически пересылаются другим игрокам в той же локации.

Если в тексте сообщения встречается команда скрытного действия
[скрытно [id1|Игрок] [id2|Игрок] "описание действия"]:
  - описание действия (текст без команды) публикуется в чат локации;
  - POV-игроки, которых не отметили в команде, получают очищенный текст в ЛС;
  - для каждого отмеченного игрока выполняется проверка
    «Ловкость автора + 1..100» против «Восприятие цели + 1..100».

Обычные сообщения проверяются на минимальный объём (300 символов без пробелов)
и антиспам. Если сообщение слишком короткое — игрок получает предупреждение.
"""

import re

from vkbottle.bot import Message

from loader import user_bot
from service.db_engine import db
from service.utils import forward_pov_message, forward_stealth_action
from service.pov_effects import is_valid_pov_message


# ─── Хэндлер входящих сообщений пользователей в ЛС юзербота ─────────────────

STEALTH_ACTION_PATTERN = re.compile(
    r'\[\s*скрытно\s+'
    r'(?P<mentions>(?:\[id\d+\|[^\]]+\]\s*)+)'
    r'[«"](?P<description>.*?)[»"]\s*\]',
    re.IGNORECASE | re.DOTALL
)


@user_bot.on.private_message(blocking=False)
async def pov_userbot_message(m: Message):
    """
    Обрабатывает все входящие личные сообщения юзерботу.

    Команда скрытного действия ([скрытно ...]) доступна только игрокам,
    находящимся в POV-режиме. Обычные (не скрытные) сообщения пересылаются
    только для игроков, у которых POV-режим включён по-настоящему.
    """
    # Пропускаем системные сообщения с пустым peer_id
    if not m.from_id or m.from_id < 0:
        return

    # Проверяем, находится ли пользователь в POV-режиме
    pov_mode = await db.select([db.User.pov_mode]).where(
        db.User.user_id == m.from_id).gino.scalar()

    text = m.text or ''

    stealth_match = STEALTH_ACTION_PATTERN.search(text)

    if not pov_mode and not stealth_match:
        return  # Обычные сообщения не в POV-режиме хэндлер не обрабатывает

    # Скрытное действие доступно только игроку в POV-режиме
    if not pov_mode:
        await m.answer('⚠ Вы не находитесь в POV-режиме, ваше сообщение не будет обработано')
        return

    await _handle_pov_message(m, text, stealth_match)


async def _handle_pov_message(m: Message, text: str, stealth_match):
    """Основная логика обработки одного входящего сообщения юзерботу"""
    # Команда скрытного действия:
    # [скрытно [id1|Игрок] [id2|Игрок] "описание действия"]
    if stealth_match:
        target_ids = [
            int(user_id) for user_id in re.findall(
                r'\[id(\d+)\|[^\]]+\]', stealth_match.group('mentions'), re.IGNORECASE
            )
        ]
        description = stealth_match.group('description').strip()
        if not target_ids or not description:
            await m.answer(
                'Формат скрытного действия:\n'
                '[скрытно [id123|Игрок] [id456|Игрок] "Описание действия"]'
            )
            return

        # Текст без команды: заменяем [скрытно ...] на само описание действия,
        # сохраняя остальной текст сообщения вокруг команды.
        clean_text = (
            text[:stealth_match.start()]
            + description
            + text[stealth_match.end():]
        ).strip()

        try:
            result = await forward_stealth_action(
                sender_id=m.from_id,
                target_ids=target_ids,
                visible_text=clean_text,
                original_text=text,
            )
        except ValueError as error:
            await m.answer(f'⚠ {error}')
            return

        reply = '🔐 Скрытное действие отправлено судьям и в локацию.\n'
        if result['absent_targets']:
            reply += '\nНе в этой локации: ' + ', '.join(map(str, result['absent_targets'])) + '.'
        if result['without_map']:
            reply += '\nБез карты экспедитора (проверка пропущена): ' + ', '.join(
                map(str, result['without_map'])
            ) + '.'
        await m.answer(reply)
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
