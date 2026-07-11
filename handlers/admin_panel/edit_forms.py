"""
Модуль для редактирования анкет пользователей администратором.
Содержит функции для изменения полей анкет, включая фото, профессии, статусы и другие параметры.
"""

import asyncio
import datetime

from vkbottle.bot import Message
from vkbottle.dispatch.rules.base import PayloadRule
from vkbottle import Keyboard, Text, KeyboardButtonColor
from sqlalchemy import and_, func

import messages
import service.keyboards as keyboards
from loader import bot
from service.serializers import fields_admin as fields
from service.custom_rules import AdminRule, StateRule, NumericRule
from service.middleware import states
from service.states import Admin
from service.db_engine import db
<<<<<<< Updated upstream
from service.utils import loads_form, take_off_payments, reload_image, update_daughter_levels
=======
from service.utils import loads_form, take_off_payments, reload_image, update_daughter_levels, get_current_form_id
from handlers.public_menu.form import load_forms_page
>>>>>>> Stashed changes


@bot.on.private_message(StateRule(Admin.MENU), PayloadRule({"admin_menu": "edit_form"}), AdminRule())
async def edit_users_forms(m: Message):
    """
    Начало процесса редактирования анкет пользователей.

    Поиск анкеты для администрации теперь аналогичен пользовательскому: показывается
    тот же нумерованный список анкет (см. handlers.public_menu.form.load_forms_page),
    и можно выбрать анкету по индексу из списка, а не только по упоминанию/ссылке.
    """
    states.set(m.from_id, Admin.EDIT_FORMS)
    reply, keyboard = await load_forms_page(1)
    reply += ("\n\nОтправьте ссылку/айди/имя в игре/пересланное сообщение/упоминание участника, "
              "либо номер анкеты из списка, чтобы отредактировать её")
    await m.answer(reply, keyboard=keyboard)


@bot.on.private_message(StateRule(Admin.EDIT_FORMS), AdminRule())
async def search_form_for_edit(m: Message):
    """Поиск и отображение анкеты для редактирования — по номеру из списка либо по упоминанию/ссылке/имени"""
    from service.utils import get_mention_from_message

    user_id = await get_mention_from_message(m)
    if not user_id and m.text and m.text.isdigit():
        count = await db.select([func.count(db.Form.id)]).where(db.Form.is_request.is_(False)).gino.scalar()
        value = int(m.text)
        if 1 <= value <= count:
            user_id = await db.select([db.Form.user_id]).where(
                db.Form.is_request.is_(False)).order_by(db.Form.id.asc()).offset(value - 1).limit(1).gino.scalar()
    if not user_id:
        await m.answer(messages.not_form_id)
        return
    name = await db.select([db.Form.name]).where(
        and_(db.Form.user_id == user_id, db.Form.is_request.is_(False))).gino.scalar()
    if not name:
        await m.answer(messages.not_form_id)
        return
    form_id = await get_current_form_id(user_id)

    states.set(m.from_id, f"{Admin.SELECT_FIELDS}*{form_id}")
    # Загружаем анкету пользователя
    form, photo = await loads_form(user_id, m.from_id, form_id=form_id, absolute_params=True)
    await m.answer(form, photo)
    reply = messages.select_field
    for i, field in enumerate(fields):
        reply = f"{reply}{i + 1}. {field.name}\n"
    await m.answer(reply)


@bot.on.private_message(StateRule(Admin.SELECT_FIELDS), NumericRule(), AdminRule())
async def send_select_fields(m: Message, value: int = None):
    """Обработчик выбора поля для редактирования"""
    if value and not 0 < value <= len(fields):
        await m.answer("Указано неверное поле")
        return
    _, form_id = states.get(m.from_id).split("*")
    # Записываем в стейт название редактируемого поля из fields_admin
    states.set(m.from_id, f"{Admin.ENTER_FIELD_VALUE}*{form_id}*{fields[value - 1].state}")
    reply = messages.new_value_field.format(fields[value - 1].name)
    keyboard = None

    # Специальная обработка для разных типов полей
    if value == 2:  # Профессии
        professions = await db.select([db.Profession.name]).order_by(db.Profession.id.asc()).gino.all()
        for i, prof in enumerate(professions):
            reply = f"{reply}{i + 1}. {prof.name}\n"
    if value == 10:  # Ориентация
        keyboard = keyboards.orientations
    elif value == 15:  # Каюты
        cabins = await db.select([db.Cabins.name]).order_by(db.Cabins.id.asc()).gino.all()
        for i, cabin in enumerate(cabins):
            reply = f"{reply}{i + 1}. {cabin.name}\n"
    elif value == 16:  # Заморозка/разморозка
        keyboard = Keyboard().add(
            Text("Заморозить", {"freeze": True}), KeyboardButtonColor.NEGATIVE
        ).row().add(
            Text("Разморозить", {"freeze": False}), KeyboardButtonColor.POSITIVE
        )
    elif value == 17:  # Статусы
        statuses = await db.select([db.Status.name]).order_by(db.Status.id.asc()).gino.all()
        for i, status in enumerate(statuses):
            reply = f"{reply}{i + 1}. {status.name}\n"
    elif value == 18:  # Фракции
        fractions = await db.select([db.Fraction.name]).order_by(db.Fraction.id.asc()).gino.all()
        for i, fraction in enumerate(fractions):
            reply = f"{reply}{i + 1}. {fraction.name}\n"
    elif value == 25:  # Допуск к секретам: профессия
        professions = await db.select([db.Profession.name]).order_by(db.Profession.id.asc()).gino.all()
        reply += "Отправьте 0, чтобы снять допуск по профессии\n"
        for i, prof in enumerate(professions):
            reply = f"{reply}{i + 1}. {prof.name}\n"
    elif value == 26:  # Допуск к секретам: фракция
        fractions = await db.select([db.Fraction.name]).order_by(db.Fraction.id.asc()).gino.all()
        reply += "Отправьте 0, чтобы снять допуск по фракции\n"
        for i, fraction in enumerate(fractions):
            reply = f"{reply}{i + 1}. {fraction.name}\n"
    elif value == 27:  # Допуск к секретам: репутация
        reply += "\nЧисло действует только вместе с допуском по фракции (пункт выше)"
    await m.answer(reply, keyboard=keyboard)


