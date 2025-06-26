from vkbottle.bot import Message
from vkbottle.dispatch.rules.base import PayloadRule
from vkbottle import Keyboard

from loader import bot
from service.utils import allow_edit_content, send_content_page, info_target_reward, parse_reward, parse_daughter_params
from service.middleware import states
from service.db_engine import db
from service.custom_rules import StateRule, AdminRule, NumericRule
from service.states import Admin
import service.keyboards as keyboards


@bot.on.private_message(StateRule(f"{Admin.SELECT_ACTION}_DaughterTarget"), PayloadRule({"DaughterTarget": "add"}), AdminRule())
async def create_quest(m: Message):
    quest = await db.DaughterTarget.create()
    states.set(m.from_id, f"{Admin.DAUGHTER_TARGET_NAME}*{quest.id}")
    await m.answer("Напишите название доп. цели", keyboard=Keyboard())


@bot.on.private_message(StateRule(Admin.DAUGHTER_TARGET_NAME), AdminRule())
@allow_edit_content('DaughterTarget', state=Admin.DAUGHTER_TARGET_DESCRIPTION, text='Укажите описание доп. цели')
async def daughter_target_name(m: Message):
    target_id = int(states.get(m.from_id).split("*")[-1])
    await db.DaughterTarget.update.values(name=m.text).where(db.DaughterTarget.id == target_id).gino.status()


@bot.on.private_message(StateRule(Admin.DAUGHTER_TARGET_DESCRIPTION), AdminRule())
@allow_edit_content('DaughterTarget', state=Admin.DAUGHTER_TARGET_REWARD)
async def daughter_target_description(m: Message):
    target_id = int(states.get(m.from_id).split("*")[-1])
    await db.DaughterTarget.update.values(description=m.text).where(db.DaughterTarget.id == target_id).gino.status()
    editing_content = await db.select([db.User.editing_content]).where(db.User.user_id == m.from_id).gino.scalar()
    if not editing_content:
        await m.answer((await info_target_reward())[0])


@bot.on.private_message(StateRule(Admin.DAUGHTER_TARGET_REWARD), AdminRule())
@allow_edit_content('DaughterTarget', state=Admin.DAUGHTER_TARGET_PARAMS,
                    text='Укажите параметры либидо и подчинения, которые будут необходимы для выдачи доп. цели\n\n'
                         'Например:\n«10 и 15»\n«10 или 15»', keyboard=Keyboard())
async def daughter_target_reward(m: Message):
    data = await parse_reward(m.text)
    target_id = int(states.get(m.from_id).split("*")[-1])
    await db.DaughterTarget.update.values(reward=data).where(db.DaughterTarget.id == target_id).gino.status()


@bot.on.private_message(StateRule(Admin.DAUGHTER_TARGET_PARAMS), AdminRule())
@allow_edit_content('DaughterTarget', end=True, text='Доп. цель успешно создана')
async def aughter_target_params(m: Message):
    libido, word, subordination = parse_daughter_params(m.text.lower())
    target_id = int(states.get(m.from_id).split("*")[-1])
    await db.DaughterTarget.update.values(params=[libido, word, subordination]).where(db.DaughterTarget.id == target_id).gino.status()


@bot.on.private_message(StateRule(f"{Admin.SELECT_ACTION}_DaughterTarget"), PayloadRule({"DaughterTarget": "delete"}), AdminRule())
async def select_delete_quest(m: Message):
    quests = await db.select([db.DaughterTarget.name]).order_by(db.DaughterTarget.id.asc()).gino.all()
    if not quests:
        return "Доп. цели ещё не созданы"
    reply = "Выберите доп. цель для удаления:\n\n"
    for i, quest in enumerate(quests):
        reply = f"{reply}{i + 1}. {quest.name}\n"
    states.set(m.peer_id, Admin.DAUGHTER_TARGET_DELETE)
    await m.answer(reply, keyboard=Keyboard())


@bot.on.private_message(StateRule(Admin.DAUGHTER_TARGET_DELETE), NumericRule(), AdminRule())
async def delete_quest(m: Message, value: int):
    quest_id = await db.select([db.DaughterTarget.id]).order_by(db.DaughterTarget.id.asc()).offset(value - 1).limit(1).gino.scalar()
    await db.DaughterTarget.delete.where(db.DaughterTarget.id == quest_id).gino.status()
    data = await db.select([db.DaughterQuest.id, db.DaughterQuest.target_ids]).where(db.DaughterQuest.target_ids.op('@>')([quest_id])).gino.all()
    for quest_id, target_ids in data:
        if quest_id in target_ids:
            target_ids.remove(quest_id)
        await db.DaughterQuest.update.values(target_ids=target_ids).where(db.DaughterQuest.id == quest_id).gino.status()
    states.set(m.peer_id, f"{Admin.SELECT_ACTION}_DaughterTarget")
    await m.answer("Доп. цель успешно удалена", keyboard=keyboards.gen_type_change_content("DaughterTarget"))
    await send_content_page(m, "DaughterTarget", 1)
