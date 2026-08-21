"""
Секретные разделы анкеты.

Игрок может добавить скрытые разделы в свою анкету, которые будут видны
только тем, кто прошёл фильтры доступа: фракция / уровень репутации / профессия.

Судьи и администраторы видят ВСЕ секретные разделы.
"""

import re

from vkbottle.bot import Message
from vkbottle.dispatch.rules.base import PayloadRule, PayloadMapRule
from vkbottle import Keyboard, Text, KeyboardButtonColor

from loader import bot
from service.custom_rules import StateRule, AdminRule
from service.middleware import states
from service.states import FormSecrets, Menu
from service.db_engine import db


# ─── Клавиатуры ──────────────────────────────────────────────────────────────

secrets_menu_kb = Keyboard().add(
    Text('✏ Особенности (скрытые)', {'secret': 'features'}), KeyboardButtonColor.SECONDARY
).row().add(
    Text('✏ Биография (скрытая)', {'secret': 'bio'}), KeyboardButtonColor.SECONDARY
).row().add(
    Text('✏ Характер (скрытый)', {'secret': 'character'}), KeyboardButtonColor.SECONDARY
).row().add(
    Text('✏ Мотивы (скрытые)', {'secret': 'motives'}), KeyboardButtonColor.SECONDARY
).row().add(
    Text('🔒 Настроить доступ', {'secret': 'access'}), KeyboardButtonColor.PRIMARY
).row().add(
    Text('Назад', {'secret': 'back'}), KeyboardButtonColor.NEGATIVE
)


def _access_kb(auction_id=None):
    kb = Keyboard().add(
        Text('По фракции', {'secret_access': 'fraction'}), KeyboardButtonColor.PRIMARY
    ).row().add(
        Text('По репутации', {'secret_access': 'reputation'}), KeyboardButtonColor.PRIMARY
    ).row().add(
        Text('По профессии', {'secret_access': 'profession'}), KeyboardButtonColor.PRIMARY
    ).row().add(
        Text('По конкретным игрокам', {'secret_access': 'users'}), KeyboardButtonColor.PRIMARY
    ).row().add(
        Text('Сбросить (видят все)', {'secret_access': 'reset'}), KeyboardButtonColor.NEGATIVE
    ).row().add(
        Text('Назад', {'secret': 'back_to_menu'}), KeyboardButtonColor.SECONDARY
    )
    return kb


# ─── Вход в меню секретных разделов ─────────────────────────────────────────

@bot.on.private_message(PayloadRule({'menu': 'form_secrets'}), StateRule(Menu.SHOW_FORM))
async def form_secrets_main(m: Message):
    """Открывает меню секретных разделов анкеты."""
    has_form = await db.select([db.Form.id]).where(db.Form.user_id == m.from_id).gino.scalar()
    if not has_form:
        await m.answer('У вас нет активной анкеты.')
        return

    states.set(m.from_id, FormSecrets.MENU)
    await m.answer('🔐 Секретные разделы анкеты\n\n'
                   'Здесь вы можете добавить скрытые разделы, '
                   'которые будут видны только выбранным игрокам.',
                   keyboard=secrets_menu_kb)


@bot.on.private_message(StateRule(FormSecrets.MENU), PayloadRule({'secret': 'back'}))
async def form_secrets_back(m: Message):
    """Назад в главное меню."""
    states.set(m.from_id, Menu.MAIN)
    from service.keyboards import main_menu
    await m.answer('Главное меню', keyboard=await main_menu(m.from_id))


@bot.on.private_message(StateRule(FormSecrets.MENU), PayloadRule({'secret': 'back_to_menu'}))
async def form_secrets_back_to_menu(m: Message):
    await m.answer('🔐 Секретные разделы анкеты', keyboard=secrets_menu_kb)


# ─── Редактирование разделов ─────────────────────────────────────────────────

async def _enter_section(m: Message, field: str, prompt: str, next_state: str):
    """Общий обработчик перехода к вводу секретного раздела."""
    states.set(m.from_id, next_state)
    # Показываем текущее значение, если есть
    form_id = await db.select([db.Form.id]).where(db.Form.user_id == m.from_id).gino.scalar()
    current_row = await db.select([getattr(db.FormSecret, field)]).where(
        db.FormSecret.form_id == form_id).gino.first()
    current = current_row[0] if current_row else None

    current_text = f'\n\nТекущее значение:\n{current}' if current else '\n\nЕщё не заполнено.'
    kb = Keyboard().add(Text('Назад', {'secret': 'back_to_menu'}), KeyboardButtonColor.NEGATIVE)
    await m.answer(f'{prompt}{current_text}', keyboard=kb)


