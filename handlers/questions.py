import json
from collections import namedtuple

from vkbottle.bot import Message, MessageEvent
from vkbottle.dispatch.rules.base import PayloadRule, PayloadMapRule, AttachmentTypeRule, FromPeerRule
from vkbottle import Keyboard, GroupEventType, Callback, KeyboardButtonColor, Text
from sqlalchemy import and_, func

from service.db_engine import db
from loader import bot, states
from service.states import Registration, Menu, DaughterQuestions, Judge
import messages
from service.custom_rules import StateRule, NumericRule, LimitSymbols, CommandWithAnyArgs
import service.keyboards as keyboards
from service.utils import loads_form, reload_image, show_fields_edit, page_fractions, get_admin_ids
from config import OWNER, ADMINS


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


@bot.on.private_message(PayloadRule({"command": "start"}))
@bot.on.private_message(text=["начать", "регистрация", "заполнить заново", 'старт', 'меню', 'start', 'menu'])
@bot.on.private_message(command="start")
@bot.on.private_message(PayloadRule({"menu": "home"}))
@bot.on.private_message(StateRule(Menu.SHOP_MENU), PayloadRule({"shop": "back"}))
@bot.on.private_message(StateRule(Judge.MENU), PayloadRule({"judge_menu": "back"}))
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
        creating_form, editing_form, creating_expeditor = await db.select([db.User.creating_form, db.User.editing_form, db.User.creating_expeditor]).where(db.User.user_id == m.from_id).gino.first()
        if creating_form:
            await m.answer("Вы сейчас находитесь в режиме создания анкеты, пожалуйста, "
                                           "заполните её до конца")
            return
        if editing_form:
            await m.answer("Вы сейчас находитесь в режиме редактирования анкеты, пожалуйста, "
                           "заполните её до конца или отклоните изменения")
            return
        if creating_expeditor:
            await m.answer('Вы сейчас находитесь в режиме создания Карты экспедитора!\n'
                           'Заполните сначала её до конца')
            return
        chat_id = await db.select([db.ActionMode.chat_id]).where(db.ActionMode.judge_id == m.from_id).gino.scalar()
        if chat_id:
            chat_name = (await bot.api.messages.get_conversations_by_id(peer_ids=2000000000 + chat_id)).items[0].chat_settings.title
            await m.answer(f'Вы сейчас являетесь судьей экшен-режима в чате «{chat_name}»')
            return
        states.set(m.from_id, Menu.MAIN)
        await m.answer("Главное меню", keyboard=await keyboards.main_menu(m.from_id))
    await db.User.update.values(editing_content=False).where(db.User.user_id == m.from_id).gino.status()
    await db.User.update.values(judge_panel=False).where(db.User.user_id == m.from_id).gino.status()


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
        await show_fields_edit(m.from_id, new=False)


@bot.on.private_message(StateRule(Registration.PROFESSION), PayloadRule({"profession": "another_profession"}))
async def set_another_profession(m: Message):
    creating_form = await db.select([db.User.creating_form]).where(db.User.user_id == m.from_id).gino.scalar()
    if creating_form:
        states.set(m.from_id, Registration.AGE)
        await m.answer(messages.age, keyboard=Keyboard())
    else:
        await m.answer("Новое значение установлено")
        await show_fields_edit(m.from_id, new=False)


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
        await show_fields_edit(m.from_id, new=False)


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
        await show_fields_edit(m.from_id, new=False)


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
        await show_fields_edit(m.from_id, new=False)


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
        await show_fields_edit(m.from_id, new=False)


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
        await show_fields_edit(m.from_id, new=False)


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
        await show_fields_edit(m.from_id, new=False)


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
        await show_fields_edit(m.from_id, new=False)


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
        await show_fields_edit(m.from_id, new=False)


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
        await show_fields_edit(m.from_id, new=False)


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
        await show_fields_edit(m.from_id, new=False)


