"""
Инструмент судей и администраторов для выставления предметов карты экспедитора
(db.Item) на торги (module auction_system).
"""
import datetime

from vkbottle.bot import Message
from vkbottle.dispatch.rules.base import PayloadRule
from vkbottle.dispatch.rules.abc import OrRule
from vkbottle import Keyboard, Text, KeyboardButtonColor

from loader import bot, states
from service.custom_rules import AdminRule, JudgeRule, StateRule, NumericRule
from service.states import Admin, Judge
from service.db_engine import db
from service import keyboards
from service.auctions import schedule_auction
from config import DATETIME_FORMAT

staff_rule = OrRule(AdminRule(), JudgeRule())


@bot.on.private_message(StateRule(Admin.MENU), PayloadRule({"admin_menu": "auctions"}), staff_rule)
@bot.on.private_message(StateRule(Judge.MENU), PayloadRule({"judge_menu": "auctions"}), staff_rule)
async def select_auction_item(m: Message):
    """Начало создания аукциона: выбор предмета-лота"""
    items = await db.select([db.Item.name]).order_by(db.Item.id.asc()).gino.all()
    if not items:
        await m.answer('Предметы карты экспедитора ещё не созданы')
        return
    reply = 'Выберите предмет для выставления на аукцион:\n\n'
    for i, item in enumerate(items):
        reply += f'{i + 1}. {item.name}\n'
    states.set(m.from_id, Admin.AUCTION_SELECT_ITEM)
    await m.answer(reply, keyboard=Keyboard())


@bot.on.private_message(StateRule(Admin.AUCTION_SELECT_ITEM), NumericRule(), staff_rule)
async def select_auction_type(m: Message, value: int):
    """Выбор типа аукциона (публичный/закрытый)"""
    item_id = await db.select([db.Item.id]).order_by(db.Item.id.asc()).offset(value - 1).limit(1).gino.scalar()
    if not item_id:
        await m.answer('Предмет с таким номером не найден')
        return
    auction = await db.Auction.create(item_id=item_id, created_by=m.from_id)
    states.set(m.from_id, f'{Admin.AUCTION_TYPE}*{auction.id}')
    keyboard = Keyboard(inline=True).add(
        Text('Публичный (стена)', {'auction_type': 'public'}), KeyboardButtonColor.PRIMARY
    ).row().add(
        Text('Закрытый (ЛС)', {'auction_type': 'closed'}), KeyboardButtonColor.SECONDARY
    )
    await m.answer('Выберите тип аукциона:', keyboard=keyboard)


@bot.on.private_message(StateRule(Admin.AUCTION_TYPE), PayloadRule({'auction_type': 'public'}), staff_rule)
@bot.on.private_message(StateRule(Admin.AUCTION_TYPE), PayloadRule({'auction_type': 'closed'}), staff_rule)
async def set_auction_type(m: Message):
    """Установка типа аукциона и переход к стартовой цене"""
    _, auction_id = states.get(m.from_id).split('*')
    is_public = m.payload['auction_type'] == 'public'
    await db.Auction.update.values(is_public=is_public).where(db.Auction.id == int(auction_id)).gino.status()
    states.set(m.from_id, f'{Admin.AUCTION_START_PRICE}*{auction_id}')
    await m.answer('Укажите стартовую цену лота:', keyboard=Keyboard())


@bot.on.private_message(StateRule(Admin.AUCTION_START_PRICE), NumericRule(min_number=0), staff_rule)
async def set_auction_start_price(m: Message, value: int):
    """Установка стартовой цены"""
    _, auction_id = states.get(m.from_id).split('*')
    await db.Auction.update.values(start_price=value).where(db.Auction.id == int(auction_id)).gino.status()
    states.set(m.from_id, f'{Admin.AUCTION_MIN_BID}*{auction_id}')
    await m.answer('Укажите минимальный шаг ставки:')


@bot.on.private_message(StateRule(Admin.AUCTION_MIN_BID), NumericRule(min_number=1), staff_rule)
async def set_auction_min_bid(m: Message, value: int):
    """Установка минимального шага ставки"""
    _, auction_id = states.get(m.from_id).split('*')
    await db.Auction.update.values(min_bid_step=value).where(db.Auction.id == int(auction_id)).gino.status()
    states.set(m.from_id, f'{Admin.AUCTION_START_AT}*{auction_id}')
    keyboard = Keyboard().add(Text('Начать сейчас', {'auction_start': 'now'}), KeyboardButtonColor.POSITIVE)
    await m.answer(f'Укажите дату и время начала аукциона в формате {DATETIME_FORMAT}, '
                   f'либо нажмите «Начать сейчас»:', keyboard=keyboard)


@bot.on.private_message(StateRule(Admin.AUCTION_START_AT), PayloadRule({'auction_start': 'now'}), staff_rule)
async def set_auction_start_now(m: Message):
    """Установка немедленного начала аукциона"""
    _, auction_id = states.get(m.from_id).split('*')
    await db.Auction.update.values(start_at=datetime.datetime.now()).where(db.Auction.id == int(auction_id)).gino.status()
    states.set(m.from_id, f'{Admin.AUCTION_END_AT}*{auction_id}')
    await m.answer(f'Укажите дату и время завершения аукциона в формате {DATETIME_FORMAT}:', keyboard=Keyboard())


@bot.on.private_message(StateRule(Admin.AUCTION_START_AT), staff_rule)
async def set_auction_start_at(m: Message):
    """Установка отложенного начала аукциона"""
    try:
        day = datetime.datetime.strptime(m.text, DATETIME_FORMAT)
    except ValueError:
        await m.answer(f'Неправильный формат даты, используйте: {DATETIME_FORMAT}')
        return
    if day < datetime.datetime.now():
        await m.answer('Укажите время в будущем')
        return
    _, auction_id = states.get(m.from_id).split('*')
    await db.Auction.update.values(start_at=day).where(db.Auction.id == int(auction_id)).gino.status()
    states.set(m.from_id, f'{Admin.AUCTION_END_AT}*{auction_id}')
    await m.answer(f'Укажите дату и время завершения аукциона в формате {DATETIME_FORMAT}:', keyboard=Keyboard())


@bot.on.private_message(StateRule(Admin.AUCTION_END_AT), staff_rule)
async def set_auction_end_at(m: Message):
    """Установка времени завершения и запуск аукциона по расписанию"""
    try:
        day = datetime.datetime.strptime(m.text, DATETIME_FORMAT)
    except ValueError:
        await m.answer(f'Неправильный формат даты, используйте: {DATETIME_FORMAT}')
        return
    _, auction_id = states.get(m.from_id).split('*')
    auction_id = int(auction_id)
    start_at = await db.select([db.Auction.start_at]).where(db.Auction.id == auction_id).gino.scalar()
    if day <= start_at:
        await m.answer('Завершение аукциона должно быть позже его начала')
        return
    await db.Auction.update.values(end_at=day).where(db.Auction.id == auction_id).gino.status()

    is_judge = await db.select([db.User.judge]).where(db.User.user_id == m.from_id).gino.scalar()
    states.set(m.from_id, Judge.MENU if is_judge else Admin.MENU)
    await m.answer(
        f'Аукцион создан и будет запущен {start_at.strftime(DATETIME_FORMAT)}, '
        f'завершение — {day.strftime(DATETIME_FORMAT)}',
        keyboard=keyboards.judge_menu if is_judge else keyboards.admin_menu,
    )
    await schedule_auction(auction_id)
