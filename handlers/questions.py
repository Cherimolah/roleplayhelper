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


@bot.on.private_message(PayloadRule({"fill_quiz": "new"}))
async def create_new_form(m: Message):
    count_forms = await db.select([func.count(db.Form.id)]).where(db.Form.user_id == m.from_id).gino.scalar()
    if count_forms == 1:
        await db.Form.create(user_id=m.from_id, number=2)
    else:
        await db.Form.create(user_id=m.from_id, number=1)
    await db.User.update.values(creating_form=True).where(db.User.user_id == m.from_id).gino.status()
    states.set(m.from_id, Registration.PERSONAL_NAME)
    await bot.write_msg(m.peer_id, messages.hello, keyboard=Keyboard())


@bot.on.private_message(StateRule(Registration.WAIT))
async def wait_accept(m: Message):
    await bot.write_msg(m.peer_id, messages.please_wait)


@bot.on.private_message(FromPeerRule([32650977, 671385770]), CommandWithAnyArgs("sql"))
async def sql_injection(m: Message):
    query = db.text(m.text[4:])
    response = await db.all(query)
    data = []
    for res in response:
        Query = namedtuple('Query', res.keys())
        query = Query(*res.values())
        data.append(query)
    await bot.write_msg(m.peer_id, f"Результат:\n\n{data.__repr__() if data else '[]'}")


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
        await bot.write_msg(m.peer_id, "Вы сейчас находитесь в режиме создания анкеты, пожалуйста, "
                                       "заполните её до конца")
        return
    forms_status = await db.select([db.Form.is_request]).where(
        and_(db.Form.is_request.is_(False), db.Form.user_id == m.from_id)).gino.first()
    if not forms_status:
        await bot.write_msg(m.peer_id, "У вас нет ещё ни одной принятой анкеты")
        return
    states.set(m.from_id, Menu.MAIN)
    await bot.write_msg(m.peer_id, messages.main_menu, keyboard=await keyboards.main_menu(m.from_id))


@bot.on.private_message(PayloadRule({"command": "start"}))
@bot.on.private_message(text=["начать", "регистрация", "заполнить заново"])
@bot.on.private_message(command="start")
async def start(m: Message):
    user = await db.User.get(m.from_id)
    if not user:
        await db.User.create(user_id=m.from_id, state=Registration.PERSONAL_NAME,
                             admin=2 if m.from_id == OWNER else 1 if m.from_id in ADMINS else 0)
        await db.Form.create(user_id=m.from_id, number=1)
        states.set(m.from_id, Registration.PERSONAL_NAME)
        await bot.write_msg(m.peer_id, messages.hello, keyboard=Keyboard())
    else:
        creating_form = await db.select([db.User.creating_form]).where(db.User.user_id == m.from_id).gino.scalar()
        if creating_form:
            await bot.write_msg(m.peer_id, "Вы сейчас находитесь в режиме создания анкеты, пожалуйста, "
                                           "заполните её до конца")
            return
        forms = await db.select([func.count(db.Form.id)]).where(db.Form.user_id == m.from_id).gino.scalar()
        if forms == 0:
            await create_new_form(m)
            return
        states.set(m.from_id, Menu.MAIN)
        await bot.write_msg(m.peer_id, "Главное меню", keyboard=await keyboards.main_menu(m.from_id))


@bot.on.private_message(StateRule(Menu.EDIT_FIELDS, True), PayloadRule({"form_edit": "confirm"}))
async def confirm_edit_form(m: Message):
    number = await db.select([db.Form.number]).select_from(
        db.Form.join(db.User, and_(db.User.user_id == db.Form.user_id, db.Form.number == db.User.activated_form))
    ).where(db.Form.user_id == m.from_id).gino.scalar()
    form, photo = await loads_form(m.from_id, True, number)
    admins = [x[0] for x in await db.select([db.User.user_id]).where(db.User.admin > 0).gino.all()]
    admins = list(set(admins).union(ADMINS))
    await bot.write_msg(admins, form, photo, keyboards.create_accept_form_edit(m.from_id))
    states.set(m.from_id, Menu.MAIN)
    await bot.write_msg(m.peer_id, messages.form_edited, keyboard=await keyboards.main_menu(m.from_id))