@bot.on.private_message(StateRule(Registration.TABOO), LimitSymbols(1000))
async def set_character(m: Message):
    if not m.payload or m.payload != {"taboo": "skip"}:
        await db.Form.update.values(taboo=m.text).where(
            and_(db.Form.user_id == m.from_id, db.Form.is_request.is_(True))
        ).gino.status()
    creating_form = await db.select([db.User.creating_form]).where(db.User.user_id == m.from_id).gino.scalar()
    if creating_form:
        states.set(m.from_id, Registration.FRACTION)
        await m.answer("Выбери в какую фракцию вступить", keyboard=Keyboard())
        reply, kb, photo = await page_fractions(1)
        await m.answer(reply, keyboard=kb, attachment=photo)
    else:
        await m.answer("Новое значение установлено")
        await show_fields_edit(m.from_id, new=False)


@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent, PayloadMapRule({"fraction_page": int}), StateRule(Registration.FRACTION))
async def show_fraction_page(m: MessageEvent):
    reply, kb, photo = await page_fractions(m.payload['fraction_page'])
    await m.edit_message(reply, keyboard=kb.get_json(), attachment=photo)


@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent, PayloadMapRule({"fraction_select": int}), StateRule(Registration.FRACTION))
async def select_fraction(m: MessageEvent):
    fraction_id = m.payload['fraction_select']
    name = await db.select([db.Fraction.name]).where(db.Fraction.id == fraction_id).gino.scalar()
    kb = Keyboard(inline=True).add(
        Callback("Да", {"fraction_accept": fraction_id}), KeyboardButtonColor.POSITIVE
    ).add(
        Callback("Нет", {"fraction_page": 1}), KeyboardButtonColor.NEGATIVE
    )
    await m.edit_message(f"Вы уверены, что хотите вступить в фракцию «{name}»?", keyboard=kb.get_json())


@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent, PayloadMapRule({"fraction_accept": int}), StateRule(Registration.FRACTION))
async def fraction_accept(m: MessageEvent):
    fraction_id = m.payload['fraction_accept']
    name = await db.select([db.Fraction.name]).where(db.Fraction.id == fraction_id).gino.scalar()
    await db.Form.update.values(fraction_id=fraction_id).where(
        and_(db.Form.user_id == m.user_id, db.Form.is_request.is_(True))
    ).gino.status()
    await db.change_reputation(m.user_id, fraction_id, 0)
    creating_form = await db.select([db.User.creating_form]).where(db.User.user_id == m.user_id).gino.scalar()
    if creating_form:
        states.set(m.user_id, Registration.PHOTO)
        await m.edit_message(f"Вы успешно вступили в фракцию «{name}»")
        await m.send_message("Отправьте фотографию своего персонажа", keyboard=Keyboard().get_json())
    else:
        await m.edit_message("Новая фракция установлена")
        await show_fields_edit(m.user_id, new=False)


@bot.on.private_message(StateRule(Registration.PHOTO), AttachmentTypeRule("photo"))
async def set_character(m: Message):
    if not m.attachments or m.attachments[0].type != m.attachments[0].type.PHOTO:
        await m.answer(messages.need_photo)
        return
    photo = await reload_image(m.attachments[0], f"data/photo{m.from_id}.jpg")
    await db.Form.update.values(photo=photo).where(
        and_(db.Form.user_id == m.from_id, db.Form.is_request.is_(True))
    ).gino.status()
    creating_form = await db.select([db.User.creating_form]).where(db.User.user_id == m.from_id).gino.scalar()
    if creating_form:
        states.set(m.from_id, Registration.WANT_DAUGHTER)
        keyboard = Keyboard().add(
            Text("Да", {"want_daughter": True}), KeyboardButtonColor.POSITIVE
        ).add(
            Text("Нет", {"want_daughter": False}), KeyboardButtonColor.NEGATIVE
        )
        await m.answer('Фото успешно установлено!\n\nОсновная анкета заполнена, хотите ли заполнить дополнительную '
                       'для получения статуса «Дочь❤»?', keyboard=keyboard)
    else:
        await m.answer("Новое значение установлено")
        await show_fields_edit(m.from_id, new=False)


