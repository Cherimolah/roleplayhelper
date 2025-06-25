import datetime

from vkbottle.bot import Message
from vkbottle.dispatch.rules.base import PayloadRule
from sqlalchemy import and_

from loader import bot
from service.custom_rules import StateRule, DaughterRule
from service.states import Menu
from service.db_engine import db
from service.utils import get_current_form_id, serialize_target_reward, parse_cooldown


@bot.on.private_message(StateRule(Menu.MAIN), PayloadRule({"menu": 'daughter_quests'}), DaughterRule())
async def daughter_quest(m: Message):
    form_id = await get_current_form_id(m.from_id)
    quest = await db.select([*db.DaughterQuest]).where(db.DaughterQuest.to_form_id == form_id).gino.first()
    if not quest:
        await m.answer('Для вас пока не создано квеста')
        return
    confirmed = await db.select([db.DaughterQuestRequest.confirmed]).where(and_(db.DaughterQuestRequest.form_id == form_id, db.DaughterQuestRequest.created_at == datetime.date.today())).gino.scalar()
    if confirmed:
        await m.answer('На сегодня вы выполнили квест, приходите завтра!')
        return
    now = datetime.datetime.now()
    tomorrow = now + datetime.timedelta(days=1)
    next_day = datetime.datetime(tomorrow.year, tomorrow.month, tomorrow.day, 0, 0, 0)
    cooldown = (next_day - now).total_seconds()
    reply = ('У вас активен квест:\n\n'
             f'Название: {quest.name}\n'
             f'Описание: {quest.description}\n'
             f'Награда: {await serialize_target_reward(quest.reward)}\n'
             f'Штраф: {await serialize_target_reward(quest.penalty)}\n'
             f'Остаётся на выполнение: {parse_cooldown(cooldown)}\n\n')
    if quest.target_ids:
        reply += 'Дополнительные цели:\n'
        statuses = []
        for i, target_id in enumerate(quest.target_ids):
            target = await db.DaughterTarget.get(target_id)
            reply += (f'{i + 1}. {target.name}\n{target.description}\n'
                      f'Награда: {await serialize_target_reward(target.reward)}\n\n')
            confirmed = await db.select([db.DaughterTargetRequest.confirmed]).where(
                and_(db.DaughterTargetRequest.target_id == target_id, db.DaughterTargetRequest.form_id == form_id,
                     db.DaughterTargetRequest.created_at == datetime.date.today())
            ).gino.scalar()
            if confirmed is None:
                statuses.append((target.name, 0))
            elif not confirmed:
                statuses.append((target.name, 1))
            else:
                statuses.append((target.name, 2))
        reply += 'Статус выполнения квеста:\n✅ - выполнено\n⚠ - на проверке\n❌ - не выполнено\n'
        for i, data in enumerate(statuses):
            emoji = '❌' if data[1] == 0 else '⚠' if data[1] == 1 else '❌'
            reply += f'{i + 1}. {emoji} {data[0]}'
    await m.answer(reply)