async def _save_section(m: Message, field: str):
    """Сохраняет введённый текст в соответствующее поле FormSecret."""
    if m.payload and m.payload.get('secret') == 'back_to_menu':
        states.set(m.from_id, FormSecrets.MENU)
        await m.answer('🔐 Секретные разделы анкеты', keyboard=secrets_menu_kb)
        return

    form_id = await db.select([db.Form.id]).where(db.Form.user_id == m.from_id).gino.scalar()
    # Создаём или обновляем запись FormSecret
    existing = await db.FormSecret.query.where(db.FormSecret.form_id == form_id).gino.first()
    if existing:
        await db.FormSecret.update.values(**{field: m.text}).where(
            db.FormSecret.form_id == form_id).gino.status()
    else:
        await db.FormSecret.create(form_id=form_id, **{field: m.text})

    states.set(m.from_id, FormSecrets.MENU)
    await m.answer('✅ Сохранено!', keyboard=secrets_menu_kb)


# Особенности
@bot.on.private_message(StateRule(FormSecrets.MENU), PayloadRule({'secret': 'features'}))
async def secret_features_enter(m: Message):
    await _enter_section(m, 'secret_features', 'Введите скрытые особенности персонажа:',
                         FormSecrets.ENTER_SECRET_FEATURES)


@bot.on.private_message(StateRule(FormSecrets.ENTER_SECRET_FEATURES))
async def secret_features_save(m: Message):
    await _save_section(m, 'secret_features')


# Биография
@bot.on.private_message(StateRule(FormSecrets.MENU), PayloadRule({'secret': 'bio'}))
async def secret_bio_enter(m: Message):
    await _enter_section(m, 'secret_bio', 'Введите скрытую биографию персонажа:',
                         FormSecrets.ENTER_SECRET_BIO)


@bot.on.private_message(StateRule(FormSecrets.ENTER_SECRET_BIO))
async def secret_bio_save(m: Message):
    await _save_section(m, 'secret_bio')


# Характер
@bot.on.private_message(StateRule(FormSecrets.MENU), PayloadRule({'secret': 'character'}))
async def secret_character_enter(m: Message):
    await _enter_section(m, 'secret_character', 'Введите скрытые черты характера персонажа:',
                         FormSecrets.ENTER_SECRET_CHARACTER)


@bot.on.private_message(StateRule(FormSecrets.ENTER_SECRET_CHARACTER))
async def secret_character_save(m: Message):
    await _save_section(m, 'secret_character')


# Мотивы
@bot.on.private_message(StateRule(FormSecrets.MENU), PayloadRule({'secret': 'motives'}))
async def secret_motives_enter(m: Message):
    await _enter_section(m, 'secret_motives', 'Введите скрытые мотивы персонажа:',
                         FormSecrets.ENTER_SECRET_MOTIVES)


@bot.on.private_message(StateRule(FormSecrets.ENTER_SECRET_MOTIVES))
async def secret_motives_save(m: Message):
    await _save_section(m, 'secret_motives')


# ─── Управление доступом ─────────────────────────────────────────────────────

@bot.on.private_message(StateRule(FormSecrets.MENU), PayloadRule({'secret': 'access'}))
async def secret_access_menu(m: Message):
    """Меню настройки доступа к секретным разделам."""
    form_id = await db.select([db.Form.id]).where(db.Form.user_id == m.from_id).gino.scalar()
    row = await db.FormSecret.query.where(db.FormSecret.form_id == form_id).gino.first()
    if not row:
        await m.answer('Сначала добавьте хотя бы один секретный раздел.')
        return

    frac_name = None
    prof_name = None
    if row.access_fraction_id:
        frac_name = await db.select([db.Fraction.name]).where(
            db.Fraction.id == row.access_fraction_id).gino.scalar()
    if row.access_profession_id:
        prof_name = await db.select([db.Profession.name]).where(
            db.Profession.id == row.access_profession_id).gino.scalar()

    info = (
        f'Текущие настройки доступа:\n'
        f'• Фракция: {frac_name or "любая"}\n'
        f'• Мин. репутация: {row.access_reputation or 0}\n'
        f'• Профессия: {prof_name or "любая"}\n'
        f'• Конкретные игроки: {len(row.access_user_ids or [])}'
    )
    states.set(m.from_id, FormSecrets.ENTER_ACCESS_FRACTION)
    await m.answer(info, keyboard=_access_kb())


