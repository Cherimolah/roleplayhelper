from vkbottle.bot import Message, MessageEvent
from vkbottle import Keyboard, Text, KeyboardButtonColor, GroupEventType, Callback
from vkbottle.dispatch.rules.base import PayloadRule, PayloadMapRule, AttachmentTypeRule
from vkbottle.dispatch.rules.abc import OrRule
from sqlalchemy import func

from loader import bot, states
from service.custom_rules import StateRule, AdminRule, NumericRule, JudgeRule
from service.states import Admin
from service.db_engine import db
from service import keyboards
from service.utils import send_content_page, allow_edit_content, FormatDataException, reload_image, soft_divide
from service.serializers import info_item_group, info_item_bonus, info_item_type, serialize_item_bonus, info_item_fraction, info_item_photo


@bot.on.private_message(StateRule(f"{Admin.SELECT_ACTION}_Item"), PayloadRule({"Item": "add"}), OrRule(JudgeRule(), AdminRule()))
async def create_quest(m: Message):
    item = await db.Item.create()
    states.set(m.from_id, f"{Admin.ITEM_NAME}*{item.id}")
    await m.answer("Напишите название предмета", keyboard=Keyboard())


@bot.on.private_message(StateRule(Admin.ITEM_NAME), OrRule(JudgeRule(), AdminRule()))
@allow_edit_content('Item', state=Admin.ITEM_DESCRIPTION, text='Укажите описание предмета')
async def item_name(m: Message, item_id: int, editing_content: bool):
    await db.Item.update.values(name=m.text).where(db.Item.id == item_id).gino.status()


@bot.on.private_message(StateRule(Admin.ITEM_DESCRIPTION), OrRule(JudgeRule(), AdminRule()))
@allow_edit_content('Item', state=Admin.ITEM_GROUP)
async def item_description(m: Message, item_id: int, editing_content: bool):
    await db.Item.update.values(description=m.text).where(db.Item.id == item_id).gino.status()
    if not editing_content:
        reply, keyboard = await info_item_group()
        await m.answer(reply, keyboard=keyboard)


@bot.on.private_message(StateRule(Admin.ITEM_GROUP), PayloadMapRule({"item_group": int}), OrRule(JudgeRule(), AdminRule()))
@allow_edit_content('Item', state=Admin.ITEM_TYPE)
async def item_type(m: Message, item_id: int, editing_content: bool):
    await db.Item.update.values(group_id=m.payload['item_group']).where(db.Item.id == item_id).gino.status()
    if not editing_content:
        reply, keyboard = await info_item_type()
        await m.answer(reply, keyboard=keyboard)


@bot.on.private_message(StateRule(Admin.ITEM_TYPE), PayloadMapRule({"item_type": int}), OrRule(JudgeRule(), AdminRule()))
@allow_edit_content('Item')
async def item_type(m: Message, item_id: int, editing_content: bool):
    await db.Item.update.values(type_id=m.payload['item_type']).where(db.Item.id == item_id).gino.status()
    if not editing_content:
        if m.payload['item_type'] != 2:
            states.set(m.from_id, f"{Admin.ITEM_AVAILABLE_FOR_SALE}*{item_id}")
            await m.answer('Укажите тип предмета', keyboard=keyboards.item_type)
            return
        else:
            states.set(m.from_id, f'{Admin.ITEM_COUNT_USE}*{item_id}')
            await m.answer('Укажите количество использований предмета', keyboard=Keyboard())
            return


@bot.on.private_message(StateRule(Admin.ITEM_COUNT_USE), NumericRule(min_number=2), OrRule(JudgeRule(), AdminRule()))
@allow_edit_content('Item', state=Admin.ITEM_AVAILABLE_FOR_SALE,
                    text='Укажите тип предмета', keyboard=keyboards.item_type)
async def item_count_use(m: Message, item_id: int, editing_content: bool, value: int):
    await db.Item.update.values(count_use=value).where(db.Item.id == item_id).gino.status()


