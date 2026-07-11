"""
Принудительная выдача существующих квестов игрокам из панели судьи
(module admin_improvements, п.7).
"""
from vkbottle.bot import Message
from vkbottle.dispatch.rules.base import PayloadRule
from vkbottle import Keyboard, Text, KeyboardButtonColor

from loader import bot, states
from service.custom_rules import JudgeRule, StateRule, NumericRule, ManyUsersSpecified
from service.states import Judge
from service.db_engine import db
from service import keyboards
from service.utils import create_mention, force_assign_quest


@bot.on.private_message(StateRule(Judge.MENU), PayloadRule({'judge_menu': 'force_quest'}), JudgeRule())
async def select_quest_to_force(m: Message):
    """Выбор квеста для принудительной выдачи"""
    quests = await db.select([db.Quest.name]).order_by(db.Quest.id.asc()).gino.all()
    if not quests:
        await m.answer('Квесты ещё не созданы')
        return
    reply = 'Выберите квест по номеру для принудительной выдачи:\n\n'
    for i, quest in enumerate(quests):
        reply += f'{i + 1}. {quest.name}\n'
    states.set(m.from_id, Judge.FORCE_QUEST_SELECT)
    keyboard = Keyboard().add(Text('Назад', {'judge_menu': 'back'}), KeyboardButtonColor.NEGATIVE)
    await m.answer(reply, keyboard=keyboard)


@bot.on.private_message(StateRule(Judge.FORCE_QUEST_SELECT), NumericRule(), JudgeRule())
async def enter_force_quest_targets(m: Message, value: int):
    """Выбор игроков, которым принудительно выдаётся выбранный квест"""
    quest_id = await db.select([db.Quest.id]).order_by(db.Quest.id.asc()).offset(value - 1).limit(1).gino.scalar()
    if not quest_id:
        await m.answer('Квест с таким номером не найден')
        return
    states.set(m.from_id, f'{Judge.FORCE_QUEST_TARGETS}*{quest_id}')
    await m.answer('Отправьте ссылку/упоминание/пересланное сообщение на игроков, которым нужно выдать квест',
                   keyboard=Keyboard())


@bot.on.private_message(StateRule(Judge.FORCE_QUEST_TARGETS), ManyUsersSpecified(), JudgeRule())
async def confirm_force_quest(m: Message, forms: list):
    """Принудительная выдача квеста выбранным игрокам"""
    _, quest_id = states.get(m.from_id).split('*')
    quest_id = int(quest_id)
    quest_name = await db.select([db.Quest.name]).where(db.Quest.id == quest_id).gino.scalar()

    issued = []
    for form_id, user_id in forms:
        if not form_id:
            continue
        if await force_assign_quest(quest_id, form_id, user_id):
            issued.append(user_id)
            try:
                await bot.api.messages.send(
                    peer_id=user_id,
                    message=f'⚔ Судья принудительно выдал вам квест «{quest_name}»',
                    random_id=0,
                    is_notification=True,
                )
            except Exception:
                pass

    states.set(m.from_id, Judge.MENU)
    mentions = ', '.join([await create_mention(x) for x in issued]) if issued else 'никому (уже выдан или анкеты не найдены)'
    await m.answer(f'Квест «{quest_name}» выдан: {mentions}', keyboard=keyboards.judge_menu)
