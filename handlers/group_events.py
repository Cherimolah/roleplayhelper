"""
Модуль обработки событий группы ВК.
Содержит обработчики для автоматического принятия заявок
и отправки приветственных сообщений новым участникам.
"""

import asyncio

from vkbottle import GroupEventType
from vkbottle_types.events.bot_events import GroupJoin, WallReplyNew

from loader import bot, user_bot
import messages
from service.db_engine import db
from service.auctions import place_bid


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


@bot.on.raw_event(GroupEventType.WALL_REPLY_NEW, WallReplyNew)
async def wall_auction_bid(event: WallReplyNew):
    """
    Отслеживание ставок на публичных аукционах через комментарии на стене (module auction_system).
    Комментарий засчитывается как ставка, если он состоит из числа (суммы ставки) и оставлен
    под постом активного публичного аукциона.
    """
    comment = event.object
    if comment.from_id <= 0:  # комментарий от имени сообщества
        return
    auction_id = await db.select([db.Auction.id]).where(
        (db.Auction.wall_post_id == comment.post_id) &
        db.Auction.is_public.is_(True) & db.Auction.is_finished.is_(False)
    ).gino.scalar()
    if not auction_id:
        return
    digits = ''.join(ch for ch in (comment.text or '') if ch.isdigit())
    if not digits:
        return
    success, message = await place_bid(auction_id, comment.from_id, int(digits), comment_id=comment.id)
    try:
        await bot.api.messages.send(peer_id=comment.from_id, message=message, random_id=0, is_notification=True)
    except Exception:
        pass