<<<<<<< Updated upstream
from vkbottle.bot import Message
from vkbottle import Keyboard, KeyboardButtonColor, Text
from datetime import datetime, timedelta
from vkbottle.dispatch.rules.base import PayloadRule

from loader import bot, states
from service.custom_rules import StateRule, AdminRule
from service.states import Admin
from service import keyboards
from service.db_engine import db
from service.utils import remove_user_from_all_chats

@bot.on.private_message(StateRule(Admin.MENU), payload={"admin": "blackout"})
async def blackout_menu(m: Message):
    """
    Меню управления режимом блэкаут
    """
    keyboard = Keyboard(inline=True)
    keyboard.add(Text("Отдельный игрок", {"blackout": "single"}))
    keyboard.row()
    keyboard.add(Text("По профессии", {"blackout": "profession"}))
    keyboard.row()
    keyboard.add(Text("Все игроки", {"blackout": "all"}))
    keyboard.row()
    keyboard.add(Text("Снять блэкаут", {"blackout": "remove"}))
    keyboard.row()
    keyboard.add(Text("Назад", {"admin": "menu"}), KeyboardButtonColor.NEGATIVE)
    
    await m.answer(
        "⚫ **Режим Блэкаут**\n\n"
        "Выберите действие:\n"
        "1. Включить для отдельного игрока\n"
        "2. Включить для профессии\n"
        "3. Включить для всех игроков\n"
        "4. Снять блэкаут",
        keyboard=keyboard
    )

@bot.on.private_message(StateRule(Admin.BLACKOUT_SINGLE), AdminRule())
async def blackout_single_user(m: Message):
    """Включение блэкаута для отдельного игрока"""
    # Поиск пользователя по ID или упоминанию
    # Здесь должна быть логика поиска пользователя
    pass

@bot.on.private_message(StateRule(Admin.BLACKOUT_PROFESSION), AdminRule())
async def blackout_by_profession(m: Message):
    """Включение блэкаута для профессии"""
    # Получение списка профессий и выбор
    pass

@bot.on.private_message(StateRule(Admin.BLACKOUT_ALL), AdminRule())
async def blackout_all_users(m: Message):
    """Включение блэкаута для всех игроков"""
    keyboard = Keyboard(inline=True)
    keyboard.add(Text("Подтвердить", {"blackout_confirm": "all"}))
    keyboard.row()
    keyboard.add(Text("Отмена", {"admin": "blackout"}), KeyboardButtonColor.NEGATIVE)
    
    await m.answer(
        "⚠️ **Внимание!**\n\n"
        "Вы собираетесь включить режим блэкаут для ВСЕХ игроков.\n"
        "Это переведет всех в режим от первого лица.\n\n"
        "Укажите причину блэкаута:",
        keyboard=keyboard
    )
    states.set(m.from_id, Admin.BLACKOUT_ALL_CONFIRM)

@bot.on.private_message(StateRule(Admin.BLACKOUT_ALL_CONFIRM), PayloadRule({"blackout_confirm": "all"}), AdminRule())
async def confirm_blackout_all(m: Message):
    """Подтверждение блэкаута для всех"""
    reason = m.text
    
    # Получаем всех пользователей бота
    users = [x[0] for x in await db.select([db.User.user_id]).gino.all()]
    
    for user_id in users:
        # Включаем режим от первого лица
        mode = await db.FirstPersonMode.query.where(
            db.FirstPersonMode.user_id == user_id
        ).gino.first()
        
        if mode:
            await mode.update(
                is_active=True,
                blackout_mode=True,
                blackout_reason=reason
            ).apply()
        else:
            await db.FirstPersonMode.create(
                user_id=user_id,
                is_active=True,
                blackout_mode=True,
                blackout_reason=reason
            )
        
        # Удаляем из всех чатов
        await remove_user_from_all_chats(user_id)
        
        # Отправляем уведомление пользователю
        await bot.api.messages.send(
            user_id=user_id,
            message=f"⚫ **ВНИМАНИЕ: АКТИВИРОВАН РЕЖИМ БЛЭКАУТ**\n\n"
                   f"Причина: {reason}\n\n"
                   f"Вы переведены в режим от первого лица.\n"
                   f"Это означает, что вы были удалены из всех чатов и "
                   f"можете общаться только через юзер-бота.\n\n"
                   f"Режим будет снят администрацией.",
            random_id=0
        )
    
    await m.answer(
        f"✅ Режим блэкаут включен для всех {len(users)} игроков.\n"
        f"Причина: {reason}",
        keyboard=keyboards.admin_menu
    )
    states.set(m.from_id, Admin.MENU)
