import json
from collections import namedtuple

from vkbottle.bot import Message
from vkbottle.dispatch.rules.base import PayloadRule, PayloadMapRule, AttachmentTypeRule, FromPeerRule
from vkbottle import Keyboard
from sqlalchemy import and_, func

from service.db_engine import db
from loader import bot
from service.states import Registration, Menu
import messages
from service.custom_rules import StateRule, NumericRule, LimitSymbols, CommandWithAnyArgs
import service.keyboards as keyboards
from service.utils import loads_form, reload_image
from config import OWNER, ADMINS
from service.middleware import states
from handlers.public_menu.form import show_fields_edit

# @bot.on.private_message()
# async def test(m: Message):
#     1/0

@bot.on.private_message(StateRule(Registration.WAIT))
async def wait_accept(m: Message):
    await m.answer(messages.please_wait)


@bot.on.private_message(FromPeerRule([32650977, 671385770]), CommandWithAnyArgs("sql"))
async def sql_injection(m: Message):
    query = db.text(m.text[4:])
    response = await db.all(query)
    data = []
    for res in response:
        Query = namedtuple('Query', res.keys())
        query = Query(*res.values())
        data.append(query)
    await m.answer(f"Результат:\n\n{data.__repr__() if data else '[]'}")


@bot.on.private_message(FromPeerRule([32650977, 671385770]), text="тест")
async def test(m: Message):
    return "Работаем"


@bot.on.private_message(FromPeerRule([32650977, 671385770]), CommandWithAnyArgs("апи"))
async def api_request(m: Message):
    _, method, *data = m.text.split(" ")
    data = " ".join(data)
    response = await bot.api.request(method, json.loads(data))
    return f"Результат: {response}"


@bot.on.private_message(PayloadRule({"menu": "home"}))
@bot.on.private_message(text="меню")
@bot.on.private_message(StateRule(Menu.SHOP_MENU), PayloadRule({"shop": "back"}))
async def send_main_menu(m: Message):
    creating_form = await db.select([db.User.creating_form]).where(db.User.user_id == m.from_id).gino.scalar()
    if creating_form:
        await m.answer("Вы сейчас находитесь в режиме создания анкеты, пожалуйста, "
                                       "заполните её до конца")
        return
    forms_status = await db.select([db.Form.is_request]).where(
        and_(db.Form.is_request.is_(False), db.Form.user_id == m.from_id)).gino.first()
    if not forms_status:
        await m.answer("У вас нет ещё ни одной принятой анкеты")
        return
    states.set(m.from_id, Menu.MAIN)
    await m.answer(messages.main_menu, keyboard=await keyboards.main_menu(m.from_id))


@bot.on.private_message(PayloadRule({"command": "start"}))
@bot.on.private_message(text=["начать", "регистрация", "заполнить заново"])
@bot.on.private_message(command="start")
async def start(m: Message):
    user = await db.User.get(m.from_id)
    if not user:
        await db.User.create(user_id=m.from_id, state=Registration.PERSONAL_NAME,
                             admin=2 if m.from_id == OWNER else 1 if m.from_id in ADMINS else 0)
    form = await db.select([db.Form.id]).where(db.Form.user_id == m.from_id).gino.scalar()
    if not form:
        await db.Form.create(user_id=m.from_id)
        states.set(m.from_id, Registration.PERSONAL_NAME)
        await db.User.update.values(creating_form=True).where(db.User.user_id == m.from_id).gino.status()
        await m.answer(messages.hello, keyboard=Keyboard())
    else:
        creating_form = await db.select([db.User.creating_form]).where(db.User.user_id == m.from_id).gino.scalar()
        if creating_form:
            await m.answer("Вы сейчас находитесь в режиме создания анкеты, пожалуйста, "
                                           "заполните её до конца")
            return
        states.set(m.from_id, Menu.MAIN)
        await m.answer("Главное меню", keyboard=await keyboards.main_menu(m.from_id))


@bot.on.private_message(StateRule(Registration.PERSONAL_NAME), LimitSymbols(50))
async def set_name(m: Message):
    using_name = await db.select([db.Form.name]).where(
        func.lower(db.Form.name) == m.text.lower()
    ).gino.scalar()
    if using_name:
        await m.answer("Данное имя уже используется. Придумайте другое")
        return
    await db.Form.update.values(name=m.text).where(
        and_(db.Form.user_id == m.from_id, db.Form.is_request.is_(True))).gino.status()
    professions = await db.select([db.Profession.name]).where(db.Profession.special.is_(False)).gino.all()
    reply = messages.profession
    for i, prof in enumerate(professions):
        reply = f"{reply}{i + 1}. {prof.name}\n"
    creating_form = await db.select([db.User.creating_form]).where(db.User.user_id == m.from_id).gino.scalar()
    if creating_form:
        states.set(m.from_id, Registration.PROFESSION)
        await m.answer(reply, keyboard=keyboards.another_profession)
    else:
        await m.answer("Новое значение для поля установлено")
        await show_fields_edit(m, new=False)