@bot.on.private_message(StateRule(Registration.WANT_DAUGHTER), PayloadRule({"want_daughter": False}))
async def want_daughter(m: Message):
    creating_form = await db.select([db.User.creating_form]).where(db.User.user_id == m.from_id).gino.scalar()
    if creating_form:
        states.set(m.from_id, Registration.WAIT)
        await db.User.update.values(creating_form=False).where(db.User.user_id == m.from_id).gino.scalar()
        await m.answer(messages.form_ready, keyboard=Keyboard())
    else:
        states.set(m.from_id, Menu.MAIN)
        await db.User.update.values(editing_form=False).where(db.User.user_id == m.from_id).gino.scalar()
        await m.answer('Отредактированная анкета отправлена администрации', keyboard=await keyboards.main_menu(m.from_id),
                       is_notification=True)
    form_id = await db.select([db.Form.id]).where(db.Form.user_id == m.from_id).gino.scalar()
    user = await m.get_user()
    admins = await get_admin_ids()
    for admin_id in admins:
        form, photo = await loads_form(m.from_id, admin_id, is_request=True)
        if creating_form:
            await bot.api.messages.send(peer_id=admin_id, message=f'Пользователь [id{user.id}|{user.first_name} {user.last_name}] '
                                                                  f'заполнил анкету')
        else:
            await bot.api.messages.send(peer_id=admin_id,
                                        message=f'Пользователь [id{user.id}|{user.first_name} {user.last_name}] '
                                                f'перезаполнил ответы дочерей')
        await bot.api.messages.send(peer_id=admin_id, message=form, attachment=photo, keyboard=keyboards.create_accept_form(form_id))


@bot.on.private_message(StateRule(Registration.WANT_DAUGHTER), PayloadRule({"want_daughter": True}))
async def q1(m: Message | MessageEvent):
    reply = ('Как вы родились?\n\n'
                       '1) Родилась от матери - дочери\n'
                       '2) Искусственным оплодотворением\n'
                       '3) Клонированием или иным полностью искусственным способом\n\n'
                       'В сообщении укажите номер варианта ответа или нажмите кнопку')
    keyboard = Keyboard().add(
        Text('1) Родилась от матери - дочери'[:40], {'q': 1, 'a': 1}), KeyboardButtonColor.SECONDARY
    ).row().add(
        Text('2) Искусственным оплодотворением'[:40], {'q': 1, 'a': 2}), KeyboardButtonColor.SECONDARY
    ).row().add(
        Text('3) Клонированием или иным полностью искусственным способом'[:40], {'q': 1, 'a': 3}), KeyboardButtonColor.SECONDARY
    )
    if isinstance(m, Message):
        states.set(m.from_id, DaughterQuestions.Q1)
        await db.Form.update.values(status=2).where(db.Form.user_id == m.from_id).gino.status()
        await m.answer(reply, keyboard=keyboard)
    else:
        states.set(m.user_id, DaughterQuestions.Q1)
        await db.Form.update.values(status=2).where(db.Form.user_id == m.user_id).gino.status()
        await bot.api.messages.send(message=reply, keyboard=keyboard, peer_id=m.user_id)


