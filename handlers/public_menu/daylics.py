import datetime
import json

from vkbottle.bot import Message
from vkbottle.dispatch.rules.base import PayloadRule, PayloadMapRule
from vkbottle import Keyboard, Text, KeyboardButtonColor, Callback
from sqlalchemy import and_

from loader import bot
from service.custom_rules import StateRule
from service.states import Menu
from service.db_engine import db
from service.utils import get_current_form_id, parse_cooldown
from service.middleware import states
from config import ADMINS, OWNER


@bot.on.private_message(PayloadRule({"menu": "daylics"}), StateRule(Menu.MAIN))
async def send_daylics(m: Message):
    form_id = await get_current_form_id(m.from_id)
    deactivated = await db.select([db.Form.deactivated_daylic]).where(db.Form.id == form_id).gino.scalar()
    if deactivated > datetime.datetime.now():
        await bot.write_msg(m.from_id, "Вы не можете получать дейлики так как на вас перезарядка ещё "
                                       f"{parse_cooldown((deactivated - datetime.datetime.now()).total_seconds())}")
        return
    daylic_id = await db.select([db.Form.activated_daylic]).where(db.Form.id == form_id).gino.scalar()
    if not daylic_id:
        await bot.write_msg(m.from_id, "Сейчас нет доступного дейлика")
        return
    states.set(m.from_id, Menu.DAYLICS)
    daylic = await db.select([*db.Daylic]).where(db.Daylic.id == daylic_id).gino.first()
    keyboard = Keyboard().add(
        Text("Отправить отчёт о выполнении", {"daylic_ready": daylic_id}), KeyboardButtonColor.PRIMARY
    ).row().add(
        Text("Назад", {"menu": "quests and daylics"}), KeyboardButtonColor.NEGATIVE
    )
    await bot.write_msg(m.from_id, "Доступный дейлик:\n"
                                   f"{daylic.name}\n"
                                   f"{daylic.description}\n"
                                   f"Награда: {daylic.reward}\n"
                                   f"Кулдаун: {parse_cooldown(daylic.cooldown)}", keyboard=keyboard)


@bot.on.private_message(StateRule(Menu.DAYLICS), PayloadMapRule({"daylic_ready": int}))
async def send_ready_daylic(m: Message):
    daylic_id = json.loads(m.payload)['daylic_ready']
    form_id = await get_current_form_id(m.from_id)
    exist = await db.select([db.CompletedDaylic.id]).where(
        and_(db.CompletedDaylic.daylic_id == daylic_id, db.CompletedDaylic.form_id == form_id)
    ).gino.scalar()
    if exist:
        await bot.write_msg(m.from_id, "Вы уже отправили отчёт о выполненном дейлике, дождитесь, когда администрация "
                                       "его примет")
        return
    response = await db.CompletedDaylic.create(form_id=form_id, daylic_id=daylic_id)
    name = await db.select([db.Form.name]).where(db.Form.id == form_id).gino.scalar()
    daylic_name, reward = await db.select([db.Daylic.name, db.Daylic.reward]).where(db.Daylic.id == daylic_id).gino.first()
    keyboard = Keyboard(inline=True).add(
        Callback("Подтвердить", {"daylic_confirm": response.id}), KeyboardButtonColor.POSITIVE
    ).add(
        Callback("Отклонить", {"daylic_reject": response.id}), KeyboardButtonColor.NEGATIVE
    )
    await bot.write_msg(ADMINS + [OWNER], f"Отчёт игрока [id{m.from_id}|{name}] о выполненном дейлике {daylic_name}\n"
                                          f"Награда: {reward}", keyboard=keyboard)
    await bot.write_msg(m.from_id, f"Ваш отчёт о выполнении {daylic_name} отправлен администрации")

