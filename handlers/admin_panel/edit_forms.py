import asyncio
import datetime
import json

from vkbottle.bot import Message
from vkbottle.dispatch.rules.base import PayloadRule
from vkbottle import Keyboard, Text, KeyboardButtonColor

import messages
import service.keyboards as keyboards
from loader import bot
from loader import fields_admin as fields
from service.custom_rules import AdminRule, StateRule, NumericRule, UserSpecified
from service.middleware import states
from service.states import Admin
from service.db_engine import db
from service.utils import loads_form, take_off_payments, reload_image


@bot.on.private_message(StateRule(Admin.MENU), PayloadRule({"admin_menu": "edit_form"}), AdminRule())
async def edit_users_forms(m: Message):
    states.set(m.from_id, Admin.EDIT_FORMS)
    keyboard = Keyboard().add(
        Text("Назад", {"admin_forms_edit": "back"}), KeyboardButtonColor.NEGATIVE
    )
    await m.answer(messages.edit_users_forms, keyboard=keyboard)


@bot.on.private_message(StateRule(Admin.EDIT_FORMS, True), AdminRule(), UserSpecified(Admin.EDIT_FORMS))
async def search_form_for_edit(m: Message, form: tuple):
    form_id, user_id = form
    states.set(m.from_id, f"{Admin.SELECT_FIELDS}*{form_id}")
    form, photo = await loads_form(user_id, form_id=form_id)
    await m.answer(form, photo)
    reply = messages.select_field
    for i, field in enumerate(fields):
        reply = f"{reply}{i + 1}. {field.name}\n"
    await m.answer(reply)


@bot.on.private_message(StateRule(Admin.SELECT_FIELDS, True), NumericRule(), AdminRule())
async def send_select_fields(m: Message, value: int = None):
    if value and not 0 < value <= len(fields):
        await m.answer("Указано неверное поле")
        return
    _, form_id = states.get(m.from_id).split("*")
    states.set(m.from_id, f"{Admin.ENTER_FIELD_VALUE}*{form_id}*{fields[value - 1].state}")
    reply = messages.new_value_field.format(fields[value-1].name)
    keyboard = None
    if value == 2:
        professions = await db.select([db.Profession.name]).gino.all()
        for i, prof in enumerate(professions):
            reply = f"{reply}{i + 1}. {prof.name}\n"
    if value == 10:
        keyboard = keyboards.orientations
    elif value == 15:
        cabins = await db.select([db.Cabins.name]).gino.all()
        for i, cabin in enumerate(cabins):
            reply = f"{reply}{i+1}. {cabin.name}\n"
    elif value == 16:
        keyboard = Keyboard().add(
            Text("Заморозить", {"freeze": True}), KeyboardButtonColor.NEGATIVE
        ).row().add(
            Text("Разморозить", {"freeze": False}), KeyboardButtonColor.POSITIVE
        )
    elif value == 17:
        statuses = await db.select([db.Status.name]).gino.all()
        for i, status in enumerate(statuses):
            reply = f"{reply}{i+1}. {status.name}\n"
    await m.answer(reply, keyboard=keyboard)


@bot.on.private_message(StateRule(Admin.ENTER_FIELD_VALUE, True), AdminRule())
async def enter_field_value(m: Message):
    _, form_id, field = states.get(m.from_id).split("*")
    form_id = int(form_id)
    if field == "photo":
        if not m.attachments:
            await m.answer(messages.need_photo)
            return
        user_id = await db.select([db.Form.user_id]).where(db.Form.id == form_id).gino.scalar()
        photo = await reload_image(m.attachments[0], f"data/photo{user_id}{form_id}.jpg")
        await db.Form.update.values(photo=photo).where(db.Form.id == form_id).gino.status()
    elif field == "orientation":
        if not m.payload or "orientation" not in m.payload:
            await m.answer(messages.nedd_orientation)
            return
        await db.Form.update.values(orientation=m.payload['orientation']).where(db.Form.id == form_id).gino.status()
    elif field == "cabin_lux":
        if not m.text.isdigit():
            await m.answer(messages.need_cabin_class)
            return
        value = int(m.text)
        cabin_id, price = await db.select([db.Cabins.id, db.Cabins.cost]).offset(value - 1).limit(1).gino.first()
        await db.Form.update.values(cabin_type=cabin_id,
                                    balance=db.Form.balance - price,
                                    last_payment=datetime.datetime.now()).where(db.Form.id == form_id).gino.status()
        asyncio.get_event_loop().create_task(take_off_payments(form_id))
    elif field == "freeze":
        if not m.payload or "freeze" not in m.payload:
            await m.answer(messages.need_status_freeze)
            return
        freeze = m.payload['freeze']
        await db.Form.update.values(freeze=freeze).where(db.Form.id == form_id).gino.status()
    elif field == "profession":
        if not m.text.isdigit():
            await m.answer("Необходимо указать число")
            return
        value = int(m.text)
        profession_id = await db.select([db.Profession.id]).offset(value-1).gino.scalar()
        await db.Form.update.values(profession=profession_id).where(db.Form.id == form_id).gino.status()
    elif field == "status":
        if not m.text.isdigit():
            await m.answer("Необходимо указать число")
            return
        value = int(m.text)
        status_id = await db.select([db.Status.id]).offset(value-1).gino.scalar()
        await db.Form.update.values(status=status_id).where(db.Form.id == form_id).gino.status()
    else:
        if m.text.isdigit():
            value = int(m.text)
        else:
            value = m.text
        await db.Form.update.values(**{field: value}).where(db.Form.id == form_id).gino.status()
    keyboard = Keyboard().add(
        Text("Назад", {"admin_forms_edit": "back"}), KeyboardButtonColor.NEGATIVE
    )
    states.set(m.from_id, f"{Admin.SELECT_FIELDS}*{form_id}")
    await m.answer(messages.field_edit_from_admin, keyboard=keyboard)
