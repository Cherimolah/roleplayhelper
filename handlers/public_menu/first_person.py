from vkbottle.bot import Message
from vkbottle import Keyboard, KeyboardButtonColor, Text
from datetime import datetime, timedelta

from loader import bot, db, states
from service.custom_rules import StateRule, AdminRule
from service.states import UserState
from service import keyboards
from service.text_processors import check_message_length
from service.chat_manager import (
    save_user_chats_before_first_person,
    restore_user_to_chats,
    clear_user_chat_history
)

@bot.on.private_message(StateRule(UserState.MENU), payload={"menu": "first_person"})
async def toggle_first_person_mode(m: Message):
    """Включение/выключение режима от первого лица"""
    user_id = m.from_id
    
    # Проверяем текущий режим
    mode = await db.FirstPersonMode.query.where(
        db.FirstPersonMode.user_id == user_id
    ).gino.first()
    
    if mode and mode.is_active:
        # Выключаем режим
        await mode.update(
            is_active=False,
            blackout_mode=False,
            blackout_reason=None
        ).apply()
        
        # Восстанавливаем пользователя во все чаты
        restored_chats = await restore_user_to_chats(user_id)
        
        # Очищаем историю
        await clear_user_chat_history(user_id)
        
        # Обновляем текущий чат пользователя (ставим главный холл или первый восстановленный)
        if restored_chats:
            # Получаем чат холла из конфига
            from config import HALL_CHAT_ID
            await db.User.update.values(
                current_chat_id=HALL_CHAT_ID
            ).where(db.User.vk_id == user_id).gino.status()
        
        await m.answer(
            f"✅ Режим от первого лица выключен.\n"
            f"Вы были восстановлены в {len(restored_chats)} чатах.\n\n"
            f"Теперь вы можете полноценно участвовать в общих беседах.",
            keyboard=keyboards.main_menu(user_id)
        )
        
        # Возвращаем в главное меню
        states.set(m.from_id, UserState.MENU)
        
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
            f"👁️ Вы перешли в режим от первого лица.\n\n"
            f"📊 **Статистика:**\n"
            f"- Сохранено чатов: {len(saved_chats)}\n"
            f"- Удалено из чатов: {len(removed_chats)}\n\n"
            f"Теперь вы можете играть только через общение с @siren_bot (юзер-бот).\n"
            f"Все ваши сообщения будут пересылаться в локации, где вы находитесь.\n\n"
            f"⚠️ **Требования к сообщениям:**\n"
            f"- Минимум 300 символов без пробелов\n"
            f"- Без повторяющихся слов\n"
            f"- Команды бота не учитываются\n\n"
            f"Чтобы выйти из режима, нажмите кнопку ещё раз.",
            keyboard=keyboards.first_person_menu()
        )
        
        # Переводим в состояние режима от первого лица
        states.set(m.from_id, UserState.FIRST_PERSON_MENU)

@bot.on.private_message(StateRule(UserState.FIRST_PERSON_MENU), payload={"action": "first_person_chats"})
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
