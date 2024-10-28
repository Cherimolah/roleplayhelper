from typing import List, Tuple

from vkbottle.bot import Message
from vkbottle.dispatch.rules.base import PayloadRule, PayloadMapRule
from vkbottle import Keyboard, Text, KeyboardButtonColor


import messages
import service.keyboards as keyboards
from loader import bot
from service.custom_rules import AdminRule, StateRule, UserSpecified, ManyUsersSpecified
from service.middleware import states
from service.states import Admin
from service.db_engine import db


@bot.on.private_message(StateRule(Admin.MENU), PayloadRule({"admin_menu": "present_reward"}), AdminRule())
async def give_reward(m: Message):
    states.set(m.from_id, Admin.ENTER_USER_REWARD)
    keyboard = Keyboard().add(
        Text("Назад", {"give_reward": "back"}), KeyboardButtonColor.NEGATIVE
    )
    await m.answer(messages.enter_user_reward, keyboard=keyboard)


@bot.on.private_message(StateRule(Admin.ENTER_USER_REWARD), AdminRule(), UserSpecified(Admin.ENTER_AMOUNT_REWARD), ManyUsersSpecified())
async def user_reward(m: Message, forms: List[Tuple[int, int]] = None, form: Tuple[int, int] = None):
    if forms:
        forms_state = "*".join([str(x[0]) for x in forms])
        states.set(m.from_id, f"{Admin.ENTER_AMOUNT_REWARD}*{forms_state}")
    else:
        states.set(m.from_id, f"{Admin.ENTER_AMOUNT_REWARD}*{form[0]}")
    await m.answer(messages.enter_amount_reward)


@bot.on.private_message(StateRule(Admin.ENTER_AMOUNT_REWARD), AdminRule(), ManyUsersSpecified())
async def set_amount_reward(m: Message, forms: List[Tuple[int, int]]):
    try:
        amount = int(m.text)
    except ValueError:
        await m.answer("Необходимо ввести число")
        return
    forms_state = "*".join([str(x[0]) for x in forms])
    states.set(m.from_id, f"{Admin.CONFIRM_REWARD}*{forms_state}")
    keyboard = Keyboard().add(
        Text("Подтвердить", {"reward": amount}), KeyboardButtonColor.POSITIVE
    ).row().add(
        Text("Отклонить", {"reward": "decline"}), KeyboardButtonColor.NEGATIVE
    )
    form_ids = [x[0] for x in forms]
    user_ids = [x[1] for x in forms]
    names = [x[0] for x in await db.select([db.Form.name]).where(db.Form.id.in_(form_ids)).gino.all()]
    mentions = "\n".join([f"[id{user_id}|{name}]" for user_id, name in zip(user_ids, names)])
    await m.answer(messages.confirm_reward.format(amount, mentions), keyboard=keyboard)


@bot.on.private_message(StateRule(Admin.CONFIRM_REWARD), PayloadMapRule({"reward": int}), ManyUsersSpecified(), AdminRule())
async def accept_reward(m: Message, forms: List[Tuple[int, int]]):
    form_ids = [x[0] for x in forms]
    user_ids = [x[1] for x in forms]
    amount = int(m.payload['reward'])
    await db.Form.update.values(balance=db.Form.balance + amount).where(db.Form.id.in_(form_ids)).gino.status()
    names = [x[0] for x in await db.select([db.Form.name]).where(db.Form.id.in_(form_ids)).gino.all()]
    states.set(m.from_id, Admin.MENU)
    mentions = "\n".join([f"[id{user_id}|{name}]" for user_id, name in zip(user_ids, names)])
    await m.answer(messages.reward_accept.format(amount, mentions),
                        keyboard=keyboards.admin_menu)
    reply = f"Вам выдан{'а награда' if amount > 0 else ' штраф'} в размере {abs(amount)}"
    await bot.api.messages.send(peer_ids=user_ids, message=reply, is_notification=True)


@bot.on.private_message(StateRule(Admin.CONFIRM_REWARD), PayloadRule({"reward": "decline"}), AdminRule())
async def decline_reward(m: Message):
    states.set(m.from_id, Admin.MENU)
    await m.answer(messages.admin_menu, keyboard=keyboards.admin_menu)
