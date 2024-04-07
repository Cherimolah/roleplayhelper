from typing import Tuple

from vkbottle.bot import Message, MessageEvent
from vkbottle.dispatch.rules.base import PayloadRule, PayloadMapRule
from vkbottle import Keyboard, Callback, KeyboardButtonColor, GroupEventType
from sqlalchemy import and_, func

import messages
from loader import bot, fields
from service.custom_rules import StateRule, NumericRule
from service.states import Menu
from service.utils import loads_form, get_mention_from_message, show_fields_edit
import service.keyboards as keyboards
from service.middleware import states
from service.db_engine import db


async def load_forms_page(page) -> Tuple[str, Keyboard]:
    data = await db.select([db.Form.user_id, db.Form.name]).where(db.Form.is_request.is_(False)).limit(15).offset((page - 1) * 15).order_by(db.Form.created_at.asc()).order_by(db.Form.id.asc()).gino.all()
    pages = (await db.select([func.count(db.Form.id)]).where(db.Form.is_request.is_(False)).gino.scalar()) // 15 + 1
    reply = f"Список анкет пользователей:\n\nСтраница {page}/{pages}\n\n"
    user_ids = [x[0] for x in data]
    names = [x[1] for x in data]
    user_names = [f"{x.first_name} {x.last_name}" for x in await bot.api.users.get(user_ids=user_ids)]
    data = zip(range(len(user_names)), user_ids, names, user_names)
    for i, user_id, name, user_name in data:
        reply += f"{(page - 1) * 15 + i + 1}. [id{user_id}|{user_name} / {name}]\n"
    reply += "\nДля просмотра анкеты отправьте номер из списка"
    reply += ("\n⚠ Вы можете отправить ссылку/айди/имя в игре/пересланное сообщение/упоминание участника, "
              "анкету которого вы хотите найти")
    if page == 1 and page == pages:
        keyboard = None
    else:
        keyboard = Keyboard(inline=True)
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
async def send_form(m: Message):
    form, photo = await loads_form(m.from_id)
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
@bot.on.private_message(StateRule(Menu.EDIT_FIELDS, True), PayloadRule({"form": "edit"}))
async def send_form_edit(m: Message, new=True):
    await show_fields_edit(m, new)


@bot.on.private_message(StateRule(Menu.SELECT_FIELD_EDIT_NUMBER), PayloadRule({"form_edit": "confirm"}))
async def confirm_edit_fields(m: Message):
    form_id = await db.select([db.Form.id]).where(and_(db.Form.user_id == m.from_id, db.Form.is_request.is_(True))).gino.scalar()
    form, photo = await loads_form(m.from_id, True)
    admins = [x[0] for x in await db.select([db.User.user_id]).where(db.User.admin > 0).gino.all()]
    await bot.api.messages.send(admins, form, photo, keyboard=keyboards.create_accept_form(form_id))
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


@bot.on.private_message(StateRule(Menu.SHOW_FORM))
async def search_user_form(m: Message):
    user_id = await get_mention_from_message(m)
    count = await db.select([func.count(db.Form.id)]).gino.scalar()
    if not user_id and (not m.text.isdigit() or int(m.text) < 1 or int(m.text) > count):
        await m.answer(messages.user_not_found)
        return
    if not user_id:
        # Try get by form index (not id)
        user_id = await db.select([db.Form.user_id]).offset(int(m.text) - 1).limit(1).gino.scalar()
    if not user_id:
        await m.answer(messages.user_not_found)
        return
    form, photo = await loads_form(user_id)
    keyboard = None
    admin = await db.select([db.User.admin]).where(db.User.user_id == m.from_id).gino.scalar()
    if admin:
        form_id = await db.select([db.Form.id]).where(db.Form.user_id == user_id).gino.scalar()
        keyboard = Keyboard(inline=True).add(
            Callback("Удалить анкету", {"form_delete": form_id}), KeyboardButtonColor.NEGATIVE
        )
    await m.answer(form, attachment=photo, keyboard=keyboard)
