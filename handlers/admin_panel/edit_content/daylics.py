from vkbottle.bot import Message
from vkbottle.dispatch.rules.base import PayloadRule
from vkbottle import Keyboard

from loader import bot
from service.custom_rules import StateRule, AdminRule, NumericRule
from service.states import Admin
from service.middleware import states
from service.db_engine import db
from service.utils import parse_period, parse_cooldown
from service import keyboards


@bot.on.private_message(PayloadRule({"daylics": "add"}), StateRule(Admin.SELECT_ACTION), AdminRule())
async def create_daylic(m: Message):
    daylic = await db.Daylic.create()
    states.set(m.from_id, f"{Admin.DAYLIC_NAME}*{daylic.id}")
    await bot.write_msg(m.from_id, "Введи название дейлика", keyboard=Keyboard())


@bot.on.private_message(StateRule(Admin.DAYLIC_NAME, True), AdminRule())
async def set_name_daylic(m: Message):
    daylic_id = int(states.get(m.from_id).split("*")[-1])
    await db.Daylic.update.values(name=m.text).where(db.Daylic.id == daylic_id).gino.status()
    states.set(m.from_id, f"{Admin.DAYLIC_DESCRIPTION}*{daylic_id}")
    await bot.write_msg(m.from_id, "Название дейлика записал. Теперь отправь описание")


@bot.on.private_message(StateRule(Admin.DAYLIC_DESCRIPTION, True), AdminRule())
async def set_description_daylic(m: Message):
    daylic_id = int(states.get(m.from_id).split("*")[-1])
    await db.Daylic.update.values(description=m.text).where(db.Daylic.id == daylic_id).gino.status()
    states.set(m.from_id, f"{Admin.DAYLIC_REWARD}*{daylic_id}")
    await bot.write_msg(m.from_id, "Описание установлено, теперь укажи награду за выполнение")


@bot.on.private_message(StateRule(Admin.DAYLIC_REWARD, True), NumericRule(), AdminRule())
async def set_daylic_reward(m: Message, value: int):
    daylic_id = int(states.get(m.from_id).split("*")[-1])
    await db.Daylic.update.values(reward=value).where(db.Daylic.id == daylic_id).gino.status()
    states.set(m.from_id, f"{Admin.DAYLIC_COOLDOWN}*{daylic_id}")
    await bot.write_msg(m.from_id, "Награда за выполнение установлена. Теперь пришлите кулдаун в формате "
                                   "\"1 день 2 часа 3 минуты\"")


@bot.on.private_message(StateRule(Admin.DAYLIC_COOLDOWN, True), AdminRule())
async def set_cooldown_daylic(m: Message):
    daylic_id = int(states.get(m.from_id).split("*")[-1])
    await db.Daylic.update.values(cooldown=parse_period(m)).where(db.Daylic.id == daylic_id).gino.status()
    states.set(m.from_id, f"{Admin.DAYLIC_PROFESSION}*{daylic_id}")
    professions = await db.select([db.Profession.name]).order_by(db.Profession.id).gino.all()
    reply = "Время колдауна установлено. Осталось указать профессию к которй будет привязан дейлик\n\n"
    for i, profession in enumerate(professions):
        reply = f"{reply}{i + 1}. {profession.name}\n"
    await bot.write_msg(m.from_id, reply)


@bot.on.private_message(StateRule(Admin.DAYLIC_PROFESSION, True), NumericRule(), AdminRule())
async def set_daylic_profession(m: Message, value: int):
    daylic_id = int(states.get(m.from_id).split("*")[-1])
    profession_id = await db.select([db.Profession.id]).order_by(db.Profession.id).offset(value - 1).limit(1).gino.scalar()
    await db.Daylic.update.values(profession_id=profession_id).where(db.Daylic.id == daylic_id).gino.status()
    daylic = await db.select([*db.Daylic]).where(db.Daylic.id == daylic_id).gino.first()
    profession_name = await db.select([db.Profession.name]).where(db.Profession.id == daylic.profession_id).gino.scalar()
    states.set(m.from_id, Admin.SELECT_ACTION)
    await bot.write_msg(m.peer_id, f"Дейлик успешно создан\n"
                                   f"Название: {daylic.name}\n"
                                   f"Описание: {daylic.description}\n"
                                   f"Награда: {daylic.reward}\n"
                                   f"Кулдаун: {parse_cooldown(daylic.cooldown)}\n"
                                   f"Профессия: {profession_name}", keyboard=keyboards.gen_type_change_content("daylics"))


@bot.on.private_message(StateRule(Admin.SELECT_ACTION), PayloadRule({"daylics": "delete"}), AdminRule())
async def select_delete_daylic(m: Message):
    daylics = await db.select([db.Daylic.name, db.Daylic.reward]).order_by(db.Daylic.id).gino.all()
    reply = "Выберите дейлик для удаления\n\n"
    for i, daylic in enumerate(daylics):
        reply = f"{reply}{i + 1}. {daylic.name}({daylic.reward})\n"
    states.set(m.from_id, Admin.DAYLIC_SELECT_ID)
    await bot.write_msg(m.from_id, reply)


@bot.on.private_message(StateRule(Admin.DAYLIC_SELECT_ID), NumericRule(), AdminRule())
async def delete_daylic(m: Message, value: int):
    daylic_id, daylic_name = await db.select([db.Daylic.id, db.Daylic.name]).order_by(db.Daylic.id).offset(value - 1).limit(1).gino.first()
    await db.Daylic.delete.where(db.Daylic.id == daylic_id).gino.status()
    states.set(m.from_id, Admin.SELECT_ACTION)
    await bot.write_msg(m.from_id, f"Дейлик {daylic_name} удалён", keyboard=keyboards.gen_type_change_content("daylics"))

