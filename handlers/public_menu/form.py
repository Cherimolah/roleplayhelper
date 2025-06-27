from typing import Tuple

from vkbottle.bot import Message, MessageEvent
from vkbottle.dispatch.rules.base import PayloadRule, PayloadMapRule
from vkbottle import Keyboard, Callback, KeyboardButtonColor, GroupEventType, Text
from sqlalchemy import and_, func

import messages
from loader import bot
from service.serializers import fields
from service.custom_rules import StateRule, NumericRule
from service.states import Menu
from service.utils import (loads_form, get_mention_from_message, show_fields_edit, soft_divide, page_fractions,
                           parse_reputation)
import service.keyboards as keyboards
from service.middleware import states
from service.db_engine import db


async def load_forms_page(page) -> Tuple[str, Keyboard]:
    data = await db.select([db.Form.user_id, db.Form.name]).where(db.Form.is_request.is_(False)).limit(15).offset((page - 1) * 15).order_by(db.Form.created_at.asc()).order_by(db.Form.id.asc()).gino.all()
    count = (await db.select([func.count(db.Form.id)]).where(db.Form.is_request.is_(False)).gino.scalar())
    if count % 15 == 0:
        pages = count // 15
    else:
        pages = count // 15 + 1
    reply = f"Список анкет пользователей:\n\n"
    user_ids = [x[0] for x in data]
    names = [x[1] for x in data]
    user_names = [f"{x.first_name} {x.last_name}" for x in await bot.api.users.get(user_ids=user_ids)]
    data = list(zip(range(len(user_names)), user_ids, names, user_names))
    for i, user_id, name, user_name in data:
        reply += f"{(page - 1) * 15 + i + 1}. [id{user_id}|{user_name} / {name}]\n"
    reply += "\nДля просмотра анкеты отправьте номер из списка"
    reply += ("\n⚠ Вы можете отправить ссылку/айди/имя в игре/пересланное сообщение/упоминание участника, "
              "анкету которого вы хотите найти")
    if page == 1 and page == pages:
        keyboard = None
    else:
        keyboard = Keyboard(inline=True)
        reply += f"\n\nСтраница {page}/{pages}"
    if page > 1:
        keyboard.add(
            Callback("<-", {"forms_page": page - 1}), KeyboardButtonColor.PRIMARY
        )
    if pages > page:
        keyboard.add(
            Callback("->", {"forms_page": page + 1}), KeyboardButtonColor.PRIMARY
        )
    return reply, keyboard


@bot.on.private_message(PayloadRule({"menu": "form"}), StateRule(Menu.MAIN))
@bot.on.private_message(StateRule(Menu.EDIT_FORM), PayloadRule({"form_edit": "back"}))
@bot.on.private_message(PayloadRule({"cabins_menu": "back"}), StateRule(Menu.CABINS_MENU))
async def send_form(m: Message):
    form, photo = await loads_form(m.from_id, m.from_id)
    states.set(m.from_id, Menu.SHOW_FORM)
    await m.answer(f"Ваша анкета:\n\n{form}", attachment=photo, keyboard=keyboards.form_activity)


@bot.on.private_message(PayloadRule({"form": "search"}), StateRule(Menu.SHOW_FORM))
async def search_form(m: Message):
    reply, keyboard = await load_forms_page(1)
    await m.answer(reply, keyboard=keyboard)


@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent, PayloadMapRule({"forms_page": int}))
async def map_form(m: MessageEvent):
    reply, keyboard = await load_forms_page(m.payload['forms_page'])
    await m.edit_message(message=reply, keyboard=keyboard.get_json())


@bot.on.private_message(StateRule(Menu.SHOW_FORM), PayloadRule({"form": "edit"}))
@bot.on.private_message(StateRule(Menu.EDIT_FIELDS), PayloadRule({"form": "edit"}))
async def send_form_edit(m: Message, new=True):
    await show_fields_edit(m.from_id, new)


@bot.on.private_message(StateRule(Menu.SELECT_FIELD_EDIT_NUMBER), PayloadRule({"form_edit": "confirm"}))
async def confirm_edit_fields(m: Message):
    form_id = await db.select([db.Form.id]).where(and_(db.Form.user_id == m.from_id, db.Form.is_request.is_(True))).gino.scalar()
    form, photo = await loads_form(m.from_id, m.from_id, True)
    admins = [x[0] for x in await db.select([db.User.user_id]).where(db.User.admin > 0).gino.all()]
    await bot.api.messages.send(peer_ids=admins, message=form, attachment=photo, keyboard=keyboards.create_accept_form(form_id))
    states.set(m.from_id, Menu.MAIN)
    await db.User.update.values(editing_form=False).where(db.User.user_id == m.from_id).gino.scalar()
    await m.answer("Новая версия анкеты успешно отправлена на проверку")
    await m.answer("Главное меню", keyboard=await keyboards.main_menu(m.from_id))


