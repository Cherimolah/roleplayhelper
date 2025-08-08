from vkbottle.bot import Message, MessageEvent
from vkbottle import Keyboard, GroupEventType, Callback, KeyboardButtonColor
from vkbottle.dispatch.rules.base import PayloadRule, PayloadMapRule
from sqlalchemy import and_, func

from loader import bot, states
from service.custom_rules import StateRule, AdminRule, NumericRule
from service.states import Admin
from service.db_engine import db
from service.utils import send_content_page, allow_edit_content, FormatDataException
from service.serializers import info_expeditor_attributes, info_expeditor_debuffs, info_expeditor_items
from service import keyboards


@bot.on.private_message(StateRule(f"{Admin.SELECT_ACTION}_Expeditor"), PayloadRule({"Expeditor": "add"}), AdminRule())
async def create_quest(m: Message):
    await m.answer('Создание Карты экспедитора из админ-панели не поддерживается')


@bot.on.private_message(StateRule(Admin.EXPEDITOR_NAME), AdminRule())
@allow_edit_content('Expeditor')
async def set_expeditor_name(m: Message, item_id: int, editing_content: bool):
    # No need to set name expeditor by admin panel
    pass


@bot.on.private_message(StateRule(Admin.EXPEDITOR_SEX), PayloadMapRule({'sex': int}), AdminRule())
@allow_edit_content('Expeditor')
async def set_expeditor_sex(m: Message, item_id: int, editing_content: bool):
    await db.Expeditor.update.values(sex=m.payload['sex']).where(db.Expeditor.id == item_id).gino.status()


@bot.on.private_message(StateRule(Admin.EXPEDITOR_RACE), NumericRule(), AdminRule())
@allow_edit_content('Expeditor')
async def set_expeditor_race(m: Message, item_id: int, editing_content: bool, value: int):
    race_id = await db.select([db.Race.id]).order_by(db.Race.id.asc()).offset(value - 1).limit(1).gino.scalar()
    if not race_id:
        raise FormatDataException('Неправильный номер расы!')
    await db.Expeditor.update.values(race_id=race_id).where(db.Expeditor.id == item_id).gino.status()


@bot.on.private_message(StateRule(Admin.EXPEDITOR_PREGNANT), PayloadRule({'delete_expeditor_pregnant': True}), AdminRule())
@allow_edit_content('Expeditor')
async def set_expeditor_pregnant(m: Message, item_id: int, editing_content: bool):
    await db.Expeditor.update.values(pregnant=None).where(db.Expeditor.id == item_id).gino.status()


@bot.on.private_message(StateRule(Admin.EXPEDITOR_PREGNANT), AdminRule())
@allow_edit_content('Expeditor')
async def set_expeditor_pregnant(m: Message, item_id: int, editing_content: bool):
    await db.Expeditor.update.values(pregnant=m.text).where(db.Expeditor.id == item_id).gino.status()


@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent, StateRule(Admin.EXPEDITOR_ATTRIBUTES), PayloadMapRule({'expeditor_id': int, 'attributes': 'back'}), AdminRule())
async def back_attrs(m: MessageEvent):
    expeditor_id = m.payload['expeditor_id']
    reply, keyboard = await info_expeditor_attributes(expeditor_id)
    await m.edit_message(message=reply, keyboard=keyboard.get_json())


@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent, StateRule(Admin.EXPEDITOR_ATTRIBUTES), PayloadMapRule({'expeditor_id': int, 'attribute_id': int, 'action': 'select_attribute'}), AdminRule())
async def select_attribute(m: MessageEvent):
    attribute_id = m.payload['attribute_id']
    expeditor_id = m.payload['expeditor_id']
    state = f'{Admin.EXPEDITOR_ATTRIBUTES}*{expeditor_id}*{attribute_id}'
    await db.User.update.values(state=state).where(db.User.user_id == m.user_id).gino.status()
    attribute_name = await db.select([db.Attribute.name]).where(db.Attribute.id == attribute_id).gino.scalar()
    value = await db.select([db.ExpeditorToAttributes.value]).where(
        and_(db.ExpeditorToAttributes.expeditor_id == expeditor_id, db.ExpeditorToAttributes.attribute_id == attribute_id)
    ).gino.scalar()
    reply = f'Текущее значение «{attribute_name}»: {value}'
    keyboard = Keyboard(inline=True).add(
        Callback('-5', {'expeditor_id': expeditor_id, 'attribute_id': attribute_id, 'delta': -5}), KeyboardButtonColor.PRIMARY
    ).add(
        Callback('-1', {'expeditor_id': expeditor_id, 'attribute_id': attribute_id, 'delta': -1}), KeyboardButtonColor.PRIMARY
    ).add(
        Callback('+1', {'expeditor_id': expeditor_id, 'attribute_id': attribute_id, 'delta': 1}), KeyboardButtonColor.PRIMARY
    ).add(
        Callback('+5', {'expeditor_id': expeditor_id, 'attribute_id': attribute_id, 'delta': 5}), KeyboardButtonColor.PRIMARY
    ).row().add(
        Callback('-10', {'expeditor_id': expeditor_id, 'attribute_id': attribute_id, 'delta': -10}), KeyboardButtonColor.PRIMARY
    ).add(
        Callback('+10', {'expeditor_id': expeditor_id, 'attribute_id': attribute_id, 'delta': 10}), KeyboardButtonColor.PRIMARY
    ).row().add(
        Callback('Назад', {'expeditor_id': expeditor_id, 'attributes': 'back'}), KeyboardButtonColor.NEGATIVE
    )
    await m.edit_message(message=reply, keyboard=keyboard.get_json())


