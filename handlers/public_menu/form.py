from vkbottle.bot import Message, MessageEvent
from vkbottle.dispatch.rules.base import PayloadRule
from vkbottle import GroupEventType, Keyboard, Text, KeyboardButtonColor
from sqlalchemy import and_, func

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
    number_form = await db.select([db.User.activated_form]).where(db.User.user_id == m.from_id).gino.scalar()
    form, photo = await loads_form(m.from_id, number=number_form)
    count_forms = await db.select([db.func.count()]).where(
        and_(db.Form.user_id == m.from_id, db.Form.is_request.is_(False))
    ).gino.scalar()
    states.set(m.from_id, Menu.SHOW_FORM)
    await bot.write_msg(m.peer_id, "Ваша анкета:", keyboard=keyboards.form_activity)
    keyboard = None
    if number_form > 1:
        keyboard = keyboards.previous_form
    elif count_forms > number_form:
        keyboard = keyboards.next_form
    await bot.write_msg(m.peer_id, form, photo, keyboard=keyboard)


@bot.on.private_message(StateRule(Menu.EDIT_FORM), PayloadRule({"form_edit": "edit_all"}))
async def edit_all_form(m: Message):
    form = await db.select([*db.Form]).select_from(
        db.Form.join(db.User, and_(db.User.user_id == db.Form.user_id, db.Form.number == db.User.activated_form))
    ).where(db.Form.user_id == m.from_id).gino.first()
    await db.Form.update.values(is_edit=True).where(db.Form.id == form.id).gino.status()
    await db.Form.create(is_request=True, is_edit=False, user_id=m.from_id, name=form.name,
                         profession=form.profession, age=form.age, height=form.height, weight=form.weight,
                         features=form.features, bio=form.bio, character=form.character, motives=form.motives,
                         orientation=form.orientation, fetishes=form.fetishes, taboo=form.taboo, photo=form.photo,
                         cabin=form.cabin, cabin_type=form.cabin_type, number=form.number, balance=form.balance,
                         freeze=form.freeze)
    states.set(m.from_id, Registration.PERSONAL_NAME)
    await bot.write_msg(m.peer_id, messages.hello, keyboard=Keyboard())


@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent, PayloadRule({"form": "next"}))
async def send_next_form(m: MessageEvent):
    form, photo = await loads_form(m.user_id, number=2)
    await db.User.update.values(activated_form=2).where(db.User.user_id == m.user_id).gino.status()
    await bot.edit_msg(m, message=form, attachment=photo, keyboard=keyboards.previous_form)


@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent, PayloadRule({"form": "previous"}))
async def send_next_form(m: MessageEvent):
    form, photo = await loads_form(m.user_id, number=1)
    await db.User.update.values(activated_form=1).where(db.User.user_id == m.user_id).gino.status()
    await bot.edit_msg(m, message=form, attachment=photo, keyboard=keyboards.next_form)


@bot.on.private_message(PayloadRule({"form": "search"}), StateRule(Menu.SHOW_FORM))
async def search_form(m: Message):
    states.set(m.from_id, Menu.SEARCH_FORM)
    await bot.write_msg(m.peer_id, messages.search_forms, keyboard=keyboards.form_search)


@bot.on.private_message(StateRule(Menu.SEARCH_FORM), PayloadRule({"form_search": "back"}))
@bot.on.private_message(StateRule(Menu.SELECT_NUMBER_SEARCH_FORMS, True), PayloadRule({"form_search": "back"}))
async def back_to_show_form(m: Message):
    states.set(m.from_id, Menu.SHOW_FORM)
    await bot.write_msg(m.peer_id, messages.back_to_form, keyboard=keyboards.form_activity)


@bot.on.private_message(StateRule(Menu.SEARCH_FORM))
async def search_user_form(m: Message):
    user_id = await get_mention_from_message(m)
    if not user_id:
        await bot.write_msg(m.peer_id, messages.user_not_found)
        return
    count_forms = await db.select([db.func.count()]).where(
        and_(db.Form.user_id == user_id, db.Form.is_request.is_(False))).gino.scalar()
    if count_forms > 1:
        states.set(m.from_id, f"{Menu.SELECT_NUMBER_SEARCH_FORMS}@{user_id}")
        user = (await bot.api.users.get(user_id))[0]
        reply = messages.select_number_form.format(f"[id{user_id}|{user.first_name} {user.last_name}]\n\n")
        names = [x[0] for x in await db.select([db.Form.name]).where(
            and_(db.Form.user_id == user_id, db.Form.is_request.is_(False))
        ).gino.all()]
        for i, name in enumerate(names):
            reply = f"{reply}{i+1}. {name}\n"
        await bot.write_msg(m.peer_id, reply)
        return
    form, photo = await loads_form(user_id)
    await bot.write_msg(m.peer_id, form, photo)