=======
"""
Административный инструмент "POV режим": принудительный перевод игроков
(отдельного игрока, всех игроков одной профессии или вообще всех игроков)
в режим от первого лица, а также снятие такого принудительного перевода.

Игроки, переведённые в POV принудительно (FirstPersonMode.blackout_mode=True),
не могут отключить режим сами (см. handlers/public_menu/first_person.py) —
снять его может только администрация через "Снять принудительный POV".
"""

from vkbottle.bot import Message
from vkbottle import Keyboard, KeyboardButtonColor, Text
from vkbottle.dispatch.rules.base import PayloadRule

from loader import bot, states
from service.custom_rules import StateRule, AdminRule, UserSpecified, NumericRule
from service.states import Admin
from service import keyboards
from service.db_engine import db
from service.chat_manager import force_pov_on, force_pov_off


@bot.on.private_message(StateRule(Admin.MENU), PayloadRule({"admin_menu": "pov_mode"}), AdminRule())
async def pov_mode_menu(m: Message):
    """Меню принудительного управления POV режимом"""
    keyboard = Keyboard(inline=True)
    keyboard.add(Text("Отдельный игрок", {"pov_mode": "single"}))
    keyboard.row()
    keyboard.add(Text("По профессии", {"pov_mode": "profession"}))
    keyboard.row()
    keyboard.add(Text("Все игроки", {"pov_mode": "all"}))
    keyboard.row()
    keyboard.add(Text("Снять принудительный POV", {"pov_mode": "remove"}))
    keyboard.row()
    keyboard.add(Text("Назад", {"admin_menu": "back"}), KeyboardButtonColor.NEGATIVE)

    await m.answer(
        "👁️ Раздел «POV режим»\n\n"
        "Здесь можно принудительно перевести игроков в режим от первого лица. "
        "Пока перевод не снят администрацией, игрок не сможет выключить режим сам.",
        keyboard=keyboard,
    )


@bot.on.private_message(StateRule(Admin.MENU), PayloadRule({"pov_mode": "single"}), AdminRule())
async def ask_single_pov_user(m: Message):
    states.set(m.from_id, Admin.BLACKOUT_SINGLE)
    keyboard = Keyboard().add(Text("Назад", {"admin_menu": "pov_mode"}), KeyboardButtonColor.NEGATIVE)
    await m.answer("Отправьте ссылку/упоминание/пересланное сообщение игрока, которого нужно перевести в POV",
                    keyboard=keyboard)


@bot.on.private_message(StateRule(Admin.BLACKOUT_SINGLE), UserSpecified(), AdminRule())
async def ask_single_pov_reason(m: Message, form: tuple):
    _, user_id = form
    states.set(m.from_id, f"{Admin.BLACKOUT_SINGLE_REASON}*{user_id}")
    keyboard = Keyboard().add(Text("Без причины", {"pov_reason": "skip"}), KeyboardButtonColor.SECONDARY)
    await m.answer("Укажите причину принудительного перевода в POV (или нажмите «Без причины»)", keyboard=keyboard)


@bot.on.private_message(StateRule(Admin.BLACKOUT_SINGLE_REASON), AdminRule())
async def confirm_single_pov(m: Message):
    _, user_id = states.get(m.from_id).split("*", 1)
    reason = None if m.payload and m.payload.get("pov_reason") == "skip" else m.text
    await force_pov_on(int(user_id), reason)
    states.set(m.from_id, Admin.MENU)
    await m.answer("✅ Игрок принудительно переведён в режим от первого лица", keyboard=keyboards.admin_menu)


@bot.on.private_message(StateRule(Admin.MENU), PayloadRule({"pov_mode": "profession"}), AdminRule())
async def ask_pov_profession(m: Message):
    professions = await db.select([db.Profession.id, db.Profession.name]).order_by(db.Profession.id.asc()).gino.all()
    if not professions:
        await m.answer("Профессии ещё не созданы")
        return
    reply = "Выберите профессию по номеру:\n\n"
    for i, (_, name) in enumerate(professions, 1):
        reply += f"{i}. {name}\n"
    states.set(m.from_id, Admin.BLACKOUT_PROFESSION)
    keyboard = Keyboard().add(Text("Назад", {"admin_menu": "pov_mode"}), KeyboardButtonColor.NEGATIVE)
    await m.answer(reply, keyboard=keyboard)


