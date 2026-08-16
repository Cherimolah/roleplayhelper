"""
Панель POV-режима для администраторов и судей.

Позволяет:
- Принудительно переводить игроков в «режим от первого лица».
- Выбор цели: конкретный игрок / профессия / все игроки.
- Назначать дебаффы, связанные с POV (ограниченная видимость, контузия, глухота, слепота).
- Управлять «Режимом скрытности».
"""

import asyncio

from vkbottle.bot import Message
from vkbottle.dispatch.rules.base import PayloadRule
from vkbottle import Keyboard, Text, KeyboardButtonColor

from loader import bot, user_bot
from service.custom_rules import AdminRule, JudgeRule, StateRule, NumericRule
from service.middleware import states
from service.states import PovPanel
from service.db_engine import db
from service.utils import enable_pov_mode, disable_pov_mode, get_current_form_id, get_mention_from_message
from config import USER_ID


# ─── Клавиатуры ──────────────────────────────────────────────────────────────

pov_panel_kb = Keyboard().add(
    Text('👤 Конкретный игрок', {'pov': 'select_player'}), KeyboardButtonColor.PRIMARY
).row().add(
    Text('💼 Профессия', {'pov': 'select_profession'}), KeyboardButtonColor.PRIMARY
).row().add(
    Text('🌐 Все игроки', {'pov': 'all_players'}), KeyboardButtonColor.NEGATIVE
).row().add(
    Text('📋 Список игроков в POV', {'pov': 'list'}), KeyboardButtonColor.SECONDARY
).row().add(
    Text('↩ Вернуть из POV', {'pov': 'disable'}), KeyboardButtonColor.SECONDARY
).row().add(
    Text('Назад', {'pov': 'back'}), KeyboardButtonColor.NEGATIVE
)

enable_disable_kb = Keyboard().add(
    Text('✅ Включить POV', {'pov_action': 'enable'}), KeyboardButtonColor.POSITIVE
).row().add(
    Text('❌ Выключить POV', {'pov_action': 'disable'}), KeyboardButtonColor.NEGATIVE
).row().add(
    Text('Назад', {'pov_action': 'back'}), KeyboardButtonColor.SECONDARY
)


# ─── Вход в панель ───────────────────────────────────────────────────────────

@bot.on.private_message(PayloadRule({'admin_menu': 'pov_panel'}), AdminRule())
@bot.on.private_message(PayloadRule({'judge_menu': 'pov_panel'}), JudgeRule())
async def pov_panel_menu(m: Message):
    """Главное меню панели POV."""
    states.set(m.from_id, PovPanel.MENU)
    await m.answer('👁 Панель POV-режима', keyboard=pov_panel_kb)


@bot.on.private_message(StateRule(PovPanel.MENU), PayloadRule({'pov': 'back'}))
async def pov_panel_back(m: Message):
    from service.keyboards import admin_menu
    states.set(m.from_id, 'Admin.admin_menu')
    await m.answer('Админ-панель', keyboard=admin_menu)


# ─── Конкретный игрок ────────────────────────────────────────────────────────

@bot.on.private_message(StateRule(PovPanel.MENU), PayloadRule({'pov': 'select_player'}))
async def pov_select_player(m: Message):
    """Выбор конкретного игрока для перевода в POV."""
    states.set(m.from_id, PovPanel.SELECT_PLAYER)
    kb = Keyboard().add(Text('Назад', {'pov': 'back_to_menu'}), KeyboardButtonColor.NEGATIVE)
    await m.answer(
        'Пришлите упоминание, ссылку или пересланное сообщение игрока.\n'
        'После выбора укажите действие: включить или выключить POV.',
        keyboard=kb
    )


