from vkbottle.bot import Message
from vkbottle.dispatch.rules.base import PayloadRule
from vkbottle import Keyboard

from loader import bot
from service.custom_rules import StateRule, AdminRule, NumericRule
from service.states import Admin
from service.middleware import states
from service.db_engine import db
from service.utils import parse_period, send_content_page, allow_edit_content
from service import keyboards


@bot.on.private_message(PayloadRule({"Daylic": "add"}), StateRule(f"{Admin.SELECT_ACTION}_Daylic"), AdminRule())
async def create_daylic(m: Message):
    daylic = await db.Daylic.create()
    states.set(m.from_id, f"{Admin.DAYLIC_NAME}*{daylic.id}")
    await m.answer("Введи название дейлика", keyboard=Keyboard())


@bot.on.private_message(StateRule(Admin.DAYLIC_NAME), AdminRule())
@allow_edit_content("Daylic", text="Название дейлика записал. Теперь отправь описание", state=Admin.DAYLIC_DESCRIPTION)
async def set_name_daylic(m: Message):
    daylic_id = int(states.get(m.from_id).split("*")[-1])
    await db.Daylic.update.values(name=m.text).where(db.Daylic.id == daylic_id).gino.status()


@bot.on.private_message(StateRule(Admin.DAYLIC_DESCRIPTION), AdminRule())
@allow_edit_content("Daylic", text="Описание установлено, теперь укажи награду за выполнение", state=Admin.DAYLIC_REWARD)
async def set_description_daylic(m: Message):
    daylic_id = int(states.get(m.from_id).split("*")[-1])
    await db.Daylic.update.values(description=m.text).where(db.Daylic.id == daylic_id).gino.status()


@bot.on.private_message(StateRule(Admin.DAYLIC_REWARD), NumericRule(), AdminRule())
@allow_edit_content("Daylic", text="Награда за выполнение установлена. Теперь пришлите кулдаун в формате "
                                   "\"1 день 2 часа 3 минуты\"", state=Admin.DAYLIC_COOLDOWN)
async def set_daylic_reward(m: Message, value: int):
    daylic_id = int(states.get(m.from_id).split("*")[-1])
    await db.Daylic.update.values(reward=value).where(db.Daylic.id == daylic_id).gino.status()


@bot.on.private_message(StateRule(Admin.DAYLIC_COOLDOWN), AdminRule())
@allow_edit_content("Daylic", state=Admin.DAYLIC_PROFESSION)
async def set_cooldown_daylic(m: Message):
    daylic_id = int(states.get(m.from_id).split("*")[-1])
    await db.Daylic.update.values(cooldown=parse_period(m)).where(db.Daylic.id == daylic_id).gino.status()
    is_editing = await db.select([db.User.editing_content]).where(db.User.user_id == m.from_id).gino.scalar()
    if not is_editing:
        professions = await db.select([db.Profession.name]).order_by(db.Profession.id).gino.all()
        reply = "Время кулдауна установлено. Осталось указать профессию к которй будет привязан дейлик\n\n"
        for i, profession in enumerate(professions):
            reply = f"{reply}{i + 1}. {profession.name}\n"
        return reply


@bot.on.private_message(StateRule(Admin.DAYLIC_PROFESSION), NumericRule(), AdminRule())
@allow_edit_content("Daylic", text="Дейлик успешно создан", state=f"{Admin.SELECT_ACTION}_Daylic", end=True)
async def set_daylic_profession(m: Message, value: int):
    daylic_id = int(states.get(m.from_id).split("*")[-1])
    profession_id = await db.select([db.Profession.id]).order_by(db.Profession.id).offset(value - 1).limit(
        1).gino.scalar()
    await db.Daylic.update.values(profession_id=profession_id).where(db.Daylic.id == daylic_id).gino.status()


@bot.on.private_message(StateRule(f"{Admin.SELECT_ACTION}_Daylic"), PayloadRule({"Daylic": "delete"}), AdminRule())
async def select_delete_daylic(m: Message):
    daylics = (await db.select([db.Daylic.name, db.Daylic.reward, db.Profession.name])
               .select_from(db.Daylic.join(db.Profession, db.Daylic.profession_id == db.Profession.id))
               .order_by(db.Daylic.id).gino.all())
    reply = "Выберите дейлик для удаления\n\n"
    for i, daylic in enumerate(daylics):
        reply = f"{reply}{i + 1}. {daylic[0]} ({daylic[2]}, {daylic[1]})\n"
    states.set(m.from_id, f"{Admin.SELECT_ACTION}_Daylic")
    await m.answer(reply)


@bot.on.private_message(StateRule(Admin.DAYLIC_SELECT_ID), NumericRule(), AdminRule())
async def delete_daylic(m: Message, value: int):
    daylic_id, daylic_name = await db.select([db.Daylic.id, db.Daylic.name]).order_by(db.Daylic.id).offset(
        value - 1).limit(1).gino.first()
    await db.Daylic.delete.where(db.Daylic.id == daylic_id).gino.status()
    states.set(m.from_id, f"{Admin.SELECT_ACTION}_Daylic")
    await m.answer(f"Дейлик {daylic_name} удалён",
                        keyboard=keyboards.gen_type_change_content("Daylic"))
    await send_content_page(m, "Daylic", 1)
