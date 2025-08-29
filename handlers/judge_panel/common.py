from vkbottle.bot import Message
from vkbottle.dispatch.rules.base import PayloadRule

from loader import bot, states
from service.custom_rules import JudgeRule, StateRule
from service.states import Menu, Judge, Admin
from service import keyboards
from service.db_engine import db


@bot.on.private_message(StateRule(Menu.MAIN), PayloadRule({'main_menu': 'judge_panel'}), JudgeRule())
@bot.on.private_message(StateRule(Judge.SET_CONSEQUENCES), PayloadRule({'main_menu': 'judge_panel'}), JudgeRule())
async def judge_menu(m: Message):
    states.set(m.from_id, Judge.MENU)
    await db.User.update.values(judge_panel=True).where(db.User.user_id == m.from_id).gino.status()
    await m.answer('Добро пожаловать в панель судьи', keyboard=keyboards.judge_menu)
