from vkbottle.bot import Message
from vkbottle.dispatch.rules.base import PayloadRule
from vkbottle import Keyboard

from loader import bot
from service.custom_rules import StateRule, AdminRule, NumericRule
from service.states import Admin
from service.middleware import states
from service.db_engine import db
from service.utils import parse_period, send_content_page, allow_edit_content, FormatDataException
from service import keyboards


@bot.on.private_message(PayloadRule({"Daylic": "add"}), StateRule(f"{Admin.SELECT_ACTION}_Daylic"), AdminRule())
async def create_daylic(m: Message):
    daylic = await db.Daylic.create()
    states.set(m.from_id, f"{Admin.DAYLIC_NAME}*{daylic.id}")
    await m.answer("Введи название дейлика", keyboard=Keyboard())


@bot.on.private_message(StateRule(Admin.DAYLIC_NAME), AdminRule())
@allow_edit_content("Daylic", text="Название дейлика записал. Теперь отправь описание", state=Admin.DAYLIC_DESCRIPTION)
async def set_name_daylic(m: Message, item_id: int, editing_content: bool):
    await db.Daylic.update.values(name=m.text).where(db.Daylic.id == item_id).gino.status()


@bot.on.private_message(StateRule(Admin.DAYLIC_DESCRIPTION), AdminRule())
@allow_edit_content("Daylic", text="Описание установлено, теперь укажи награду за выполнение",
                    state=Admin.DAYLIC_REWARD)
async def set_description_daylic(m: Message, item_id: int, editing_content: bool):
    await db.Daylic.update.values(description=m.text).where(db.Daylic.id == item_id).gino.status()


@bot.on.private_message(StateRule(Admin.DAYLIC_REWARD), NumericRule(), AdminRule())
@allow_edit_content("Daylic", text="Награда за выполнение установлена. Теперь пришлите кулдаун в формате "
                                   "\"1 день 2 часа 3 минуты\"", state=Admin.DAYLIC_COOLDOWN)
async def set_daylic_reward(m: Message, value: int, item_id: int, editing_content: bool):
    await db.Daylic.update.values(reward=value).where(db.Daylic.id == item_id).gino.status()


@bot.on.private_message(StateRule(Admin.DAYLIC_COOLDOWN), AdminRule())
@allow_edit_content("Daylic", state=Admin.DAYLIC_PROFESSION)
async def set_cooldown_daylic(m: Message, item_id: int, editing_content: bool):
    if not parse_period(m.text):
        raise FormatDataException("Период указан неверно")
    await db.Daylic.update.values(cooldown=parse_period(m.text)).where(db.Daylic.id == item_id).gino.status()
    if not editing_content:
        professions = await db.select([db.Profession.name]).order_by(db.Profession.id).gino.all()
        reply = "Время кулдауна установлено. Теперь укажите профессию к которй будет привязан дейлик\n\n"
        for i, profession in enumerate(professions):
            reply = f"{reply}{i + 1}. {profession.name}\n"
        return reply


@bot.on.private_message(StateRule(Admin.DAYLIC_PROFESSION), NumericRule(), AdminRule())
@allow_edit_content("Daylic", state=Admin.DAYLIC_FRACTION)
async def set_daylic_profession(m: Message, value: int, item_id: int, editing_content: bool):
    profession_id = await db.select([db.Profession.id]).order_by(db.Profession.id).offset(value - 1).limit(
        1).gino.scalar()
    if not profession_id:
        raise FormatDataException("Профессия не найдена")
    await db.Daylic.update.values(profession_id=profession_id).where(db.Daylic.id == item_id).gino.status()
    fractions = [x[0] for x in await db.select([db.Fraction.name]).order_by(db.Fraction.id.asc()).gino.all()]
    reply = "Теперь укажи номер фракции, к которой будет бонус к репутации:\n\n"
    for i, name in enumerate(fractions):
        reply += f"{i + 1}. {name}\n"
    await m.answer(reply, keyboard=keyboards.without_fraction_bonus)


