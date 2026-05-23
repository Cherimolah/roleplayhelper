import datetime

from vkbottle.bot import Message
from vkbottle.dispatch.rules import OrRule
from vkbottle.dispatch.rules.base import PayloadRule

from loader import bot, states
from service.custom_rules import StateRule, AdminRule, JudgeRule
from service.states import Admin
from service.db_engine import db, now
from service.utils import parse_period, create_mention
from service.serializers import info_target_reward, parse_reward, FormatDataException, info_quest_penalty
from handlers.questions import start


@bot.on.private_message(StateRule(Admin.MANDATORY_QUEST_DESCRIPTION), OrRule(AdminRule(), JudgeRule()))
async def set_description(m: Message):
    quest_id = int(states.get(m.from_id).split('*')[-1])
    await db.MandatoryQuest.update.values(description=m.text).where(db.MandatoryQuest.id == quest_id).gino.status()
    states.set(m.from_id, f'{Admin.MANDATORY_QUEST_EXPIRED_AT}*{quest_id}')
    await m.answer('Описание квеста установлено.\n'
                   'Теперь напишите дату и время выполнения квеста\n'
                   'Например: 1 неделя 2 дня 3 часа 5 минут')


@bot.on.private_message(StateRule(Admin.MANDATORY_QUEST_EXPIRED_AT), OrRule(AdminRule(), JudgeRule()))
async def set_expired_at(m: Message):
    quest_id = int(states.get(m.from_id).split('*')[-1])
    period = parse_period(m.text)
    if period <= 0:
        await m.answer('Не удалось распознать время выполнения')
        return
    expired_at = now() + datetime.timedelta(seconds=period)
    await db.MandatoryQuest.update.values(expired_at=expired_at).where(db.MandatoryQuest.id == quest_id).gino.status()
    states.set(m.from_id, f'{Admin.MANDATORY_QUEST_REWARD}*{quest_id}')
    await m.answer('Время выполнения квеста успешно установлено. Теперь необходимо указать награду за выполнение квеста')
    reply, _ = await info_target_reward()
    await m.answer(reply)


@bot.on.private_message(StateRule(Admin.MANDATORY_QUEST_REWARD), OrRule(AdminRule(), JudgeRule()))
async def set_reward(m: Message):
    quest_id = int(states.get(m.from_id).split('*')[-1])
    try:
        reward = await parse_reward(m.text)
    except FormatDataException as e:
        await m.answer(f'Произошла ошибка в обработки параметров награды.\n'
                       f'{e.args[0]}')
        return
    states.set(m.from_id, f'{Admin.MANDATORY_QUEST_PENALTY}*{quest_id}')
    await db.MandatoryQuest.update.values(reward=reward).where(db.MandatoryQuest.id == quest_id).gino.status()
    await m.answer('Награда квеста успешно установлена.\n'
                   'Теперь напишите штраф за невыполнение квеста')
    reply, keyboard = await info_quest_penalty()
    await m.answer(reply, keyboard=keyboard)


@bot.on.private_message(StateRule(Admin.MANDATORY_QUEST_PENALTY), OrRule(AdminRule(), JudgeRule()), PayloadRule({"without_penalty": True}))
async def save_mandatory_quest(m: Message):
    quest_id = int(states.get(m.from_id).split('*')[-1])
    await m.answer('Квест успешно создан')
    await start(m)
    form_id, name = await db.select([db.MandatoryQuest.form_id, db.MandatoryQuest.name]).where(
        db.MandatoryQuest.id == quest_id
    ).gino.first()
    user_id = await db.select([db.Form.user_id]).where(db.Form.id == form_id).gino.scalar()
    await bot.api.messages.send(peer_id=user_id, message=f'Игрок {await create_mention(m.from_id)} создал вам '
                                                         f'обязательный квест «{name}»')


@bot.on.private_message(StateRule(Admin.MANDATORY_QUEST_PENALTY), OrRule(AdminRule(), JudgeRule()))
async def set_penalty(m: Message):
    quest_id = int(states.get(m.from_id).split('*')[-1])
    try:
        penalty = await parse_reward(m.text)
    except FormatDataException as e:
        await m.answer(f'Произошла ошибка в обработки параметров штрафа.\n'
                       f'{e.args[0]}')
        return
    await db.MandatoryQuest.update.values(penalty=penalty).where(db.MandatoryQuest.id == quest_id).gino.status()
    await save_mandatory_quest(m)
