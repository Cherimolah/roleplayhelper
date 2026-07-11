"""
Бизнес-логика аукционов (module auction_system).

Лотом аукциона является предмет карты экспедитора (db.Item) — у него уже есть
фото/описание для объявления и fraction_id/reputation для фильтрации получателей
закрытого аукциона ("только игроки, проходящие по условиям предмета").

Публичный аукцион: объявление постится на стену группы, ставки принимаются
комментариями к посту (см. handlers/group_events.py: wall_auction_bid).
Закрытый аукцион: таргетированная рассылка в ЛС подходящим игрокам, ставки
принимаются командой [ставка N] в ЛС боту (см. handlers/chat_commands.py: dm_auction_bid).
"""
import asyncio
import datetime

from sqlalchemy import func

from loader import bot
from service.db_engine import db
from config import GROUP_ID

DATE_FORMAT = '%d.%m.%Y %H:%M'


async def schedule_auction(auction_id: int):
    """Ставит в очередь запуск и завершение аукциона. Вызывается при создании и при рестарте бота"""
    auction = await db.Auction.get(auction_id)
    if not auction or auction.is_finished:
        return
    if not auction.is_started:
        delay = (auction.start_at - datetime.datetime.now()).total_seconds()
        asyncio.get_event_loop().create_task(_delayed(max(0, delay), start_auction, auction_id))
    delay_end = (auction.end_at - datetime.datetime.now()).total_seconds()
    asyncio.get_event_loop().create_task(_delayed(max(0, delay_end), finish_auction, auction_id))


async def _delayed(delay: float, func_, *args):
    if delay > 0:
        await asyncio.sleep(delay)
    await func_(*args)


async def _closed_auction_recipients(item) -> list[int]:
    """Игроки, проходящие по условиям предмета (фракция + уровень репутации), либо все, если условий нет"""
    if item.fraction_id:
        return [x[0] for x in await db.select([db.UserToFraction.user_id]).where(
            (db.UserToFraction.fraction_id == item.fraction_id) &
            (db.UserToFraction.reputation >= (item.reputation or 0))
        ).gino.all()]
    return [x[0] for x in await db.select([db.Form.user_id]).where(db.Form.is_request.is_(False)).gino.all()]


def _lot_text(item, auction, title: str, call_to_action: str) -> str:
    return (
        f"{title}: {item.name}\n\n"
        f"{item.description or ''}\n\n"
        f"Стартовая цена: {auction.start_price}\n"
        f"Минимальный шаг ставки: {auction.min_bid_step}\n"
        f"Завершение: {auction.end_at.strftime(DATE_FORMAT)}\n\n"
        f"{call_to_action}"
    )


async def start_auction(auction_id: int):
    """Публикует пост на стену (публичный) либо рассылает лот в ЛС подходящим игрокам (закрытый)"""
    auction = await db.Auction.get(auction_id)
    if not auction or auction.is_started or auction.is_finished:
        return
    item = await db.Item.get(auction.item_id)
    if not item:
        return

    if auction.is_public:
        text = _lot_text(item, auction, '📢 АУКЦИОН', 'Чтобы сделать ставку — оставьте комментарий с суммой ставки под этим постом!')
        attachments = [item.photo] if item.photo else None
        try:
            response = await bot.api.wall.post(owner_id=GROUP_ID, message=text, attachments=attachments, from_group=True)
            await auction.update(wall_post_id=response.post_id).apply()
        except Exception:
            pass
    else:
        text = _lot_text(item, auction, '🔒 ЗАКРЫТЫЙ АУКЦИОН', 'Чтобы сделать ставку, напишите боту в ЛС: [ставка СУММА]')
        recipients = await _closed_auction_recipients(item)
        for i in range(0, len(recipients), 100):
            try:
                await bot.api.messages.send(peer_ids=recipients[i:i + 100], message=text, random_id=0, is_notification=True)
            except Exception:
                for user_id in recipients[i:i + 100]:
                    try:
                        await bot.api.messages.send(peer_id=user_id, message=text, random_id=0, is_notification=True)
                    except Exception:
                        pass

    await auction.update(is_started=True).apply()


