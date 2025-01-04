from vkbottle.bot import Message

from loader import bot
from service.custom_rules import ChatAction, AdminRule
from service.db_engine import db
from handlers.public_menu.bank import send_create_transactions, create_donate, ask_salary
from handlers.public_menu.daylics import send_ready_daylic
from handlers.public_menu.quests import send_ready_quest


@bot.on.chat_message(AdminRule(), text='/peer_id')
async def get_peer_id(m: Message):
    await m.answer(str(m.peer_id))


@bot.on.chat_message(ChatAction('заказать коктейль'), blocking=False)
async def order_cocktail(m: Message):
    price = await db.select([db.Shop.price]).where(db.Shop.id == 1).gino.scalar()
    balance = await db.select([db.Form.balance]).where(db.Form.user_id == m.from_id).gino.scalar()
    if balance >= price:
        await db.Form.update.values(balance=db.Form.balance - price).where(db.Form.user_id == m.from_id).gino.status()
        await m.reply('Коктейль успешно заказан')
        return
    await m.reply('Недостаточно средств для оплаты коктейля')


@bot.on.chat_message(ChatAction('заказать премиальный коктейль'), blocking=False)
async def order_premium_cocktail(m: Message):
    price = await db.select([db.Shop.price]).where(db.Shop.id == 2).gino.scalar()
    balance = await db.select([db.Form.balance]).where(db.Form.user_id == m.from_id).gino.scalar()
    if balance >= price:
        await db.Form.update.values(balance=db.Form.balance - price).where(db.Form.user_id == m.from_id).gino.status()
        await m.reply('Премиальный коктейль успешно заказан')
        return
    await m.reply('Недостаточно средств для оплаты премиального коктейля')


@bot.on.chat_message(ChatAction('заказать бутылку дорогого алкоголя'), blocking=False)
async def order_expensive_alcohol(m: Message):
    price = await db.select([db.Shop.price]).where(db.Shop.id == 3).gino.scalar()
    balance = await db.select([db.Form.balance]).where(db.Form.user_id == m.from_id).gino.scalar()
    if balance >= price:
        await db.Form.update.values(balance=db.Form.balance - price).where(db.Form.user_id == m.from_id).gino.status()
        await m.reply('Бутылка дорогого алкоголя успешно оплачена')
        return
    await m.reply('Недостаточно средств для оплаты дорогого алкоголя')


@bot.on.chat_message(ChatAction('запросить зарплату'), blocking=False)
async def ask_salary_command(m: Message):
    return await ask_salary(m)


@bot.on.chat_message(ChatAction('сдать отчёт'), blocking=False)
@bot.on.chat_message(ChatAction('сдать отчет'), blocking=False)
async def ask_salary_command(m: Message):
    daylic = await db.select([db.Form.activated_daylic]).where(db.Form.user_id == m.from_id).gino.scalar()
    if daylic:
        m.payload = {"daylic_ready": daylic}
        await send_ready_daylic(m)
        return
    quest = await db.select([db.Form.active_quest]).where(db.Form.user_id == m.from_id).gino.scalar()
    if quest:
        return await send_ready_quest(m)
    return await m.reply('У вас нет активного дейлика или квеста')


@bot.on.chat_message(ChatAction('совершить сделку'))
async def create_transaction(m: Message):
    m.peer_id = m.from_id
    await m.reply('Перейдите в ЛС для завершения совершения сделки')
    return await send_create_transactions(m)


@bot.on.chat_message(ChatAction('пожертвовать в храм'))
async def create_donate_command(m: Message):
    m.peer_id = m.from_id
    await m.reply('Перейдите в ЛС для завершения пожертвования')
    return await create_donate(m)