@bot.on.private_message(StateRule(PovPanel.SELECT_PLAYER))
async def pov_player_received(m: Message):
    """Получаем игрока и спрашиваем включить/выключить."""
    if m.payload and m.payload.get('pov') == 'back_to_menu':
        states.set(m.from_id, PovPanel.MENU)
        await m.answer('Панель POV-режима', keyboard=pov_panel_kb)
        return

    user_id = await get_mention_from_message(m)
    if not user_id:
        await m.answer('Пользователь не найден. Пришлите упоминание.')
        return

    form_name = await db.select([db.Form.name]).where(db.Form.user_id == user_id).gino.scalar()
    if not form_name:
        await m.answer('У этого пользователя нет анкеты в боте.')
        return

    pov_mode = await db.select([db.User.pov_mode]).where(db.User.user_id == user_id).gino.scalar()
    current = '✅ включён' if pov_mode else '❌ выключен'

    kb = Keyboard().add(
        Text(f'{"❌ Выключить" if pov_mode else "✅ Включить"} POV',
             {'pov_player': user_id, 'pov_action': not pov_mode}),
        KeyboardButtonColor.POSITIVE if not pov_mode else KeyboardButtonColor.NEGATIVE
    ).row().add(
        Text('Назад', {'pov': 'back_to_menu'}), KeyboardButtonColor.SECONDARY
    )

    states.set(m.from_id, PovPanel.CONFIRM)
    await m.answer(
        f'Игрок: [id{user_id}|{form_name}]\n'
        f'POV-режим сейчас: {current}',
        keyboard=kb
    )


@bot.on.private_message(StateRule(PovPanel.DISABLE))
async def pov_disable_selected(m: Message):
    """Выключить POV для выбранного из списка игрока."""
    if not m.payload:
        return
    if m.payload.get('pov') == 'back_to_menu':
        states.set(m.from_id, PovPanel.MENU)
        await m.answer('Панель POV-режима', keyboard=pov_panel_kb)
        return
    if 'disable_pov_user' not in m.payload:
        return

    uid = int(m.payload['disable_pov_user'])
    await disable_pov_mode(uid)
    name = await db.select([db.Form.name]).where(db.Form.user_id == uid).gino.scalar()
    states.set(m.from_id, PovPanel.MENU)
    await m.answer(f'✅ POV-режим выключен для [id{uid}|{name}].', keyboard=pov_panel_kb)



@bot.on.private_message(StateRule(PovPanel.CONFIRM), PayloadRule({'pov': 'back_to_menu'}))
async def pov_confirm_back(m: Message):
    states.set(m.from_id, PovPanel.MENU)
    await m.answer('Панель POV-режима', keyboard=pov_panel_kb)


@bot.on.private_message(StateRule(PovPanel.CONFIRM))
async def pov_toggle_player(m: Message):
    """Включение/выключение POV для конкретного игрока."""
    if not m.payload or 'pov_player' not in m.payload:
        return

    target_user_id = int(m.payload['pov_player'])
    enable = bool(m.payload['pov_action'])

    if enable:
        await enable_pov_mode(target_user_id)
        form_name = await db.select([db.Form.name]).where(db.Form.user_id == target_user_id).gino.scalar()
        await m.answer(f'✅ POV-режим включён для [id{target_user_id}|{form_name}]')
    else:
        await disable_pov_mode(target_user_id)
        form_name = await db.select([db.Form.name]).where(db.Form.user_id == target_user_id).gino.scalar()
        await m.answer(f'❌ POV-режим выключен для [id{target_user_id}|{form_name}]')

    states.set(m.from_id, PovPanel.MENU)
    await m.answer('Панель POV-режима', keyboard=pov_panel_kb)


# ─── По профессии ─────────────────────────────────────────────────────────────

@bot.on.private_message(StateRule(PovPanel.MENU), PayloadRule({'pov': 'select_profession'}))
async def pov_select_profession(m: Message):
    """Выбор профессии для массового включения POV."""
    professions = await db.select([db.Profession.id, db.Profession.name]).order_by(
        db.Profession.id.asc()).gino.all()
    if not professions:
        await m.answer('Профессий не найдено.')
        return

    reply = 'Выберите номер профессии:\n\n'
    for i, (pid, name) in enumerate(professions):
        reply += f'{i + 1}. {name}\n'

    states.set(m.from_id, PovPanel.SELECT_PROFESSION)
    await m.answer(reply, keyboard=Keyboard().add(
        Text('Назад', {'pov': 'back_to_menu'}), KeyboardButtonColor.NEGATIVE
    ))


@bot.on.private_message(StateRule(PovPanel.SELECT_PROFESSION), PayloadRule({'pov': 'back_to_menu'}))
async def pov_profession_back(m: Message):
    states.set(m.from_id, PovPanel.MENU)
    await m.answer('Панель POV-режима', keyboard=pov_panel_kb)
    return


