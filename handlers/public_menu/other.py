from datetime import datetime, timedelta, timezone

from vkbottle.bot import Message
from vkbottle.dispatch.rules.base import PayloadRule
from vkbottle import Keyboard, Text, KeyboardButtonColor
from sqlalchemy import and_


import messages
from loader import bot
from service.custom_rules import StateRule
from service.states import Menu
import service.keyboards as keyboards
from service.middleware import states
from service.db_engine import db
from service.utils import reload_image


@bot.on.private_message(StateRule(Menu.MAIN), PayloadRule({"menu": "call_admin"}))
async def send_call_admin(m: Message):
    await m.answer(messages.call_admin)


@bot.on.private_message(StateRule(Menu.MAIN), PayloadRule({"menu": "book"}))
async def send_book(m: Message):
    states.set(m.from_id, Menu.WRITE_PETITION)
    keyboard = Keyboard().add(
        Text("Назад", {"book": "back"}), KeyboardButtonColor.NEGATIVE
    )
    await m.answer(messages.write_petition, keyboard=keyboard)


@bot.on.private_message(StateRule(Menu.WRITE_PETITION), PayloadRule({"book": "back"}))
async def back_from_write(m: Message):
    states.set(m.from_id, Menu.MAIN)
    keyboard = Keyboard().add(
        Text("Связь с администарцией", {"menu": "call_admin"}), KeyboardButtonColor.PRIMARY
    ).row().add(
        Text("Книга жалоб и предложений", {"menu": "book"}), KeyboardButtonColor.NEGATIVE
    ).row().add(
        Text("Назад", {"menu": "home"}), KeyboardButtonColor.NEGATIVE
    )
    await m.answer("Выберите раздел", keyboard=keyboard)


@bot.on.private_message(StateRule(Menu.WRITE_PETITION))
async def save_petition(m: Message):
    attachments = []
    if m.attachments:
        await m.answer("Загружаем вложения")
        for i, attach in enumerate(m.attachments):
            if attach.type == attach.type.PHOTO:
                attachment = await reload_image(attach, f"book{m.from_id}_{i}.jpg", delete=True)
                attachments.append(attachment)
    attachment_str = ",".join(attachments)
    name = await db.select([db.Form.name]).where(db.Form.user_id == m.from_id).gino.scalar()
    admins = [x[0] for x in await db.select([db.User.user_id]).where(db.User.admin > 0).gino.all()]
    day = datetime.now(timezone(timedelta(hours=3))).strftime("%d.%m.%Y %H:%M:%S")
    await bot.api.messages.send(peer_ids=admins, message=messages.petition_new.format(f"[id{m.from_id}|{name}]", m.text, day), attachment=attachment_str)
    states.set(m.from_id, Menu.MAIN)
    await m.answer(messages.petition_send, keyboard=await keyboards.main_menu(m.from_id))


@bot.on.private_message(PayloadRule({"menu": "quests and daylics"}), StateRule(Menu.MAIN))
@bot.on.private_message(PayloadRule({"menu": "quests and daylics"}), StateRule(Menu.SHOW_QUESTS))
@bot.on.private_message(PayloadRule({"menu": "quests and daylics"}), StateRule(Menu.DAYLICS))
@bot.on.private_message(PayloadRule({"daughter_quests": "back"}), StateRule(Menu.DAUGHTER_QUEST_MENU))
async def quests_or_daylics(m: Message):
    states.set(m.peer_id, Menu.MAIN)
    keyboard = (Keyboard().add(
        Text("Квесты", {"menu": "quests"}), KeyboardButtonColor.PRIMARY
    ).add(
        Text("Ежедневное задание", {"menu": "daylics"}), KeyboardButtonColor.PRIMARY
    ))
    status = await db.select([db.Form.status]).where(db.Form.user_id == m.from_id).gino.scalar()
    if status == 2:
        keyboard.row().add(Text('Квест для дочерей', {"menu": 'daughter_quests'}), KeyboardButtonColor.PRIMARY)
    keyboard.row().add(
        Text("Назад", {"menu": "home"}), KeyboardButtonColor.NEGATIVE
    )
    await m.answer("Выберите необходимый раздел", keyboard=keyboard)


@bot.on.private_message(PayloadRule({"menu": "staff"}), StateRule(Menu.MAIN))
async def staff(m: Message):
    keyboard = Keyboard().add(
        Text("Связь с администарцией", {"menu": "call_admin"}), KeyboardButtonColor.PRIMARY
    ).row().add(
        Text("Книга жалоб и предложений", {"menu": "book"}), KeyboardButtonColor.NEGATIVE
    ).row().add(
        Text("Назад", {"menu": "home"}), KeyboardButtonColor.NEGATIVE
    )
    await m.answer("Выберите раздел", keyboard=keyboard)
