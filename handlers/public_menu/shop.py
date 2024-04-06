from vkbottle.bot import Message, MessageEvent
from vkbottle.dispatch.rules.base import PayloadRule, PayloadMapRule
from vkbottle import GroupEventType, Keyboard, Text, KeyboardButtonColor, Callback
from sqlalchemy import and_


import messages
from loader import bot
from service.custom_rules import StateRule, ValidateAccount
from service.states import Menu
import service.keyboards as keyboards
from service.middleware import states
from service.db_engine import db


@bot.on.private_message(StateRule(Menu.MAIN), PayloadRule({"menu": "shop"}))
@bot.on.private_message(StateRule(Menu.SHOP_SERVICES), PayloadRule({"services": "back"}))
@bot.on.private_message(StateRule(Menu.SHOP_SERVICES), PayloadRule({"products": "back"}))
async def send_shop(m: Message):
    states.set(m.from_id, Menu.SHOP_MENU)
    await m.answer(messages.shop, keyboard=keyboards.shop_menu)


@bot.on.private_message(StateRule(Menu.SHOP_MENU), PayloadRule({"shop": "services"}))
async def send_services(m: Message):
    count_services = await db.select([db.func.count(db.Shop.id)]).where(db.Shop.service.is_(True)).gino.scalar()
    if count_services <= 0:
        await m.answer(messages.not_services)
        return
    states.set(m.from_id, Menu.SHOP_SERVICES)
    keyboard = Keyboard().add(
        Text("Назад", {"services": "back"}), KeyboardButtonColor.NEGATIVE
    )
    await m.answer(messages.services, keyboard=keyboard)
    service = await db.Shop.query.where(db.Shop.service.is_(True)).gino.first()
    keyboard = Keyboard(inline=True)
    keyboard.add(
        Callback("Купить", {"buy_service": service.id}), KeyboardButtonColor.POSITIVE
    )
    if count_services > 1:
        keyboard.row().add(
            Callback("->", {"services_page": 2}), KeyboardButtonColor.PRIMARY
        )
    await m.answer(messages.service.format(service.name, service.description, service.price),
                        attachment=service.photo, keyboard=keyboard)


@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent, PayloadMapRule({"services_page": int}))
async def send_services_page(m: MessageEvent):
    new_page = int(m.payload['services_page'])
    service = await db.Shop.query.where(db.Shop.service.is_(True)).offset(new_page - 1).limit(1).gino.first()
    count_services = await db.select([db.func.count()]).where(db.Shop.service.is_(True)).gino.scalar()
    keyboard = Keyboard(inline=True).add(
        Callback("Купить", {"buy_service": service.id}), KeyboardButtonColor.POSITIVE
    )
    if new_page > 1 or new_page < count_services:
        keyboard.row()
    if new_page > 1:
        keyboard.add(
            Callback("<-", {"services_page": new_page - 1}), KeyboardButtonColor.PRIMARY
        )
    if new_page < count_services:
        keyboard.add(
            Callback("->", {"services_page": new_page + 1}), KeyboardButtonColor.PRIMARY
        )
    await m.edit_message(messages.service.format(service.name, service.description, service.price),
                         keyboard=keyboard.get_json(), attachment=service.photo)


@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent, PayloadMapRule({"buy_service": int}), ValidateAccount())
async def buy_service(m: MessageEvent):
    shop_id = int(m.payload['buy_service'])
    balance, form_id = await db.select([db.Form.balance, db.Form.id]).where(db.Form.user_id == m.user_id).gino.first()
    price, name = await db.select([db.Shop.price, db.Shop.name]).where(db.Shop.id == shop_id).gino.first()
    if balance < price:
        await m.show_snackbar(messages.error_not_enogh_to_buy.format(balance))
        return
    await db.Form.update.values(balance=db.Form.balance - price).where(db.Form.id == form_id).gino.status()
    await m.show_snackbar(messages.buy_service.format(name, price, balance - price))


@bot.on.private_message(StateRule(Menu.SHOP_MENU), PayloadRule({"shop": "products"}))
async def send_services(m: Message):
    count_services = await db.select([db.func.count(db.Shop.id)]).where(db.Shop.service.is_(False)).gino.scalar()
    if count_services <= 0:
        await m.answer(messages.not_products)
        return
    states.set(m.from_id, Menu.SHOP_SERVICES)
    keyboard = Keyboard().add(
        Text("Назад", {"products": "back"}), KeyboardButtonColor.NEGATIVE
    )
    await m.answer(messages.products, keyboard=keyboard)
    service = await db.Shop.query.where(db.Shop.service.is_(False)).gino.first()
    keyboard = Keyboard(inline=True).add(
        Callback("Купить", {"buy_products": service.id}), KeyboardButtonColor.POSITIVE
    )
    if count_services > 1:
        keyboard.row().add(
            Callback("->", {"products_page": 2}), KeyboardButtonColor.PRIMARY
        )
    await m.answer(messages.product.format(service.name, service.description, service.price),
                        attachment=service.photo, keyboard=keyboard)


@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent, PayloadMapRule({"products_page": int}))
async def send_services_page(m: MessageEvent):
    new_page = int(m.payload['products_page'])
    service = await db.Shop.query.where(db.Shop.service.is_(False)).offset(new_page - 1).limit(1).gino.first()
    count_services = await db.select([db.func.count(db.Shop.id)]).where(db.Shop.service.is_(False)).gino.scalar()
    keyboard = Keyboard(inline=True).add(
        Callback("Купить", {"buy_products": service.id}), KeyboardButtonColor.POSITIVE
    )
    if new_page > 1 or new_page < count_services:
        keyboard.row()
    if new_page > 1:
        keyboard.add(
            Callback("<-", {"products_page": new_page - 1}), KeyboardButtonColor.PRIMARY
        )
    if new_page < count_services:
        keyboard.add(
            Callback("->", {"products_page": new_page + 1}), KeyboardButtonColor.PRIMARY
        )
    await m.edit_message(messages.service.format(service.name, service.description, service.price),
                         keyboard=keyboard.get_json(), attachment=service.photo)


@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent, PayloadMapRule({"buy_products": int}), ValidateAccount())
async def buy_service(m: MessageEvent):
    shop_id = int(m.payload['buy_products'])
    balance, form_id = await db.select([db.Form.balance, db.Form.id]).where(db.Form.user_id == m.user_id).gino.first()
    price, name = await db.select([db.Shop.price, db.Shop.name]).where(db.Shop.id == shop_id).gino.first()
    if balance < price:
        await m.show_snackbar(messages.error_not_enogh_to_buy.format(balance))
        return
    await db.Form.update.values(balance=db.Form.balance - price).where(db.Form.id == form_id).gino.status()
    await m.show_snackbar(messages.buy_service.format(name, price, balance - price))