@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent, StateRule(Admin.EXPEDITOR_ATTRIBUTES), PayloadMapRule({'expeditor_id': int, 'attribute_id': int, 'delta': int}), AdminRule())
async def update_attribute(m: MessageEvent):
    expeditor_id = m.payload['expeditor_id']
    attribute_id = m.payload['attribute_id']
    delta = m.payload['delta']
    await db.ExpeditorToAttributes.update.values(value=db.ExpeditorToAttributes.value + delta).where(
        and_(db.ExpeditorToAttributes.attribute_id == attribute_id, db.ExpeditorToAttributes.expeditor_id == expeditor_id)
    ).gino.status()
    await select_attribute(m)


@bot.on.private_message(StateRule(Admin.EXPEDITOR_ATTRIBUTES), PayloadRule({'action': 'save_attribute'}), AdminRule())
@allow_edit_content('Expeditor')
async def save_content(m: Message, item_id: int, editing_content: bool):
    # Changes saving automatically
    pass


@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent, PayloadMapRule({'expeditor_id': int, 'action': 'back_debuffs'}), StateRule(Admin.EXPEDITOR_SELECT_TYPE_DEBUFF), AdminRule())
@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent, PayloadMapRule({'expeditor_id': int, 'action': 'back_delete_debuff'}), StateRule(Admin.EXPEDITOR_DELETE_DEBUFF), AdminRule())
async def back_debuffs(m: MessageEvent):
    expeditor_id = m.payload['expeditor_id']
    reply, keyboard = await info_expeditor_debuffs(expeditor_id)
    await db.User.update.values(state=f'{Admin.EXPEDITOR_DEBUFFS}*{expeditor_id}').where(db.User.user_id == m.user_id).gino.status()
    await m.edit_message(message=reply, keyboard=keyboard.get_json())


@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent, PayloadMapRule({'expeditor_id': int, 'action': 'add_debuff'}), StateRule(Admin.EXPEDITOR_DEBUFFS), AdminRule())
@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent, PayloadMapRule({'expeditor_id': int, 'action': 'back_add_debuff'}), StateRule(Admin.EXPEDITOR_ADD_DEBUFF), AdminRule())
async def select_debuff_to_add(m: MessageEvent):
    debuffs = await db.select([func.count(db.StateDebuff.id)]).gino.scalar()
    if not debuffs:
        await m.show_snackbar('На данный момент не создано никаких дебафов')
        return
    reply = 'Выберите тип дебафа, который хотите выдать:'
    debuff_types = await db.select([db.DebuffType.id, db.DebuffType.name]).order_by(db.DebuffType.id.asc()).gino.all()
    keyboard = Keyboard(inline=True)
    expeditor_id = m.payload['expeditor_id']
    for id, name in debuff_types:
        keyboard.add(
            Callback(name, {'expeditor_id': expeditor_id, 'action': f'add_debuff_type', 'debuff_type_id': id}), KeyboardButtonColor.PRIMARY
        )
        keyboard.row()
    keyboard.add(
        Callback('Назад', {'expeditor_id': expeditor_id, 'action': 'back_debuffs'}), KeyboardButtonColor.NEGATIVE
    )
    await db.User.update.values(state=f'{Admin.EXPEDITOR_SELECT_TYPE_DEBUFF}*{expeditor_id}').where(db.User.user_id == m.user_id).gino.status()
    await m.edit_message(reply, keyboard=keyboard.get_json())