@bot.on.private_message(StateRule(Admin.ITEM_AVAILABLE_FOR_SALE), PayloadMapRule({"item_type": int}), OrRule(JudgeRule(), AdminRule()))
@allow_edit_content('Item')
async def item_available_for_sale(m: Message, item_id: int, editing_content: bool):
    await db.Item.update.values(available_for_sale=m.payload['item_type']).where(db.Item.id == item_id).gino.status()
    if not editing_content:
        if m.payload['item_type'] == 1:  # Доступно в магазине
            states.set(m.from_id, f'{Admin.ITEM_PRICE}*{item_id}')
            await m.answer('Укажите цену предмета в магазине', keyboard=Keyboard())
        else:
            states.set(m.from_id, f'{Admin.ITEM_PHOTO}*{item_id}')
            reply, keyboard = await info_item_photo()
            await m.answer(reply, keyboard=keyboard)


@bot.on.private_message(StateRule(Admin.ITEM_PRICE), NumericRule(), OrRule(JudgeRule(), AdminRule()))
@allow_edit_content('Item', state=Admin.ITEM_FRACTION_ID)
async def item_price(m: Message, item_id: int, editing_content: bool, value: int):
    await db.Item.update.values(price=value).where(db.Item.id == item_id).gino.status()
    if not editing_content:
        reply, keyboard = await info_item_fraction()
        await m.answer(reply, keyboard=keyboard)


@bot.on.private_message(StateRule(Admin.ITEM_FRACTION_ID), PayloadRule({"item_for_all_fractions": True}), OrRule(JudgeRule(), AdminRule()))
@allow_edit_content('Item', state=Admin.ITEM_PHOTO, text='Отправьте изображение предмета',
                    keyboard=Keyboard().add(Text('Без фото', {"item_without_photo": True}), KeyboardButtonColor.SECONDARY))
async def item_fraction_id(m: Message, item_id: int, editing_content: bool):
    await db.Item.update.values(fraction_id=None, reputation=0).where(db.Item.id == item_id).gino.status()


@bot.on.private_message(StateRule(Admin.ITEM_FRACTION_ID), NumericRule(), OrRule(JudgeRule(), AdminRule()))
@allow_edit_content('Item', state=Admin.ITEM_REPUTATION, text='Укажите уровень необходимой репутации', keyboard=Keyboard())
async def item_reputation(m: Message, item_id: int, editing_content: bool, value: int):
    fraction_id = await db.select([db.Fraction.id]).order_by(db.Fraction.id.asc()).offset(value - 1).limit(1).gino.scalar()
    if fraction_id is None:
        raise FormatDataException('Номер не соответствует ни одной фракции')
    await db.Item.update.values(fraction_id=fraction_id).where(db.Item.id == item_id).gino.status()


@bot.on.private_message(StateRule(Admin.ITEM_REPUTATION), NumericRule(min_number=-100, max_number=100), OrRule(JudgeRule(), AdminRule()))
@allow_edit_content('Item', state=Admin.ITEM_PHOTO, text='Отправьте изображение предмета',
                    keyboard=Keyboard().add(Text('Без фото', {"item_without_photo": True}), KeyboardButtonColor.SECONDARY))
async def item_reputation(m: Message, value: int, item_id: int, editing_content: bool):
    await db.Item.update.values(reputation=value).where(db.Item.id == item_id).gino.status()


@bot.on.private_message(StateRule(Admin.ITEM_PHOTO), PayloadRule({"item_without_photo": True}), OrRule(JudgeRule(), AdminRule()))
@allow_edit_content('Item', state=Admin.ITEM_BONUS)
async def item_photo(m: Message, item_id: int, editing_content: bool):
    await db.Item.update.values(photo=None).where(db.Item.id == item_id).gino.status()
    if not editing_content:
        await show_bonus_menu(m, item_id)


@bot.on.private_message(StateRule(Admin.ITEM_PHOTO), AttachmentTypeRule('photo'), OrRule(JudgeRule(), AdminRule()))
@allow_edit_content('Item', state=Admin.ITEM_BONUS)
async def item_photo_set(m: Message, item_id: int, editing_content: bool):
    message = await m.get_full_message()
    name = await db.select([db.Item.name]).where(db.Item.id == item_id).gino.scalar()
    photo = await reload_image(message.attachments[0], f'data/items/{name}.jpg')
    await db.Item.update.values(photo=photo).where(db.Item.id == item_id).gino.status()
    if not editing_content:
        await show_bonus_menu(m, item_id)


