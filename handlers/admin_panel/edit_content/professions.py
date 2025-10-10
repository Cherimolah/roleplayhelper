from vkbottle.bot import Message, MessageEvent
from vkbottle.dispatch.rules.base import PayloadRule, PayloadMapRule
from vkbottle import Keyboard, GroupEventType
from sqlalchemy import and_

import messages
import service.keyboards as keyboards
from loader import bot
from service.custom_rules import AdminRule, StateRule, NumericRule
from service.middleware import states
from service.states import Admin
from service.db_engine import db
from service.utils import send_content_page, allow_edit_content
from service.serializers import info_profession_bonus


@bot.on.private_message(StateRule(f"{Admin.SELECT_ACTION}_Profession"), PayloadRule({"Profession": "add"}), AdminRule())
async def select_action_profession(m: Message):
    """
    Обработчик начала создания новой профессии.
    Создает новую запись профессии в БД и переводит в состояние ввода названия.
    """
    profession = await db.Profession.create()
    states.set(m.from_id, f"{Admin.NAME_PROFESSION}*{profession.id}")
    await m.answer(messages.profession_name_add, keyboard=Keyboard())


@bot.on.private_message(StateRule(Admin.NAME_PROFESSION), AdminRule())
@allow_edit_content("Profession", text=messages.profession_salary, state=Admin.SALARY_PROFESSION)
async def set_name_profession(m: Message, item_id: int, editing_content: bool):
    """Установка названия профессии и переход к вводу зарплаты"""
    await db.Profession.update.values(name=m.text).where(db.Profession.id == item_id).gino.status()


@bot.on.private_message(StateRule(Admin.SALARY_PROFESSION), NumericRule(), AdminRule())
@allow_edit_content("Profession", text=messages.profession_special,
                    keyboard=keyboards.select_type_profession, state=Admin.HIDDEN_PROFESSION)
async def set_salary_profession(m: Message, value: int, item_id: int, editing_content: bool):
    """Установка зарплаты профессии и переход к выбору типа"""
    await db.Profession.update.values(salary=value).where(db.Profession.id == item_id).gino.status()


@bot.on.private_message(StateRule(Admin.HIDDEN_PROFESSION), PayloadMapRule({"service_profession": bool}), AdminRule())
@allow_edit_content("Profession", state=Admin.PROFESSION_BONUS)
async def set_special_profession(m: Message, item_id: int, editing_content: bool):
    """
    Установка специального типа профессии (сервисная/обычная).
    Если не редактируется существующая запись, переходит к настройке бонусов.
    """
    await db.Profession.update.values(special=m.payload['service_profession']).where(
        db.Profession.id == item_id).gino.status()
    if not editing_content:
        await m.answer('Укажите бонусы к характеристикам в карте экспедитора', keyboard=Keyboard())
        reply, keyboard = await info_profession_bonus(item_id)
        await m.answer(reply, keyboard=keyboard)


@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent, StateRule(Admin.PROFESSION_BONUS), PayloadMapRule({'profession_id': int, 'attribute_id': int, 'action': 'select'}), AdminRule())
async def select_bonus_profession(m: MessageEvent):
    """Обработчик выбора атрибута для настройки бонуса профессии"""
    attribute = await db.select([db.Attribute.name]).where(db.Attribute.id == m.payload['attribute_id']).gino.scalar()
    bonus = await db.select([db.ProfessionBonus.bonus]).where(
        and_(db.ProfessionBonus.profession_id == m.payload['profession_id'], db.ProfessionBonus.attribute_id == m.payload['attribute_id'])
    ).gino.scalar()
    if not bonus:
        bonus = 0
    reply = f'Текущий уровень бонуса к «{attribute}»: {"+" if bonus >= 0 else ""}{bonus}'
    keyboard = keyboards.gen_profession_bonus(m.payload['profession_id'], m.payload['attribute_id'])
    await m.edit_message(reply, keyboard=keyboard.get_json())