@bot.on.private_message(StateRule(PovPanel.SELECT_PROFESSION), NumericRule())
async def pov_profession_enable(m: Message, value: int):
    """Включить POV всем представителям выбранной профессии."""
    professions = await db.select([db.Profession.id, db.Profession.name]).order_by(
        db.Profession.id.asc()).gino.all()
    if value > len(professions):
        await m.answer('Неверный номер профессии.')
        return

    prof_id, prof_name = professions[value - 1]
    user_ids = [x[0] for x in await db.select([db.Form.user_id])
                .where(db.Form.profession == prof_id).gino.all()]

    count = 0
    for uid in user_ids:
        try:
            await enable_pov_mode(uid)
            count += 1
        except Exception:
            pass

    states.set(m.from_id, PovPanel.MENU)
    await m.answer(f'✅ POV-режим включён для {count} игроков профессии «{prof_name}».',
                   keyboard=pov_panel_kb)


# ─── Все игроки ───────────────────────────────────────────────────────────────

@bot.on.private_message(StateRule(PovPanel.MENU), PayloadRule({'pov': 'all_players'}))
async def pov_all_players(m: Message):
    """Включить POV для всех игроков с подтверждением."""
    kb = Keyboard().add(
        Text('✅ Подтвердить — POV всем', {'pov_all_confirm': True}), KeyboardButtonColor.NEGATIVE
    ).row().add(
        Text('Отмена', {'pov': 'back_to_menu'}), KeyboardButtonColor.SECONDARY
    )
    await m.answer(
        '⚠ Вы хотите перевести ВСЕХ игроков в POV-режим?\n'
        'Это действие нельзя отменить массово.',
        keyboard=kb
    )


@bot.on.private_message(StateRule(PovPanel.MENU), PayloadRule({'pov_all_confirm': True}))
async def pov_all_confirm(m: Message):
    """Массовое включение POV для всех."""
    user_ids = [x[0] for x in await db.select([db.User.user_id]).where(
        db.User.user_id == db.Form.user_id
    ).gino.all()]
    # Проще: берём всех пользователей у которых есть анкета
    form_user_ids = [x[0] for x in await db.select([db.Form.user_id]).gino.all()]
    count = 0
    for uid in form_user_ids:
        try:
            await enable_pov_mode(uid)
            count += 1
            await asyncio.sleep(0.05)
        except Exception:
            pass

    states.set(m.from_id, PovPanel.MENU)
    await m.answer(f'✅ POV-режим включён для {count} игроков.', keyboard=pov_panel_kb)


# ─── Вернуть из POV (по игроку) ──────────────────────────────────────────────

@bot.on.private_message(StateRule(PovPanel.MENU), PayloadRule({'pov': 'disable'}))
async def pov_disable_menu(m: Message):
    """Выключить POV у конкретного игрока."""
    pov_users = [x[0] for x in await db.select([db.User.user_id]).where(
        db.User.pov_mode.is_(True)).gino.all()]
    if not pov_users:
        await m.answer('Нет игроков в POV-режиме.')
        return

    reply = 'Игроки в POV-режиме:\n\n'
    for i, uid in enumerate(pov_users):
        name = await db.select([db.Form.name]).where(db.Form.user_id == uid).gino.scalar()
        reply += f'{i + 1}. [id{uid}|{name}]\n'

    kb = Keyboard()
    for i, uid in enumerate(pov_users):
        if i % 3 == 0:
            kb.row()
        kb.add(Text(str(i + 1), {'disable_pov_user': uid}), KeyboardButtonColor.SECONDARY)
    kb.row().add(Text('Назад', {'pov': 'back_to_menu'}), KeyboardButtonColor.NEGATIVE)

    states.set(m.from_id, PovPanel.DISABLE)
    await m.answer(reply, keyboard=kb)


# ─── Список игроков в POV ─────────────────────────────────────────────────────

@bot.on.private_message(StateRule(PovPanel.MENU), PayloadRule({'pov': 'list'}))
async def pov_list(m: Message):
    """Список всех игроков в POV-режиме."""
    pov_users = [x[0] for x in await db.select([db.User.user_id]).where(
        db.User.pov_mode.is_(True)).gino.all()]
    if not pov_users:
        await m.answer('Нет игроков в POV-режиме.', keyboard=pov_panel_kb)
        return

    reply = f'Игроки в POV-режиме ({len(pov_users)}):\n\n'
    for uid in pov_users:
        name = await db.select([db.Form.name]).where(db.Form.user_id == uid).gino.scalar()
        reply += f'• [id{uid}|{name or "—"}]\n'

    await m.answer(reply, keyboard=pov_panel_kb)