async def show_bonus_menu(m, item_id):
    reply, keyboard = await info_item_bonus(item_id)
    if isinstance(m, Message):
        await m.answer('Укажите бонус для предмета:', keyboard=Keyboard())
        await m.answer(reply, keyboard=keyboard)
    else:
        await m.edit_message(reply, keyboard=keyboard.get_json())


@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent, StateRule(Admin.ITEM_BONUS), PayloadMapRule({"item_id": int, "action": "add_bonus"}), OrRule(JudgeRule(), AdminRule()))
async def add_item_bonus(m: MessageEvent):
    reply = 'Укажите тип бонуса:'
    keyboard = Keyboard(inline=True).add(
        Callback('Характеристики', {"select_bonus_type": 'attribute', 'item_id': m.payload['item_id']}), KeyboardButtonColor.PRIMARY
    ).row().add(
        Callback('Состояние', {"select_bonus_type": 'state', 'item_id': m.payload['item_id']}), KeyboardButtonColor.PRIMARY
    ).row().add(
        Callback('Сексуальное состояние', {"select_bonus_type": 'sex_state', 'item_id': m.payload['item_id']}), KeyboardButtonColor.PRIMARY
    ).row().add(
        Callback('Назад', {"select_bonus_type": 'back', 'item_id': m.payload['item_id']}), KeyboardButtonColor.NEGATIVE
    )
    await m.edit_message(reply, keyboard=keyboard.get_json())


@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent, StateRule(Admin.ITEM_BONUS), PayloadMapRule({"select_bonus_type": 'back', 'item_id': int}), OrRule(JudgeRule(), AdminRule()))
@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent, StateRule('delete_item_bonus'), PayloadMapRule({"select_bonus_type": 'back', 'item_id': int}), OrRule(JudgeRule(), AdminRule()))
async def edit_item_bonus(m: MessageEvent):
    await db.User.update.values(state=f'{Admin.ITEM_BONUS}*{m.payload["item_id"]}').where(db.User.user_id == m.user_id).gino.status()
    await show_bonus_menu(m, m.payload['item_id'])


@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent, StateRule(Admin.ITEM_BONUS), PayloadMapRule({"select_bonus_type": 'attribute', 'item_id': int}), OrRule(JudgeRule(), AdminRule()))
@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent, StateRule('set_bonus_attribute'), PayloadMapRule({"select_bonus_type": 'attribute', 'item_id': int}), OrRule(JudgeRule(), AdminRule()))
async def select_item_bonus_type(m: MessageEvent):
    await db.User.update.values(state=f'{Admin.ITEM_BONUS}*{m.payload["item_id"]}').gino.status()
    attributes = await db.select([*db.Attribute]).gino.all()
    keyboard = Keyboard(inline=True)
    for i, attribute in enumerate(attributes):
        keyboard.add(Callback(attribute.name, {"bonus_attribute_id": attribute.id, 'item_id': m.payload['item_id']}), KeyboardButtonColor.PRIMARY)
        if i % 2 == 1:
            keyboard.row()
    if len(keyboard.buttons[-1]) > 0:
        keyboard.row()
    keyboard.add(Callback('Назад', {"item_id": m.payload['item_id'], "action": "add_bonus"}), KeyboardButtonColor.NEGATIVE)
    reply = 'Выберите тип характеристики для бонуса'
    await m.edit_message(reply, keyboard=keyboard.get_json())