@bot.on.private_message(StateRule(FormSecrets.ENTER_ACCESS_FRACTION),
                        PayloadRule({'secret_access': 'fraction'}))
async def secret_access_fraction(m: Message):
    """Выбор фракции для доступа."""
    fractions = await db.select([db.Fraction.id, db.Fraction.name]).order_by(
        db.Fraction.id.asc()).gino.all()
    if not fractions:
        await m.answer('Фракций не найдено.')
        return

    reply = 'Выберите номер фракции:\n\n'
    for i, (fid, fname) in enumerate(fractions):
        reply += f'{i + 1}. {fname}\n'
    states.set(m.from_id, f'{FormSecrets.ENTER_ACCESS_FRACTION}*fraction_select')
    await m.answer(reply, keyboard=Keyboard().add(
        Text('Назад', {'secret': 'back_to_menu'}), KeyboardButtonColor.NEGATIVE
    ))


async def _start_users_access(m: Message, form_id: int, is_admin_setting: bool = False):
    """Запрашивает VK-упоминания игроков, которым открыт доступ к секретам."""
    row = await db.FormSecret.query.where(db.FormSecret.form_id == form_id).gino.first()
    if not row:
        await m.answer('У этой анкеты ещё нет заполненных секретных разделов.')
        return

    existing_ids = row.access_user_ids or []
    existing_text = ', '.join(map(str, existing_ids)) if existing_ids else 'никому'
    states.set(m.from_id, f'{FormSecrets.ENTER_ACCESS_USERS}*{form_id}*{int(is_admin_setting)}')
    await m.answer(
        'Отправьте VK-упоминания игроков, которым будет доступна секретная информация.\n'
        'Например: [id123|Игрок] [id456|Игрок]\n\n'
        f'Сейчас доступ открыт: {existing_text}.\n'
        'Напишите «очистить», чтобы убрать только список конкретных игроков.',
        keyboard=Keyboard().add(
            Text('Назад', {'secret': 'back_to_menu'}), KeyboardButtonColor.NEGATIVE
        )
    )


@bot.on.private_message(StateRule(FormSecrets.ENTER_ACCESS_FRACTION),
                        PayloadRule({'secret_access': 'users'}))
async def secret_access_users_enter(m: Message):
    """Выбор конкретных пользователей владельцем анкеты."""
    form_id = await db.select([db.Form.id]).where(db.Form.user_id == m.from_id).gino.scalar()
    await _start_users_access(m, form_id)


@bot.on.private_message(PayloadMapRule({'form_secrets_access': int}), AdminRule())
async def admin_secret_access_users_enter(m: Message):
    """Администратор открывает список конкретных пользователей для чужой анкеты."""
    await _start_users_access(m, int(m.payload['form_secrets_access']), is_admin_setting=True)


@bot.on.private_message(StateRule(FormSecrets.ENTER_ACCESS_USERS))
async def secret_access_users_save(m: Message):
    """Сохраняет список конкретных пользователей с доступом."""
    if m.payload and m.payload.get('secret') == 'back_to_menu':
        states.set(m.from_id, FormSecrets.MENU)
        await m.answer('🔐 Секретные разделы анкеты', keyboard=secrets_menu_kb)
        return

    state = states.get(m.from_id) or await db.select([db.User.state]).where(
        db.User.user_id == m.from_id
    ).gino.scalar()
    parts = state.split('*') if state else []
    if len(parts) < 2 or not parts[1].isdigit():
        await m.answer('Не удалось определить анкету. Откройте настройку доступа заново.')
        return
    form_id = int(parts[1])
    is_admin_setting = len(parts) > 2 and parts[2] == '1'

    if (m.text or '').strip().lower() == 'очистить':
        user_ids = []
    else:
        user_ids = list(dict.fromkeys(
            int(user_id) for user_id in re.findall(r'\[id(\d+)\|[^\]]+\]', m.text or '', re.IGNORECASE)
        ))
        if not user_ids:
            await m.answer('Пришлите хотя бы одно VK-упоминание или напишите «очистить».')
            return
        registered_ids = {
            row[0] for row in await db.select([db.Form.user_id]).where(
                db.Form.user_id.in_(user_ids)
            ).gino.all()
        }
        if not registered_ids:
            await m.answer('У указанных пользователей нет активных анкет.')
            return
        user_ids = sorted(registered_ids)

    await db.FormSecret.update.values(access_user_ids=user_ids).where(
        db.FormSecret.form_id == form_id
    ).gino.status()

    if is_admin_setting:
        states.set(m.from_id, Menu.SHOW_FORM)
        await m.answer('✅ Список конкретных пользователей с доступом сохранён.')
    else:
        states.set(m.from_id, FormSecrets.MENU)
        await m.answer('✅ Список конкретных пользователей с доступом сохранён.', keyboard=secrets_menu_kb)