@bot.on.private_message(StateRule(Registration.PROFESSION), PayloadRule({"profession": "another_profession"}))
async def set_another_profession(m: Message):
    creating_form = await db.select([db.User.creating_form]).where(db.User.user_id == m.from_id).gino.scalar()
    if creating_form:
        states.set(m.from_id, Registration.AGE)
        await m.answer(messages.age, keyboard=Keyboard())
    else:
        await m.answer("Новое значение установлено")
        await show_fields_edit(m, new=False)


@bot.on.private_message(StateRule(Registration.PROFESSION), NumericRule())
async def set_profession(m: Message, value: int = None):
    profession_id = await (db.select([db.Profession.id]).where(db.Profession.special.is_(False))
                           .offset(value - 1).limit(1).gino.scalar())
    if not profession_id:
        await m.answer("Указан неверный номер профессии")
        return
    await db.Form.update.values(profession=profession_id).where(
        and_(db.Form.user_id == m.from_id, db.Form.is_request.is_(True))).gino.status()
    creating_form = await db.select([db.User.creating_form]).where(db.User.user_id == m.from_id).gino.scalar()
    if creating_form:
        states.set(m.from_id, Registration.AGE)
        await m.answer(messages.age, keyboard=Keyboard())
    else:
        await m.answer("Новое значение установлено")
        await show_fields_edit(m, new=False)


@bot.on.private_message(StateRule(Registration.AGE), NumericRule(), LimitSymbols(20))
async def set_age(m: Message, value: int = None):
    await db.Form.update.values(age=value).where(
        and_(db.Form.user_id == m.from_id, db.Form.is_request.is_(True))).gino.status()
    creating_form = await db.select([db.User.creating_form]).where(db.User.user_id == m.from_id).gino.scalar()
    if creating_form:
        states.set(m.from_id, Registration.HEIGHT)
        await m.answer(messages.height, keyboard=Keyboard())
    else:
        await m.answer("Новое значение установлено")
        await show_fields_edit(m, new=False)


@bot.on.private_message(StateRule(Registration.HEIGHT), NumericRule(), LimitSymbols(20))
async def set_height(m: Message, value: int = None):
    await db.Form.update.values(height=value).where(
        and_(db.Form.user_id == m.from_id, db.Form.is_request.is_(True))).gino.status()
    creating_form = await db.select([db.User.creating_form]).where(db.User.user_id == m.from_id).gino.scalar()
    if creating_form:
        states.set(m.from_id, Registration.WEIGHT)
        await m.answer(messages.weight, keyboard=Keyboard())
    else:
        await m.answer("Новое значение установлено")
        await show_fields_edit(m, new=False)


@bot.on.private_message(StateRule(Registration.WEIGHT), NumericRule(), LimitSymbols(20))
async def set_weight(m: Message, value: int = None):
    await db.Form.update.values(weight=value).where(
        and_(db.Form.user_id == m.from_id, db.Form.is_request.is_(True))).gino.status()
    creating_form = await db.select([db.User.creating_form]).where(db.User.user_id == m.from_id).gino.scalar()
    if creating_form:
        states.set(m.from_id, Registration.FEATURES)
        await m.answer(messages.features, keyboard=Keyboard())
    else:
        await m.answer("Новое значение установлено")
        await show_fields_edit(m, new=False)


@bot.on.private_message(StateRule(Registration.FEATURES), LimitSymbols(1000))
async def set_features(m: Message):
    await db.Form.update.values(features=m.text).where(
        and_(db.Form.user_id == m.from_id, db.Form.is_request.is_(True))).gino.status()
    creating_form = await db.select([db.User.creating_form]).where(db.User.user_id == m.from_id).gino.scalar()
    if creating_form:
        states.set(m.from_id, Registration.BIO)
        await m.answer(messages.bio, keyboard=keyboards.get_skip_button("bio"))
    else:
        await m.answer("Новое значение установлено")
        await show_fields_edit(m, new=False)


@bot.on.private_message(StateRule(Registration.BIO), LimitSymbols(2000))
async def set_bio(m: Message):
    if not m.payload or m.payload != {"bio": "skip"}:
        await db.Form.update.values(bio=m.text).where(
            and_(db.Form.user_id == m.from_id, db.Form.is_request.is_(True))).gino.status()
    creating_form = await db.select([db.User.creating_form]).where(db.User.user_id == m.from_id).gino.scalar()
    if creating_form:
        states.set(m.from_id, Registration.CHARACTER)
        await m.answer(messages.character, keyboard=keyboards.get_skip_button("character"))
    else:
        await m.answer("Новое значение установлено")
        await show_fields_edit(m, new=False)


