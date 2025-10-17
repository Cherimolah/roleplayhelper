"""
Модуль магазина:
- Покупка услуг
- Покупка товаров
- Покупка декора для кают
- Покупка функциональных товаров
- Покупка предметов для экспедитора
"""

from vkbottle.bot import Message, MessageEvent
from vkbottle.dispatch.rules.base import PayloadRule, PayloadMapRule
from vkbottle import GroupEventType, Keyboard, Text, KeyboardButtonColor, Callback
from sqlalchemy import func, and_, or_

import messages
from loader import bot
from service.custom_rules import StateRule, ValidateAccount
from service.states import Menu
import service.keyboards as keyboards
from service.middleware import states
from service.db_engine import db
from service.utils import soft_divide, get_current_form_id
from service.serializers import serialize_item_group, serialize_item_type, serialize_item_bonus


@bot.on.private_message(StateRule(Menu.MAIN), PayloadRule({"menu": "shop"}))
@bot.on.private_message(StateRule(Menu.SHOP_SERVICES), PayloadRule({"services": "back"}))
@bot.on.private_message(StateRule(Menu.SHOP_SERVICES), PayloadRule({"products": "back"}))
@bot.on.private_message(StateRule(Menu.SHOP_CABINS), PayloadRule({"shop_cabins": "back"}))
async def send_shop(m: Message):
    """Обработчик открытия магазина"""
    states.set(m.from_id, Menu.SHOP_MENU)
    await m.answer(messages.shop, keyboard=keyboards.shop_menu)


@bot.on.private_message(StateRule(Menu.SHOP_MENU), PayloadRule({"shop": "services"}))
async def send_services(m: Message):
    """Показ услуг магазина"""
    count_services = await db.select([db.func.count(db.Shop.id)]).where(db.Shop.service.is_(True)).gino.scalar()

    if count_services <= 0:
        await m.answer(messages.not_services)
        return

    states.set(m.from_id, Menu.SHOP_SERVICES)
    keyboard = Keyboard().add(
        Text("Назад", {"services": "back"}), KeyboardButtonColor.NEGATIVE
    )
    await m.answer(messages.services, keyboard=keyboard)

    # Получаем первую услугу
    service = await db.Shop.query.where(db.Shop.service.is_(True)).gino.first()

    keyboard = Keyboard(inline=True)
    keyboard.add(
        Callback("Купить", {"buy_service": service.id}), KeyboardButtonColor.POSITIVE
    )

    # Добавляем навигацию, если услуг больше одной
    if count_services > 1:
        keyboard.row().add(
            Callback("->", {"services_page": 2}), KeyboardButtonColor.PRIMARY
        )

    await m.answer(messages.service.format(service.name, service.description, service.price),
                   attachment=service.photo, keyboard=keyboard)


@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent, PayloadMapRule({"services_page": int}))
async def send_services_page(m: MessageEvent):
    """Переключение страницы услуг"""
    new_page = int(m.payload['services_page'])
    service = await db.Shop.query.where(db.Shop.service.is_(True)).offset(new_page - 1).limit(1).gino.first()
    count_services = await db.select([db.func.count()]).where(db.Shop.service.is_(True)).gino.scalar()

    keyboard = Keyboard(inline=True).add(
        Callback("Купить", {"buy_service": service.id}), KeyboardButtonColor.POSITIVE
    )

    # Добавляем навигацию
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
    """Покупка услуги"""
    shop_id = int(m.payload['buy_service'])
    balance, form_id = await db.select([db.Form.balance, db.Form.id]).where(db.Form.user_id == m.user_id).gino.first()
    price, name = await db.select([db.Shop.price, db.Shop.name]).where(db.Shop.id == shop_id).gino.first()

    if balance < price:
        await m.show_snackbar(messages.error_not_enogh_to_buy.format(balance))
        return

    # Списание средств и покупка услуги
    await db.Form.update.values(balance=db.Form.balance - price).where(db.Form.id == form_id).gino.status()
    await m.show_snackbar(messages.buy_service.format(name, price, balance - price))


@bot.on.private_message(StateRule(Menu.SHOP_MENU), PayloadRule({"shop": "products"}))
async def send_services(m: Message):
    """Показ товаров магазина"""
    count_services = await db.select([db.func.count(db.Shop.id)]).where(db.Shop.service.is_(False)).gino.scalar()

    if count_services <= 0:
        await m.answer(messages.not_products)
        return

    states.set(m.from_id, Menu.SHOP_SERVICES)
    keyboard = Keyboard().add(
        Text("Назад", {"products": "back"}), KeyboardButtonColor.NEGATIVE
    )
    await m.answer(messages.products, keyboard=keyboard)

    # Получаем первый товар
    service = await db.Shop.query.where(db.Shop.service.is_(False)).gino.first()

    keyboard = Keyboard(inline=True).add(
        Callback("Купить", {"buy_products": service.id}), KeyboardButtonColor.POSITIVE
    )

    # Добавляем навигацию, если товаров больше одного
    if count_services > 1:
        keyboard.row().add(
            Callback("->", {"products_page": 2}), KeyboardButtonColor.PRIMARY
        )

    await m.answer(messages.product.format(service.name, service.description, service.price),
                   attachment=service.photo, keyboard=keyboard)


