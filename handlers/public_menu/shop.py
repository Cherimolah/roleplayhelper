from vkbottle.bot import Message, MessageEvent
from vkbottle.dispatch.rules.base import PayloadRule, PayloadMapRule
from vkbottle import GroupEventType, Keyboard, Text, KeyboardButtonColor, Callback
from sqlalchemy import func, and_

import messages
from loader import bot
from service.custom_rules import StateRule, ValidateAccount
from service.states import Menu
import service.keyboards as keyboards
from service.middleware import states
from service.db_engine import db
from service.utils import soft_divide


@bot.on.private_message(StateRule(Menu.MAIN), PayloadRule({"menu": "shop"}))
@bot.on.private_message(StateRule(Menu.SHOP_SERVICES), PayloadRule({"services": "back"}))
@bot.on.private_message(StateRule(Menu.SHOP_SERVICES), PayloadRule({"products": "back"}))
@bot.on.private_message(StateRule(Menu.SHOP_CABINS), PayloadRule({"shop_cabins": "back"}))
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
    await m.edit_message(messages.product.format(service.name, service.description, service.price),
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


@bot.on.private_message(PayloadRule({"shop": "cabins"}), StateRule(Menu.SHOP_MENU))
async def cabins(m: Message):
    states.set(m.from_id, Menu.SHOP_CABINS)
    await m.answer("Выберите вариант прокачки номеров", keyboard=keyboards.shop_cabins_menu)


@bot.on.private_message(PayloadRule({"shop_cabins": "decor"}), StateRule(Menu.SHOP_CABINS))
async def decor_handler(m: Message):
    decor = await db.select([*db.Decor]).order_by(db.Decor.id.asc()).where(db.Decor.is_func.is_(False)).limit(1).gino.first()
    if not decor:
        return "На данный момент не создано декора"
    kb = Keyboard(inline=True)
    count = await db.select([func.count(db.Decor.id)]).where(db.Decor.is_func.is_(False)).gino.scalar()
    if count > 1:
        kb.add(
            Callback("->", {"decors_page": 2}), KeyboardButtonColor.SECONDARY
        ).row()
    kb.add(
        Callback("Купить", {"buy_decor": decor.id}), KeyboardButtonColor.POSITIVE
    )
    await m.answer(f"Название: {decor.name}\n"
                   f"Цена: {decor.price}\n"
                   f"Описание: {decor.description}\n", keyboard=kb, attachment=decor.photo)


@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent, PayloadMapRule({"decors_page": int}))
async def decor_page(m: MessageEvent):
    page = int(m.payload['decors_page'])
    decor = await db.select([*db.Decor]).order_by(db.Decor.id.asc()).where(db.Decor.is_func.is_(False)).offset(page - 1).limit(1).gino.first()
    count = await db.select([func.count(db.Decor.id)]).where(db.Decor.is_func.is_(False)).gino.scalar()
    kb = Keyboard(inline=True)
    if page > 1:
        kb.add(
            Callback("<-", {"decors_page": page - 1}), KeyboardButtonColor.SECONDARY
        )
    if count > page:
        kb.add(
            Callback("->", {"decors_page": page + 1}), KeyboardButtonColor.SECONDARY
        )
    kb.row().add(
        Callback("Купить", {"buy_decor": decor.id}), KeyboardButtonColor.POSITIVE
    )
    await m.edit_message(f"Название: {decor.name}\n"
                         f"Цена: {decor.price}\n"
                         f"Описание: {decor.description}", keyboard=kb.get_json(), attachment=decor.photo)


@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent, PayloadMapRule({"buy_decor": int}))
async def buy_decor_handler(m: MessageEvent):
    decor_slots = await db.select([db.Cabins.decor_slots]).select_from(
        db.Form.join(db.Cabins, db.Form.cabin_type == db.Cabins.id)
    ).where(db.Form.user_id == m.user_id).gino.scalar()
    count_decor = await db.select([func.count(db.UserDecor.id)]).select_from(
        db.Decor.join(db.UserDecor, db.UserDecor.decor_id == db.Decor.id)
    ).where(and_(db.Decor.is_func.is_(False), db.UserDecor.user_id == m.user_id)).gino.scalar()
    if count_decor >= decor_slots:
        await m.show_snackbar("❌ Недостаточно слотов для покупки декора!")
        return
    decor_id = int(m.payload['buy_decor'])
    price = await db.select([db.Decor.price]).where(db.Decor.id == decor_id).gino.scalar()
    balance = await db.select([db.Form.balance]).where(db.Form.user_id == m.user_id).gino.scalar()
    if balance < price:
        await m.show_snackbar(f"❌ Недостаточно балнса!\nУ вас на счету: {balance}")
        return
    await db.Form.update.values(balance=db.Form.balance - price).where(db.Form.user_id == m.user_id).gino.scalar()
    await db.UserDecor.create(user_id=m.user_id, decor_id=decor_id)
    await m.show_snackbar("✅ Декор успешно куплен!\n"
                          f"Баланс: {balance - price}")


