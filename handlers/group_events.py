"""
Модуль обработки событий группы ВК.
Содержит обработчики для автоматического принятия заявок
и отправки приветственных сообщений новым участникам.
"""

import asyncio

from vkbottle import GroupEventType
from vkbottle_types.events.bot_events import GroupJoin

from loader import bot, user_bot
import messages


@bot.on.raw_event(GroupEventType.GROUP_JOIN, GroupJoin)
async def group_join(event: GroupJoin):
    """
    Обработка вступления пользователя в группу

    Args:
        event: Событие вступления в группу
    """
    group_id = (await bot.api.groups.get_by_id()).groups[0].id
    if await bot.api.groups.is_member(group_id=group_id, user_id=event.object.user_id):
        return
    await user_bot.api.groups.approve_request(group_id=event.group_id, user_id=event.object.user_id)
    await asyncio.sleep(0.34)
    can_write = (await user_bot.api.users.get(user_ids=[event.object.user_id],
                                              fields=['can_write_private_message']))[
        0].can_write_private_message  # type: ignore
    await asyncio.sleep(0.34)
    if can_write:
        await user_bot.api.messages.send(peer_id=event.object.user_id, message=messages.accepted_to_group, random_id=0)

# ─── Обработка комментариев к постам на стене (ставки в аукционе) ─────────────

@bot.on.raw_event(GroupEventType.WALL_REPLY_NEW)
async def wall_reply_new(event: dict):
    """
    Ловит новые комментарии к постам на стене группы.
    Если комментарий содержит «ставка <число>» — передаёт в обработчик аукциона.
    """
    try:
        obj = event.get('object', {})
        user_id = obj.get('from_id')
        post_id = obj.get('post_id')
        text = obj.get('text', '')
        if user_id and post_id and text:
            from handlers.admin_panel.auctions import handle_wall_comment_bet
            await handle_wall_comment_bet(user_id, post_id, text)
    except Exception as e:
        import traceback
        print(f'[wall_reply_new] ошибка: {e}\n{traceback.format_exc()}')