@bot.on.private_message(StateRule(DaughterQuestions.Q1), NumericRule(max_number=3))
@bot.on.private_message(StateRule(DaughterQuestions.Q1), PayloadMapRule({'q': 1, 'a': int}))
async def q2(m: Message, value: int = None):
    if not m.payload:
        await db.Form.update.values(libido_bonus=db.Form.libido_bonus + value).where(db.Form.user_id == m.from_id).gino.scalar()
    else:
        await db.Form.update.values(libido_bonus=db.Form.libido_bonus + m.payload['a']).where(
            db.Form.user_id == m.from_id).gino.scalar()
    states.set(m.from_id, DaughterQuestions.Q2)
    keyboard = Keyboard().add(
        Text('1) Да. Она/они помогают себя контролировать'[:40], {'q': 2, 'a': 1}), KeyboardButtonColor.SECONDARY
    ).row().add(
        Text('2) Нет. У меня нет врождённых особенностей'[:40], {'q': 2, 'a': 2}), KeyboardButtonColor.SECONDARY
    ).row().add(
        Text('3)  Да. Она/они усиливают моё половое влечение.'[:40], {'q': 2, 'a': 3}),
        KeyboardButtonColor.SECONDARY
    )
    await m.answer('У вас есть врождённые особенности, оказывающее вторичное влияние на вашу половую систему?\n\n'
                   '1) Да. Она/они помогают себя контролировать\n'
                   '2) Нет. У меня нет врождённых особенностей\n'
                   '3) Да. Она/они усиливают моё половое влечение.', keyboard=keyboard)


@bot.on.private_message(StateRule(DaughterQuestions.Q2), NumericRule(max_number=3))
@bot.on.private_message(StateRule(DaughterQuestions.Q2), PayloadMapRule({'q': 2, 'a': int}))
async def q3(m: Message, value: int = None):
    if not m.payload:
        await db.Form.update.values(libido_bonus=db.Form.libido_bonus + value).where(db.Form.user_id == m.from_id).gino.scalar()
    else:
        await db.Form.update.values(libido_bonus=db.Form.libido_bonus + m.payload['a']).where(
            db.Form.user_id == m.from_id).gino.scalar()
    states.set(m.from_id, DaughterQuestions.Q3)
    keyboard = Keyboard().add(
        Text('1) Да. Она/они помогают себя контролировать'[:40], {'q': 3, 'a': 1}), KeyboardButtonColor.SECONDARY
    ).row().add(
        Text('2) Нет. У меня нет каких-либо модификаций такого рода'[:40], {'q': 3, 'a': 2}), KeyboardButtonColor.SECONDARY
    ).row().add(
        Text('3) Да. Она/они усиливают моё половое влечение'[:40], {'q': 3, 'a': 3}),
        KeyboardButtonColor.SECONDARY
    )
    await m.answer('Есть ли у вас приобретённые модификации (генетические или кибернетические), влияющие на контроль ваших физиологических потребностей? \n\n'
                   '1) Да. Она/они помогают себя контролировать\n'
                   '2) Нет. У меня нет каких-либо модификаций такого рода\n'
                   '3) Да. Она/они усиливают моё половое влечение\n', keyboard=keyboard)


@bot.on.private_message(StateRule(DaughterQuestions.Q3), NumericRule(max_number=3))
@bot.on.private_message(StateRule(DaughterQuestions.Q3), PayloadMapRule({'q': 3, 'a': int}))
async def q4(m: Message, value: int = None):
    if not m.payload:
        await db.Form.update.values(libido_bonus=db.Form.libido_bonus + value).where(db.Form.user_id == m.from_id).gino.scalar()
    else:
        await db.Form.update.values(libido_bonus=db.Form.libido_bonus + m.payload['a']).where(
            db.Form.user_id == m.from_id).gino.scalar()
    states.set(m.from_id, DaughterQuestions.Q4)
    keyboard = Keyboard().add(
        Text('1) Да. Она/они помогают сдерживаться какое-то время'[:40], {'q': 4, 'a': 1}), KeyboardButtonColor.SECONDARY
    ).row().add(
        Text('2) Да. Она/они мне не помогают в полной мере'[:40], {'q': 4, 'a': 2}), KeyboardButtonColor.SECONDARY
    ).row().add(
        Text('3) Нет. Я предпочитаю контролировать это естественным путём'[:40], {'q': 4, 'a': 3}),
        KeyboardButtonColor.SECONDARY
    )
    await m.answer('Используете ли вы какие-либо препараты или предметы для контроля ваших физиологических потребностей?\n\n'
                   '1) Да. Она/они помогают сдерживаться какое-то время\n'
                   '2) Да. Она/они мне не помогают в полной мере\n'
                   '3) Нет. Я предпочитаю контролировать это естественным путём', keyboard=keyboard)