@bot.on.private_message(PayloadRule({"shop_cabins": "functional"}), StateRule(Menu.SHOP_CABINS))
async def functional_products(m: Message):
    func_product = await db.select([*db.Decor]).where(db.Decor.is_func.is_(True)).order_by(db.Decor.id.asc()).limit(1).gino.first()
    if not func_product:
        return "На данный момент нет функциональных товаров"
    count = await db.select([func.count(db.Decor.id)]).where(db.Decor.is_func.is_(True)).gino.scalar()
    kb = Keyboard(inline=True)
    if count > 1:
        kb.add(
            Callback("->", {"functional_products_page": 2}), KeyboardButtonColor.SECONDARY
        ).row()
    kb.add(
        Callback("Купить", {"functional_product_buy": func_product.id}), KeyboardButtonColor.POSITIVE
    )
    await m.answer(f"Название: {func_product.name}\n"
                   f"Цена: {func_product.price}\n"
                   f"Описание: {func_product.description}\n"
                   f"Стоимость ренты увеличится на {int(func_product.price // 10)}",
                   keyboard=kb, attachment=func_product.photo)


@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent, PayloadMapRule({"functional_products_page": int}))
async def func_products_page(m: MessageEvent):
    page = int(m.payload['functional_products_page'])
    func_product = await db.select([*db.Decor]).where(db.Decor.is_func.is_(True)).order_by(db.Decor.id.asc()).offset(page - 1).limit(1).gino.first()
    kb = Keyboard(inline=True)
    if page > 1:
        kb.add(
            Callback("<-", {"functional_products_page": page - 1}), KeyboardButtonColor.SECONDARY
        )
    count = await db.select([func.count(db.Decor.id)]).where(db.Decor.is_func.is_(True)).gino.scalar()
    if count > page:
        kb.add(
            Callback("->", {"functional_products_page": page + 1}), KeyboardButtonColor.SECONDARY
        )
    kb.row().add(
        Callback("Купить", {"functional_product_buy": func_product.id}), KeyboardButtonColor.POSITIVE
    )
    await m.edit_message(f"Название: {func_product.name}\n"
                         f"Цена: {func_product.price}\n"
                         f"Описание: {func_product.description}\n"
                         f"Стоимость ренты увеличится на: {soft_divide(func_product.price, 10)}",
                         keyboard=kb.get_json(), attachment=func_product.photo)


@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent, PayloadMapRule({"functional_product_buy": int}))
async def buy_func_product(m: MessageEvent):
    func_slots = await db.select([db.Cabins.functional_slots]).select_from(
        db.Form.join(db.Cabins, db.Form.cabin_type == db.Cabins.id)
    ).where(db.Form.user_id == m.user_id).gino.scalar()
    count_func_prods = await db.select([func.count(db.UserDecor.id)]).select_from(
        db.Decor.join(db.UserDecor, db.UserDecor.decor_id == db.Decor.id)
    ).where(and_(db.Decor.is_func.is_(True), db.UserDecor.user_id == m.user_id)).gino.scalar()
    if count_func_prods >= func_slots:
        await m.show_snackbar("❌ Недостаточно слотов для покупки декора!")
        return
    decor_id = int(m.payload['functional_product_buy'])
    price = await db.select([db.Decor.price]).where(db.Decor.id == decor_id).gino.scalar()
    balance = await db.select([db.Form.balance]).where(db.Form.user_id == m.user_id).gino.scalar()
    if balance < price:
        await m.show_snackbar(f"❌ Недостаточно балнса!\nУ вас на счету: {balance}")
        return
    await db.Form.update.values(balance=db.Form.balance - price).where(db.Form.user_id == m.user_id).gino.scalar()
    await db.UserDecor.create(user_id=m.user_id, decor_id=decor_id)
    await m.show_snackbar("✅ Функциональный товар успешно куплен!\n"
                          f"Стоимость ренты увеличена на: {soft_divide(price, 10)}\n"
                          f"Баланс: {balance - price}\n")


@bot.on.private_message(PayloadRule({"shop": 'items'}))
async def shop_items(m: Message):
    pass