@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent, StateRule(Admin.ITEM_BONUS), PayloadMapRule({"bonus_attribute_id": int, 'item_id': int}), OrRule(JudgeRule(), AdminRule()))
async def select_item_bonus_attribute(m: MessageEvent):
    reply = 'Укажите значение для бонуса/штрафа к характеристике'
    await db.User.update.values(state=f'set_bonus_attribute*{m.payload["item_id"]}*{m.payload["bonus_attribute_id"]}').where(db.User.user_id == m.user_id).gino.status()
    keyboard = Keyboard(inline=True).add(Callback('Назад', {"select_bonus_type": 'attribute', 'item_id': m.payload['item_id']}), KeyboardButtonColor.NEGATIVE)
    await m.edit_message(reply, keyboard=keyboard.get_json())


@bot.on.private_message(StateRule('set_bonus_attribute'), NumericRule(min_number=-200, max_number=200), OrRule(JudgeRule(), AdminRule()))
async def select_item_bonus_attribute(m: Message, value: int):
    _, item_id, attribute_id = states.get(m.from_id).split('*')
    item_id = int(item_id)
    attribute_id = int(attribute_id)
    bonus = await db.select([db.Item.bonus]).where(db.Item.id == item_id).gino.scalar()
    bonus.append({'type': 'attribute', 'attribute_id': attribute_id, 'bonus': value})
    await db.Item.update.values(bonus=bonus).where(db.Item.id == item_id).gino.status()
    states.set(m.from_id, f'{Admin.ITEM_BONUS}*{item_id}')
    await show_bonus_menu(m, item_id)


@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent, StateRule(Admin.ITEM_BONUS), PayloadMapRule({"select_bonus_type": 'state', 'item_id': int}), OrRule(JudgeRule(), AdminRule()))
@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent, StateRule('add_debuff'), PayloadMapRule({"select_bonus_type": 'state', 'item_id': int}), OrRule(JudgeRule(), AdminRule()))
@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent, StateRule('delete_debuff'), PayloadMapRule({"select_bonus_type": 'state', 'item_id': int}), OrRule(JudgeRule(), AdminRule()))
async def select_item_bonus_state(m: MessageEvent):
    await db.User.update.values(state=f"{Admin.ITEM_BONUS}*{m.payload['item_id']}").where(db.User.user_id == m.user_id).gino.status()
    reply = 'Выберите вариант воздействия на состояние'
    keyboard = Keyboard(inline=True).add(
        Callback('Добавить дебаф', {"item_id": m.payload['item_id'], 'action': 'add_debuff'}), KeyboardButtonColor.PRIMARY
    ).row().add(
        Callback('Удалить дебаф', {"item_id": m.payload['item_id'], 'action': 'delete_debuff'}), KeyboardButtonColor.PRIMARY
    ).row().add(
        Callback('Удалить тип дебафов', {"item_id": m.payload['item_id'], 'action': 'delete_type_debuff'}), KeyboardButtonColor.PRIMARY
    ).row().add(
        Callback('Удалить все дебафы', {"item_id": m.payload['item_id'], 'action': 'delete_all_debuff'}), KeyboardButtonColor.PRIMARY
    ).row().add(
        Callback('Назад', {"item_id": m.payload['item_id'], "action": "add_bonus"}), KeyboardButtonColor.NEGATIVE
    )
    await m.edit_message(reply, keyboard=keyboard.get_json())


@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent, StateRule(Admin.ITEM_BONUS), PayloadMapRule({"item_id": int, 'action': 'add_debuff'}), OrRule(JudgeRule(), AdminRule()))
async def add_item_bonus_state(m: MessageEvent):
    await db.User.update.values(state=f'add_debuff*{m.payload["item_id"]}').where(db.User.user_id == m.user_id).gino.status()
    await show_page_debuffs(m, 1, m.payload['item_id'])


@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent, StateRule(Admin.ITEM_BONUS), PayloadMapRule({"item_id": int, 'action': 'delete_debuff'}), OrRule(JudgeRule(), AdminRule()))
async def add_item_bonus_state(m: MessageEvent):
    await db.User.update.values(state=f'delete_debuff*{m.payload["item_id"]}').where(db.User.user_id == m.user_id).gino.status()
    await show_page_debuffs(m, 1, m.payload['item_id'])