async def place_bid(auction_id: int, user_id: int, amount: int, comment_id: int | None = None) -> tuple[bool, str]:
    """Пытается зарегистрировать ставку. Возвращает (успех, сообщение для игрока)"""
    auction = await db.Auction.get(auction_id)
    if not auction or auction.is_finished or not auction.is_started:
        return False, 'Аукцион недоступен для ставок'
    if datetime.datetime.now() > auction.end_at:
        return False, 'Аукцион уже завершён'

    highest = await db.select([func.max(db.AuctionBid.amount)]).where(
        db.AuctionBid.auction_id == auction_id).gino.scalar()
    min_required = (highest + auction.min_bid_step) if highest else auction.start_price
    if amount < min_required:
        return False, f'Ставка слишком мала. Минимальная ставка сейчас: {min_required}'

    await db.AuctionBid.create(auction_id=auction_id, user_id=user_id, amount=amount, comment_id=comment_id)
    return True, f'Ваша ставка {amount} принята!'


async def eligible_closed_auction_ids(user_id: int) -> list[int]:
    """Активные закрытые аукционы, к которым у игрока есть допуск"""
    rows = await db.select([db.Auction.id, db.Auction.item_id]).where(
        db.Auction.is_public.is_(False) & db.Auction.is_started.is_(True) & db.Auction.is_finished.is_(False)
    ).gino.all()
    result = []
    for auction_id, item_id in rows:
        item = await db.Item.get(item_id)
        if item and user_id in await _closed_auction_recipients(item):
            result.append(auction_id)
    return result


async def finish_auction(auction_id: int):
    """Подводит итоги аукциона: выбирает победителя по наивысшей ставке и рассылает результат"""
    auction = await db.Auction.get(auction_id)
    if not auction or auction.is_finished:
        return
    if not auction.is_started:
        await start_auction(auction_id)
        auction = await db.Auction.get(auction_id)

    item = await db.Item.get(auction.item_id)
    winner = await db.select([db.AuctionBid.user_id, db.AuctionBid.amount]).where(
        db.AuctionBid.auction_id == auction_id
    ).order_by(db.AuctionBid.amount.desc()).limit(1).gino.first()

    from service.utils import create_mention  # локальный импорт, чтобы избежать циклического импорта service.utils <-> service.auctions

    if winner:
        winner_user_id, winner_amount = winner
        await auction.update(is_finished=True, winner_user_id=winner_user_id, winner_bid=winner_amount).apply()
        result_text = (f'🏆 Аукцион «{item.name}» завершён!\n'
                       f'Победитель: {await create_mention(winner_user_id)} со ставкой {winner_amount}')
        try:
            await bot.api.messages.send(
                peer_id=winner_user_id,
                message=f'Поздравляем! Вы выиграли аукцион «{item.name}» со ставкой {winner_amount}',
                random_id=0, is_notification=True,
            )
        except Exception:
            pass
    else:
        await auction.update(is_finished=True).apply()
        result_text = f'Аукцион «{item.name}» завершён. Ставок не поступило.'

    if auction.is_public:
        try:
            await bot.api.wall.post(owner_id=GROUP_ID, message=result_text, attachments=[item.photo] if item.photo else None, from_group=True)
        except Exception:
            pass
    else:
        recipients = await _closed_auction_recipients(item)
        for i in range(0, len(recipients), 100):
            try:
                await bot.api.messages.send(peer_ids=recipients[i:i + 100], message=result_text, random_id=0, is_notification=True)
            except Exception:
                pass

    if auction.created_by:
        try:
            await bot.api.messages.send(peer_id=auction.created_by, message=result_text, random_id=0, is_notification=True)
        except Exception:
            pass