@bot.on.private_message(StateRule(DaughterQuestions.Q4), NumericRule(max_number=3))
@bot.on.private_message(StateRule(DaughterQuestions.Q4), PayloadMapRule({'q': 4, 'a': int}))
async def q4(m: Message, value: int = None):
    if not m.payload:
        await db.Form.update.values(libido_bonus=db.Form.libido_bonus + value).where(
        db.Form.user_id == m.from_id).gino.scalar()
    else:
        await db.Form.update.values(libido_bonus=db.Form.libido_bonus + m.payload['a']).where(
            db.Form.user_id == m.from_id).gino.scalar()
    states.set(m.from_id, DaughterQuestions.Q5)
    keyboard = Keyboard().add(
        Text('1) Сдерживала их любыми доступным способами'[:40], {'q': 5, 'a': 1}), KeyboardButtonColor.SECONDARY
    ).row().add(
        Text('2) Действовала так, как скажут родители/учителя/учёные'[:40], {'q': 5, 'a': 2}), KeyboardButtonColor.SECONDARY
    ).row().add(
        Text('3) Пустила всё на самотёк'[:40], {'q': 5, 'a': 3}),
        KeyboardButtonColor.SECONDARY
    )
    await m.answer(
        'Вам от 13 до 16 лет. Как вы справлялись с первичными проявлениями ваших генетических особенностей, как Дочери?\n\n'
        '1) Сдерживала их любыми доступным способами\n'
        '2) Действовала так, как скажут родители/учителя/учёные\n'
        '3) Пустила всё на самотёк', keyboard=keyboard)


@bot.on.private_message(StateRule(DaughterQuestions.Q5), NumericRule(max_number=3))
@bot.on.private_message(StateRule(DaughterQuestions.Q5), PayloadMapRule({'q': 5, 'a': int}))
async def q4(m: Message, value: int = None):
    if not m.payload:
        await db.Form.update.values(subordination_bonus=db.Form.subordination_bonus + value).where(
        db.Form.user_id == m.from_id).gino.scalar()
    else:
        await db.Form.update.values(subordination_bonus=db.Form.subordination_bonus + m.payload['a']).where(
            db.Form.user_id == m.from_id).gino.scalar()
    states.set(m.from_id, DaughterQuestions.Q6)
    keyboard = Keyboard().add(
        Text('1) На боевую специальность'[:40], {'q': 6, 'a': 1}), KeyboardButtonColor.SECONDARY
    ).row().add(
        Text('2) На сложную техническую/медицинскую специальность'[:40], {'q': 6, 'a': 2}), KeyboardButtonColor.SECONDARY
    ).row().add(
        Text('3) На административную или иную специальность'[:40], {'q': 6, 'a': 3}),
        KeyboardButtonColor.SECONDARY
    )
    await m.answer(
        'Вы вступили в "высшие" заведения для вашей подготовки. На кого вас учат?\n\n'
        '1) На боевую специальность\n'
        '2) На сложную техническую/медицинскую специальность\n'
        '3) На административную или иную специальность', keyboard=keyboard)