@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent, PayloadMapRule({"products_page": int}))
async def send_services_page(m: MessageEvent):
    """Переключение страницы товаров"""
    new_page = int(m.payload['products_page'])
    service = await db.Shop.query.where(db.Shop.service.is_(False)).offset(new_page - 1).limit(1).gino.first()
    count_services = await db.select([db.func.count(db.Shop.id)]).where(db.Shop.service.is_(False)).gino.scalar()

    keyboard = Keyboard(inline=True).add(
        Callback("Купить", {"buy_products": service.id}), KeyboardButtonColor.POSITIVE
    )

    # Добавляем навигацию
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
    """Покупка товара"""
    shop_id = int(m.payload['buy_products'])
    balance, form_id = await db.select([db.Form.balance, db.Form.id]).where(db.Form.user_id == m.user_id).gino.first()
    price, name = await db.select([db.Shop.price, db.Shop.name]).where(db.Shop.id == shop_id).gino.first()

    if balance < price:
        await m.show_snackbar(messages.error_not_enogh_to_buy.format(balance))
        return

    # Списание средств и покупка товара
    await db.Form.update.values(balance=db.Form.balance - price).where(db.Form.id == form_id).gino.status()
    await m.show_snackbar(messages.buy_service.format(name, price, balance - price))


@bot.on.private_message(PayloadRule({"shop": "cabins"}), StateRule(Menu.SHOP_MENU))
async def cabins(m: Message):
    """Обработчик раздела кают"""
    states.set(m.from_id, Menu.SHOP_CABINS)
    await m.answer("Выберите вариант прокачки номеров", keyboard=keyboards.shop_cabins_menu)


@bot.on.private_message(PayloadRule({"shop_cabins": "decor"}), StateRule(Menu.SHOP_CABINS))
async def decor_handler(m: Message):
    """Показ декора для кают"""
    decor = await db.select([*db.Decor]).order_by(db.Decor.id.asc()).where(db.Decor.is_func.is_(False)).limit(
        1).gino.first()

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
    """Переключение страницы декора"""
    page = int(m.payload['decors_page'])
    decor = await db.select([*db.Decor]).order_by(db.Decor.id.asc()).where(db.Decor.is_func.is_(False)).offset(
        page - 1).limit(1).gino.first()
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
    """Покупка декора для каюты"""
    # Проверяем доступные слоты для декора
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

    # Списание средств и покупка декора
    await db.Form.update.values(balance=db.Form.balance - price).where(db.Form.user_id == m.user_id).gino.scalar()
    await db.UserDecor.create(user_id=m.user_id, decor_id=decor_id)
    await m.show_snackbar("✅ Декор успешно куплен!\n"
                          f"Баланс: {balance - price}")


@bot.on.private_message(PayloadRule({"shop_cabins": "functional"}), StateRule(Menu.SHOP_CABINS))
async def functional_products(m: Message):
    """Показ функциональных товаров для кают"""
    func_product = await db.select([*db.Decor]).where(db.Decor.is_func.is_(True)).order_by(db.Decor.id.asc()).limit(
        1).gino.first()

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
    """Переключение страницы функциональных товаров"""
    page = int(m.payload['functional_products_page'])
    func_product = await db.select([*db.Decor]).where(db.Decor.is_func.is_(True)).order_by(db.Decor.id.asc()).offset(
        page - 1).limit(1).gino.first()

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
    """Покупка функционального товара"""
    # Проверяем доступные слоты для функциональных товаров
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

    # Списание средств и покупка функционального товара
    await db.Form.update.values(balance=db.Form.balance - price).where(db.Form.user_id == m.user_id).gino.scalar()
    await db.UserDecor.create(user_id=m.user_id, decor_id=decor_id)
    await m.show_snackbar("✅ Функциональный товар успешно куплен!\n"
                          f"Стоимость ренты увеличена на: {soft_divide(price, 10)}\n"
                          f"Баланс: {balance - price}\n")


@bot.on.private_message(PayloadRule({"shop": 'items'}))
async def shop_items(m: Message):
    """Показ предметов для экспедитора"""
    form_id = await get_current_form_id(m.from_id)
    expeditor_id = await db.select([db.Expeditor.id]).where(db.Expeditor.form_id == form_id).gino.scalar()

    # Проверяем наличие карты экспедитора
    if not expeditor_id:
        await m.answer('У вас нет Карты экспедитора!\n'
                       'Создайте её в разделе «Анкета»')
        return

    # Проверяем подтверждение карты экспедитора
    is_confirmed = await db.select([db.Expeditor.is_confirmed]).where(db.Expeditor.id == expeditor_id).gino.scalar()
    if not is_confirmed:
        await m.answer('Ваша Карта экспедитора ещё не принята администрацией!\n'
                       'Дождитесь решения администрации')
        return

    await show_page_item(m, 1)


@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent, PayloadMapRule({'item_shop_page': int}))
async def item_shop_page(m: MessageEvent):
    """Переключение страницы предметов"""
    await show_page_item(m, m.payload['item_shop_page'])


