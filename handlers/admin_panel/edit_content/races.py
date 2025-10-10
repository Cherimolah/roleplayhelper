from vkbottle.bot import Message, MessageEvent
from vkbottle.dispatch.rules.base import PayloadRule, PayloadMapRule
from vkbottle import Keyboard, GroupEventType
from sqlalchemy import and_

import service.keyboards as keyboards
from loader import bot
from service.custom_rules import AdminRule, StateRule, NumericRule
from service.middleware import states
from service.states import Admin
from service.db_engine import db
from service.utils import send_content_page, allow_edit_content
from service.serializers import info_race_bonus


@bot.on.private_message(StateRule(f"{Admin.SELECT_ACTION}_Race"), PayloadRule({"Race": "add"}), AdminRule())
async def select_action_race(m: Message):
    """Начало создания новой расы"""
    race = await db.Race.create()
    states.set(m.from_id, f"{Admin.RACE_NAME}*{race.id}")
    await m.answer('Введите название расы', keyboard=Keyboard())


@bot.on.private_message(StateRule(Admin.RACE_NAME), AdminRule())
@allow_edit_content("Race", state=Admin.RACE_BONUS)
async def set_name_race(m: Message, item_id: int, editing_content: bool):
    """Установка названия расы и переход к настройке бонусов"""
    await db.Race.update.values(name=m.text).where(db.Race.id == item_id).gino.status()
    if not editing_content:
        await m.answer('Укажите бонусы к характеристикам в карте экспедитора', keyboard=Keyboard())
        reply, keyboard = await info_race_bonus(item_id)
        await m.answer(reply, keyboard=keyboard)


@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent, StateRule(Admin.RACE_BONUS), PayloadMapRule({'race_id': int, 'attribute_id': int, 'action': 'select'}), AdminRule())
async def select_bonus_race(m: MessageEvent):
    """Обработчик выбора атрибута для настройки бонуса расы"""
    attribute = await db.select([db.Attribute.name]).where(db.Attribute.id == m.payload['attribute_id']).gino.scalar()
    bonus = await db.select([db.RaceBonus.bonus]).where(
        and_(db.RaceBonus.race_id == m.payload['race_id'], db.RaceBonus.attribute_id == m.payload['attribute_id'])
    ).gino.scalar()
    if not bonus:
        bonus = 0
    reply = f'Текущий уровень бонуса к «{attribute}»: {"+" if bonus >= 0 else ""}{bonus}'
    keyboard = keyboards.gen_profession_bonus(m.payload['race_id'], m.payload['attribute_id'], False)
    await m.edit_message(reply, keyboard=keyboard.get_json())


@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent, StateRule(Admin.RACE_BONUS), PayloadMapRule({"race_id": int, 'attribute_id': int, 'add': int}), AdminRule())
async def change_race_bonus(m: MessageEvent):
    """Изменение бонуса расы для выбранного атрибута"""
    exist = await db.select([db.RaceBonus.id]).where(
        and_(db.RaceBonus.race_id == m.payload['race_id'], db.RaceBonus.attribute_id == m.payload['attribute_id'])
    ).gino.scalar()
    if not exist:
        current = 0
        await db.RaceBonus.create(race_id=m.payload['race_id'], attribute_id=m.payload['attribute_id'], bonus=m.payload['add'])
    else:
        current = await db.select([db.RaceBonus.bonus]).where(
            and_(db.RaceBonus.race_id == m.payload['race_id'],
                 db.RaceBonus.attribute_id == m.payload['attribute_id'])
        ).gino.scalar()
        if current + m.payload['add'] == 0:
            await db.RaceBonus.delete.where(
                and_(db.RaceBonus.race_id == m.payload['race_id'],
                     db.RaceBonus.attribute_id == m.payload['attribute_id'])
            ).gino.status()
        else:
            await db.RaceBonus.update.values(bonus=db.RaceBonus.bonus + m.payload['add']).where(
                and_(db.RaceBonus.race_id == m.payload['race_id'],
                     db.RaceBonus.attribute_id == m.payload['attribute_id'])
            ).gino.status()
    attribute = await db.select([db.Attribute.name]).where(db.Attribute.id == m.payload['attribute_id']).gino.scalar()
    reply = f'Текущий уровень бонуса к «{attribute}»: {"+" if current + m.payload['add'] >= 0 else ""}{current + m.payload['add']}'
    keyboard = keyboards.gen_profession_bonus(m.payload['race_id'], m.payload['attribute_id'], False)
    await m.edit_message(reply, keyboard=keyboard.get_json())


@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent, StateRule(Admin.RACE_BONUS), PayloadMapRule({"race_id": int, 'action': 'back'}), AdminRule())
async def back_race_bonuses(m: MessageEvent):
    """Возврат к списку бонусов расы"""
    reply, keyboard = await info_race_bonus(m.payload['race_id'])
    await m.edit_message(reply, keyboard=keyboard)


@bot.on.private_message(StateRule(Admin.RACE_BONUS), PayloadMapRule({"race_id": int, 'action': 'save'}), AdminRule())
@allow_edit_content('Race', end=True, text='Раса успешно создана')
async def save_race_bonus(m: Message, item_id: int, editing_content: bool):
    """Сохранение расы после настройки бонусов"""
    pass


@bot.on.private_message(StateRule(f"{Admin.SELECT_ACTION}_Race"), PayloadRule({"Race": "delete"}),
                        AdminRule())
async def select_id_to_delete_race(m: Message):
    """Выбор расы для удаления"""
    reply = 'Выберите расу:\n\n'
    races = await db.select([db.Race.name]).order_by(db.Race.id.asc()).gino.all()
    if not races:
        return "Расы ещё не созданы"
    for i, race in enumerate(races):
        reply = f"{reply}{i + 1}. {race.name}\n"
    states.set(m.from_id, Admin.RACE_DELETE)
    await m.answer(reply)


@bot.on.private_message(StateRule(Admin.RACE_DELETE), NumericRule(), AdminRule())
async def delete_race(m: Message, value: int):
    """Удаление выбранной расы"""
    race_id = await db.select([db.Race.id]).order_by(db.Race.id.asc()).offset(value - 1).limit(1).gino.scalar()
    await db.Race.delete.where(db.Race.id == race_id).gino.status()
    states.set(m.from_id, f"{Admin.SELECT_ACTION}_Race")
    await m.answer('раса успешно удалена',
                   keyboard=keyboards.gen_type_change_content("Race"))
    await send_content_page(m, "Race", 1)