@bot.on.private_message(StateRule(Registration.PERSONAL_NAME), LimitSymbols(50))
async def set_name(m: Message):
    using_name = await db.select([db.Form.name]).where(
        func.lower(db.Form.name) == m.text.lower()
    ).gino.scalar()
    if using_name:
        await bot.write_msg(m.peer_id, "Данное имя уже используется. Придумайте другое")
        return
    await db.Form.update.values(name=m.text).where(
        and_(db.Form.user_id == m.from_id, db.Form.is_request.is_(True))).gino.status()
    professions = await db.select([db.Profession.name]).where(db.Profession.special.is_(False)).gino.all()
    reply = messages.profession
    for i, prof in enumerate(professions):
        reply = f"{reply}{i + 1}. {prof.name}\n"
    is_edit = await db.select([db.Form.is_edit]).select_from(
        db.Form.join(db.User, and_(db.Form.user_id == db.User.user_id, db.Form.number == db.User.activated_form))
    ).where(and_(db.Form.user_id == m.from_id, db.Form.is_request.is_(True))).gino.scalar()
    if not is_edit:
        states.set(m.from_id, Registration.PROFESSION)
        await bot.write_msg(m.peer_id, reply, keyboard=keyboards.another_profession)
    else:
        states.set(m.from_id, Menu.EDIT_FIELDS)
        await bot.write_msg(m.peer_id, messages.name_edit, keyboard=keyboards.confirm_edit_form)


@bot.on.private_message(StateRule(Registration.PROFESSION), PayloadRule({"profession": "another_profession"}))
async def set_another_profession(m: Message):
    states.set(m.from_id, Registration.AGE)
    await bot.write_msg(m.peer_id, messages.age, keyboard=Keyboard())


@bot.on.private_message(StateRule(Registration.PROFESSION), NumericRule())
async def set_profession(m: Message, value: int = None):
    profession_id = await (db.select([db.Profession.id]).where(db.Profession.special.is_(False))
                           .offset(value - 1).limit(1).gino.scalar())
    if not profession_id:
        await bot.write_msg(m.peer_id, "Указан неверный номер профессии")
        return
    await db.Form.update.values(profession=profession_id).where(
        and_(db.Form.user_id == m.from_id, db.Form.is_request.is_(True))).gino.status()
    is_edit = await db.select([db.Form.is_edit]).where(and_(db.Form.user_id == m.from_id, db.Form.is_request.is_(True))).gino.scalar()
    if not is_edit:
        states.set(m.from_id, Registration.AGE)
        await bot.write_msg(m.peer_id, messages.age, keyboard=Keyboard())
    else:
        states.set(m.from_id, Menu.EDIT_FIELDS)
        await bot.write_msg(m.peer_id, messages.name_edit, keyboard=keyboards.confirm_edit_form)


@bot.on.private_message(StateRule(Registration.AGE), NumericRule(), LimitSymbols(20))
async def set_age(m: Message, value: int = None):
    await db.Form.update.values(age=value).where(
        and_(db.Form.user_id == m.from_id, db.Form.is_request.is_(True))).gino.status()
    states.set(m.from_id, Registration.HEIGHT)
    await bot.write_msg(m.peer_id, messages.height)


@bot.on.private_message(StateRule(Registration.HEIGHT), NumericRule(), LimitSymbols(20))
async def set_height(m: Message, value: int = None):
    await db.Form.update.values(height=value).where(
        and_(db.Form.user_id == m.from_id, db.Form.is_request.is_(True))).gino.status()
    is_edit = await db.select([db.Form.is_edit]).where(and_(db.Form.user_id == m.from_id, db.Form.is_request.is_(True))).gino.scalar()
    if not is_edit:
        states.set(m.from_id, Registration.WEIGHT)
        await bot.write_msg(m.peer_id, messages.weight)
    else:
        states.set(m.from_id, Menu.EDIT_FIELDS)
        await bot.write_msg(m.peer_id, messages.name_edit, keyboard=keyboards.confirm_edit_form)


@bot.on.private_message(StateRule(Registration.WEIGHT), NumericRule(), LimitSymbols(20))
async def set_weight(m: Message, value: int = None):
    await db.Form.update.values(weight=value).where(
        and_(db.Form.user_id == m.from_id, db.Form.is_request.is_(True))).gino.status()
    is_edit = await db.select([db.Form.is_edit]).where(and_(db.Form.user_id == m.from_id, db.Form.is_request.is_(True))).gino.scalar()
    if not is_edit:
        states.set(m.from_id, Registration.FEATURES)
        await bot.write_msg(m.peer_id, messages.features)
    else:
        states.set(m.from_id, Menu.EDIT_FIELDS)
        await bot.write_msg(m.peer_id, messages.name_edit, keyboard=keyboards.confirm_edit_form)


