from vkbottle.bot import Message
from vkbottle.dispatch.rules.base import VBMLRule, PayloadRule

import messages
import service.keyboards as keyboards
from loader import bot
from service.custom_rules import AdminRule, StateRule
from service.middleware import states
from service.states import Admin, Menu


@bot.on.private_message(VBMLRule("/admin"), AdminRule())
@bot.on.private_message(PayloadRule({"menu": "admin_panel"}), AdminRule())
async def send_admin_panel(m: Message):
    states.set(m.from_id, Admin.MENU)
    await m.answer(messages.admin_menu, keyboard=keyboards.admin_menu)


@bot.on.private_message(StateRule(Admin.MENU), PayloadRule({"admin_menu": "back"}), AdminRule())
async def back_from_admin_menu(m: Message):
    states.set(m.from_id, Menu.MAIN)
    await m.answer(messages.main_menu, keyboard=await keyboards.main_menu(m.from_id))


# Назад в админку
@bot.on.private_message(StateRule(Admin.EDIT_FORMS), PayloadRule({"admin_forms_edit": "back"}), AdminRule())
@bot.on.private_message(StateRule(Admin.SELECT_NUMBER_FORM), PayloadRule({"admin_forms_edit": "back"}), AdminRule())
@bot.on.private_message(StateRule(Admin.SELECT_FIELDS), PayloadRule({"admin_forms_edit": "back"}), AdminRule())
@bot.on.private_message(StateRule(Admin.ENTER_FIELD_VALUE), PayloadRule({"admin_forms_edit": "back"}), AdminRule())
@bot.on.private_message(StateRule(Admin.SELECT_MANAGE_ADMINS), PayloadRule({"manage_admins": "back"}), AdminRule())
@bot.on.private_message(StateRule(Admin.ENTER_NEW_ADMIN_ID), PayloadRule({"manage_admins": "back"}), AdminRule())
@bot.on.private_message(StateRule(Admin.ENTER_OLD_ADMIN_ID), PayloadRule({"manage_admins": "back"}), AdminRule())
@bot.on.private_message(StateRule(Admin.SELECT_EDIT_CONTENT), PayloadRule({"edit_content": "back"}), AdminRule())
@bot.on.private_message(StateRule(Admin.WRITE_MAILING), PayloadRule({"mailing": "back"}), AdminRule())
@bot.on.private_message(PayloadRule({"give_reward": "back"}), AdminRule())
async def back_to_admin_menu(m: Message):
    states.set(m.from_id, Admin.MENU)
    await m.answer(messages.admin_menu, keyboard=keyboards.admin_menu)
