from typing import Tuple

from vkbottle.bot import Message
from vkbottle.dispatch.rules.base import PayloadRule, AttachmentTypeRule
from vkbottle import Keyboard

from loader import bot
from service.custom_rules import AdminRule, StateRule, UserSpecified, NumericRule
from service.states import Admin
from service.db_engine import db
from service.middleware import states
from service.utils import allow_edit_content, reload_image, send_content_page
import messages
from service.keyboards import gen_type_change_content


@bot.on.private_message(PayloadRule({"Fraction": "add"}), StateRule(f"{Admin.SELECT_ACTION}_Fraction"), AdminRule())
async def add_fraction(m: Message):
    fraction = await db.Fraction.create()
    states.set(m.from_id, f"{Admin.NAME_FRACTION}*{fraction.id}")
    await m.answer("Введите название фракции:", keyboard=Keyboard())


@bot.on.private_message(StateRule(Admin.NAME_FRACTION), AdminRule())
@allow_edit_content("Fraction", state=Admin.DESCRIPTION_FRACTION,
                    text="Название установлено. Теперь напишите описание фракции")
async def set_name_fraction(m: Message):
    fraction_id = int(states.get(m.from_id).split("*")[1])
    await db.Fraction.update.values(name=m.text).where(db.Fraction.id == fraction_id).gino.status()


@bot.on.private_message(StateRule(Admin.DESCRIPTION_FRACTION), AdminRule())
@allow_edit_content("Fraction", state=Admin.LEADER_FRACTION,
                    text="Описание фракции установлено. Теперь пришлите ссылку или перешлите сообщение на лидера фракции")
async def set_description_fraction(m: Message):
    fraction_id = int(states.get(m.from_id).split("*")[1])
    await db.Fraction.update.values(description=m.text).where(db.Fraction.id == fraction_id).gino.status()


@bot.on.private_message(StateRule(Admin.LEADER_FRACTION), AdminRule(), UserSpecified())
@allow_edit_content("Fraction", state=Admin.PHOTO_FRACTION,
                    text="Лидер фракции установлен. Теперь пришлите фотографию фракции")
async def set_leader_fraction(m: Message, form: Tuple[int, int]):
    fraction_id = int(states.get(m.from_id).split("*")[1])
    await db.Fraction.update.values(leader_id=form[1]).where(db.Fraction.id == fraction_id).gino.status()


@bot.on.private_message(StateRule(Admin.PHOTO_FRACTION), AdminRule(), AttachmentTypeRule("photo"))
@allow_edit_content("Fraction", state=Admin.PHOTO_FRACTION,
                    keyboard=gen_type_change_content("Decor"), end=True, text="Фракция успешно создана")
async def set_photo_fraction(m: Message):
    fraction_id = int(states.get(m.from_id).split("*")[1])
    if not m.attachments or m.attachments[0].type != m.attachments[0].type.PHOTO:
        await m.answer(messages.need_photo)
        return
    photo = await reload_image(m.attachments[0], f"data/photo{m.from_id}.jpg")
    await db.Fraction.update.values(photo=photo).where(db.Fraction.id == fraction_id).gino.status()


@bot.on.private_message(StateRule(f"{Admin.SELECT_ACTION}_Fraction"), PayloadRule({"Fraction": "delete"}), AdminRule())
async def select_number_product_to_delete(m: Message):
    fractions = await db.select([db.Fraction.name]).order_by(db.Fraction.id.asc()).gino.all()
    if not fractions:
        return "Фракции ещё не созданы"
    reply = "Выберите фракции:\n\n"
    for i, product in enumerate(fractions):
        reply = f"{reply}{i+1}. {product.name}\n"
    states.set(m.from_id, Admin.ID_FRACTION)
    await m.answer(reply, keyboard=Keyboard())


@bot.on.private_message(StateRule(Admin.ID_FRACTION), NumericRule(), AdminRule())
async def delete_poduct(m: Message, value: int):
    fraction_id = await db.select([db.Fraction.id]).order_by(db.Fraction.id.asc()).offset(value-1).limit(1).gino.scalar()
    if not fraction_id:
        await m.answer("Указан неверный номер товара")
        return
    await db.Fraction.delete.where(db.Fraction.id == fraction_id).gino.status()
    states.set(m.from_id, f"{Admin.SELECT_ACTION}_Fraction")
    await m.answer("Фракция успешно удалена", keyboard=gen_type_change_content("Fraction"))
    await send_content_page(m, "Fraction", 1)