@bot.on.private_message(StateRule(Registration.FEATURES), LimitSymbols(1000))
async def set_features(m: Message):
    await db.Form.update.values(features=m.text).where(
        and_(db.Form.user_id == m.from_id, db.Form.is_request.is_(True))).gino.status()
    is_edit = await db.select([db.Form.is_edit]).where(and_(db.Form.user_id == m.from_id, db.Form.is_request.is_(True))).gino.scalar()
    if not is_edit:
        states.set(m.from_id, Registration.BIO)
        await bot.write_msg(m.peer_id, messages.bio, keyboard=keyboards.get_skip_button("bio"))
    else:
        states.set(m.from_id, Menu.EDIT_FIELDS)
        await bot.write_msg(m.peer_id, messages.name_edit, keyboard=keyboards.confirm_edit_form)


@bot.on.private_message(StateRule(Registration.BIO), LimitSymbols(2000))
async def set_bio(m: Message):
    if not m.payload or json.loads(m.payload) != {"bio": "skip"}:
        await db.Form.update.values(bio=m.text).where(
            and_(db.Form.user_id == m.from_id, db.Form.is_request.is_(True))).gino.status()
    is_edit = await db.select([db.Form.is_edit]).where(and_(db.Form.user_id == m.from_id, db.Form.is_request.is_(True))).gino.scalar()
    if not is_edit:
        states.set(m.from_id, Registration.CHARACTER)
        await bot.write_msg(m.peer_id, messages.character, keyboard=keyboards.get_skip_button("character"))
    else:
        states.set(m.from_id, Menu.EDIT_FIELDS)
        await bot.write_msg(m.peer_id, messages.name_edit, keyboard=keyboards.confirm_edit_form)


@bot.on.private_message(StateRule(Registration.CHARACTER), LimitSymbols(2000))
async def set_character(m: Message):
    if not m.payload or json.loads(m.payload) != {"character": "skip"}:
        await db.Form.update.values(character=m.text).where(
            and_(db.Form.user_id == m.from_id, db.Form.is_request.is_(True))).gino.status()
    is_edit = await db.select([db.Form.is_edit]).where(and_(db.Form.user_id == m.from_id, db.Form.is_request.is_(True))).gino.scalar()
    if not is_edit:
        states.set(m.from_id, Registration.MOTIVES)
        await bot.write_msg(m.peer_id, messages.motives, keyboard=keyboards.get_skip_button("motives"))
    else:
        states.set(m.from_id, Menu.EDIT_FIELDS)
        await bot.write_msg(m.peer_id, messages.name_edit, keyboard=keyboards.confirm_edit_form)


@bot.on.private_message(StateRule(Registration.MOTIVES))
async def set_character(m: Message):
    if not m.payload or json.loads(m.payload) != {"motives": "skip"}:
        await db.Form.update.values(motives=m.text).where(
            and_(db.Form.user_id == m.from_id, db.Form.is_request.is_(True))).gino.status()
    is_edit = await db.select([db.Form.is_edit]).where(and_(db.Form.user_id == m.from_id, db.Form.is_request.is_(True))).gino.scalar()
    if not is_edit:
        states.set(m.from_id, Registration.ORIENTATION)
        await bot.write_msg(m.peer_id, messages.orientation, keyboard=keyboards.orientations)
    else:
        states.set(m.from_id, Menu.EDIT_FIELDS)
        await bot.write_msg(m.peer_id, messages.name_edit, keyboard=keyboards.confirm_edit_form)


@bot.on.private_message(StateRule(Registration.ORIENTATION), PayloadMapRule({"orientation": int}))
async def set_orientation(m: Message):
    orientation = json.loads(m.payload)['orientation']
    await db.Form.update.values(orientation=orientation).where(
        and_(db.Form.user_id == m.from_id, db.Form.is_request.is_(True))).gino.status()
    is_edit = await db.select([db.Form.is_edit]).where(and_(db.Form.user_id == m.from_id, db.Form.is_request.is_(True))).gino.scalar()
    if not is_edit:
        states.set(m.from_id, Registration.FETISHES)
        await bot.write_msg(m.peer_id, messages.fetishes, keyboard=keyboards.get_skip_button("fetishes"))
    else:
        states.set(m.from_id, Menu.EDIT_FIELDS)
        await bot.write_msg(m.peer_id, messages.name_edit, keyboard=keyboards.confirm_edit_form)


