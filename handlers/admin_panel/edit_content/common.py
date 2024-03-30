from vkbottle.bot import Message
from vkbottle.dispatch.rules.base import PayloadRule, PayloadMapRule


import messages
import service.keyboards as keyboards
from loader import bot
from service.custom_rules import AdminRule, StateRule
from service.middleware import states
from service.states import Admin


@bot.on.private_message(StateRule(Admin.MENU), PayloadRule({"admin_menu": "edit_content"}), AdminRule())
@bot.on.private_message(PayloadRule({"cabins": "back"}), AdminRule())
@bot.on.private_message(PayloadRule({"professions": "back"}), AdminRule())
@bot.on.private_message(PayloadRule({"products": "back"}), AdminRule())
@bot.on.private_message(PayloadRule({"statuses": "back"}), AdminRule())
@bot.on.private_message(PayloadRule({"quests": "back"}), AdminRule())
@bot.on.private_message(PayloadRule({"daylics": "back"}), AdminRule())
@bot.on.private_message(PayloadRule({"events": "back"}), AdminRule())
async def select_edit_content(m: Message):
    states.set(m.from_id, Admin.SELECT_EDIT_CONTENT)
    await m.answer(messages.content, keyboard=keyboards.manage_content)


@bot.on.private_message(StateRule(Admin.SELECT_EDIT_CONTENT), PayloadMapRule({"edit_content": str}), AdminRule())
async def select_action_with_cabins(m: Message):
    edit_content = m.payload['edit_content']
    states.set(m.from_id, Admin.SELECT_ACTION)
    await m.answer(messages.select_action, keyboard=keyboards.gen_type_change_content(edit_content))