@bot.on.private_message(StateRule(Admin.DAYLIC_FRACTION), PayloadRule({"withot_fraction_bonus": True}), AdminRule())
@allow_edit_content("Daylic", text="Дейлик успешно создана без бонуса к репутации", end=True,
                    state=f"{Admin.SELECT_ACTION}_Daylic")
async def save_daylic_without_bonus(m: Message, item_id: int, editing_content: bool):
    await db.Daylic.update.values(fraction_id=None, reputation=0).where(db.Daylic.id == item_id).gino.status()


@bot.on.private_message(StateRule(Admin.DAYLIC_FRACTION), NumericRule(), AdminRule())
@allow_edit_content("Daylic", text="Номер фракции установлен теперь укажи бонус к репутации числом",
                    state=Admin.DAYLIC_REPUTATTION)
async def set_daylic_fraction(m: Message, value: int, item_id: int, editing_content: bool):
    fractions = [x[0] for x in await db.select([db.Fraction.id]).order_by(db.Fraction.id.asc()).gino.all()]
    if value > len(fractions):
        raise FormatDataException("Номер фракции слишком большой")
    fraction_id = fractions[value - 1]
    await db.Daylic.update.values(fraction_id=fraction_id).where(db.Daylic.id == item_id).gino.status()


@bot.on.private_message(StateRule(Admin.DAYLIC_REPUTATTION), AdminRule())
@allow_edit_content("Daylic", text="Дейлик успешно создан с бонусом к репутации", end=True)
async def save_daylic_with_bonus(m: Message, item_id: int, editing_content: bool):
    try:
        value = int(m.text)
    except ValueError:
        raise FormatDataException("Необходимо ввести целое число")

    fraction_id = await db.select([db.Daylic.fraction_id]).where(db.Daylic.id == item_id).gino.scalar()
    if not fraction_id and value != 0:
        raise FormatDataException("Бонус к репутации может быть установлен только, когда есть фракция\n"
                                  "Установите сначала фракцию, потом бонус к репутации\n\n"
                                  "Введите 0, чтобы выйти из режима редактирования репутации")

    if not -200 <= value <= 200:
        raise FormatDataException("Диапазон значений [-200; 200]")
    await db.Daylic.update.values(reputation=value).where(db.Daylic.id == item_id).gino.status()


@bot.on.private_message(StateRule(f"{Admin.SELECT_ACTION}_Daylic"), PayloadRule({"Daylic": "delete"}), AdminRule())
async def select_delete_daylic(m: Message):
    daylics = (await db.select([db.Daylic.name, db.Daylic.reward, db.Profession.name])
               .select_from(db.Daylic.join(db.Profession, db.Daylic.profession_id == db.Profession.id))
               .order_by(db.Daylic.id.asc()).gino.all())
    if not daylics:
        return "Дейлики ещё не созданы"
    reply = "Выберите дейлик для удаления\n\n"
    for i, daylic in enumerate(daylics):
        reply = f"{reply}{i + 1}. {daylic[0]} ({daylic[2]}, {daylic[1]})\n"
    states.set(m.from_id, Admin.DAYLIC_SELECT_ID)
    await m.answer(reply)


@bot.on.private_message(StateRule(Admin.DAYLIC_SELECT_ID), NumericRule(), AdminRule())
async def delete_daylic(m: Message, value: int):
    daylic_id, daylic_name = await db.select([db.Daylic.id, db.Daylic.name]).order_by(db.Daylic.id.asc()).offset(
        value - 1).limit(1).gino.first()
    await db.Daylic.delete.where(db.Daylic.id == daylic_id).gino.status()
    states.set(m.from_id, f"{Admin.SELECT_ACTION}_Daylic")
    await m.answer(f"Дейлик {daylic_name} удалён",
                   keyboard=keyboards.gen_type_change_content("Daylic"))
    await send_content_page(m, "Daylic", 1)
