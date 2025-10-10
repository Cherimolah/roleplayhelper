from vkbottle.bot import Message
from vkbottle.dispatch.rules.base import PayloadRule, PayloadMapRule
from vkbottle import Keyboard, Text, KeyboardButtonColor
from vkbottle_types.objects import MessagesMessageAttachmentType as attach_type

import messages
import service.keyboards as keyboards
from loader import bot
from service.custom_rules import AdminRule, StateRule, NumericRule
from service.middleware import states
from service.states import Admin
from service.db_engine import db
from service.utils import reload_image, send_content_page, allow_edit_content


@bot.on.private_message(StateRule(f"{Admin.SELECT_ACTION}_Shop"), PayloadRule({"Shop": "add"}), AdminRule())
async def send_name_product(m: Message):
    """Начало создания товара/услуги"""
    product = await db.Shop.create()
    states.set(m.from_id, f"{Admin.NAME_PRODUCT}*{product.id}")
    await m.answer(messages.name_product, keyboard=Keyboard())


@bot.on.private_message(StateRule(Admin.NAME_PRODUCT), AdminRule())
@allow_edit_content("Shop", state=Admin.PRICE_PRODUCT, text=messages.price_product)
async def set_name_product(m: Message, item_id: int, editing_content: bool):
    """Установка названия товара/услуги"""
    await db.Shop.update.values(name=m.text).where(db.Shop.id == item_id).gino.status()


@bot.on.private_message(StateRule(Admin.PRICE_PRODUCT), NumericRule(), AdminRule())
@allow_edit_content("Shop", state=Admin.DESCRIPTION_PRODUCT, text=messages.description_product)
async def set_price_product(m: Message, value: int, item_id: int, editing_content: bool):
    """Установка цены товара/услуги"""
    await db.Shop.update.values(price=value).where(db.Shop.id == item_id).gino.status()


@bot.on.private_message(StateRule(Admin.DESCRIPTION_PRODUCT), AdminRule())
@allow_edit_content("Shop", state=Admin.SERVICE_PRODUCT, text=messages.service_product, keyboard=Keyboard().add(
        Text("Услуга", {"service": True}), KeyboardButtonColor.PRIMARY
    ).row().add(
        Text("Товар", {"service": False}), KeyboardButtonColor.PRIMARY
    ))
async def set_description(m: Message, item_id: int, editing_content: bool):
    """Установка описания товара/услуги"""
    await db.Shop.update.values(description=m.text).where(db.Shop.id == item_id).gino.status()


@bot.on.private_message(StateRule(Admin.SERVICE_PRODUCT), PayloadMapRule({"service": bool}), AdminRule())
@allow_edit_content("Shop", state=Admin.ART_PRODUCT, text="Теперь пришли арт для товара/услуги",
                    keyboard=Keyboard())
async def set_service(m: Message, item_id: int, editing_content: bool):
    """Установка типа (товар/услуга)"""
    await db.Shop.update.values(service=m.payload['service']).where(db.Shop.id == item_id).gino.status()


@bot.on.private_message(StateRule(Admin.ART_PRODUCT), AdminRule())
@allow_edit_content("Shop", state=f"{Admin.SELECT_ACTION}_Shop", text=messages.product_added,
                    keyboard=keyboards.gen_type_change_content("Shop"), end=True)
async def set_art_product(m: Message, item_id: int, editing_content: bool):
    """Установка изображения для товара/услуги"""
    message = await m.get_full_message()
    if not message.attachments or message.attachments[0].type != attach_type.PHOTO:
        await m.answer("Нужно прислать одно фото")
        return
    name = await db.select([db.Shop.name]).where(db.Shop.id == item_id).gino.scalar()
    photo = await reload_image(message.attachments[0], f"data/shop/{name}.jpg")
    await db.Shop.update.values(photo=photo).where(db.Shop.id == item_id).gino.status()


@bot.on.private_message(StateRule(f"{Admin.SELECT_ACTION}_Shop"), PayloadRule({"Shop": "delete"}), AdminRule())
async def select_number_product_to_delete(m: Message):
    """Выбор товара/услуги для удаления"""
    reply = messages.products_list
    products = await db.select([db.Shop.name]).order_by(db.Shop.id.asc()).gino.all()
    if not products:
        return "Товары ещё не созданы"
    for i, product in enumerate(products):
        reply = f"{reply}{i+1}. {product.name}\n"
    states.set(m.from_id, Admin.ID_PRODUCT)
    await m.answer(reply, keyboard=Keyboard())


@bot.on.private_message(StateRule(Admin.ID_PRODUCT), NumericRule(), AdminRule())
async def delete_poduct(m: Message, value: int):
    """Удаление выбранного товара/услуги"""
    product_id = await db.select([db.Shop.id]).order_by(db.Shop.id.asc()).offset(value-1).limit(1).gino.scalar()
    if not product_id:
        await m.answer("Указан неверный номер товара")
        return
    await db.Shop.delete.where(db.Shop.id == product_id).gino.status()
    states.set(m.from_id, f"{Admin.SELECT_ACTION}_Shop")
    await m.answer(messages.product_deleted, keyboard=keyboards.gen_type_change_content("Shop"))
    await send_content_page(m, "Shop", 1)
