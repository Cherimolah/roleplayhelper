import datetime

from vkbottle.bot import Message
from vkbottle.dispatch.rules.base import PayloadRule
from vkbottle import Keyboard, Text, KeyboardButtonColor

from loader import bot
from service.db_engine import db
from service.utils import get_current_form_id
from service.custom_rules import StateRule
from service.states import Menu
from service.middleware import states
from config import DATETIME_FORMAT
from service import keyboards

@bot.on.private_message(PayloadRule({"menu": "flights"}))
async def flight_info(m: Message):
    form_id = await get_current_form_id(m.from_id)
    activated_flight = await db.select([db.Form.activated_flight]).where(db.Form.id == form_id).gino.scalar()
    states.set(m.from_id, Menu.FLIGHTS)
    if not activated_flight:
        keyboard = Keyboard().add(
            Text("Назад", {"menu": "home"}), KeyboardButtonColor.NEGATIVE
        )
        await bot.write_msg(m.peer_id, "Сейчас у вас нет активного вылета", keyboard=keyboard)
        flights = await db.select([db.Flight.organizer, db.Flight.started_at]).where(db.Flight.started_at > datetime.datetime.now()).gino.all()
        if flights:
            reply = "Доступные вылеты на выбор:\n\n"
            for i, flight in enumerate(flights):
                user_id, name = await db.select([db.Form.user_id, db.Form.name]).where(db.Form.id == form_id).gino.first()
                reply = f"{reply}{i + 1}. Вылет от [id{user_id}|{name}]. Старт {flight.started_at.strftime(DATETIME_FORMAT)}\n"
            await bot.write_msg(m.peer_id, reply)
        else:
            await bot.write_msg(m.peer_id, "Сейчас нет доступных вылетов на выбор")
        admin_id = await db.select([db.User.admin]).where(db.User.user_id == m.from_id).gino.scalar()
        profession_id = await db.select([db.Form.profession]).where(db.Form.id == form_id).gino.scalar()
        if admin_id > 0 or profession_id == 21:
            keyboard = Keyboard().add(
                Text("Создать вылет", {"flight": "create"}), KeyboardButtonColor.POSITIVE
            ).row().add(
                Text("Назад", {"menu": "home"}), KeyboardButtonColor.NEGATIVE
            )
            await bot.write_msg(m.peer_id, "Вы можете создать новый вылет",
                                keyboard=keyboard)
            return
        return
    await bot.write_msg(m.peer_id, "Информация по активному вылету") #TODO


@bot.on.private_message(StateRule(Menu.FLIGHTS), PayloadRule({"flight": "create"}))
async def create_flight(m: Message):
    form_id = await get_current_form_id(m.from_id)
    flight = await db.Flight.create(organizer=form_id)
    states.set(m.from_id, f"{Menu.FLIGHT_DATE}*{flight.id}")
    await bot.write_msg(m.peer_id, "Укажите дату начала вылета в будущем. До этого времени будет идти набор участников\n"
                                   "Формат ДД.ММ.ГГГГ ЧЧ:ММ:СС", keyboard=Keyboard())


@bot.on.private_message(StateRule(Menu.FLIGHT_DATE, True))
async def set_flight_date(m: Message):
    flight_id = int(states.get(m.from_id).split("*")[1])
    try:
        started_at = datetime.datetime.strptime(m.text, DATETIME_FORMAT)
    except:
        await m.answer("Дата указана в неверном формате")
        return
    if started_at < datetime.datetime.now():
        await bot.write_msg(m.peer_id, "Дата начала вылета должна быть в будущем")
        return
    await db.Flight.update.values(started_at=started_at).where(db.Flight.id == flight_id).gino.status()
    states.set(m.from_id, Menu.MAIN)
    await m.answer("Вылет успешно создан", keyboard=await keyboards.main_menu(m.from_id))