async def show_page_debuffs(m: MessageEvent, page: int, item_id: int):
    debuffs = await db.select([*db.StateDebuff]).order_by(db.StateDebuff.id.asc()).offset((page - 1) * 15).limit(15).gino.all()
    count = await db.select([func.count(db.StateDebuff.id)]).gino.scalar()
    reply = f'Выберите тип дебафа:\n\nСтраница {page}/{soft_divide(count, 15)}\n'
    for i, debuff in enumerate(debuffs):
        attribute = await db.select([db.DebuffType.name]).where(db.DebuffType.id == debuff.type_id).gino.scalar()
        reply += f'{(page - 1) * 15 + i + 1}. {debuff.name} / {attribute} {"+" if debuff.penalty >= 0 else ""}{debuff.penalty}\n'
    keyboard = Keyboard(inline=True)
    if page > 1:
        keyboard.add(Callback('<-', {"debuff_page": page - 1}), KeyboardButtonColor.PRIMARY)
    if count > page * 15:
        keyboard.add(Callback('->', {"debuff_page": page + 1}), KeyboardButtonColor.PRIMARY)
    if page > 1 or count > page * 15:
        keyboard.row()
    keyboard.add(Callback('Назад', {"select_bonus_type": 'state', 'item_id': item_id}))
    await m.edit_message(reply, keyboard=keyboard.get_json())


@bot.on.private_message(StateRule('add_debuff'), NumericRule(), OrRule(JudgeRule(), AdminRule()))
async def add_item_bonus_state(m: Message, value: int):
    debuff_id = await db.select([db.StateDebuff.id]).order_by(db.StateDebuff.id.asc()).offset(value - 1).limit(1).gino.scalar()
    item_id = int(states.get(m.from_id).split('*')[-1])
    bonus = await db.select([db.Item.bonus]).where(db.Item.id == item_id).gino.scalar()
    bonus.append({'type': 'state', 'action': 'add', 'debuff_id': debuff_id})
    await db.Item.update.values(bonus=bonus).where(db.Item.id == item_id).gino.status()
    states.set(m.from_id, f"{Admin.ITEM_BONUS}*{item_id}")
    await show_bonus_menu(m, item_id)


@bot.on.private_message(StateRule('delete_debuff'), NumericRule(), OrRule(JudgeRule(), AdminRule()))
async def add_item_bonus_state(m: Message, value: int):
    debuff_id = await db.select([db.StateDebuff.id]).order_by(db.StateDebuff.id.asc()).offset(value - 1).limit(1).gino.scalar()
    item_id = int(states.get(m.from_id).split('*')[-1])
    bonus = await db.select([db.Item.bonus]).where(db.Item.id == item_id).gino.scalar()
    bonus.append({'type': 'state', 'action': 'delete', 'debuff_id': debuff_id})
    await db.Item.update.values(bonus=bonus).where(db.Item.id == item_id).gino.status()
    states.set(m.from_id, f"{Admin.ITEM_BONUS}*{item_id}")
    await show_bonus_menu(m, item_id)


@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent, StateRule(Admin.ITEM_BONUS), PayloadMapRule({"item_id": int, 'action': 'delete_type_debuff'}), OrRule(JudgeRule(), AdminRule()))
async def delete_type_debuff(m: MessageEvent):
    types = await db.select([*db.DebuffType]).order_by(db.DebuffType.id.asc()).gino.all()
    reply = 'Выберите тип дебафа, который будет удален при использовании предмета'
    keyboard = Keyboard(inline=True)
    for type in types:
        keyboard.add(Callback(type.name, {"item_id": m.payload['item_id'], 'action': 'select_type_debuff_delete', 'type_id': type.id}), KeyboardButtonColor.PRIMARY).row()
    keyboard.add(Callback('Назад', {"select_bonus_type": 'state', 'item_id': m.payload['item_id']}), KeyboardButtonColor.NEGATIVE)
    await m.edit_message(reply, keyboard=keyboard.get_json())


