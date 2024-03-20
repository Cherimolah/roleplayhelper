import json

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
from service.utils import reload_image


@bot.on.private_message(StateRule(Admin.SELECT_ACTION), PayloadRule({"products": "add"}), AdminRule())
async def send_name_product(m: Message):
    product = await db.Shop.create()
    states.set(m.from_id, f"{Admin.NAME_PRODUCT}*{product.id}")
    await bot.write_msg(m.peer_id, messages.name_product, keyboard=Keyboard())


@bot.on.private_message(StateRule(Admin.NAME_PRODUCT, True), AdminRule())
async def set_name_product(m: Message):
    product_id = int(states.get(m.from_id).split("*")[1])
    await db.Shop.update.values(name=m.text).where(db.Shop.id == product_id).gino.status()
    states.set(m.from_id, f"{Admin.PRICE_PRODUCT}*{product_id}")
    await bot.write_msg(m.peer_id, messages.price_product)


@bot.on.private_message(StateRule(Admin.PRICE_PRODUCT, True), NumericRule(), AdminRule())
async def set_price_product(m: Message):
    product_id = int(states.get(m.from_id).split("*")[1])
    await db.Shop.update.values(price=int(m.text)).where(db.Shop.id == product_id).gino.status()
    states.set(m.from_id, f"{Admin.DESCRIPTION_PRODUCT}*{product_id}")
    await bot.write_msg(m.peer_id, messages.description_product)


@bot.on.private_message(StateRule(Admin.DESCRIPTION_PRODUCT, True), AdminRule())
async def set_description(m: Message):
    product_id = int(states.get(m.from_id).split("*")[1])
    await db.Shop.update.values(description=m.text).where(db.Shop.id == product_id).gino.status()
    states.set(m.from_id, f"{Admin.SERVICE_PRODUCT}*{product_id}")
    keyboard = Keyboard().add(
        Text("Услуга", {"service": True}), KeyboardButtonColor.PRIMARY
    ).row().add(
        Text("Товар", {"service": False}), KeyboardButtonColor.PRIMARY
    )
    await bot.write_msg(m.peer_id, messages.service_product, keyboard=keyboard)


@bot.on.private_message(StateRule(Admin.SERVICE_PRODUCT, True), PayloadMapRule({"service": bool}), AdminRule())
async def set_service(m: Message):
    product_id = int(states.get(m.from_id).split("*")[1])
    await db.Shop.update.values(service=json.loads(m.payload)['service']).where(db.Shop.id == product_id).gino.status()
    states.set(m.from_id, f"{Admin.ART_PRODUCT}*{product_id}")
    await bot.write_msg(m.peer_id, "Теперь пришли арт для товара/услуги", keyboard=Keyboard())


@bot.on.private_message(StateRule(Admin.ART_PRODUCT, True), AdminRule())
async def set_art_product(m: Message):
    message = await m.get_full_message()
    if not message.attachments or message.attachments[0].type != attach_type.PHOTO:
        await bot.write_msg(m.peer_id, "Нужно прислать одно фото")
        return
    product_id = int(states.get(m.from_id).split("*")[1])
    name = await db.select([db.Shop.name]).where(db.Shop.id == product_id).gino.scalar()
    photo = await reload_image(message.attachments[0], f"{name}.jpg")
    await db.Shop.update.values(photo=photo).where(db.Shop.id == product_id).gino.status()
    states.set(m.from_id, Admin.SELECT_ACTION)
    await bot.write_msg(m.peer_id, messages.product_added, keyboard=keyboards.gen_type_change_content("products"))


@bot.on.private_message(StateRule(Admin.SELECT_ACTION), PayloadRule({"products": "delete"}), AdminRule())
async def select_number_product_to_delete(m: Message):
    reply = messages.products_list
    products = await db.select([db.Shop.name]).gino.all()
    for i, product in enumerate(products):
        reply = f"{reply}{i+1}. {product.name}\n"
    states.set(m.from_id, Admin.ID_PRODUCT)
    await bot.write_msg(m.peer_id, reply, keyboard=Keyboard())


@bot.on.private_message(StateRule(Admin.ID_PRODUCT), NumericRule(), AdminRule())
async def delete_poduct(m: Message, value: int):
    product_id = await db.select([db.Shop.id]).offset(value-1).limit(1).gino.scalar()
    if not product_id:
        await bot.write_msg(m.from_id, "Указан неверный номер товара")
        return
    await db.Shop.delete.where(db.Shop.id == product_id).gino.status()
    states.set(m.from_id, Admin.SELECT_ACTION)
    await bot.write_msg(m.peer_id, messages.product_deleted, keyboard=keyboards.gen_type_change_content("products"))
