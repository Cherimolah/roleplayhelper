from vkbottle.bot import Message
from vkbottle import Keyboard, KeyboardButtonColor, Text
from datetime import datetime, timedelta

from loader import bot, db, states
from service.custom_rules import StateRule, AdminRule
from service.states import Admin
from service import keyboards
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
    
    # Получаем всех активных пользователей
    users = await db.User.query.where(db.User.is_active == True).gino.all()
    
    for user in users:
        # Включаем режим от первого лица
        mode = await db.FirstPersonMode.query.where(
            db.FirstPersonMode.user_id == user.vk_id
        ).gino.first()
        
        if mode:
            await mode.update(
                is_active=True,
                blackout_mode=True,
                blackout_reason=reason
            ).apply()
        else:
            await db.FirstPersonMode.create(
                user_id=user.vk_id,
                is_active=True,
                blackout_mode=True,
                blackout_reason=reason
            )
        
        # Удаляем из всех чатов
        await remove_user_from_all_chats(user.vk_id)
        
        # Отправляем уведомление пользователю
        await bot.api.messages.send(
            user_id=user.vk_id,
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
        keyboard=keyboards.admin_menu()
    )
    states.set(m.from_id, Admin.MENU)