@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent, StateRule(Admin.ITEM_BONUS), PayloadMapRule({"item_id": int, 'action': 'select_type_debuff_delete', 'type_id': int}), OrRule(JudgeRule(), AdminRule()))
async def select_type_debuff_delete(m: MessageEvent):
    bonus = await db.select([db.Item.bonus]).where(db.Item.id == m.payload['item_id']).gino.scalar()
    bonus.append({"type": 'state', 'action': 'delete_type', 'type_id': m.payload['type_id']})
    await db.Item.update.values(bonus=bonus).where(db.Item.id == m.payload['item_id']).gino.status()
    await show_bonus_menu(m, m.payload['item_id'])


@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent, StateRule(Admin.ITEM_BONUS), PayloadMapRule({"item_id": int, 'action': 'delete_all_debuff'}), OrRule(JudgeRule(), AdminRule()))
async def delete_all_debuff(m: MessageEvent):
    bonus = await db.select([db.Item.bonus]).where(db.Item.id == m.payload['item_id']).gino.scalar()
    bonus.append({"type": 'state', 'action': 'delete_all'})
    await db.Item.update.values(bonus=bonus).where(db.Item.id == m.payload['item_id']).gino.status()
    await show_bonus_menu(m, m.payload['item_id'])


@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent, StateRule(Admin.ITEM_BONUS), PayloadMapRule({"select_bonus_type": 'sex_state', 'item_id': int}), OrRule(JudgeRule(), AdminRule()))
@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent, StateRule('set_libido'), PayloadMapRule({"select_bonus_type": 'sex_state', 'item_id': int}), OrRule(JudgeRule(), AdminRule()))
@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent, StateRule('set_subordination'), PayloadMapRule({"select_bonus_type": 'sex_state', 'item_id': int}), OrRule(JudgeRule(), AdminRule()))
async def select_bonus_type(m: MessageEvent):
    await db.User.update.values(state=f'{Admin.ITEM_BONUS}*{m.payload["item_id"]}').where(db.User.user_id == m.user_id).gino.status()
    reply = 'Выберите тип бонуса'
    keyboard = Keyboard(inline=True).add(
        Callback('Подчинение', {'bonus_type': 'subordination', 'item_id': m.payload['item_id']}), KeyboardButtonColor.PRIMARY
    ).row().add(
        Callback('Либидо', {'bonus_type': 'libido', 'item_id': m.payload['item_id']}), KeyboardButtonColor.PRIMARY
    ).row().add(
        Callback('Оплодотворение', {'bonus_type': 'pregnant', 'item_id': m.payload['item_id']}), KeyboardButtonColor.PRIMARY
    ).row().add(
        Callback('Назад', {"item_id": m.payload['item_id'], "action": "add_bonus"}), KeyboardButtonColor.NEGATIVE
    )
    await m.edit_message(reply, keyboard=keyboard.get_json())


@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent, StateRule(Admin.ITEM_BONUS), PayloadMapRule({'bonus_type': 'subordination', 'item_id': int}), OrRule(JudgeRule(), AdminRule()))
async def select_bonus_type(m: MessageEvent):
    await db.User.update.values(state=f'set_subordination*{m.payload["item_id"]}').where(db.User.user_id == m.user_id).gino.status()
    reply = 'Укажите бонус/штраф к Подчинение при использовании предмета'
    keyboard = Keyboard(inline=True).add(
        Callback('Назад', {"select_bonus_type": 'sex_state', 'item_id': m.payload['item_id']}), KeyboardButtonColor.NEGATIVE
    )
    await m.edit_message(reply, keyboard=keyboard.get_json())


@bot.on.private_message(StateRule('set_subordination'), NumericRule(min_number=-100, max_number=100), OrRule(JudgeRule(), AdminRule()))
async def select_bonus_state(m: Message, value: int):
    item_id = int(states.get(m.from_id).split('*')[-1])
    bonus = await db.select([db.Item.bonus]).where(db.Item.id == item_id).gino.scalar()
    bonus.append({"type": 'sex_state', 'attribute': 'subordination', 'bonus': value})
    await db.Item.update.values(bonus=bonus).where(db.Item.id == item_id).gino.status()
    states.set(m.from_id, f'{Admin.ITEM_BONUS}*{item_id}')
    await show_bonus_menu(m, item_id)