@bot.on.private_message(StateRule(Menu.SELECT_NUMBER_SEARCH_FORMS, True), NumericRule())
async def selected_number_forms(m: Message, value: int):
    if value not in (1, 2):
        await bot.write_msg(m.peer_id, messages.error_not_number_form)
        return
    user_id = int(states.get(m.from_id).split("@")[1])
    number = await db.select([db.Form.number]).where(
        and_(db.Form.user_id == user_id, db.Form.is_request.is_(False))).offset(value-1).gino.scalar()
    form, photo = await loads_form(user_id, number=number)
    states.set(m.from_id, Menu.SEARCH_FORM)
    await bot.write_msg(m.peer_id, form, photo)


@bot.on.private_message(StateRule(Menu.SHOW_FORM), PayloadRule({"form": "edit"}))
@bot.on.private_message(StateRule(Menu.EDIT_FIELDS, True), PayloadRule({"form": "edit"}))
async def send_form_edit(m: Message):
    name_request = await db.select([db.Form.name]).where(
        and_(db.Form.user_id == m.from_id, db.Form.is_request.is_(True))
    ).gino.scalar()
    if name_request:
        await bot.write_msg(m.peer_id, messages.has_requests.format(name_request))
        return
    states.set(m.from_id, Menu.EDIT_FORM)
    await bot.write_msg(m.peer_id, "Выберите действие", keyboard=keyboards.how_edit_form)


@bot.on.private_message(StateRule(Menu.EDIT_FORM), PayloadRule({"form_edit": "edit_fields"}))
async def choice_fields_to_edit(m: Message):
    states.set(m.from_id, f"{Menu.EDIT_FIELDS}")
    reply = messages.select_field
    for i, field in enumerate(fields):
        reply = f"{reply}{i + 1}. {field.name}\n"
    keyboard = Keyboard().add(
        Text("Назад", {"form": "edit"}), KeyboardButtonColor.NEGATIVE
    )
    await bot.write_msg(m.peer_id, reply, keyboard=keyboard)


@bot.on.private_message(StateRule(Menu.EDIT_FIELDS, True), NumericRule())
async def start_edit_field(m: Message, value: int = None):
    if not 0 < value <= len(fields):
        await bot.write_msg(m.peer_id, "Указано неверное поле")
        return
    is_request = await db.select([db.Form.is_request]).where(and_(db.Form.user_id == m.from_id, db.Form.is_request.is_(True))).gino.scalar()
    if not is_request:
        form = await db.select([*db.Form]).select_from(
            db.Form.join(db.User, and_(db.User.user_id == db.Form.user_id, db.Form.number == db.User.activated_form))
        ).where(db.Form.user_id == m.from_id).gino.first()
        await db.Form.update.values(is_edit=True).where(db.Form.id == form.id).gino.status()
        await db.Form.create(is_request=True, is_edit=True, user_id=m.from_id, name=form.name,
                             profession=form.profession, age=form.age, height=form.height, weight=form.weight,
                             features=form.features, bio=form.bio, character=form.character, motives=form.motives,
                             orientation=form.orientation, fetishes=form.fetishes, taboo=form.taboo, photo=form.photo,
                             cabin=form.cabin, cabin_type=form.cabin_type, number=form.number, balance=form.balance,
                             freeze=form.freeze)
    states.set(m.from_id, f"{fields[value - 1].table}")
    reply = f"Введите новое значение для поля {fields[value - 1].name}\n\n"
    keyboard = Keyboard()
    if value == 2:
        professions = await db.select([db.Profession.name]).where(db.Profession.special.is_(False)).gino.all()
        for i, prof in enumerate(professions):
            reply = f"{reply}{i + 1}. {prof.name}\n"
    if value == 10:
        keyboard = keyboards.orientations
    await bot.write_msg(m.peer_id, reply, keyboard=keyboard)
