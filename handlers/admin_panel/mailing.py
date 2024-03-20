import asyncio
import datetime
import time

from vkbottle.bot import Message
from vkbottle.dispatch.rules.base import PayloadRule
from vkbottle import Keyboard, Text, KeyboardButtonColor

import messages
import service.keyboards as keyboards
from loader import bot
from service.custom_rules import AdminRule, StateRule
from service.middleware import states
from service.states import Admin
from service.db_engine import db
from service.utils import send_mailing
from config import DATETIME_FORMAT


@bot.on.private_message(StateRule(Admin.MENU), PayloadRule({"admin_menu": "mailing"}), AdminRule())
async def write_new_mailing(m: Message):
    states.set(m.from_id, Admin.WRITE_MAILING)
    keyboard = Keyboard().add(
        Text("Назад", {"mailing": "back"}), KeyboardButtonColor.NEGATIVE
    )
    await bot.write_msg(m.peer_id, messages.write_mail, keyboard=keyboard)


@bot.on.private_message(StateRule(Admin.WRITE_MAILING), AdminRule())
async def create_mailing(m: Message):
    message = (await bot.api.messages.get_by_id(m.id)).items[0]
    mailing = await db.Mailings.create(message_id=message.id)
    keyboard = Keyboard().add(
        Text("Разослать сейчас", {"mailing": "send_now"}), KeyboardButtonColor.NEGATIVE
    )
    states.set(m.from_id, f"{Admin.TIME_MAILING}*{mailing.id}")
    await bot.write_msg(m.peer_id, messages.mailing_created, keyboard=keyboard)


@bot.on.private_message(StateRule(Admin.TIME_MAILING, True), PayloadRule({"mailing": "send_now"}), AdminRule())
async def send_now_mailing(m: Message):
    mailing_id = int(states.get(m.from_id).split("*")[1])
    message_id = await db.select([db.Mailings.message_id]).where(db.Mailings.id == mailing_id).gino.first()
    user_ids = [x[0] for x in await db.select([db.User.user_id]).gino.all()]
    states.set(m.from_id, Admin.MENU)
    await bot.write_msg(m.peer_id, messages.send_mailing, keyboard=keyboards.admin_menu)
    for i in range(0, len(user_ids), 100):
        await bot.api.messages.send(peer_ids=user_ids[i:i+100], forward_messages=message_id, random_id=0)
    await db.Mailings.delete.where(db.Mailings.id == mailing_id).gino.status()
    await bot.write_msg(m.peer_id, messages.sent_mailing)


@bot.on.private_message(StateRule(Admin.TIME_MAILING, True), AdminRule())
async def send_deferred_mailing(m: Message):
    try:
        day = datetime.datetime.strptime(m.text, DATETIME_FORMAT)
    except:
        await bot.write_msg(m.peer_id, messages.error_date)
        return
    if day < datetime.datetime.now():
        await bot.write_msg(m.peer_id, messages.date_is_out)
        return
    mailing_id = int(states.get(m.from_id).split("*")[1])
    await db.Mailings.update.values(send_at=day).where(db.Mailings.id == mailing_id).gino.status()
    message_id = await db.select([db.Mailings.message_id]).where(
        db.Mailings.id == mailing_id).gino.first()
    unixtime = time.mktime(day.timetuple())
    states.set(m.from_id, Admin.MENU)
    await bot.write_msg(m.peer_id, messages.deferred_mailing.format(day.strftime(DATETIME_FORMAT)),
                        keyboard=keyboards.admin_menu)
    asyncio.get_event_loop().create_task(send_mailing(unixtime - time.time(), message_id, mailing_id))