@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent, StateRule(Admin.ITEM_BONUS), PayloadMapRule({'bonus_type': 'libido', 'item_id': int}), OrRule(JudgeRule(), AdminRule()))
async def select_bonus_type(m: MessageEvent):
    await db.User.update.values(state=f'set_libido*{m.payload["item_id"]}').where(
        db.User.user_id == m.user_id).gino.status()
    reply = 'Укажите бонус/штраф к Либидо при использовании предмета'
    keyboard = Keyboard(inline=True).add(
        Callback('Назад', {"select_bonus_type": 'sex_state', 'item_id': m.payload['item_id']}),
        KeyboardButtonColor.NEGATIVE
    )
    await m.edit_message(reply, keyboard=keyboard.get_json())


@bot.on.private_message(StateRule('set_libido'), NumericRule(min_number=-100, max_number=100), OrRule(JudgeRule(), AdminRule()))
async def select_bonus_state(m: Message, value: int):
    item_id = int(states.get(m.from_id).split('*')[-1])
    bonus = await db.select([db.Item.bonus]).where(db.Item.id == item_id).gino.scalar()
    bonus.append({"type": 'sex_state', 'attribute': 'libido', 'bonus': value})
    await db.Item.update.values(bonus=bonus).where(db.Item.id == item_id).gino.status()
    states.set(m.from_id, f'{Admin.ITEM_BONUS}*{item_id}')
    await show_bonus_menu(m, item_id)


@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent, StateRule(Admin.ITEM_BONUS), PayloadMapRule({'bonus_type': 'pregnant', 'item_id': int}), OrRule(JudgeRule(), AdminRule()))
@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent, StateRule('set_pregnant'), PayloadMapRule({'bonus_type': 'pregnant', 'item_id': int}), OrRule(JudgeRule(), AdminRule()))
async def select_bonus_type(m: MessageEvent):
    await db.User.update.values(state=f'{Admin.ITEM_BONUS}*{m.payload["item_id"]}').where(db.User.user_id == m.user_id).gino.status()
    reply = 'Выберите действие с состоянием Оплодотворение'
    keyboard = Keyboard(inline=True).add(
        Callback('Добавить оплодотворение', {'select_type': 'add_pregnant', 'item_id': m.payload['item_id']}), KeyboardButtonColor.PRIMARY
    ).row().add(
        Callback('Удалить оплодотворение', {'select_type': 'delete_pregnant', 'item_id': m.payload['item_id']}), KeyboardButtonColor.PRIMARY
    ).row().add(
        Callback('Назад', {"select_bonus_type": 'sex_state', 'item_id': m.payload['item_id']}), KeyboardButtonColor.NEGATIVE
    )
    await m.edit_message(reply, keyboard=keyboard.get_json())


@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent, StateRule(Admin.ITEM_BONUS), PayloadMapRule({'select_type': 'add_pregnant', 'item_id': int}), OrRule(JudgeRule(), AdminRule()))
async def select_bonus_state(m: MessageEvent):
    await db.User.update.values(state=f'set_pregnant*{m.payload["item_id"]}').where(db.User.user_id == m.user_id).gino.status()
    reply = 'Укажите строку, которая будет записана в Оплодотворение'
    keyboard = Keyboard(inline=True).add(
        Callback('Назад', {'bonus_type': 'pregnant', 'item_id': m.payload['item_id']}), KeyboardButtonColor.NEGATIVE
    )
    await m.edit_message(reply, keyboard=keyboard.get_json())


@bot.on.private_message(StateRule('set_pregnant'), OrRule(JudgeRule(), AdminRule()))
async def select_bonus_state(m: Message):
    item_id = int(states.get(m.from_id).split('*')[-1])
    bonus = await db.select([db.Item.bonus]).where(db.Item.id == item_id).gino.scalar()
    bonus.append({"type": 'sex_state', 'action': 'set_pregnant', 'text': m.text})
    await db.Item.update.values(bonus=bonus).where(db.Item.id == item_id).gino.status()
    states.set(m.from_id, f'{Admin.ITEM_BONUS}*{item_id}')
    await show_bonus_menu(m, item_id)


