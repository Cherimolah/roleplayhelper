from vkbottle.bot import Message
from vkbottle.dispatch.rules.base import VBMLRule, PayloadRule
from sqlalchemy import and_

import messages
import service.keyboards as keyboards
from loader import bot
from service.custom_rules import AdminRule, StateRule, NumericRule
from service.middleware import states
from service.states import Admin, Menu
from service.db_engine import db


@bot.on.private_message(StateRule(Admin.SELECT_NUMBER_FORM, True), AdminRule(), NumericRule(), blocking=False)
async def selected_number_form(m: Message, value: int):
    if value not in (1, 2):
        await bot.write_msg(m.peer_id, messages.error_not_number_form)
        return
    user_id = int(states.get(m.from_id).split("@")[1])
    form_id = await db.select([db.Form.id]).where(and_(db.Form.number == value, db.Form.user_id == user_id)).gino.scalar()
    if not form_id:
        await bot.write_msg(m.peer_id, messages.not_form_id)
        return
    state = states.get(m.from_id).split("@")[2]
    states.set(m.from_id, f"{state}*{form_id}")


@bot.on.private_message(VBMLRule("/admin"), AdminRule())
@bot.on.private_message(PayloadRule({"menu": "admin_panel"}), AdminRule())
async def send_admin_panel(m: Message):
    states.set(m.from_id, Admin.MENU)
    await bot.write_msg(m.peer_id, messages.admin_menu, keyboard=keyboards.admin_menu)


@bot.on.private_message(StateRule(Admin.MENU), PayloadRule({"admin_menu": "back"}), AdminRule())
async def back_from_admin_menu(m: Message):
    states.set(m.from_id, Menu.MAIN)
    await bot.write_msg(m.peer_id, messages.main_menu, keyboard=await keyboards.main_menu(m.from_id))


# Назад в админку
@bot.on.private_message(StateRule(Admin.EDIT_FORMS), PayloadRule({"admin_forms_edit": "back"}), AdminRule())
@bot.on.private_message(StateRule(Admin.SELECT_NUMBER_FORM, True), PayloadRule({"admin_forms_edit": "back"}), AdminRule())
@bot.on.private_message(StateRule(Admin.SELECT_FIELDS, True), PayloadRule({"admin_forms_edit": "back"}), AdminRule())
@bot.on.private_message(StateRule(Admin.ENTER_FIELD_VALUE, True), PayloadRule({"admin_forms_edit": "back"}), AdminRule())
@bot.on.private_message(StateRule(Admin.SELECT_MANAGE_ADMINS), PayloadRule({"manage_admins": "back"}), AdminRule())
@bot.on.private_message(StateRule(Admin.ENTER_NEW_ADMIN_ID), PayloadRule({"manage_admins": "back"}), AdminRule())
@bot.on.private_message(StateRule(Admin.ENTER_OLD_ADMIN_ID), PayloadRule({"manage_admins": "back"}), AdminRule())
@bot.on.private_message(StateRule(Admin.SELECT_EDIT_CONTENT), PayloadRule({"edit_content": "back"}), AdminRule())
@bot.on.private_message(StateRule(Admin.WRITE_MAILING), PayloadRule({"mailing": "back"}), AdminRule())
@bot.on.private_message(PayloadRule({"give_reward": "back"}), AdminRule())
async def back_to_admin_menu(m: Message):
    states.set(m.from_id, Admin.MENU)
    await bot.write_msg(m.peer_id, messages.admin_menu, keyboard=keyboards.admin_menu)