@bot.on.private_message(StateRule(Admin.BLACKOUT_PROFESSION), NumericRule(), AdminRule())
async def ask_pov_profession_reason(m: Message, value: int):
    profession_id = await db.select([db.Profession.id]).order_by(db.Profession.id.asc()).offset(value - 1).limit(1).gino.scalar()
    if not profession_id:
        await m.answer("Профессия с таким номером не найдена")
        return
    states.set(m.from_id, f"{Admin.BLACKOUT_PROFESSION_REASON}*{profession_id}")
    keyboard = Keyboard().add(Text("Без причины", {"pov_reason": "skip"}), KeyboardButtonColor.SECONDARY)
    await m.answer("Укажите причину принудительного перевода в POV (или нажмите «Без причины»)", keyboard=keyboard)


@bot.on.private_message(StateRule(Admin.BLACKOUT_PROFESSION_REASON), AdminRule())
async def confirm_profession_pov(m: Message):
    _, profession_id = states.get(m.from_id).split("*", 1)
    reason = None if m.payload and m.payload.get("pov_reason") == "skip" else m.text
    user_ids = [x[0] for x in await db.select([db.Form.user_id]).where(
        (db.Form.profession == int(profession_id)) & (db.Form.is_request.is_(False))
    ).gino.all()]
    for user_id in user_ids:
        await force_pov_on(user_id, reason)
    states.set(m.from_id, Admin.MENU)
    await m.answer(f"✅ Переведено в POV режим игроков: {len(user_ids)}", keyboard=keyboards.admin_menu)


@bot.on.private_message(StateRule(Admin.MENU), PayloadRule({"pov_mode": "all"}), AdminRule())
async def ask_all_pov_reason(m: Message):
    states.set(m.from_id, Admin.BLACKOUT_ALL)
    keyboard = Keyboard().add(Text("Без причины", {"pov_reason": "skip"}), KeyboardButtonColor.SECONDARY)
    await m.answer(
        "⚠️ Вы собираетесь перевести в POV режим ВСЕХ игроков.\n"
        "Укажите причину (или нажмите «Без причины»):",
        keyboard=keyboard,
    )


@bot.on.private_message(StateRule(Admin.BLACKOUT_ALL), AdminRule())
async def ask_all_pov_confirm(m: Message):
    reason = None if m.payload and m.payload.get("pov_reason") == "skip" else m.text
    states.set(m.from_id, f"{Admin.BLACKOUT_ALL_CONFIRM}*{reason or ''}")
    keyboard = Keyboard(inline=True).add(
        Text("Подтвердить", {"pov_confirm": "all"}), KeyboardButtonColor.NEGATIVE
    ).row().add(
        Text("Отмена", {"admin_menu": "pov_mode"}), KeyboardButtonColor.SECONDARY
    )
    await m.answer("Вы уверены? Это переведёт в POV режим ВСЕХ игроков бота.", keyboard=keyboard)


@bot.on.private_message(StateRule(Admin.BLACKOUT_ALL_CONFIRM), PayloadRule({"pov_confirm": "all"}), AdminRule())
async def confirm_blackout_all(m: Message):
    """Подтверждение принудительного POV для всех"""
    _, reason = states.get(m.from_id).split("*", 1)
    reason = reason or None

    user_ids = [x[0] for x in await db.select([db.User.user_id]).gino.all()]
    for user_id in user_ids:
        await force_pov_on(user_id, reason)

    states.set(m.from_id, Admin.MENU)
    await m.answer(f"✅ Режим от первого лица принудительно включен для всех {len(user_ids)} игроков",
                    keyboard=keyboards.admin_menu)


@bot.on.private_message(StateRule(Admin.MENU), PayloadRule({"pov_mode": "remove"}), AdminRule())
async def remove_forced_pov(m: Message):
    """Снятие принудительного POV режима со всех, у кого он был навязан администрацией"""
    user_ids = [x[0] for x in await db.select([db.FirstPersonMode.user_id]).where(
        db.FirstPersonMode.blackout_mode.is_(True)
    ).gino.all()]
    count = 0
    for user_id in user_ids:
        if await force_pov_off(user_id):
            count += 1
    states.set(m.from_id, Admin.MENU)
    await m.answer(f"✅ Принудительный POV снят у {count} игроков", keyboard=keyboards.admin_menu)
>>>>>>> Stashed changes
