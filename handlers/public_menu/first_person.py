from vkbottle.bot import Message

from loader import bot, states
from service.custom_rules import StateRule
from service.states import Menu
from service import keyboards
from service.chat_manager import (
    save_user_chats_before_first_person,
    restore_user_to_chats,
    clear_user_chat_history,
)
from service.db_engine import db
<<<<<<< Updated upstream
=======
from config import USER_ID
>>>>>>> Stashed changes

@bot.on.private_message(StateRule(Menu.MAIN), payload={"menu": "first_person"})
async def toggle_first_person_mode(m: Message):
    """Включение/выключение режима от первого лица"""
    user_id = m.from_id
    
    # Проверяем текущий режим
    mode = await db.FirstPersonMode.query.where(
        db.FirstPersonMode.user_id == user_id
    ).gino.first()
    
    if mode and mode.is_active:
<<<<<<< Updated upstream
=======
        if mode.blackout_mode:
            await m.answer(
                "⚫ Режим от первого лица включен принудительно администрацией.\n"
                "Вы не можете отключить его самостоятельно — дождитесь снятия администрацией."
            )
            return

>>>>>>> Stashed changes
        # Выключаем режим
        await mode.update(
            is_active=False,
            blackout_mode=False,
            blackout_reason=None
        ).apply()
        
        # Восстанавливаем пользователя во все чаты
        restored_chats = await restore_user_to_chats(user_id)
        
        # Очищаем только уже восстановленные записи (не теряем историю, если что-то не удалось восстановить)
        await clear_user_chat_history(user_id, only_restored=True)
        
        await m.answer(
            f"✅ Режим от первого лица выключен.\n"
            f"Вы были восстановлены в {len(restored_chats)} чатах.\n\n"
            f"Теперь вы можете полноценно участвовать в общих беседах.",
            keyboard=await keyboards.main_menu(user_id)
        )
        
        # Возвращаем в главное меню
        states.set(m.from_id, Menu.MAIN)
        
    else:
        # Включаем режим
        # Сначала сохраняем текущие чаты
        saved_chats = await save_user_chats_before_first_person(user_id)
        
        if not mode:
            mode = await db.FirstPersonMode.create(
                user_id=user_id,
                is_active=True
            )
        else:
            await mode.update(is_active=True).apply()
        
        # Удаляем из всех чатов (используем существующую функцию)
        from service.utils import remove_user_from_all_chats
        removed_chats = await remove_user_from_all_chats(user_id)
        
        await m.answer(
            "👁️ Вы перешли в режим от первого лица.\n\n"
<<<<<<< Updated upstream
            "Теперь вы можете играть через общение с юзерботом (Сирена).\n"
            "Сообщения будут транслироваться в вашу текущую локацию.\n\n"
=======
            f"Теперь вы можете играть через общение с юзерботом (Сирена): https://vk.com/id{USER_ID}\n"
            "Напишите юзерботу в личные сообщения — ваши посты будут транслироваться в вашу текущую локацию.\n\n"
>>>>>>> Stashed changes
            "⚠️ Антиспам для пересылаемых постов: 300–350 символов без пробелов, "
            "без повторов и без учёта строк-команд.\n\n"
            "Чтобы выйти из режима — нажмите кнопку ещё раз.",
            keyboard=keyboards.first_person_menu()
        )
        
        # Возвращаем в меню (кнопка выхода остаётся в клавиатуре)
        states.set(m.from_id, Menu.MAIN)

@bot.on.private_message(StateRule(Menu.MAIN), payload={"action": "first_person_chats"})
async def show_saved_chats(m: Message):
    """Показывает сохраненные чаты пользователя"""
    from service.chat_manager import get_user_chat_history
    
    history = await get_user_chat_history(m.from_id)
    
    if not history:
        await m.answer("У вас нет сохраненных чатов.")
        return
    
    response = "💾 **Сохраненные чаты:**\n\n"
    for i, chat in enumerate(history, 1):
        status = "✅ Восстановлен" if chat['restored'] else "❌ Ожидает восстановления"
        response += f"{i}. {chat['chat_name']}\n"
        response += f"   Статус: {status}\n"
        if chat['left_at']:
            response += f"   Вышел: {chat['left_at'].strftime('%d.%m.%Y %H:%M')}\n"
        response += "\n"
    
    await m.answer(response)