@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent, PayloadMapRule({'expeditor_id': int, 'action': f'add_debuff_type', 'debuff_type_id': int}), StateRule(Admin.EXPEDITOR_SELECT_TYPE_DEBUFF), AdminRule())
async def add_debuff_type(m: MessageEvent):
    expeditor_id = m.payload['expeditor_id']
    debuff_type = m.payload['debuff_type_id']
    debuffs = [x[0] for x in await db.select([db.StateDebuff.name]).where(db.StateDebuff.type_id == debuff_type).order_by(db.StateDebuff.id.asc()).gino.all()]
    if not debuffs:
        await m.show_snackbar('На данный момент не создано дебафов с таким типом')
        return
    reply = 'Выберите дебафы, которые хотите добавить\n'
    for i, name in enumerate(debuffs):
        reply += f'{i + 1}. {name}\n'
    keyboard = Keyboard(inline=True).add(
        Callback('Назад', {'expeditor_id': expeditor_id, 'action': 'back_add_debuff'}), KeyboardButtonColor.NEGATIVE
    )
    await db.User.update.values(state=f'{Admin.EXPEDITOR_ADD_DEBUFF}*{expeditor_id}*{debuff_type}').where(db.User.user_id == m.user_id).gino.status()
    await m.edit_message(reply, keyboard=keyboard.get_json())


@bot.on.private_message(StateRule(Admin.EXPEDITOR_ADD_DEBUFF), NumericRule(), AdminRule())
async def add_debuff(m: Message, value: int):
    _, expeditor_id, debuff_type_id = states.get(m.from_id).split('*')
    expeditor_id = int(expeditor_id)
    debuff_type_id = int(debuff_type_id)
    debuff_id = await db.select([db.StateDebuff.id]).where(db.StateDebuff.type_id == debuff_type_id).order_by(db.StateDebuff.id.asc()).offset(value - 1).limit(1).gino.scalar()
    if not debuff_id:
        await m.answer('Неправильный номер дебафа')
        return
    await db.ExpeditorToDebuffs.create(expeditor_id=expeditor_id, debuff_id=debuff_id)
    await m.answer('Дебаф успешно добавлен')
    states.set(m.from_id, f'{Admin.EXPEDITOR_DEBUFFS}*{expeditor_id}')
    reply, keyboard = await info_expeditor_debuffs(expeditor_id)
    await m.answer(message=reply, keyboard=keyboard)


@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent, PayloadMapRule({'expeditor_id': int, 'action': 'delete_debuff'}), StateRule(Admin.EXPEDITOR_DEBUFFS), AdminRule())
async def select_delete_debuff(m: MessageEvent):
    expeditor_id = m.payload['expeditor_id']
    active_debuffs = [x[0] for x in await db.select([db.ExpeditorToDebuffs.debuff_id]).where(db.ExpeditorToDebuffs.expeditor_id == expeditor_id).order_by(db.ExpeditorToDebuffs.id.asc()).gino.all()]
    if not active_debuffs:
        await m.show_snackbar('Отсутствуют активные дебафы')
        return
    reply = 'Выберите дебаф, который хотите удалить:\n\n'
    for i, debuff_id in enumerate(active_debuffs):
        name = await db.select([db.StateDebuff.name]).where(db.StateDebuff.id == debuff_id).gino.scalar()
        reply += f'{i + 1}. {name}\n'
    keyboard = Keyboard(inline=True).add(
        Callback('Назад', {'expeditor_id': expeditor_id, 'action': 'back_delete_debuff'}), KeyboardButtonColor.NEGATIVE
    )
    await db.User.update.values(state=f'{Admin.EXPEDITOR_DELETE_DEBUFF}*{expeditor_id}').where(
        db.User.user_id == m.user_id).gino.status()
    await m.edit_message(reply, keyboard=keyboard.get_json())


@bot.on.private_message(StateRule(Admin.EXPEDITOR_DELETE_DEBUFF), NumericRule(), AdminRule())
async def delete_debuff(m: Message, value: int):
    _, expeditor_id = states.get(m.from_id).split('*')
    expeditor_id = int(expeditor_id)
    row_id = await db.select([db.ExpeditorToDebuffs.id]).where(db.ExpeditorToDebuffs.expeditor_id == expeditor_id).order_by(db.ExpeditorToDebuffs.id.asc()).offset(value - 1).limit(1).gino.scalar()
    if not row_id:
        await m.answer('Неправильный номер дебафа')
        return
    await db.ExpeditorToDebuffs.delete.where(db.ExpeditorToDebuffs.id == row_id).gino.status()
    await m.answer('Дебаф успешно удален')
    states.set(m.from_id, f'{Admin.EXPEDITOR_DEBUFFS}*{expeditor_id}')
    reply, keyboard = await info_expeditor_debuffs(expeditor_id)
    await m.answer(message=reply, keyboard=keyboard)


