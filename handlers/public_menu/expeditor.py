from random import randint

from vkbottle.bot import Message, MessageEvent
from vkbottle.dispatch.rules.base import PayloadRule, PayloadMapRule
from vkbottle import Keyboard, Text, KeyboardButtonColor, Callback, GroupEventType
from sqlalchemy import func

from loader import bot, states
from service.states import Menu, ExpeditorQuestions
from service.custom_rules import StateRule, NumericRule
from service.db_engine import db
from service.utils import get_current_form_id, get_admin_ids, show_expeditor
from service import keyboards
from service.serializers import serialize_race_bonus, serialize_item_group, serialize_item_type, parse_cooldown


@bot.on.private_message(StateRule(Menu.SHOW_FORM), PayloadRule({'form': 'new_expeditor'}))
async def new_expeditor(m: Message):
    form_id = await get_current_form_id(m.from_id)
    expeditor_id = await db.select([db.Expeditor.id]).where(db.Expeditor.form_id == form_id).gino.scalar()
    if expeditor_id:
        is_confirmed = await db.select([db.Expeditor.is_confirmed]).where(db.Expeditor.form_id == form_id).gino.scalar()
        if is_confirmed:
            await m.answer('У тебя уже есть карта экспедитора!\n'
                           'Напиши «Начать», чтобы обновить бота')
            return
        await m.answer('Дождитесь принятия или отклонения карты экспедитора администратором')
        return
    keyboard = Keyboard().add(
        Text('Продолжить', {'form': 'confirm_new_expeditor'}), KeyboardButtonColor.POSITIVE
    ).row().add(
        Text('Отклонить', {'form': 'decline_new_expeditor'}), KeyboardButtonColor.NEGATIVE
    )
    states.set(m.from_id, Menu.CONFIRM_NEW_EXPEDITOR)
    await m.answer('Встречайте Карту Экспедитора!\n\nВы сможете участвовать в экшен-системах\n\n'
                   'За создание карты экспедитора вы получите +10 к репутации во всех фракциях\n'
                   'Дочери получат +30 к фракции, которой они принадлежат',
                   keyboard=keyboard)


@bot.on.private_message(StateRule(Menu.CONFIRM_NEW_EXPEDITOR), PayloadRule({'form': 'confirm_new_expeditor'}))
async def confirm_new_expeditor(m: Message):
    await db.User.update.values(creating_expeditor=True).where(db.User.user_id == m.from_id).gino.status()
    form_id = await get_current_form_id(m.from_id)
    name = await db.select([db.Form.name]).where(db.Form.id == form_id).gino.scalar()
    expeditor = await db.Expeditor.create(form_id=form_id, name=name)
    states.set(m.from_id, f'{ExpeditorQuestions.sex}*{expeditor.id}')
    await m.answer('Благодарим за создание Карты экспедитора')
    await m.answer('Укажите свой пол:', keyboard=keyboards.sex_types)


@bot.on.private_message(StateRule(ExpeditorQuestions.sex), PayloadMapRule({'sex': int}))
async def select_sex(m: Message):
    expeditor_id = int(states.get(m.from_id).split('*')[-1])
    await db.Expeditor.update.values(sex=m.payload['sex']).where(db.Expeditor.id == expeditor_id).gino.status()
    reply = 'Выберите свою расу:\n\n'
    races = [x[0] for x in await db.select([db.Race.id]).order_by(db.Race.id.asc()).gino.all()]
    for i, race_id in enumerate(races):
        race_name = await db.select([db.Race.name]).where(db.Race.id == race_id).gino.scalar()
        reply += f'{i + 1}. {race_name} ({await serialize_race_bonus(race_id)})\n'
    states.set(m.from_id, f'{ExpeditorQuestions.race}*{expeditor_id}')
    await m.answer(reply, keyboard=Keyboard())


@bot.on.private_message(StateRule(ExpeditorQuestions.race), NumericRule())
async def select_race(m: Message, value: int):
    expeditor_id = int(states.get(m.from_id).split('*')[-1])
    value = await db.select([db.Race.id]).order_by(db.Race.id.asc()).offset(value - 1).limit(1).gino.scalar()
    if not value:
        await m.answer('Указан неверный номер расы!')
        return
    await db.Expeditor.update.values(race_id=value).where(db.Expeditor.id == expeditor_id).gino.status()
    attributes = [x[0] for x in await db.select([db.Attribute.id]).gino.all()]
    for attribute_id in attributes:
        value = randint(1, 10) + randint(1, 10) + 20
        await db.ExpeditorToAttributes.create(expeditor_id=expeditor_id, attribute_id=attribute_id, value=value)
    admins = await get_admin_ids()
    for admin_id in admins:
        request = await db.ExpeditorRequest.create(expeditor_id=expeditor_id, admin_id=admin_id)
        keyboard = Keyboard(inline=True).add(
            Callback('Принять', {'request_expeditor_id': request.id, 'action': 'confirm'}), KeyboardButtonColor.POSITIVE
        ).row().add(
            Callback('Редактировать', {'request_expeditor_id': request.id, 'action': 'edit'}), KeyboardButtonColor.PRIMARY
        ).row().add(
            Callback('Отклонить', {'request_expeditor_id': request.id, 'action': 'decline'}), KeyboardButtonColor.NEGATIVE
        )
        message = (await bot.api.messages.send(peer_id=admin_id,
                                               message=await show_expeditor(expeditor_id, admin_id),
                                               keyboard=keyboard))[0]
        await db.ExpeditorRequest.update.values(message_id=message.conversation_message_id).where(db.ExpeditorRequest.id == request.id).gino.status()
    await db.User.update.values(creating_expeditor=False).where(db.User.user_id == m.from_id).gino.status()
    reply = 'Ваша Карта экспедитора:\n\n'
    reply += await show_expeditor(expeditor_id, m.from_id)
    await m.answer(reply, keyboard=Keyboard())
    from handlers.public_menu.form import send_form  # Импорт здесь потому что хендлеры из form будут спрабатывать раньше, чем для карты экспедитора
    await send_form(m)