async def show_page_item(m: Message | MessageEvent, page: int):
    """
    Показ страницы с предметами для покупки

    Args:
        m: Сообщение или событие
        page: Номер страницы
    """
    if isinstance(m, Message):
        user_id = m.from_id
    else:
        user_id = m.user_id

    # Получаем фракцию и репутацию пользователя
    fraction_id = await db.select([db.Form.fraction_id]).where(db.Form.user_id == user_id).gino.scalar()
    reputation = await db.select([db.UserToFraction.reputation]).where(
        and_(db.UserToFraction.fraction_id == fraction_id, db.UserToFraction.user_id == user_id)
    ).gino.scalar()

    # Получаем предмет для текущей страницы
    item = await db.select([*db.Item]).where(
        and_(db.Item.available_for_sale.is_(True),
             or_(db.Item.fraction_id.is_(None),
                 and_(db.Item.fraction_id == fraction_id, db.Item.reputation <= reputation)))
    ).order_by(db.Item.id.asc()).offset(page - 1).limit(1).gino.first()

    if not item:
        await m.answer('На данный момент нет доступных для вас товаров :(')
        return

    # Получаем общее количество доступных предметов
    count = await db.select([func.count(db.Item.id)]).where(
        and_(db.Item.available_for_sale.is_(True),
             or_(db.Item.fraction_id.is_(None),
                 and_(db.Item.fraction_id == fraction_id, db.Item.reputation <= reputation)))
    ).gino.scalar()

    # Создаем клавиатуру с навигацией и кнопкой покупки
    keyboard = Keyboard(inline=True)

    if page > 1:
        keyboard.add(Callback('<-', {'item_shop_page': page - 1}), KeyboardButtonColor.PRIMARY)

    if page < count:
        keyboard.add(Callback('->', {'item_shop_page': page + 1}), KeyboardButtonColor.PRIMARY)

    if keyboard.buttons and len(keyboard.buttons[-1]) > 0:
        keyboard.row()

    keyboard.add(
        Callback('Купить', {'buy_item': item.id}), KeyboardButtonColor.POSITIVE
    )

    # Формируем описание предмета
    reply = (f'Название: {item.name}\n'
             f'Описание: {item.description}\n'
             f'Группа: {await serialize_item_group(item.group_id)}\n'
             f'Тип: {await serialize_item_type(item.type_id)}\n'
             f'Количество использований: {item.count_use} раз\n'
             f'Цена: {item.price}\n'
             f'Эффект: {await serialize_item_bonus(item.bonus)}\n')

    # Отправляем сообщение
    if isinstance(m, Message):
        await m.answer(message=reply, keyboard=keyboard, attachment=item.photo)
    else:
        await m.edit_message(message=reply, keyboard=keyboard.get_json(), attachment=item.photo)


@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent, PayloadMapRule({'buy_item': int}))
async def buy_item(m: MessageEvent):
    """Покупка предмета для экспедитора"""
    item_id = m.payload['buy_item']

    # Проверяем существование предмета
    exist = await db.select([db.Item.id]).where(db.Item.id == item_id).gino.scalar()
    if not exist:
        await m.show_snackbar('Предмет удален из базы')
        return

    # Получаем информацию о предмете
    price, fraction_id, reputation = await db.select([db.Item.price, db.Item.fraction_id, db.Item.reputation]).where(
        db.Item.id == item_id).gino.first()
    balance = await db.select([db.Form.balance]).where(db.Form.user_id == m.user_id).gino.scalar()

    # Проверяем баланс
    if balance < price:
        await m.show_snackbar(f'❌ Недостаточный баланс! Не хватает {price - balance}')
        return

    # Проверяем требования фракции и репутации
    if fraction_id:
        user_fraction_id = await db.select([db.Form.fraction_id]).where(db.Form.user_id == m.user_id).gino.scalar()
        fracton_name = await db.select([db.Fraction.name]).where(db.Fraction.id == fraction_id).gino.scalar()

        if user_fraction_id != fraction_id:
            await m.show_snackbar(f'❌ Вы не состоите в нужной фракции ({fracton_name})')
            return

        user_reputation = await db.select([db.UserToFraction.reputation]).where(
            and_(db.UserToFraction.user_id == m.user_id, db.UserToFraction.fraction_id == fraction_id)
        ).gino.scalar()

        if user_reputation is None:
            await m.show_snackbar(f'❌ У вас отсутствует репутация во фракции ({fracton_name})')
            return

        if user_reputation < reputation:
            await m.show_snackbar(f'❌ Недостаточная репутация во фракции {fracton_name}')
            return

    # Списание средств и добавление предмета
    form_id = await get_current_form_id(m.user_id)
    await db.Form.update.values(balance=db.Form.balance - price).where(db.Form.id == form_id).gino.status()

    expeditor_id = await db.select([db.Expeditor.id]).where(db.Expeditor.form_id == form_id).gino.scalar()
    await db.ExpeditorToItems.create(expeditor_id=expeditor_id, item_id=item_id)

    await m.show_snackbar('✅ Предмет успешно приобретен!\n'
                          f'Баланс: {balance - price}')