@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent, StateRule(Admin.PROFESSION_BONUS), PayloadMapRule({"profession_id": int, 'attribute_id': int, 'add': int}), AdminRule())
async def change_profession_bonus(m: MessageEvent):
    """Изменение бонуса профессии для выбранного атрибута"""
    exist = await db.select([db.ProfessionBonus.id]).where(
        and_(db.ProfessionBonus.profession_id == m.payload['profession_id'], db.ProfessionBonus.attribute_id == m.payload['attribute_id'])
    ).gino.scalar()
    if not exist:
        current = 0
        await db.ProfessionBonus.create(profession_id=m.payload['profession_id'], attribute_id=m.payload['attribute_id'], bonus=m.payload['add'])
    else:
        current = await db.select([db.ProfessionBonus.bonus]).where(
            and_(db.ProfessionBonus.profession_id == m.payload['profession_id'],
                 db.ProfessionBonus.attribute_id == m.payload['attribute_id'])
        ).gino.scalar()
        if current + m.payload['add'] == 0:
            await db.ProfessionBonus.delete.where(
                and_(db.ProfessionBonus.profession_id == m.payload['profession_id'],
                     db.ProfessionBonus.attribute_id == m.payload['attribute_id'])
            ).gino.status()
        else:
            await db.ProfessionBonus.update.values(bonus=db.ProfessionBonus.bonus + m.payload['add']).where(
                and_(db.ProfessionBonus.profession_id == m.payload['profession_id'],
                     db.ProfessionBonus.attribute_id == m.payload['attribute_id'])
            ).gino.status()
    attribute = await db.select([db.Attribute.name]).where(db.Attribute.id == m.payload['attribute_id']).gino.scalar()
    reply = f'Текущий уровень бонуса к «{attribute}»: {"+" if current + m.payload['add'] >= 0 else ""}{current + m.payload['add']}'
    keyboard = keyboards.gen_profession_bonus(m.payload['profession_id'], m.payload['attribute_id'])
    await m.edit_message(reply, keyboard=keyboard.get_json())


@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent, StateRule(Admin.PROFESSION_BONUS), PayloadMapRule({"profession_id": int, 'action': 'back'}), AdminRule())
async def back_profession_bonuses(m: MessageEvent):
    """Возврат к списку бонусов профессии"""
    reply, keyboard = await info_profession_bonus(m.payload['profession_id'])
    await m.edit_message(reply, keyboard=keyboard)


@bot.on.private_message(StateRule(Admin.PROFESSION_BONUS), PayloadMapRule({"profession_id": int, 'action': 'save'}), AdminRule())
@allow_edit_content('Profession', end=True, text='Профессия успешно создана')
async def save_profession_bonus(m: Message, item_id: int, editing_content: bool):
    """Сохранение профессии после настройки бонусов"""
    pass


@bot.on.private_message(StateRule(f"{Admin.SELECT_ACTION}_Profession"), PayloadRule({"Profession": "delete"}),
                        AdminRule())
async def select_id_to_delete_profession(m: Message):
    """Выбор профессии для удаления"""
    reply = messages.professions_list
    professions = await db.select([db.Profession.name]).order_by(db.Profession.id.asc()).gino.all()
    if not professions:
        return "Профессии ещё не созданы"
    for i, profession in enumerate(professions):
        reply = f"{reply}{i + 1}. {profession.name}\n"
    states.set(m.from_id, Admin.ID_PROFESSION)
    await m.answer(reply)


@bot.on.private_message(StateRule(Admin.ID_PROFESSION), NumericRule(), AdminRule())
async def delete_profession(m: Message, value: int):
    """Удаление выбранной профессии"""
    profession_id = await db.select([db.Profession.id]).order_by(db.Profession.id.asc()).offset(value - 1).limit(1).gino.scalar()
    await db.Profession.delete.where(db.Profession.id == profession_id).gino.status()
    states.set(m.from_id, f"{Admin.SELECT_ACTION}_Profession")
    await m.answer(messages.profession_deleted,
                   keyboard=keyboards.gen_type_change_content("Profession"))
    await send_content_page(m, "Profession", 1)