@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent, StateRule(Admin.ITEM_BONUS), PayloadMapRule({'select_type': 'delete_pregnant', 'item_id': int}), OrRule(JudgeRule(), AdminRule()))
async def select_bonus_type(m: MessageEvent):
    item_id = m.payload['item_id']
    bonus = await db.select([db.Item.bonus]).where(db.Item.id == item_id).gino.scalar()
    bonus.append({"type": 'sex_state', 'action': 'delete_pregnant'})
    await db.Item.update.values(bonus=bonus).where(db.Item.id == item_id).gino.status()
    await db.User.update.values(state=f'{Admin.ITEM_BONUS}*{item_id}').where(db.User.user_id == m.user_id).gino.status()
    await show_bonus_menu(m, item_id)


@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent, StateRule(Admin.ITEM_BONUS), PayloadMapRule({"item_id": int, "action": "delete_bonus"}), OrRule(JudgeRule(), AdminRule()))
async def select_bonus_type(m: MessageEvent):
    await db.User.update.values(state=f'delete_item_bonus*{m.payload["item_id"]}').where(db.User.user_id == m.user_id).gino.status()
    reply = 'Выберите бонус, который хотите удалить:\n'
    bonus = await db.select([db.Item.bonus]).where(db.Item.id == m.payload['item_id']).gino.scalar()
    reply += await serialize_item_bonus(bonus)
    keyboard = Keyboard(inline=True).add(
        Callback('Назад', {"select_bonus_type": 'back', 'item_id': m.payload['item_id']}), KeyboardButtonColor.NEGATIVE
    )
    await m.edit_message(reply, keyboard=keyboard.get_json())


@bot.on.private_message(StateRule('delete_item_bonus'), NumericRule(), OrRule(JudgeRule(), AdminRule()))
async def delete_item_bonus(m: Message, value: int):
    item_id = int(states.get(m.from_id).split('*')[-1])
    bonus = await db.select([db.Item.bonus]).where(db.Item.id == item_id).gino.scalar()
    if value > len(bonus):
        await m.answer('Номер слишком большой')
        return
    bonus.pop(value - 1)
    await db.Item.update.values(bonus=bonus).where(db.Item.id == item_id).gino.status()
    states.set(m.from_id, f'{Admin.ITEM_BONUS}*{item_id}')
    await show_bonus_menu(m, item_id)


@bot.on.private_message(StateRule(Admin.ITEM_BONUS), PayloadMapRule({"item_id": int, "action": "save_bonus"}), OrRule(JudgeRule(), AdminRule()))
@allow_edit_content('Item', end=True, text='Предмет успешно создан')
async def save_bonus(m: Message, item_id: int, editing_content: bool):
    pass


@bot.on.private_message(StateRule(f"{Admin.SELECT_ACTION}_Item"), PayloadRule({"Item": "delete"}), OrRule(JudgeRule(), AdminRule()))
async def select_delete_quest(m: Message):
    items = await db.select([db.Item.name]).order_by(db.Item.id.asc()).gino.all()
    if not items:
        return "Предметы ещё не созданы"
    reply = "Выберите предмет для удаления:\n\n"
    for i, item in enumerate(items):
        reply = f"{reply}{i + 1}. {item.name}\n"
    states.set(m.peer_id, Admin.ITEM_DELETE)
    await m.answer(reply, keyboard=Keyboard())


@bot.on.private_message(StateRule(Admin.ITEM_DELETE), NumericRule(), OrRule(JudgeRule(), AdminRule()))
async def delete_quest(m: Message, value: int):
    item_id = await db.select([db.Item.id]).order_by(db.Item.id.asc()).offset(value - 1).limit(1).gino.scalar()
    await db.Item.delete.where(db.Item.id == item_id).gino.status()
    states.set(m.peer_id, f"{Admin.SELECT_ACTION}_Item")
    await m.answer("Предмет успешно удален", keyboard=keyboards.gen_type_change_content("Item"))
    await send_content_page(m, "Item", 1)

