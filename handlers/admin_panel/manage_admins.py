from vkbottle.bot import Message
from vkbottle.dispatch.rules.base import PayloadRule, PayloadMapRule
from vkbottle import Keyboard, Text, KeyboardButtonColor

import messages
import service.keyboards as keyboards
from loader import bot
from service.custom_rules import AdminRule, StateRule
from service.middleware import states
from service.states import Admin
from service.db_engine import db
from service.utils import get_mention_from_message


@bot.on.private_message(StateRule(Admin.SELECT_MANAGE_ADMINS), PayloadRule({"manage_admins": "add_admin"}))
@bot.on.private_message(StateRule(Admin.ENTER_OLD_ADMIN_ID), PayloadRule({"manage_admins": "add_admin"}))
@bot.on.private_message(StateRule(Admin.ENTER_NEW_ADMIN_ID), PayloadRule({"manage_admins": "add_admin"}))
async def enter_new_admin_id(m: Message):
    states.set(m.from_id, Admin.ENTER_NEW_ADMIN_ID)
    await m.answer(messages.enter_new_admin_id)


@bot.on.private_message(StateRule(Admin.ENTER_NEW_ADMIN_ID), AdminRule())
async def ask_new_admin(m: Message):
    user_id = await get_mention_from_message(m)
    user = await bot.api.users.get(user_id)
    if not user_id:
        await m.answer(messages.user_not_found)
        return
    keyboard = Keyboard().add(
        Text("Подтвердить", {"new_admin": user_id}), KeyboardButtonColor.POSITIVE
    ).row().add(
        Text("Отклонить", {"new_admin": "decline"}), KeyboardButtonColor.NEGATIVE
    )
    states.set(m.from_id, Admin.CONFIRM_NEW_ADMIN_ID)
    await m.answer(messages.confirm_new_admin.format(f"[id{user[0].id}|{user[0].first_name} {user[0].last_name}]"),
                        keyboard=keyboard)


@bot.on.private_message(StateRule(Admin.CONFIRM_NEW_ADMIN_ID), PayloadRule({"new_admin": "decline"}), AdminRule())
async def cancel_new_admin(m: Message):
    states.set(m.from_id, Admin.ENTER_NEW_ADMIN_ID)
    await m.answer(messages.enter_new_admin_id, keyboard=keyboards.manage_admins)


@bot.on.private_message(StateRule(Admin.CONFIRM_NEW_ADMIN_ID), PayloadMapRule({"new_admin": int}), AdminRule())
async def add_new_admin(m: Message):
    user_id = m.payload['new_admin']
    await db.User.update.values(admin=1).where(db.User.user_id == int(user_id)).gino.status()
    states.set(m.from_id, Admin.SELECT_MANAGE_ADMINS)
    user = await bot.api.users.get(user_id)
    await m.answer(messages.new_admin.format(f"[id{user[0].id}|{user[0].first_name} {user[0].last_name}]"))
    await m.answer(messages.manage_admins, keyboard=keyboards.manage_admins)


@bot.on.private_message(StateRule(Admin.SELECT_MANAGE_ADMINS), PayloadRule({"manage_admins": "delete_admins"}))
async def delete_old_admin(m: Message):
    states.set(m.from_id, Admin.ENTER_OLD_ADMIN_ID)
    await m.answer(messages.enter_old_admin)


@bot.on.private_message(StateRule(Admin.ENTER_OLD_ADMIN_ID), AdminRule())
@bot.on.private_message(StateRule(Admin.ENTER_OLD_ADMIN_ID), PayloadRule({"manage_admins": "add_admin"}))
@bot.on.private_message(StateRule(Admin.ENTER_NEW_ADMIN_ID), PayloadRule({"manage_admins": "add_admin"}))
async def ask_old_admin(m: Message):
    user_id = await get_mention_from_message(m)
    user = await bot.api.users.get(user_id)
    if not user_id:
        await m.answer(messages.user_not_found)
        return
    keyboard = Keyboard().add(
        Text("Подтвердить", {"old_admin": user_id}), KeyboardButtonColor.POSITIVE
    ).row().add(
        Text("Отклонить", {"old_admin": "decline"}), KeyboardButtonColor.NEGATIVE
    )
    states.set(m.from_id, Admin.CONFIRM_OLD_ADMIN_ID)
    await m.answer(messages.confirm_old_admin.format(f"[id{user[0].id}|{user[0].first_name} {user[0].last_name}]"),
                        keyboard=keyboard)


@bot.on.private_message(StateRule(Admin.CONFIRM_OLD_ADMIN_ID), PayloadRule({"old_admin": "decline"}), AdminRule())
async def cancel_old_admin(m: Message):
    states.set(m.from_id, Admin.ENTER_OLD_ADMIN_ID)
    await m.answer(messages.enter_old_admin, keyboard=keyboards.manage_admins)


@bot.on.private_message(StateRule(Admin.CONFIRM_OLD_ADMIN_ID), PayloadMapRule({"old_admin": int}), AdminRule())
async def delete_old_admin_(m: Message):
    user_id = m.payload['old_admin']
    await db.User.update.values(admin=0).where(db.User.user_id == int(user_id)).gino.status()
    states.set(m.from_id, Admin.SELECT_MANAGE_ADMINS)
    user = await bot.api.users.get(user_id)
    await m.answer(messages.deleted_admin.format(f"[id{user[0].id}|{user[0].first_name} {user[0].last_name}]"))
    await m.answer(messages.manage_admins, keyboard=keyboards.manage_admins)