@bot.on.private_message(StateRule(Menu.SELECT_FIELD_EDIT_NUMBER), PayloadRule({"form_edit": "decline"}))
async def decline_edit_fields(m: Message):
    await db.User.update.values(editing_form=False).where(db.User.user_id == m.from_id).gino.scalar()
    await db.Form.delete.where(and_(db.Form.user_id == m.from_id, db.Form.is_request.is_(True))).gino.status()
    await m.answer("Изменения отклонены")
    await send_form(m)


@bot.on.private_message(StateRule(Menu.SELECT_FIELD_EDIT_NUMBER), NumericRule())
async def select_field_edit(m: Message, value: int = None):
    if not 1 <= value <= len(fields):
        return "Номер поля неверный"
    states.set(m.from_id, fields[value-1].state)
    field = fields[value-1].name
    if field == "Должность":
        professions = await db.select([db.Profession.name]).where(db.Profession.special.is_(False)).gino.all()
        reply = "Выберите профессию\n\n"
        for i, prof in enumerate(professions):
            reply = f"{reply}{i + 1}. {prof.name}\n"
        await m.answer(reply, keyboard=keyboards.another_profession)
        return
    elif field == "Сексуальная ориентация":
        await m.answer("Выберите сексуальную ориентацию", keyboard=keyboards.orientations)
        return
    elif field == "Фракция":
        reply, kb, photo = await page_fractions(1)
        await m.answer(reply, keyboard=kb, attachment=photo)
    else:
        await m.answer(f"Введите новое значение для поля {fields[value-1].name}:")


@bot.on.private_message(PayloadRule({"form": "cabins"}), StateRule(Menu.SHOW_FORM))
async def form_cabins(m: Message):
    decor_slots = await db.select([db.Cabins.decor_slots]).select_from(
        db.Form.join(db.Cabins, db.Form.cabin_type == db.Cabins.id)
    ).where(db.Form.user_id == m.from_id).gino.scalar()
    func_slots = await db.select([db.Cabins.functional_slots]).select_from(
        db.Form.join(db.Cabins, db.Form.cabin_type == db.Cabins.id)
    ).where(db.Form.user_id == m.from_id).gino.scalar()
    decor = await db.select([db.Decor.name]).select_from(
        db.UserDecor.join(db.Decor, db.Decor.id == db.UserDecor.decor_id)
    ).where(and_(db.UserDecor.user_id == m.from_id, db.Decor.is_func.is_(False))).order_by(db.UserDecor.id.asc()).gino.all()
    func_products = await db.select([db.Decor.name]).select_from(
        db.UserDecor.join(db.Decor, db.Decor.id == db.UserDecor.decor_id)
    ).where(and_(db.UserDecor.user_id == m.from_id, db.Decor.is_func.is_(True))).order_by(db.UserDecor.id.asc()).gino.all()
    reply = f"Информация по прокачке номера:\n\nДекор\nСлотов: {len(decor)}/{decor_slots}\n"
    for i, decor in enumerate(decor):
        reply = f"{reply}{i + 1}. {decor.name}\n"
    reply += "\n"
    reply += f"Функциональные товары\nСлотов: {len(func_products)}/{func_slots}\n"
    for i, func_slot in enumerate(func_products):
        reply = f"{reply}{i + 1}. {func_slot.name}\n"
    states.set(m.from_id, Menu.CABINS_MENU)
    await m.answer(reply, keyboard=keyboards.cabins_menu)


@bot.on.private_message(PayloadRule({"cabins": "decor"}), StateRule(Menu.CABINS_MENU))
@bot.on.private_message(PayloadRule({"cabins": "func_products"}), StateRule(Menu.CABINS_MENU))
async def cabins_decor(m: Message):
    is_func = m.payload['cabins'] == "func_products"
    decor = await db.select([*db.Decor]).select_from(
        db.UserDecor.join(db.Decor, db.Decor.id == db.UserDecor.decor_id)
    ).where(and_(db.UserDecor.user_id == m.from_id, db.Decor.is_func.is_(is_func))).order_by(db.UserDecor.id.asc()).limit(1).gino.first()
    if not decor:
        return "На данный момент у вас нет декора"
    count = await db.select([func.count(db.UserDecor.id)]).select_from(
        db.UserDecor.join(db.Decor, db.Decor.id == db.UserDecor.decor_id)
    ).where(and_(db.UserDecor.user_id == m.from_id, db.Decor.is_func.is_(is_func))).gino.scalar()
    kb = Keyboard(inline=True)
    if count > 1:
        kb.add(
            Callback("->", {"decor_form_page": 2, "is_func": is_func}), KeyboardButtonColor.SECONDARY
        ).row()
    kb.add(
        Callback("Удалить", {"decor_form_delete": 1, "is_func": is_func}), KeyboardButtonColor.NEGATIVE
    )
    reply = (f"Слот 1/{count}\n"
             f"Название: {decor.name}\n"
             f"Цена: {decor.price}\n"
             f"Описание: {decor.description}\n")
    if is_func:
        reply += f"Увеличивает стоимость ренты на: {soft_divide(decor.price, 10)}"
    await m.answer(reply, keyboard=kb, attachment=decor.photo)