@bot.on.private_message(StateRule(Menu.SHOW_FORM), PayloadRule({'form': 'my_expeditor'}))
async def show_expeditor_map(m: Message):
    form_id = await get_current_form_id(m.from_id)
    is_confirmed = await db.select([db.Expeditor.is_confirmed]).where(db.Expeditor.form_id == form_id).gino.scalar()
    if not is_confirmed:
        await m.answer('Ваша карта экспедитора на рассмотрении! Дождитесь решения администрации')
        return
    expeditor_id = await db.select([db.Expeditor.id]).where(db.Expeditor.form_id == form_id).gino.scalar()
    reply = await show_expeditor(expeditor_id, m.from_id)
    keyboard = Keyboard(inline=True).add(
        Text('Инвентарь', {'inventory': 'show'}), KeyboardButtonColor.PRIMARY
    )
    await m.answer(reply, keyboard=keyboard)


async def show_page_inventory(m: Message | MessageEvent, page: int, expeditor_id: int):
    row_id = await db.select([db.ExpeditorToItems.id]).where(db.ExpeditorToItems.expeditor_id == expeditor_id).order_by(db.ExpeditorToItems.id.asc()).offset(page - 1).limit(1).gino.scalar()
    if not row_id:
        await m.answer('Далеко куда-то ушли вы')
        return
    item_id, count_use = await db.select([db.ExpeditorToItems.item_id, db.ExpeditorToItems.count_use]).where(db.ExpeditorToItems.expeditor_id == expeditor_id).order_by(db.ExpeditorToItems.id.asc()).offset(page - 1).limit(1).gino.first()
    count = await db.select([func.count(db.ExpeditorToItems.id)]).where(db.ExpeditorToItems.expeditor_id == expeditor_id).gino.scalar()
    if count > 0:
        keyboard = Keyboard(inline=True)
    else:
        keyboard = None
    if page > 1:
        keyboard.add(Callback('<-', {'inventory_page': page - 1}), KeyboardButtonColor.PRIMARY)
    if page < count:
        keyboard.add(Callback('->', {'inventory_page': page + 1}), KeyboardButtonColor.PRIMARY)
    item = await db.Item.get(item_id)
    reply = (f'Название: {item.name}\n'
             f'Описание: {item.description}\n'
             f'Группа: {await serialize_item_group(item.group_id)}\n'
             f'Тип: {await serialize_item_type(item.type_id)}\n'
             f'Количество возможных использований: {item.count_use} раз\n'
             f'Количество доступных использований: {item.count_use - count_use} раз\n'
             f'Количество циклов действия: {item.action_time}\n'
             f'Время действия: {parse_cooldown(item.time_use)}')
    if isinstance(m, Message):
        await m.answer(message=reply, keyboard=keyboard, attachment=item.photo)
    else:
        await m.edit_message(message=reply, keyboard=keyboard, attachment=item.photo)


@bot.on.private_message(StateRule(Menu.SHOW_FORM), PayloadRule({'inventory': 'show'}))
async def show_inventory(m: Message):
    form_id = await get_current_form_id(m.from_id)
    expeditor_id = await db.select([db.Expeditor.id]).where(db.Expeditor.form_id == form_id).gino.scalar()
    exist = await db.select([func.count(db.ExpeditorToItems.id)]).where(db.ExpeditorToItems.expeditor_id == expeditor_id).gino.scalar()
    if not exist:
        await m.answer('Инвентарь пуст')
        return
    await show_page_inventory(m, 1, expeditor_id)


@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent, PayloadMapRule({'inventory_page': int}))
async def page_inventory(m: MessageEvent):
    form_id = await get_current_form_id(m.user_id)
    expeditor_id = await db.select([db.Expeditor.id]).where(db.Expeditor.form_id == form_id).gino.scalar()
    await show_page_inventory(m, m.payload['inventory_page'], expeditor_id)
