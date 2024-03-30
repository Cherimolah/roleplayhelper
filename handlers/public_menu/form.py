from vkbottle.bot import Message, MessageEvent
from vkbottle.dispatch.rules.base import PayloadRule
from vkbottle import GroupEventType, Keyboard, Text, KeyboardButtonColor
from sqlalchemy import and_

import messages
from loader import bot, fields
from service.custom_rules import StateRule, NumericRule
from service.states import Menu, Registration
from service.utils import loads_form, get_mention_from_message
import service.keyboards as keyboards
from service.middleware import states
from service.db_engine import db


@bot.on.private_message(PayloadRule({"menu": "form"}), StateRule(Menu.MAIN))
@bot.on.private_message(StateRule(Menu.EDIT_FORM), PayloadRule({"form_edit": "back"}))
async def send_form(m: Message):
    form, photo = await loads_form(m.from_id)
    states.set(m.from_id, Menu.SHOW_FORM)
    await m.answer(f"Ваша анкета:\n\n{form}", attachment=photo, keyboard=keyboards.form_activity)


@bot.on.private_message(StateRule(Menu.EDIT_FORM), PayloadRule({"form_edit": "edit_all"}))
async def edit_all_form(m: Message):
    await db.Form.create(is_request=True, user_id=m.from_id)
    await db.User.update.values(creating_form=True).where(db.User.user_id == m.from_id).gino.status()
    states.set(m.from_id, Registration.PERSONAL_NAME)
    await m.answer(messages.hello, keyboard=Keyboard())


@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent, PayloadRule({"form": "next"}))
async def send_next_form(m: MessageEvent):
    form, photo = await loads_form(m.user_id)
    await db.User.update.values(activated_form=2).where(db.User.user_id == m.user_id).gino.status()
    await m.edit_message(message=form, attachment=photo, keyboard=keyboards.previous_form)


@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent, PayloadRule({"form": "previous"}))
async def send_next_form(m: MessageEvent):
    form, photo = await loads_form(m.user_id)
    await db.User.update.values(activated_form=1).where(db.User.user_id == m.user_id).gino.status()
    await m.edit_message(message=form, attachment=photo, keyboard=keyboards.next_form)


@bot.on.private_message(PayloadRule({"form": "search"}), StateRule(Menu.SHOW_FORM))
async def search_form(m: Message):
    states.set(m.from_id, Menu.SEARCH_FORM)
    await m.answer(messages.search_forms, keyboard=keyboards.form_search)


@bot.on.private_message(StateRule(Menu.SEARCH_FORM), PayloadRule({"form_search": "back"}))
@bot.on.private_message(StateRule(Menu.SELECT_NUMBER_SEARCH_FORMS, True), PayloadRule({"form_search": "back"}))
async def back_to_show_form(m: Message):
    states.set(m.from_id, Menu.SHOW_FORM)
    await m.answer(messages.back_to_form, keyboard=keyboards.form_activity)


@bot.on.private_message(StateRule(Menu.SEARCH_FORM))
async def search_user_form(m: Message):
    user_id = await get_mention_from_message(m)
    if not user_id:
        await m.answer(messages.user_not_found)
        return
    form, photo = await loads_form(user_id)
    await m.answer(form, photo)


@bot.on.private_message(StateRule(Menu.SHOW_FORM), PayloadRule({"form": "edit"}))
@bot.on.private_message(StateRule(Menu.EDIT_FIELDS, True), PayloadRule({"form": "edit"}))
async def send_form_edit(m: Message):
    name_request = await db.select([db.Form.name]).where(
        and_(db.Form.user_id == m.from_id, db.Form.is_request.is_(True))
    ).gino.scalar()
    if name_request:
        await m.answer(messages.has_requests.format(name_request))
        return
    states.set(m.from_id, Menu.EDIT_FORM)
    await m.answer("Выберите действие", keyboard=keyboards.how_edit_form)


@bot.on.private_message(StateRule(Menu.EDIT_FORM), PayloadRule({"form_edit": "edit_fields"}))
async def show_fields_edit(m: Message, new=True):
    if new:
        form = dict(await db.select([*db.Form]).where(db.Form.user_id == m.from_id).gino.first())
        params = {k: v for k, v in form.items() if k not in ("id", "is_request")}
        params['is_request'] = True
        await db.Form.create(**params)
    states.set(m.from_id, Menu.SELECT_FIELD_EDIT_NUMBER)
    reply = ("Выберите поле для редактирования."
             "Когда закончите нажмите кнопку «Подтвердить изменения»\n\n")
    for i, field in enumerate(fields):
        reply += f"{i+1}. {field.name}\n"
    await m.answer(reply, keyboard=keyboards.confirm_edit_form)


@bot.on.private_message(StateRule(Menu.SELECT_FIELD_EDIT_NUMBER), PayloadRule({"form_edit": "confirm"}))
async def confirm_edit_fields(m: Message):
    form_id = await db.select([db.Form.id]).where(and_(db.Form.user_id == m.from_id, db.Form.is_request.is_(True))).gino.scalar()
    form, photo = await loads_form(m.from_id, True)
    admins = [x[0] for x in await db.select([db.User.user_id]).where(db.User.admin > 0).gino.all()]
    await bot.api.messages.send(admins, form, photo, keyboard=keyboards.create_accept_form(form_id))
    states.set(m.from_id, Menu.MAIN)
    await m.answer("Новая версия анкеты успешно отправлена на проверку")
    await m.answer("Главное меню", keyboard=await keyboards.main_menu(m.from_id))


@bot.on.private_message(StateRule(Menu.SELECT_FIELD_EDIT_NUMBER), PayloadRule({"form_edit": "decline"}))
async def decline_edit_fields(m: Message):
    await db.Form.delete.where(and_(db.Form.user_id == m.from_id, db.Form.is_request.is_(True))).gino.status()
    await m.answer("Изменения отклонены")
    await send_form_edit(m)


@bot.on.private_message(StateRule(Menu.SELECT_FIELD_EDIT_NUMBER), NumericRule())
async def select_field_edit(m: Message, value: int = None):
    if not 1 <= value <= len(fields):
        return "Номер поля неверный"
    states.set(m.from_id, fields[value-1].state)
    field = fields[value-1].name
    if field == "Должность":
        professions = await db.select([db.Profession.name]).where(db.Profession.special.is_(False)).gino.all()
        reply = "Выберите профессию"
        for i, prof in enumerate(professions):
            reply = f"{reply}{i + 1}. {prof.name}\n"
        await m.answer(reply, keyboard=keyboards.another_profession)
        return
    elif field == "Сексуальная ориентация":
        await m.answer("Выберите сексуальную ориентацию", keyboard=keyboards.orientations)
        return
    else:
        await m.answer(f"Введите новое значение для поля {fields[value-1].name}:")
