"""
Принудительная выдача обязательного квеста из меню судьи/администратора.

Раньше эта функциональность была доступна только через чат-команду
[выдать задачу [id...|Игрок] "Название"], которая требует общего группового
чата с указанными игроками. Судьи явно исключены из общей CRUD-панели
редактирования контента (там для судей доступны только «Item» и
«StateDebuff» — см. handlers/admin_panel/edit_content/common.py), поэтому
им нужен отдельный, более простой вход в личных сообщениях с ботом.

Флоу:
1. Судья/администратор нажимает «📌 Принудительный квест» в своей панели.
2. Присылает упоминания/ссылки/имена персонажей игроков (можно несколько
   строк — как и в get_mention_from_message).
3. Пишет название квеста.
4. Квест создаётся (MandatoryQuest), игроки уведомляются в ЛС, а автор
   переводится в уже существующий общий флоу ввода описания квеста
   (Admin.MANDATORY_QUEST_DESCRIPTION), которым дальше управляет
   handlers/admin_panel/edit_content/mandatory_quests.py.
"""

from vkbottle.bot import Message
from vkbottle.dispatch.rules import OrRule
from vkbottle.dispatch.rules.base import PayloadRule
from vkbottle import Keyboard

from loader import bot, states
from service.custom_rules import JudgeRule, AdminRule, StateRule
from service.states import Judge, Admin
from service.db_engine import db
from service.utils import get_mention_from_message, create_mention, get_current_form_id


@bot.on.private_message(StateRule(Judge.MENU), PayloadRule({'judge_menu': 'force_quest'}), OrRule(JudgeRule(), AdminRule()))
async def start_force_quest(m: Message):
    """Запрашивает у судьи/админа игроков, которым нужно принудительно выдать квест."""
    states.set(m.from_id, Judge.FORCE_QUEST_TARGETS)
    await m.answer(
        '📌 Принудительная выдача квеста.\n\n'
        'Пришлите упоминания/ссылки/имена персонажей игроков, которым нужно выдать квест '
        '(можно несколько, каждое с новой строки).',
        keyboard=Keyboard()
    )


@bot.on.private_message(StateRule(Judge.FORCE_QUEST_TARGETS), OrRule(JudgeRule(), AdminRule()))
async def set_force_quest_targets(m: Message):
    """Определяет игроков для принудительного квеста и запрашивает название."""
    user_ids = await get_mention_from_message(m, many_users=True)
    if not user_ids:
        await m.answer('Не удалось найти пользователей. Пришлите упоминание, ссылку или точное имя персонажа.')
        return

    form_ids = [x[0] for x in await db.select([db.Form.id]).where(db.Form.user_id.in_(user_ids)).gino.all()]
    if not form_ids:
        await m.answer('У указанных пользователей нет анкет. Попробуйте ещё раз.')
        return

    mentions = ', '.join([await create_mention(uid) for uid in user_ids])
    states.set(m.from_id, f'{Judge.FORCE_QUEST_NAME}*{",".join(map(str, user_ids))}')
    await m.answer(
        f'Игроки: {mentions}\n\n'
        f'Теперь напишите название обязательного квеста.'
    )


@bot.on.private_message(StateRule(Judge.FORCE_QUEST_NAME), OrRule(JudgeRule(), AdminRule()))
async def set_force_quest_name(m: Message):
    """Создаёт обязательный квест и переводит в общий флоу ввода описания."""
    state_value = states.get(m.from_id)
    user_ids = [int(x) for x in state_value.split('*')[1].split(',') if x]
    name = m.text.strip()
    if not name:
        await m.answer('Название не может быть пустым. Напишите название обязательного квеста.')
        return

    form_ids = [x[0] for x in await db.select([db.Form.id]).where(db.Form.user_id.in_(user_ids)).gino.all()]
    if not form_ids:
        await m.answer('У указанных пользователей больше нет анкет. Начните заново.')
        states.set(m.from_id, Judge.MENU)
        return

    from_form_id = await get_current_form_id(m.from_id)
    quest = await db.MandatoryQuest.create(form_ids=form_ids, name=name, from_form_id=from_form_id)

    for uid in user_ids:
        try:
            await bot.api.messages.send(
                peer_id=uid,
                message='Вам выдан новый обязательный квест. Панель обязательных квестов доступна в меню бота.',
                random_id=0
            )
        except Exception:
            pass  # Пользователь мог заблокировать бота — не критично

    states.set(m.from_id, f'{Admin.MANDATORY_QUEST_DESCRIPTION}*{quest.id}')
    await m.answer(
        f'Обязательный квест «{name}» создан.\n\n'
        f'Теперь напишите описание квеста 👇',
        keyboard=Keyboard()
    )
