"""
POV (режим от первого лица): обработка сообщений, которые игрок пишет в ЛС юзерботу.

Юзербот выступает как "прокси": отправляет текст игрока в текущую локацию (чат-локацию),
а основной бот уже разошлёт этот пост другим игрокам в POV в той же локации.
"""

from vkbottle.user import Message

from loader import user_bot, bot
from service.custom_rules import FromUserRule
from service.db_engine import db
from service.text_processors import is_commands_only, is_forwardable_post
from config import GROUP_ID


@user_bot.on.private_message()
async def pov_private_proxy(m: Message):
    user_id = m.from_id
    if not user_id or not m.text:
        return

    mode = await db.FirstPersonMode.query.where(db.FirstPersonMode.user_id == user_id).gino.first()
    if not mode or not mode.is_active:
        return

    # Локация игрока (система перемещения остаётся прежней)
    chat_id = await db.select([db.UserToChat.chat_id]).where(db.UserToChat.user_id == user_id).gino.scalar()
    if not chat_id:
        await user_bot.api.messages.send(peer_id=user_id, message="У вас не выбрана локация для игры.")
        return

    # Команды пропускаем (чтобы работали все текущие механики в чатах)
    if not is_commands_only(m.text) and not is_forwardable_post(m.text):
        await user_bot.api.messages.send(
            peer_id=user_id,
            message=(
                "Сообщение слишком короткое для пересылки в POV.\n"
                "Нужно примерно 300–350 символов без пробелов (строки-команды не учитываются)."
            ),
        )
        return

    # Подпись отправителя внутри чата (иначе в чате всё будет от лица юзербота)
    try:
        u = (await bot.api.users.get([user_id]))[0]
        label = f"[id{user_id}|{u.first_name} {u.last_name}]"
    except Exception:
        label = f"[id{user_id}|{user_id}]"

    text = m.text.strip()
    payload = f"{label}:\n{text}"

    await user_bot.api.messages.send(peer_id=chat_id + 2000000000, message=payload, random_id=0)

