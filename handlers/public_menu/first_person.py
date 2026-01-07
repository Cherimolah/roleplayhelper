from vkbottle.bot import Message
from vkbottle import Keyboard, KeyboardButtonColor, Text
from datetime import datetime, timedelta

from loader import bot, db, states
from service.custom_rules import StateRule, AdminRule
from service.states import UserState
from service import keyboards
from service.text_processors import check_message_length
from service.utils import remove_user_from_all_chats

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
        
        # Возвращаем в чаты (нужно реализовать логику возврата)
        await return_user_to_chats(user_id)
        
        await m.answer(
            "✅ Режим от первого лица выключен.\n"
            "Вы были возвращены во все чаты, в которых находились ранее.",
            keyboard=keyboards.main_menu(user_id)
        )
    else:
        # Включаем режим
        if not mode:
            mode = await db.FirstPersonMode.create(
                user_id=user_id,
                is_active=True
            )
        else:
            await mode.update(is_active=True).apply()
        
        # Удаляем из всех чатов
        await remove_user_from_all_chats(user_id)
        
        await m.answer(
            "👁️ Вы перешли в режим от первого лица.\n\n"
            "Теперь вы можете играть только через общение с @siren_bot (юзер-бот).\n"
            "Все ваши сообщения будут пересылаться в локации, где вы находитесь.\n\n"
            "⚠️ **Требования к сообщениям:**\n"
            "- Минимум 300 символов без пробелов\n"
            "- Без повторяющихся слов\n"
            "- Команды бота не учитываются\n\n"
            "Чтобы выйти из режима, нажмите кнопку ещё раз.",
            keyboard=keyboards.first_person_menu()
        )

@bot.on.private_message(StateRule(UserState.FIRST_PERSON_CHAT))
async def handle_first_person_message(m: Message):
    """Обработка сообщений в режиме от первого лица"""
    user_id = m.from_id
    
    # Проверяем длину сообщения
    if not check_message_length(m.text, min_chars=300):
        await m.answer(
            "❌ Сообщение слишком короткое для режима от первого лица.\n"
            "Требуется минимум 300 символов без пробелов и повторений.\n"
            "Попробуйте написать более развернутое сообщение."
        )
        return
    
    # Получаем текущую локацию пользователя
    user = await db.User.query.where(db.User.vk_id == user_id).gino.first()
    if not user or not user.current_chat_id:
        await m.answer("Вы не находитесь ни в одной локации.")
        return
    
    # Получаем информацию о чате
    chat = await db.Chat.query.where(db.Chat.id == user.current_chat_id).gino.first()
    
    # Отправляем сообщение в чат через юзер-бота
    # (это нужно интегрировать с существующей системой юзер-бота)
    await forward_to_chat(user_id, chat.chat_id, m.text, m.attachments)
    
    await m.answer(
        f"✅ Сообщение отправлено в {chat.name}\n"
        f"Ожидайте ответов от других игроков."
    )

async def forward_to_chat(sender_id: int, chat_id: int, text: str, attachments=None):
    """
    Пересылает сообщение в чат через юзер-бота
    Нужно интегрировать с существующей системой юзер-бота
    """
    # Здесь должна быть логика отправки через юзер-бота
    # Временно заглушка
    pass

async def return_user_to_chats(user_id: int):
    """
    Возвращает пользователя во все чаты, из которых его удалили
    Нужно интегрировать с существующей системой чатов
    """
    # Здесь должна быть логика возврата в чаты
    # Временно заглушка
    pass