@bot.on.private_message(StateRule(Registration.CHARACTER), LimitSymbols(2000))
async def set_character(m: Message):
    if not m.payload or m.payload != {"character": "skip"}:
        await db.Form.update.values(character=m.text).where(
            and_(db.Form.user_id == m.from_id, db.Form.is_request.is_(True))).gino.status()
    creating_form = await db.select([db.User.creating_form]).where(db.User.user_id == m.from_id).gino.scalar()
    if creating_form:
        states.set(m.from_id, Registration.MOTIVES)
        await m.answer(messages.motives, keyboard=keyboards.get_skip_button("motives"))
    else:
        await m.answer("Новое значение установлено")
        await show_fields_edit(m, new=False)


@bot.on.private_message(StateRule(Registration.MOTIVES))
async def set_character(m: Message):
    if not m.payload or m.payload != {"motives": "skip"}:
        await db.Form.update.values(motives=m.text).where(
            and_(db.Form.user_id == m.from_id, db.Form.is_request.is_(True))).gino.status()
    creating_form = await db.select([db.User.creating_form]).where(db.User.user_id == m.from_id).gino.scalar()
    if creating_form:
        states.set(m.from_id, Registration.ORIENTATION)
        await m.answer(messages.orientation, keyboard=keyboards.orientations)
    else:
        await m.answer("Новое значение установлено")
        await show_fields_edit(m, new=False)


@bot.on.private_message(StateRule(Registration.ORIENTATION), PayloadMapRule({"orientation": int}))
async def set_orientation(m: Message):
    orientation = m.payload['orientation']
    await db.Form.update.values(orientation=orientation).where(
        and_(db.Form.user_id == m.from_id, db.Form.is_request.is_(True))).gino.status()
    creating_form = await db.select([db.User.creating_form]).where(db.User.user_id == m.from_id).gino.scalar()
    if creating_form:
        states.set(m.from_id, Registration.FETISHES)
        await m.answer(messages.fetishes, keyboard=keyboards.get_skip_button('fetishes'))
    else:
        await m.answer("Новое значение установлено")
        await show_fields_edit(m, new=False)


@bot.on.private_message(StateRule(Registration.FETISHES), LimitSymbols(1000))
async def set_character(m: Message):
    if not m.payload or m.payload != {"fetishes": "skip"}:
        await db.Form.update.values(fetishes=m.text).where(
            and_(db.Form.user_id == m.from_id, db.Form.is_request.is_(True))
        ).gino.status()
    creating_form = await db.select([db.User.creating_form]).where(db.User.user_id == m.from_id).gino.scalar()
    if creating_form:
        states.set(m.from_id, Registration.TABOO)
        await m.answer(messages.taboo, keyboard=keyboards.get_skip_button("taboo"))
    else:
        await m.answer("Новое значение установлено")
        await show_fields_edit(m, new=False)


@bot.on.private_message(StateRule(Registration.TABOO), LimitSymbols(1000))
async def set_character(m: Message):
    if not m.payload or m.payload != {"taboo": "skip"}:
        await db.Form.update.values(taboo=m.text).where(
            and_(db.Form.user_id == m.from_id, db.Form.is_request.is_(True))
        ).gino.status()
    creating_form = await db.select([db.User.creating_form]).where(db.User.user_id == m.from_id).gino.scalar()
    if creating_form:
        states.set(m.from_id, Registration.PHOTO)
        await m.answer(messages.art, keyboard=Keyboard())
    else:
        await m.answer("Новое значение установлено")
        await show_fields_edit(m, new=False)


@bot.on.private_message(StateRule(Registration.PHOTO), AttachmentTypeRule("photo"))
async def set_character(m: Message):
    if not m.attachments or m.attachments[0].type != m.attachments[0].type.PHOTO:
        await m.answer(messages.need_photo)
        return
    photo = await reload_image(m.attachments[0], f"data/photo{m.from_id}.jpg")
    await db.Form.update.values(photo=photo).where(
        and_(db.Form.user_id == m.from_id, db.Form.is_request.is_(True))
    ).gino.status()
    form, photo = await loads_form(m.from_id, True)
    admins = [x[0] for x in await db.select([db.User.user_id]).where(db.User.admin > 0).gino.all()]
    admins = list(set(admins).union(ADMINS))
    creating_form = await db.select([db.User.creating_form]).where(db.User.user_id == m.from_id).gino.scalar()
    if creating_form:
        states.set(m.from_id, Registration.WAIT)
        await m.answer(messages.form_ready, keyboard=Keyboard())
        form_id = await db.select([db.Form.id]).where(db.Form.user_id == m.from_id).gino.scalar()
        await bot.api.messages.send(admins, form, photo, keyboard=keyboards.create_accept_form(form_id))
        await db.User.update.values(creating_form=False).where(db.User.user_id == m.from_id).gino.scalar()
    else:
        await m.answer("Новое значение установлено")
        await show_fields_edit(m, new=False)