@bot.on.private_message(StateRule(FormSecrets.ENTER_ACCESS_FRACTION))
async def secret_access_fraction_save(m: Message):
    """Сохранение выбора фракции."""
    if m.payload and m.payload.get('secret') == 'back_to_menu':
        states.set(m.from_id, FormSecrets.MENU)
        await m.answer('🔐 Секретные разделы анкеты', keyboard=secrets_menu_kb)
        return

    if not m.text.isdigit():
        await m.answer('Введите номер фракции.')
        return

    idx = int(m.text)
    fractions = await db.select([db.Fraction.id, db.Fraction.name]).order_by(
        db.Fraction.id.asc()).gino.all()
    if idx > len(fractions):
        await m.answer('Неверный номер.')
        return

    form_id = await db.select([db.Form.id]).where(db.Form.user_id == m.from_id).gino.scalar()
    frac_id = fractions[idx - 1][0]
    await db.FormSecret.update.values(access_fraction_id=frac_id).where(
        db.FormSecret.form_id == form_id).gino.status()

    states.set(m.from_id, FormSecrets.MENU)
    await m.answer('✅ Фракция сохранена.', keyboard=secrets_menu_kb)


@bot.on.private_message(StateRule(FormSecrets.ENTER_ACCESS_FRACTION),
                        PayloadRule({'secret_access': 'reputation'}))
async def secret_access_reputation_enter(m: Message):
    """Начало ввода минимальной репутации."""
    states.set(m.from_id, FormSecrets.ENTER_ACCESS_REPUTATION)
    await m.answer('Введите минимальный уровень репутации (число):',
                   keyboard=Keyboard().add(Text('Назад', {'secret': 'back_to_menu'}),
                                           KeyboardButtonColor.NEGATIVE))


@bot.on.private_message(StateRule(FormSecrets.ENTER_ACCESS_REPUTATION))
async def secret_access_reputation_save(m: Message):
    if m.payload and m.payload.get('secret') == 'back_to_menu':
        states.set(m.from_id, FormSecrets.MENU)
        await m.answer('🔐 Секретные разделы анкеты', keyboard=secrets_menu_kb)
        return

    if not m.text.lstrip('-').isdigit():
        await m.answer('Введите целое число.')
        return

    form_id = await db.select([db.Form.id]).where(db.Form.user_id == m.from_id).gino.scalar()
    rep = int(m.text)
    await db.FormSecret.update.values(access_reputation=rep).where(
        db.FormSecret.form_id == form_id).gino.status()

    states.set(m.from_id, FormSecrets.MENU)
    await m.answer('✅ Репутация сохранена.', keyboard=secrets_menu_kb)


@bot.on.private_message(StateRule(FormSecrets.ENTER_ACCESS_FRACTION),
                        PayloadRule({'secret_access': 'profession'}))
async def secret_access_profession_enter(m: Message):
    """Выбор профессии для доступа."""
    professions = await db.select([db.Profession.id, db.Profession.name]).order_by(
        db.Profession.id.asc()).gino.all()
    if not professions:
        await m.answer('Профессий не найдено.')
        return

    reply = 'Выберите номер профессии:\n\n'
    for i, (pid, pname) in enumerate(professions):
        reply += f'{i + 1}. {pname}\n'
    states.set(m.from_id, FormSecrets.ENTER_ACCESS_PROFESSION)
    await m.answer(reply, keyboard=Keyboard().add(
        Text('Назад', {'secret': 'back_to_menu'}), KeyboardButtonColor.NEGATIVE
    ))


