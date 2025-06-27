from vkbottle.bot import Message
from vkbottle.dispatch.rules.base import PayloadRule, PayloadMapRule
from vkbottle import Keyboard
from vkbottle_types.objects import MessagesMessageAttachmentType as attach_type

from loader import bot
from service.custom_rules import StateRule, AdminRule, NumericRule
from service.states import Admin
from service.db_engine import db
from service.middleware import states
from service.utils import allow_edit_content, reload_image, send_content_page
from service.keyboards import decor_vars, gen_type_change_content


@bot.on.private_message(PayloadRule({"Decor": "add"}), StateRule(f"{Admin.SELECT_ACTION}_Decor"), AdminRule())
async def add_decor(m: Message):
    decor = await db.Decor.create()
    states.set(m.from_id, f"{Admin.NAME_DECOR}*{decor.id}")
    await m.answer("Введите название декора:", keyboard=Keyboard())


@bot.on.private_message(StateRule(Admin.NAME_DECOR), AdminRule())
@allow_edit_content("Decor", state=Admin.PRICE_DECOR, text="Название успешно установлено, теперь укажите цену")
async def name_decor(m: Message, item_id: int, editing_content: bool):
    await db.Decor.update.values(name=m.text).where(db.Decor.id == item_id).gino.status()


@bot.on.private_message(StateRule(Admin.PRICE_DECOR), AdminRule(), NumericRule())
@allow_edit_content("Decor", state=Admin.DESCRIPTION_DECOR, text="Цена успешно установлена. Напишите описание товара")
async def price_decor(m: Message, value: int, item_id: int, editing_content: bool):
    await db.Decor.update.values(price=value).where(db.Decor.id == item_id).gino.status()


@bot.on.private_message(StateRule(Admin.DESCRIPTION_DECOR), AdminRule())
@allow_edit_content("Decor", state=Admin.IS_FUNC_DECOR, text="Описание успешно установлено. Выберите тип товара:",
                    keyboard=decor_vars)
async def description_decor(m: Message, item_id: int, editing_content: bool):
    await db.Decor.update.values(description=m.text).where(db.Decor.id == item_id).gino.status()


@bot.on.private_message(PayloadMapRule({"is_functional_product": bool}), StateRule(Admin.IS_FUNC_DECOR), AdminRule())
@allow_edit_content("Decor", state=Admin.PHOTO_DECOR,
                    text="Тип товара установлен. Теперь пришлите фотографию товара", keyboard=Keyboard())
async def is_functional_decor(m: Message, item_id: int, editing_content: bool):
    is_func = m.payload["is_functional_product"]
    await db.Decor.update.values(is_func=is_func).where(db.Decor.id == item_id).gino.status()


@bot.on.private_message(StateRule(Admin.PHOTO_DECOR), AdminRule())
@allow_edit_content("Decor", text="Товар успешно добавлен",
                    keyboard=gen_type_change_content("Decor"), end=True)
async def photo_decor(m: Message, item_id: int, editing_content: bool):
    message = await m.get_full_message()
    if not message.attachments or message.attachments[0].type != attach_type.PHOTO:
        await m.answer("Нужно прислать одно фото")
        return
    name = await db.select([db.Decor.name]).where(db.Decor.id == item_id).gino.scalar()
    photo = await reload_image(message.attachments[0], f"data/decors/{name}.jpg")
    await db.Decor.update.values(photo=photo).where(db.Decor.id == item_id).gino.status()


@bot.on.private_message(StateRule(f"{Admin.SELECT_ACTION}_Decor"), PayloadRule({"Decor": "delete"}), AdminRule())
async def select_number_product_to_delete(m: Message):
    reply = "Выберите товар:\n\n"
    decors = await db.select([db.Decor.name]).order_by(db.Decor.id.asc()).gino.all()
    if not decors:
        return "Товары ещё не созданы"
    for i, product in enumerate(decors):
        reply = f"{reply}{i+1}. {product.name}\n"
    states.set(m.from_id, Admin.ID_DECOR)
    await m.answer(reply, keyboard=Keyboard())


@bot.on.private_message(StateRule(Admin.ID_DECOR), NumericRule(), AdminRule())
async def delete_poduct(m: Message, value: int):
    decor_id = await db.select([db.Decor.id]).order_by(db.Decor.id.asc()).offset(value-1).limit(1).gino.scalar()
    if not decor_id:
        await m.answer("Указан неверный номер товара")
        return
    await db.Decor.delete.where(db.Decor.id == decor_id).gino.status()
    states.set(m.from_id, f"{Admin.SELECT_ACTION}_Decor")
    await m.answer("Товар успешно удалён", keyboard=gen_type_change_content("Decor"))
    await send_content_page(m, "Decor", 1)