@bot.on.private_message(StateRule(DaughterQuestions.Q6), NumericRule(max_number=3))
@bot.on.private_message(StateRule(DaughterQuestions.Q6), PayloadMapRule({'q': 6, 'a': int}))
async def q4(m: Message, value: int = None):
    if not m.payload:
        await db.Form.update.values(subordination_bonus=db.Form.subordination_bonus + value).where(
        db.Form.user_id == m.from_id).gino.scalar()
    else:
        await db.Form.update.values(subordination_bonus=db.Form.subordination_bonus + m.payload['a']).where(
            db.Form.user_id == m.from_id).gino.scalar()
    states.set(m.from_id, DaughterQuestions.Q7)
    keyboard = Keyboard().add(
        Text('1) Рутинно. Удовольствие получу лишь в процессе соития, а до него только при настоящем сближении с целью'[:40], {'q': 7, 'a': 1}), KeyboardButtonColor.SECONDARY
    ).row().add(
        Text('2) Не без удовольствия. Особенно если цель вам по нраву'[:40], {'q': 7, 'a': 2}), KeyboardButtonColor.SECONDARY
    ).row().add(
        Text('3) С удовольствием. Ведь для вас это очередной повод чтобы «развлечься»'[:40], {'q': 7, 'a': 3}),
        KeyboardButtonColor.SECONDARY
    )
    await m.answer(
        'После обучения в спец. ВУЗе вас направили на «стажировку». Вы получаете своё первое задание, например, по соблазнению цели. Как вы отнесётесь к его выполнению?\n\n'
        '1) Рутинно. Удовольствие получу лишь в процессе соития, а до него только при настоящем сближении с целью\n'
        '2) Не без удовольствия. Особенно если цель вам по нраву\n'
        '3) С удовольствием. Ведь для вас это очередной повод чтобы «развлечься»', keyboard=keyboard)


@bot.on.private_message(StateRule(DaughterQuestions.Q7), NumericRule(max_number=3))
@bot.on.private_message(StateRule(DaughterQuestions.Q7), PayloadMapRule({'q': 7, 'a': int}))
async def q4(m: Message, value: int = None):
    if not m.payload:
        await db.Form.update.values(subordination_bonus=db.Form.subordination_bonus + value).where(
        db.Form.user_id == m.from_id).gino.scalar()
    else:
        await db.Form.update.values(subordination_bonus=db.Form.subordination_bonus + m.payload['a']).where(
            db.Form.user_id == m.from_id).gino.scalar()
    states.set(m.from_id, DaughterQuestions.Q8)
    keyboard = Keyboard().add(
        Text('1) Трудиться ради блага Империи'[:40],
             {'q': 8, 'a': 1}), KeyboardButtonColor.SECONDARY
    ).row().add(
        Text('2) Служить во благо своей фракции'[:40], {'q': 8, 'a': 2}), KeyboardButtonColor.SECONDARY
    ).row().add(
        Text('3) Жить ради себя и своих прихотей'[:40], {'q': 8, 'a': 3}),
        KeyboardButtonColor.SECONDARY
    )
    await m.answer(
        'Какова ваша цель, как дочери?\n\n'
        '1) Трудиться ради блага Империи\n'
        '2) Служить во благо своей фракции\n'
        '3) Жить ради себя и своих прихотей', keyboard=keyboard)


@bot.on.private_message(StateRule(DaughterQuestions.Q8), NumericRule(max_number=3))
@bot.on.private_message(StateRule(DaughterQuestions.Q8), PayloadMapRule({'q': 8, 'a': int}))
async def q4(m: Message, value: int = None):
    if not m.payload:
        await db.Form.update.values(subordination_bonus=db.Form.subordination_bonus + value).where(
        db.Form.user_id == m.from_id).gino.scalar()
    else:
        await db.Form.update.values(subordination_bonus=db.Form.subordination_bonus + m.payload['a']).where(
            db.Form.user_id == m.from_id).gino.scalar()
    fraction_id, l_bonus, s_bonus = await db.select([db.Form.fraction_id, db.Form.libido_bonus, db.Form.subordination_bonus]).where(db.Form.user_id == m.from_id).gino.first()
    l_multiplier, s_multiplier = await db.select([db.Fraction.libido_koef, db.Fraction.subordination_koef]).where(db.Fraction.id == fraction_id).gino.first()
    l_level = min(100, max(0, int(2 + 2 * l_multiplier + l_bonus)))
    s_level = min(100, max(0, int(2 + 2 * s_multiplier + s_bonus)))
    await db.Form.update.values(subordination_level=s_level, libido_level=l_level).where(db.Form.user_id == m.from_id).gino.scalar()
    await want_daughter(m)