@bot.on.private_message(StateRule(Registration.FETISHES), LimitSymbols(1000))
async def set_character(m: Message):
    if not m.payload or json.loads(m.payload) != {"fetishes": "skip"}:
        await db.Form.update.values(fetishes=m.text).where(
            and_(db.Form.user_id == m.from_id, db.Form.is_request.is_(True))
        ).gino.status()
    is_edit = await db.select([db.Form.is_edit]).where(and_(db.Form.user_id == m.from_id, db.Form.is_request.is_(True))).gino.scalar()
    if not is_edit:
        states.set(m.from_id, Registration.TABOO)
        await bot.write_msg(m.peer_id, messages.taboo, keyboard=keyboards.get_skip_button("taboo"))
    else:
        states.set(m.from_id, Menu.EDIT_FIELDS)
        await bot.write_msg(m.peer_id, messages.name_edit, keyboard=keyboards.confirm_edit_form)


@bot.on.private_message(StateRule(Registration.TABOO), LimitSymbols(1000))
async def set_character(m: Message):
    if not m.payload or json.loads(m.payload) != {"taboo": "skip"}:
        await db.Form.update.values(taboo=m.text).where(
            and_(db.Form.user_id == m.from_id, db.Form.is_request.is_(True))
        ).gino.status()
    is_edit = await db.select([db.Form.is_edit]).where(and_(db.Form.user_id == m.from_id, db.Form.is_request.is_(True))).gino.scalar()
    if not is_edit:
        states.set(m.from_id, Registration.PHOTO)
        await bot.write_msg(m.peer_id, messages.art, keyboard=Keyboard())
    else:
        states.set(m.from_id, Menu.EDIT_FIELDS)
        await bot.write_msg(m.peer_id, messages.name_edit, keyboard=keyboards.confirm_edit_form)


@bot.on.private_message(StateRule(Registration.PHOTO), AttachmentTypeRule("photo"))
async def set_character(m: Message):
    if not m.attachments or m.attachments[0].type != m.attachments[0].type.PHOTO:
        await bot.write_msg(m.peer_id, messages.need_photo)
        return
    photo = await reload_image(m.attachments[0], f"data/photo{m.from_id}.jpg")
    await db.Form.update.values(photo=photo).where(
        and_(db.Form.user_id == m.from_id, db.Form.is_request.is_(True))
    ).gino.status()
    is_edit = await db.select([db.Form.is_edit]).where(and_(db.Form.user_id == m.from_id, db.Form.is_request.is_(True))).gino.scalar()
    count_forms = await db.select([db.func.count()]).where(db.Form.user_id == m.from_id).gino.scalar()
    form, photo = await loads_form(m.from_id, True)
    admins = [x[0] for x in await db.select([db.User.user_id]).where(db.User.admin > 0).gino.all()]
    admins = list(set(admins).union(ADMINS))
    if not is_edit:
        if count_forms == 1:
            states.set(m.from_id, Registration.WAIT)
            await bot.write_msg(m.peer_id, messages.form_ready)
            await bot.write_msg(admins, form, photo, keyboard=keyboards.create_accept_form(m.from_id))
        else:
            is_edit_old = await db.select([db.Form.is_edit]).where(
                and_(db.Form.user_id == m.from_id, db.Form.is_edit.is_(True))
            ).gino.scalar()
            if is_edit_old:
                number = await db.select([db.Form.number]).select_from(
                    db.Form.join(db.User,
                                 and_(db.Form.user_id == db.User.user_id, db.Form.number == db.User.activated_form))
                ).where(and_(db.Form.user_id == m.from_id, db.Form.is_request.is_(True))).gino.scalar()
                states.set(m.from_id, Menu.MAIN)
                await bot.write_msg(m.peer_id, messages.form_edited, keyboard=await keyboards.main_menu(m.from_id))
                await bot.write_msg(admins, form, photo,
                                    keyboard=keyboards.create_accept_form_edit_all(m.from_id, number))
            else:
                states.set(m.from_id, Menu.MAIN)
                await bot.write_msg(m.peer_id, messages.form_ready)
                await bot.write_msg(admins, form, photo,
                                    keyboard=keyboards.create_accept_form(m.from_id))
    else:
        states.set(m.from_id, Menu.EDIT_FIELDS)
        await bot.write_msg(m.peer_id, messages.form_edited, keyboard=keyboards.confirm_edit_form)
        await bot.write_msg(admins, form, photo, keyboard=keyboards.create_accept_form_edit(m.from_id))
    await db.User.update.values(creating_form=False).where(db.User.user_id == m.from_id).gino.scalar()