@bot.on.private_message(StateRule(Admin.EXPEDITOR_DEBUFFS), PayloadRule({'action': 'save_debuffs'}), AdminRule())
@allow_edit_content('Expeditor')
async def save_debuffs(m: Message, item_id: int, editing_content: bool):
    pass


@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent, PayloadMapRule({'expeditor_id': int, 'action': 'back_item'}), StateRule(Admin.EXPEDITOR_SELECT_TYPE_ITEMS), AdminRule())
@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent, PayloadMapRule({'expeditor_id': int, 'action': 'back_delete_item'}), StateRule(Admin.EXPEDITOR_DELETE_ITEMS), AdminRule())
async def back_items(m: MessageEvent):
    expeditor_id = m.payload['expeditor_id']
    reply, keyboard = await info_expeditor_items(expeditor_id)
    await db.User.update.values(state=f'{Admin.EXPEDITOR_ITEMS}*{expeditor_id}').where(db.User.user_id == m.user_id).gino.status()
    await m.edit_message(message=reply, keyboard=keyboard.get_json())


@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent, PayloadMapRule({'expeditor_id': int, 'action': 'add_item'}), StateRule(Admin.EXPEDITOR_ITEMS), AdminRule())
@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent, PayloadMapRule({'expeditor_id': int, 'action': 'back_add_item'}), StateRule(Admin.EXPEDITOR_ADD_ITEMS), AdminRule())
async def select_item_to_add(m: MessageEvent):
    items = await db.select([func.count(db.ItemGroup.id)]).gino.scalar()
    if not items:
        await m.show_snackbar('На данный момент не создано никаких предметов')
        return
    reply = 'Выберите тип предмета, который хотите выдать:'
    item_groups = await db.select([db.ItemGroup.id, db.ItemGroup.name]).order_by(db.ItemGroup.id.asc()).gino.all()
    keyboard = Keyboard(inline=True)
    expeditor_id = m.payload['expeditor_id']
    for id, name in item_groups:
        keyboard.add(
            Callback(name, {'expeditor_id': expeditor_id, 'action': f'add_item_type', 'item_type_id': id}), KeyboardButtonColor.PRIMARY
        )
        keyboard.row()
    keyboard.add(
        Callback('Назад', {'expeditor_id': expeditor_id, 'action': 'back_item'}), KeyboardButtonColor.NEGATIVE
    )
    await db.User.update.values(state=f'{Admin.EXPEDITOR_SELECT_TYPE_ITEMS}*{expeditor_id}').where(db.User.user_id == m.user_id).gino.status()
    await m.edit_message(reply, keyboard=keyboard.get_json())


@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent, PayloadMapRule({'expeditor_id': int, 'action': f'add_item_type', 'item_type_id': int}), StateRule(Admin.EXPEDITOR_SELECT_TYPE_ITEMS), AdminRule())
async def add_item_type(m: MessageEvent):
    expeditor_id = m.payload['expeditor_id']
    item_type = m.payload['item_type_id']
    items = [x[0] for x in await db.select([db.Item.name]).where(db.Item.group_id == item_type).order_by(db.Item.id.asc()).gino.all()]
    if not items:
        await m.show_snackbar('На данный момент не создано предметов с таким типом')
        return
    reply = 'Выберите предметы, которые хотите выдать:\n'
    for i, name in enumerate(items):
        reply += f'{i + 1}. {name}\n'
    keyboard = Keyboard(inline=True).add(
        Callback('Назад', {'expeditor_id': expeditor_id, 'action': 'back_add_item'}), KeyboardButtonColor.NEGATIVE
    )
    await db.User.update.values(state=f'{Admin.EXPEDITOR_ADD_ITEMS}*{expeditor_id}*{item_type}').where(db.User.user_id == m.user_id).gino.status()
    await m.edit_message(reply, keyboard=keyboard.get_json())