@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent, PayloadMapRule({"decor_form_page": int, "is_func": bool}))
async def decor_form_page(m: MessageEvent):
    page = int(m.payload['decor_form_page'])
    is_func = m.payload['is_func']
    decor = await db.select([*db.Decor]).select_from(
        db.UserDecor.join(db.Decor, db.Decor.id == db.UserDecor.decor_id)
    ).where(and_(db.UserDecor.user_id == m.user_id, db.Decor.is_func.is_(is_func))).order_by(db.UserDecor.id.asc()).offset(page - 1).limit(1).gino.first()
    count = await db.select([func.count(db.UserDecor.id)]).select_from(
        db.UserDecor.join(db.Decor, db.Decor.id == db.UserDecor.decor_id)
    ).where(and_(db.UserDecor.user_id == m.user_id, db.Decor.is_func.is_(is_func))).gino.scalar()
    kb = Keyboard(inline=True)
    if page > 1:
        kb.add(
            Callback("<-", {"decor_form_page": page - 1, "is_func": is_func}), KeyboardButtonColor.SECONDARY
        )
    if count > page:
        kb.add(
            Callback("->", {"decor_form_page": page + 1, "is_func": is_func}), KeyboardButtonColor.SECONDARY
        )
    kb.row()
    kb.add(
        Callback("Удалить", {"decor_form_delete": page, "is_func": is_func}), KeyboardButtonColor.NEGATIVE
    )
    reply = (f"Слот 1/{count}\n"
             f"Название: {decor.name}\n"
             f"Цена: {decor.price}\n"
             f"Описание: {decor.description}\n")
    if is_func:
        reply += f"Увеличивает стоимость ренты на: {soft_divide(decor.price, 10)}"
    await m.edit_message(reply, keyboard=kb.get_json(), attachment=decor.photo)


@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent, PayloadMapRule({"decor_form_delete": int, "is_func": bool}))
async def delete_decor(m: MessageEvent):
    page = int(m.payload['decor_form_delete'])
    is_func = m.payload['is_func']
    user_decor_id, decor_id = await db.select([db.UserDecor.id, db.UserDecor.decor_id]).where(
        and_(db.UserDecor.user_id == m.user_id, db.Decor.is_func.is_(is_func))).order_by(db.UserDecor.id.asc()).offset(page - 1).limit(1).gino.first()
    decor_name = await db.select([db.Decor.name]).where(db.Decor.id == decor_id).gino.scalar()
    await db.UserDecor.delete.where(db.UserDecor.id == user_decor_id).gino.status()
    admins = [x[0] for x in await db.select([db.User.user_id]).where(db.User.admin > 0).gino.all()]
    user = (await bot.api.users.get(user_id=m.user_id))[0]
    name = await db.select([db.Form.name]).where(db.Form.user_id == m.user_id).gino.scalar()
    await bot.api.messages.send(peer_ids=admins,
                                message=f"Пользователь [id{m.user_id}|{user.first_name} {user.last_name} / {name}] "
                                        f"удалил {'декор' if not is_func else 'функциональный товар'} «{decor_name}»")
    await m.edit_message(f"{'Декор' if not is_func else 'Функциональный товар'} «{decor_name}» был удалён из вашей каюты!")


@bot.on.private_message(PayloadRule({"form": "reputation"}), StateRule(Menu.SHOW_FORM))
async def reputation_form(m: Message):
    reputations = await db.get_reputations(m.from_id)
    reply = "Список ваших репутаций:\n\n"
    for fraction_id, reputation in reputations:
        fraction_name = await db.select([db.Fraction.name]).where(db.Fraction.id == fraction_id).gino.scalar()
        reputation_level = parse_reputation(reputation)
        reply += f"{fraction_name}: {reputation_level}"
    await m.answer(reply)


@bot.on.private_message(StateRule(Menu.SHOW_FORM))
async def search_user_form(m: Message):
    user_id = await get_mention_from_message(m)
    count = await db.select([func.count(db.Form.id)]).gino.scalar()
    if not user_id and (not m.text.isdigit() or int(m.text) < 1 or int(m.text) > count):
        await m.answer(messages.user_not_found)
        return
    if not user_id:
        # Try get by form index (not id)
        user_id = await db.select([db.Form.user_id]).where(db.Form.is_request.is_(False)).order_by(db.Form.created_at.asc()).order_by(db.Form.id.asc()).offset(int(m.text) - 1).limit(1).gino.scalar()
    if not user_id:
        await m.answer(messages.user_not_found)
        return
    form, photo = await loads_form(user_id, m.from_id)
    keyboard = None
    admin = await db.select([db.User.admin]).where(db.User.user_id == m.from_id).gino.scalar()
    if admin:
        form_id = await db.select([db.Form.id]).where(db.Form.user_id == user_id).gino.scalar()
        keyboard = Keyboard(inline=True).add(
            Text("Репутация", {"form_reputation": user_id}), KeyboardButtonColor.PRIMARY
        ).row().add(
            Callback("Удалить анкету", {"form_delete": form_id}), KeyboardButtonColor.NEGATIVE
        )
    await m.answer(form, attachment=photo, keyboard=keyboard)