@bot.on.private_message(StateRule(Admin.ENTER_FIELD_VALUE), AdminRule())
async def enter_field_value(m: Message):
    """Обработчик ввода нового значения для выбранного поля"""
    _, form_id, field = states.get(m.from_id).split("*")
    form_id = int(form_id)
    field = field.split('.')[1]
    user_id = await db.select([db.Form.user_id]).where(db.Form.id == form_id).gino.scalar()

    # Обработка разных типов полей
    if field == 'name':
        await db.Form.update.values(name=m.text).where(db.Form.id == form_id).gino.status()
        await db.Expeditor.update.values(name=m.text).where(db.Expeditor.form_id == form_id).gino.status()
    elif field == "photo":
        if not m.attachments:
            await m.answer(messages.need_photo)
            return
        user_id = await db.select([db.Form.user_id]).where(db.Form.id == form_id).gino.scalar()
        # Обновляем фото
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
        cabin_id, price = await db.select([db.Cabins.id, db.Cabins.cost]).order_by(db.Cabins.id.asc()).offset(
            value - 1).limit(1).gino.first()
        # Обновляем тип каюты и баланс
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
        profession_id = await db.select([db.Profession.id]).order_by(db.Profession.id.asc()).offset(
            value - 1).gino.scalar()
        await db.Form.update.values(profession=profession_id).where(db.Form.id == form_id).gino.status()
    elif field == "status":
        if not m.text.isdigit():
            await m.answer("Необходимо указать число")
            return
        value = int(m.text)
        status_id = await db.select([db.Status.id]).order_by(db.Status.id.asc()).offset(value - 1).gino.scalar()
        await db.Form.update.values(status=status_id).where(db.Form.id == form_id).gino.status()
    elif field == "edit_fraction":
        if not m.text.isdigit():
            await m.answer("Необходимо указать число")
            return
        value = int(m.text)
        fraction_id = await db.select([db.Fraction.id]).order_by(db.Fraction.id.asc()).offset(value - 1).gino.scalar()
        await db.Form.update.values(fraction_id=fraction_id).where(db.Form.id == form_id).gino.status()
    elif field == 'edit_level_subordination':
        if not m.text.isdigit():
            await m.answer("Необходимо указать число от 0 до 100")
            return
        value = int(m.text)
        if not 0 <= value <= 100:
            await m.answer("Число не входит в промежуток от 0 до 100")
            return
        await update_daughter_levels(user_id, subordination_level=value)
    elif field == 'edit_level_libido':
        if not m.text.isdigit():
            await m.answer("Необходимо указать число от 0 до 100")
            return
        value = int(m.text)
        if not 0 <= value <= 100:
            await m.answer("Число не входит в промежуток от 0 до 100")
            return
        await update_daughter_levels(user_id, libido_level=value)
    elif field == 'classified_profession_id':
        if not m.text.isdigit():
            await m.answer("Необходимо указать число")
            return
        value = int(m.text)
        profession_id = None
        if value != 0:
            profession_id = await db.select([db.Profession.id]).order_by(db.Profession.id.asc()).offset(
                value - 1).limit(1).gino.scalar()
        await db.Form.update.values(classified_profession_id=profession_id).where(db.Form.id == form_id).gino.status()
    elif field == 'classified_fraction_id':
        if not m.text.isdigit():
            await m.answer("Необходимо указать число")
            return
        value = int(m.text)
        fraction_id = None
        if value != 0:
            fraction_id = await db.select([db.Fraction.id]).order_by(db.Fraction.id.asc()).offset(
                value - 1).limit(1).gino.scalar()
        await db.Form.update.values(classified_fraction_id=fraction_id).where(db.Form.id == form_id).gino.status()
    else:
        # Обработка простых числовых полей
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