@bot.on.private_message(StateRule(FormSecrets.ENTER_ACCESS_PROFESSION))
async def secret_access_profession_save(m: Message):
    if m.payload and m.payload.get('secret') == 'back_to_menu':
        states.set(m.from_id, FormSecrets.MENU)
        await m.answer('🔐 Секретные разделы анкеты', keyboard=secrets_menu_kb)
        return

    if not m.text.isdigit():
        await m.answer('Введите номер профессии.')
        return

    idx = int(m.text)
    professions = await db.select([db.Profession.id]).order_by(db.Profession.id.asc()).gino.all()
    if idx > len(professions):
        await m.answer('Неверный номер.')
        return

    form_id = await db.select([db.Form.id]).where(db.Form.user_id == m.from_id).gino.scalar()
    prof_id = professions[idx - 1][0]
    await db.FormSecret.update.values(access_profession_id=prof_id).where(
        db.FormSecret.form_id == form_id).gino.status()

    states.set(m.from_id, FormSecrets.MENU)
    await m.answer('✅ Профессия сохранена.', keyboard=secrets_menu_kb)


@bot.on.private_message(StateRule(FormSecrets.ENTER_ACCESS_FRACTION),
                        PayloadRule({'secret_access': 'reset'}))
async def secret_access_reset(m: Message):
    """Сброс ограничений доступа — видят все."""
    form_id = await db.select([db.Form.id]).where(db.Form.user_id == m.from_id).gino.scalar()
    await db.FormSecret.update.values(
        access_fraction_id=None,
        access_reputation=0,
        access_profession_id=None,
        access_user_ids=[]
    ).where(db.FormSecret.form_id == form_id).gino.status()

    states.set(m.from_id, FormSecrets.MENU)
    await m.answer('✅ Ограничения доступа сброшены. Секретные разделы видят все.',
                   keyboard=secrets_menu_kb)


# ─── Утилиты для отображения секретных разделов ──────────────────────────────

async def get_secrets_for_viewer(form_id: int, viewer_id: int) -> str | None:
    """
    Возвращает текст секретных разделов для конкретного просматривающего или None,
    если у него нет доступа.

    Судьи и администраторы видят всё.
    """
    # Проверяем, является ли просматривающий судьёй/администратором
    is_admin = await db.select([db.User.admin]).where(db.User.user_id == viewer_id).gino.scalar()
    is_judge = await db.select([db.User.judge]).where(db.User.user_id == viewer_id).gino.scalar()

    row = await db.FormSecret.query.where(db.FormSecret.form_id == form_id).gino.first()
    if not row:
        return None

    # Если у разделов нет ограничений доступа — видят все
    allowed_users = set(row.access_user_ids or [])
    owner_id = await db.select([db.Form.user_id]).where(db.Form.id == form_id).gino.scalar()
    has_restrictions = (
        row.access_fraction_id or row.access_reputation or row.access_profession_id or allowed_users
    )

    if not has_restrictions or is_admin or is_judge or viewer_id == owner_id or viewer_id in allowed_users:
        pass  # Разрешаем
    else:
        # Проверяем совпадение фракции
        if row.access_fraction_id:
            viewer_form_id = await db.select([db.Form.id]).where(
                db.Form.user_id == viewer_id).gino.scalar()
            has_frac = await db.select([db.UserToFraction.id]).where(
                (db.UserToFraction.user_id == viewer_form_id) &
                (db.UserToFraction.fraction_id == row.access_fraction_id) &
                (db.UserToFraction.reputation >= (row.access_reputation or 0))
            ).gino.first()
            if not has_frac:
                return None

        if row.access_profession_id:
            viewer_prof = await db.select([db.Form.profession]).where(
                db.Form.user_id == viewer_id).gino.scalar()
            if viewer_prof != row.access_profession_id:
                return None

    parts = []
    if row.secret_features:
        parts.append(f'🔐 Особенности (скрытые):\n{row.secret_features}')
    if row.secret_bio:
        parts.append(f'🔐 Биография (скрытая):\n{row.secret_bio}')
    if row.secret_character:
        parts.append(f'🔐 Характер (скрытый):\n{row.secret_character}')
    if row.secret_motives:
        parts.append(f'🔐 Мотивы (скрытые):\n{row.secret_motives}')

    return '\n\n'.join(parts) if parts else None
