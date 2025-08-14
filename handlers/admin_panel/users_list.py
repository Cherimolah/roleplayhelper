from vkbottle.bot import Message, MessageEvent
from vkbottle.dispatch.rules.base import PayloadRule, PayloadMapRule
from vkbottle import GroupEventType

import messages
import service.keyboards as keyboards
from loader import bot
from service.custom_rules import AdminRule, StateRule
from service.middleware import states
from service.states import Admin
from service.db_engine import db
from service.utils import send_page_users


@bot.on.private_message(StateRule(Admin.MENU), PayloadRule({"admin_menu": "users_list"}))
async def send_users(m: Message):
    await send_page_users(m, 1)


@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent, PayloadMapRule({"users_list": int}))
async def change_page_users(m: MessageEvent):
    page = m.payload['users_list']
    await send_page_users(m, int(page))


@bot.on.private_message(StateRule(Admin.MENU), PayloadRule({"admin_menu": "admins_edit"}), AdminRule())
@bot.on.private_message(StateRule(Admin.ADD_JUDGE), PayloadRule({'manage_judge': 'back'}), AdminRule())
@bot.on.private_message(StateRule(Admin.DELETE_JUDGE), PayloadRule({'manage_judge': 'back'}), AdminRule())
@bot.on.private_message(StateRule(Admin.ENTER_NEW_ADMIN_ID), PayloadRule({'manage_judge': 'back'}), AdminRule())
@bot.on.private_message(StateRule(Admin.ENTER_OLD_ADMIN_ID), PayloadRule({'manage_judge': 'back'}), AdminRule())
@bot.on.private_message(StateRule(Admin.CONFIRM_NEW_ADMIN_ID), PayloadRule({"new_admin": "decline"}), AdminRule())
@bot.on.private_message(StateRule(Admin.CONFIRM_OLD_ADMIN_ID), PayloadRule({"old_admin": "decline"}), AdminRule())
@bot.on.private_message(StateRule(Admin.ENTER_NEW_JUDGE), PayloadRule({"old_judge": "decline"}), AdminRule())
@bot.on.private_message(StateRule(Admin.ENTER_OLD_JUDGE), PayloadRule({"old_judge": "decline"}), AdminRule())
async def send_administrators(m: Message):
    admin = await db.select([db.User.admin]).where(db.User.user_id == m.from_id).gino.scalar()
    if admin < 2:
        await m.answer(messages.only_for_owner)
        return
    states.set(m.from_id, Admin.SELECT_MANAGE_ADMINS)
    await m.answer(messages.manage_admins, keyboard=keyboards.manage_admins)