@bot.on.private_message(StateRule(Admin.EXPEDITOR_ADD_ITEMS), NumericRule(), AdminRule())
async def add_item(m: Message, value: int):
    _, expeditor_id, item_type_id = states.get(m.from_id).split('*')
    expeditor_id = int(expeditor_id)
    item_type_id = int(item_type_id)
    item_id = await db.select([db.Item.id]).where(db.Item.group_id == item_type_id).order_by(db.Item.id.asc()).offset(value - 1).limit(1).gino.scalar()
    if not item_id:
        await m.answer('Неправильный номер предмета')
        return
    await db.ExpeditorToItems.create(expeditor_id=expeditor_id, item_id=item_id)
    await m.answer('Предмет успешно выдан')
    states.set(m.from_id, f'{Admin.EXPEDITOR_ITEMS}*{expeditor_id}')
    reply, keyboard = await info_expeditor_items(expeditor_id)
    await m.answer(message=reply, keyboard=keyboard)


@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent, PayloadMapRule({'expeditor_id': int, 'action': 'delete_item'}), StateRule(Admin.EXPEDITOR_ITEMS), AdminRule())
async def select_delete_items(m: MessageEvent):
    expeditor_id = m.payload['expeditor_id']
    active_items = await db.select([db.ExpeditorToItems.item_id, db.ExpeditorToItems.count_use]).where(db.ExpeditorToItems.expeditor_id == expeditor_id).order_by(db.ExpeditorToItems.id.asc()).gino.all()
    if not active_items:
        await m.show_snackbar('Отсутствуют предметы в инвентаре')
        return
    reply = 'Выберите предмет, который хотите удалить:\n\n'
    for i, data in enumerate(active_items):
        item_id, count_use = data
        name, usage = await db.select([db.Item.name, db.Item.count_use]).where(db.Item.id == item_id).gino.first()
        reply += f'{i + 1}. {name} ({usage - count_use} исп. осталось)\n'
    keyboard = Keyboard(inline=True).add(
        Callback('Назад', {'expeditor_id': expeditor_id, 'action': 'back_delete_item'}), KeyboardButtonColor.NEGATIVE
    )
    await db.User.update.values(state=f'{Admin.EXPEDITOR_DELETE_ITEMS}*{expeditor_id}').where(
        db.User.user_id == m.user_id).gino.status()
    await m.edit_message(reply, keyboard=keyboard.get_json())


@bot.on.private_message(StateRule(Admin.EXPEDITOR_DELETE_ITEMS), NumericRule(), AdminRule())
async def delete_item(m: Message, value: int):
    _, expeditor_id = states.get(m.from_id).split('*')
    expeditor_id = int(expeditor_id)
    row_id = await db.select([db.ExpeditorToItems.id]).where(db.ExpeditorToItems.expeditor_id == expeditor_id).order_by(db.ExpeditorToItems.id.asc()).offset(value - 1).limit(1).gino.scalar()
    if not row_id:
        await m.answer('Неправильный номер предмета')
        return
    await db.ExpeditorToItems.delete.where(db.ExpeditorToItems.id == row_id).gino.status()
    await m.answer('Предмет успешно удален')
    states.set(m.from_id, f'{Admin.EXPEDITOR_ITEMS}*{expeditor_id}')
    reply, keyboard = await info_expeditor_items(expeditor_id)
    await m.answer(message=reply, keyboard=keyboard)


@bot.on.private_message(StateRule(Admin.EXPEDITOR_ITEMS), PayloadRule({'action': 'save_items'}), AdminRule())
@allow_edit_content('Expeditor')
async def save_items(m: Message, item_id: int, editing_content: bool):
    pass


@bot.on.private_message(StateRule(f"{Admin.SELECT_ACTION}_Expeditor"), PayloadRule({"Expeditor": "delete"}), AdminRule())
async def select_delete_quest(m: Message):
    expeditors = await db.select([db.Expeditor.name]).order_by(db.Expeditor.id.asc()).gino.all()
    if not expeditors:
        return "Карты экспедитора ещё не созданы"
    reply = "Выберите карту экспедитора для удаления:\n\n"
    for i, item in enumerate(expeditors):
        reply = f"{reply}{i + 1}. {item.name}\n"
    states.set(m.peer_id, Admin.EXPEDITOR_DELETE)
    await m.answer(reply, keyboard=Keyboard())


@bot.on.private_message(StateRule(Admin.EXPEDITOR_DELETE), NumericRule(), AdminRule())
async def delete_quest(m: Message, value: int):
    item_id = await db.select([db.Expeditor.id]).order_by(db.Expeditor.id.asc()).offset(value - 1).limit(1).gino.scalar()
    await db.Expeditor.delete.where(db.Expeditor.id == item_id).gino.status()
    states.set(m.peer_id, f"{Admin.SELECT_ACTION}_Expeditor")
    await m.answer("Карта экспедитора успешно удалена", keyboard=keyboards.gen_type_change_content("Expeditor"))
    await send_content_page(m, "Expeditor", 1)
