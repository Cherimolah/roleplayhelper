"""
Настройки режима от первого лица для администраторов
"""

from vkbottle.bot import Message
from vkbottle import Keyboard, KeyboardButtonColor, Text

from loader import bot, db, states
from service.custom_rules import StateRule, AdminRule
from service.states import Admin

@bot.on.private_message(StateRule(Admin.MENU), payload={"admin": "first_person_settings"})
async def first_person_settings_menu(m: Message):
    """Меню настроек режима от первого лица"""
    keyboard = Keyboard(inline=True)
    keyboard.add(Text("Настройки видимости", {"fp_settings": "vision"}))
    keyboard.row()
    keyboard.add(Text("Управление эффектами", {"fp_settings": "effects"}))
    keyboard.row()
    keyboard.add(Text("Статистика", {"fp_settings": "stats"}))
    keyboard.row()
    keyboard.add(Text("Назад", {"admin": "menu"}), KeyboardButtonColor.NEGATIVE)
    
    await m.answer(
        "👁️ **Настройки режима от первого лица**\n\n"
        "Выберите раздел для настройки:",
        keyboard=keyboard
    )

@bot.on.private_message(StateRule(Admin.FP_VISION_SETTINGS), AdminRule())
async def vision_settings(m: Message):
    """Настройки уровня видимости"""
    # Получаем текущие настройки по умолчанию
    default_min = 0.2
    default_max = 0.9
    
    keyboard = Keyboard(inline=True)
    keyboard.add(Text("Минимальный уровень", {"fp_vision": "min"}))
    keyboard.row()
    keyboard.add(Text("Максимальный уровень", {"fp_vision": "max"}))
    keyboard.row()
    keyboard.add(Text("Сброс к默认ным", {"fp_vision": "reset"}))
    keyboard.row()
    keyboard.add(Text("Назад", {"admin": "first_person_settings"}), KeyboardButtonColor.NEGATIVE)
    
    await m.answer(
        f"🔧 **Настройки ограниченной видимости**\n\n"
        f"Текущие настройки:\n"
        f"• Минимальный уровень: {default_min}\n"
        f"• Максимальный уровень: {default_max}\n\n"
        f"Уровень выбирается случайно для каждого сообщения.\n"
        f"Чем выше уровень - тем больше текста замазывается.",
        keyboard=keyboard
    )
