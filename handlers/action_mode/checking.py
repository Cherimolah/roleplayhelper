import random

from vkbottle.bot import MessageEvent, Message
from vkbottle import GroupEventType, Keyboard, Text, KeyboardButtonColor, Callback
from vkbottle.dispatch.rules.base import PayloadMapRule, PayloadRule
from sqlalchemy import and_, func

from loader import bot, states
from service.custom_rules import JudgeRule, StateRule, NumericRule
from service.states import Judge
from service.db_engine import db
from service import keyboards
from service.utils import next_step, show_consequences, serialize_consequence, type_difficulties, count_difficult, count_attribute, apply_consequences, apply_item, create_mention


async def send_check(m: Message | MessageEvent, post_id: int):
    action_mode_id = await db.select([db.Post.action_mode_id]).where(db.Post.id == post_id).gino.scalar()
    actions = await db.select([*db.Action]).where(db.Action.post_id == post_id).order_by(db.Action.id.asc()).gino.all()
    await db.ActionMode.update.values(number_check=db.ActionMode.number_check + 1).where(db.ActionMode.id == action_mode_id).gino.status()
    number_check = await db.select([db.ActionMode.number_check]).where(db.ActionMode.id == action_mode_id).gino.scalar()
    judge_id = await db.select([db.ActionMode.judge_id]).where(db.ActionMode.id == action_mode_id).gino.scalar()
    if len(actions) < number_check or number_check > 5:
        if actions[-1].data['type'] == 'use_item':
            await db.ActionMode.update.values(check_status=False).where(db.ActionMode.id == action_mode_id).gino.status()
            finished = await db.select([db.ActionMode.finished]).where(db.ActionMode.id == action_mode_id).gino.scalar()
            if not finished:
                states.set(judge_id, Judge.PANEL)
                if isinstance(m, Message):
                    await m.answer('Основное меню', keyboard=keyboards.action_mode_panel)
                else:
                    await db.User.update.values(state=str(Judge.PANEL)).where(db.User.user_id == judge_id).gino.status()
                    await bot.api.messages.send(peer_id=judge_id, message='Основное меню', keyboard=keyboards.action_mode_panel)
            else:
                states.set(judge_id, Judge.WAIT_END_ACTION_MODE)
                if isinstance(m, Message):
                    await m.answer('Проверка завершена')
                else:
                    await db.User.update.values(state=str(Judge.PANEL)).where(db.User.user_id == judge_id).gino.status()
                    await bot.api.messages.send(peer_id=judge_id, message='Проверка завершена')
        await next_step(action_mode_id)
        return
    action = actions[number_check - 1]
    if action.data.get('type') == 'use_item':
        row_id = action.data['row_id']
        await apply_item(row_id)
        item_name = await db.select([db.Item.name]).select_from(
            db.ExpeditorToItems.join(db.Item, db.ExpeditorToItems.item_id == db.Item.id)
        ).where(db.ExpeditorToItems.id == row_id).gino.scalar()
        chat_id = await db.select([db.ActionMode.chat_id]).where(db.ActionMode.id == action_mode_id).gino.scalar()
        user_id = await db.select([db.Post.user_id]).where(db.Post.id == action.post_id).gino.scalar()
        reply = f'Пользователь {await create_mention(user_id)} применил предмет «{item_name}»'
        await bot.api.messages.send(peer_id=2000000000 + chat_id, message=reply)
        return await send_check(m, post_id)
    elif action.data.get('type') == 'action':
        text = action.data['text']
    elif action.data.get('type') == 'pvp':
        user_id = action.data['user_id']
        name = await db.select([db.Form.name]).where(db.Form.user_id == user_id).gino.scalar()
        user = (await bot.api.users.get(user_ids=[user_id]))[0]
        text = f'PvP с пользователем [id{user_id}|{name} {user.first_name} {user.last_name}]'
    states.set(judge_id, f'{Judge.SET_BONUS}*{action.id}')
    if isinstance(m, Message):
        await m.answer(f'Проверка действия «{text}»')
        await m.answer('Укажите бонус/штраф судьи от -100 до 100 включительно', keyboard=Keyboard())
    else:
        await bot.api.messages.send(peer_id=judge_id, message=f'Проверка действия «{text}»')
        await db.User.update.values(state=f'{Judge.SET_BONUS}*{action.id}').where(db.User.user_id == judge_id).gino.status()
        await bot.api.messages.send(peer_id=judge_id, message='Укажите бонус/штраф судьи от -100 до 100 включительно',
                                    keyboard=Keyboard())


@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent, PayloadMapRule({'start_check': int}), JudgeRule())
async def start_check(m: MessageEvent):
    state = states.get(m.user_id)
    if str(state) != str(Judge.PANEL):
        await m.show_snackbar('Выйдите сначала в основное меню управления экшен-режимом')
        return
    post_id = m.payload['start_check']
    post = await db.Post.get(post_id)
    if not post:
        await m.show_snackbar('Пост уже неактулен')
        return
    if post.started_check:
        await m.show_snackbar('Пост уже проверяется/-лся')
        return
    await db.Post.update.values(started_check=True).where(db.Post.id == post.id).gino.status()
    reply = f'Начинаем проверку поста'
    await m.edit_message(reply, keyboard=Keyboard().get_json(), keep_forward_messages=True)
    states.set(m.user_id, Judge.DIFFICULT)
    await bot.api.messages.send(peer_id=m.user_id, message='Укажите базовую сложность проверки поста',
                                keyboard=keyboards.gen_difficulties(post_id))


@bot.on.private_message(StateRule(Judge.DIFFICULT), PayloadMapRule({'difficult': int, 'post_id': int}), JudgeRule())
async def set_difficult(m: Message):
    difficult = m.payload['difficult']
    post_id = m.payload['post_id']
    await db.Post.update.values(difficult=difficult).where(db.Post.id == post_id).gino.status()
    states.set(m.from_id, Judge.CAN_DECLINE)
    await m.answer('Укажите сможет ли игрок отказаться от проверки', keyboard=keyboards.gen_can_decline_check(post_id))


@bot.on.private_message(StateRule(Judge.CAN_DECLINE), PayloadMapRule({'can_skip': bool, 'post_id': int}), JudgeRule())
async def set_can_dcline(m: Message):
    can_skip = m.payload['can_skip']
    post_id = m.payload['post_id']
    await db.Post.update.values(decline_check=can_skip).where(db.Post.id == post_id).gino.status()
    await send_check(m, post_id)


@bot.on.private_message(StateRule(Judge.SET_BONUS), NumericRule(min_number=-100, max_number=100), JudgeRule())
async def set_bonus_check(m: Message, value: int):
    action_id = int(states.get(m.from_id).split('*')[-1])
    await db.Action.update.values(bonus=value).where(db.Action.id == action_id).gino.status()
    states.set(m.from_id, f"{Judge.SET_ATTRIBUTE}*{action_id}")
    attributes = await db.select([db.Attribute.id, db.Attribute.name]).order_by(db.Attribute.id.asc()).gino.all()
    keyboard = Keyboard()
    for attribute in attributes:
        keyboard.add(Text(attribute[1], {'set_attribute_id': attribute[0]}), KeyboardButtonColor.PRIMARY)
        keyboard.row()
    keyboard.buttons.pop(-1)
    await m.answer('Укажите по какому параметру будет происходит проверка', keyboard=keyboard)


@bot.on.private_message(StateRule(Judge.SET_ATTRIBUTE), PayloadMapRule({'set_attribute_id': int}), JudgeRule())
@bot.on.private_message(StateRule(Judge.SET_CONSEQUENCES), PayloadRule({'group_consequences': 'back'}), JudgeRule())
async def set_attribute(m: Message):
    attribute_id = m.payload.get('set_attribute_id')
    action_id = int(states.get(m.from_id).split('*')[1])
    if attribute_id:
        await db.Action.update.values(attribute_id=attribute_id).where(db.Action.id == action_id).gino.status()
    data = await db.select([db.Action.data]).where(db.Action.id == action_id).gino.scalar()
    if data['type'] == 'action':
        keyboard = keyboards.gen_consequences()
    else:
        keyboard = keyboards.gen_consequences(double=True)
    states.set(m.from_id, f"{Judge.SET_CONSEQUENCES}*{action_id}")
    await db.User.update.values(check_action_id=action_id).where(db.User.user_id == m.from_id).gino.status()
    await m.answer(await show_consequences(action_id), keyboard=keyboard)


@bot.on.private_message(StateRule(Judge.SET_CONSEQUENCES), PayloadMapRule({'con_var': int}), JudgeRule())
@bot.on.private_message(StateRule(Judge.SET_CONSEQUENCES), PayloadRule({'set_consequence_type': 'back'}), JudgeRule())
@bot.on.private_message(StateRule(Judge.OTHER_CONSEQUENCE), PayloadRule({'set_consequence_type': 'back'}), JudgeRule())
@bot.on.private_message(StateRule(Judge.DELETE_CONSEQUENCES), PayloadRule({'set_consequence_type': 'back'}), JudgeRule())
async def select_consequence_type(m: Message):
    if m.payload and 'con_var' in m.payload:
        con_var = m.payload['con_var']
        action_id = int(states.get(m.from_id).split('*')[1])
    else:
        _, action_id, con_var, *_ = states.get(m.from_id).split('*')
    states.set(m.from_id, f'{Judge.SET_CONSEQUENCES}*{action_id}*{con_var}')
    await m.answer('Выберите группу последствий', keyboard=keyboards.groups_consequences)


@bot.on.private_message(StateRule(Judge.SET_CONSEQUENCES), PayloadMapRule({'group_consequences': int}), JudgeRule())
@bot.on.private_message(StateRule(Judge.CONSEQUENCES_DATA), PayloadRule({'set_consequence': 'back'}), JudgeRule())
async def select_group_consequence(m: Message):
    if m.payload and m.payload.get('group_consequences'):
        group_id = m.payload['group_consequences']
        _, action_id, con_var = states.get(m.from_id).split('*')
    else:
        _, action_id, con_var, group_id, _ = states.get(m.from_id).split('*')
        group_id = int(group_id)
    if group_id != 5:
        states.set(m.from_id, f'{Judge.SET_CONSEQUENCES}*{action_id}*{con_var}*{group_id}')
        await m.answer('Выберите тип последствия', keyboard=await keyboards.gen_type_consequences(group_id))
    else:
        states.set(m.from_id, f'{Judge.OTHER_CONSEQUENCE}*{action_id}*{con_var}*{group_id}*null')
        reply = 'Напишите текстовое последствие'
        keyboard = Keyboard().add(
            Text('Назад', {'set_consequence_type': 'back'}), KeyboardButtonColor.NEGATIVE
        )
        await m.answer(reply, keyboard=keyboard)


@bot.on.private_message(StateRule(Judge.OTHER_CONSEQUENCE), JudgeRule())
async def set_other_consequence(m: Message):
    _, action_id, con_var, group_id, _ = states.get(m.from_id).split('*')
    action_id = int(action_id)
    con_var = int(con_var)
    await db.Consequence.create(action_id=action_id, type=con_var, data={'type': 'other', 'text': m.text})
    await m.answer('Последствие успешно добавлено')
    await select_consequence_type(m)
    return


@bot.on.private_message(StateRule(Judge.SET_CONSEQUENCES), PayloadMapRule({'set_consequence_type': int}), JudgeRule())
async def select_type_consequences(m: Message):
    con_type = m.payload['set_consequence_type']
    _, action_id, con_var, group_id = states.get(m.from_id).split('*')
    states.set(m.from_id, f'{Judge.CONSEQUENCES_DATA}*{action_id}*{con_var}*{group_id}*{con_type}')
    keyboard = Keyboard().add(
        Text('Назад', {'set_consequence': 'back'}), KeyboardButtonColor.NEGATIVE
    )
    action_id = int(action_id)
    con_var = int(con_var)
    post_id = await db.select([db.Action.post_id]).where(db.Action.id == action_id).gino.scalar()
    user_id = await db.select([db.Post.user_id]).where(db.Post.id == post_id).gino.scalar()
    form_id = await db.select([db.Form.user_id]).where(db.Form.user_id == user_id).gino.scalar()
    expeditor_id = await db.select([db.Expeditor.id]).where(db.Expeditor.form_id == form_id).gino.scalar()
    match con_type:
        case 1:  # Получение травмы
            injuries = [x[0] for x in await db.select([db.StateDebuff.name]).where(db.StateDebuff.type_id == 1).order_by(db.StateDebuff.id.asc()).gino.all()]
            reply = 'Укажите номер травмы:\n\n'
            for i, name in enumerate(injuries):
                reply += f'{i + 1}. {name}\n'
            await m.answer(reply, keyboard=keyboard)
            return
        case 2:  # Получение безумия
            injuries = [x[0] for x in
                        await db.select([db.StateDebuff.name]).where(db.StateDebuff.type_id == 2).order_by(
                            db.StateDebuff.id.asc()).gino.all()]
            reply = 'Укажите номер безумия:\n\n'
            for i, name in enumerate(injuries):
                reply += f'{i + 1}. {name}\n'
            await m.answer(reply, keyboard=keyboard)
            return
        case 3:  # Снятие травмы
            injuries = [x[0] for x in await db.select([db.StateDebuff.name]).select_from(
                db.ExpeditorToDebuffs.join(db.StateDebuff, db.StateDebuff.id == db.ExpeditorToDebuffs.debuff_id)
            ).where(and_(db.ExpeditorToDebuffs.expeditor_id == expeditor_id, db.StateDebuff.type_id == 1)).order_by(db.ExpeditorToDebuffs.id.asc()).gino.all()]
            reply = 'Укажите номер травмы:\n\n'
            for i, name in enumerate(injuries):
                reply += f'{i + 1}. {name}\n'
            await m.answer(reply, keyboard=keyboard)
            return
        case 4:  # Снятие безумия
            injuries = [x[0] for x in await db.select([db.StateDebuff.name]).select_from(
                db.ExpeditorToDebuffs.join(db.StateDebuff, db.StateDebuff.id == db.ExpeditorToDebuffs.debuff_id)
            ).where(and_(db.ExpeditorToDebuffs.expeditor_id == expeditor_id, db.StateDebuff.type_id == 2)).order_by(
                db.ExpeditorToDebuffs.id.asc()).gino.all()]
            reply = 'Укажите номер безумия:\n\n'
            for i, name in enumerate(injuries):
                reply += f'{i + 1}. {name}\n'
            await m.answer(reply, keyboard=keyboard)
            return
        case 5:  # Снятие всех травм
            await db.Consequence.create(action_id=action_id, data={'type': 'delete_debuff_type', 'debuff_type_id': 1}, type=con_var)
            await m.answer('Последствие успешно добавлено')
            await select_group_consequence(m)
            return
        case 6:  # Снятие всех безумий
            await db.Consequence.create(action_id=action_id, data={'type': 'delete_debuff_type', 'debuff_type_id': 2}, type=con_var)
            await m.answer('Последствие успешно добавлено')
            await select_group_consequence(m)
            return
        case 7:  # Снятие всех дебафов
            await db.Consequence.create(action_id=action_id, data={'type': 'delete_all_debuffs'}, type=con_var)
            await m.answer('Последствие успешно добавлено')
            await select_group_consequence(m)
            return
        case 8:  # Изменение либидо
            await m.answer('Укажите бонус/штраф к Либидо от -100 до 100 включительно', keyboard=keyboard)
            return
        case 9:  # Изменение подчинения
            await m.answer('Укажите бонус/штраф к Подчинению от -100 до 100 включительно', keyboard=keyboard)
            return
        case 10:  # Установить оплодотворение
            await m.answer('Укажите текст к статусу «Оплодотворение»', keyboard=keyboard)
            return
        case 11:  # Удалить оплодотворение
            await db.Consequence.create(action_id=action_id, data={'type': 'delete_pregnant'}, type=con_var)
            await m.answer('Последствие успешно добавлено')
            await select_group_consequence(m)
            return
        case 12:  # Получение предмета
            items = [x[0] for x in await db.select([db.Item.name]).order_by(db.Item.id.asc()).gino.all()]
            reply = 'Укажите номер предмета:\n\n'
            for i, item in enumerate(items):
                reply += f'{i + 1}. {item}\n'
            await m.answer(reply, keyboard=keyboard)
        case 13:  # Удаление предмета
            names = [x[0] for x in await db.select([db.Item.name]).select_from(
                db.ExpeditorToItems.join(db.Item, db.ExpeditorToItems.item_id == db.Item.id)
            ).order_by(db.ExpeditorToItems.id.asc()).gino.all()]
            reply = 'Укажите номер предмета:\n\n'
            for i, item in enumerate(names):
                reply += f'{i + 1}. {item}\n'
            await m.answer(reply, keyboard=keyboard)
            return
        case 14:  # Отключение предмета
            names = [x[0] for x in await db.select([db.Item.name]).select_from(
                db.ActiveItemToExpeditor.join(db.ExpeditorToItems,
                                              db.ActiveItemToExpeditor.row_item_id == db.ExpeditorToItems.id)
                .join(db.Item, db.ExpeditorToItems.item_id == db.Item.id)
            ).order_by(db.ActiveItemToExpeditor.id.asc()).gino.all()]
            reply = 'Укажите номер предмета:\n\n'
            for i, item in enumerate(names):
                reply += f'{i + 1}. {item}\n'
            await m.answer(reply, keyboard=keyboard)
            return
        case x:
            attribute_id = await db.select([db.Attribute.id]).where(db.Attribute.id == x - 15).gino.scalar()
            if not attribute_id:
                return
            await m.answer('Укажите бонус к характеристике', keyboard=keyboard)


@bot.on.private_message(StateRule(Judge.CONSEQUENCES_DATA), JudgeRule())
async def set_consequences_data(m: Message):
    _, action_id, con_var, group_id, con_type = states.get(m.from_id).split('*')
    action_id = int(action_id)
    con_var = int(con_var)
    con_type = int(con_type)
    post_id = await db.select([db.Action.post_id]).where(db.Action.id == action_id).gino.scalar()
    user_id = await db.select([db.Post.user_id]).where(db.Post.id == post_id).gino.scalar()
    form_id = await db.select([db.Form.user_id]).where(db.Form.user_id == user_id).gino.scalar()
    expeditor_id = await db.select([db.Expeditor.id]).where(db.Expeditor.form_id == form_id).gino.scalar()
    if con_type in (1, 2, 3, 4, 8, 9, 12, 13, 14) or con_type >= 15:
        try:
            number = int(m.text)
        except ValueError:
            await m.answer('Необходимо указать число')
            return
    match con_type:
        case 1:
            count = await db.select([func.count(db.StateDebuff.id)]).where(db.StateDebuff.type_id == 1).gino.scalar()
            if not 0 < number <= count:
                await m.answer('Неправильно указан номер!')
                return
            debuff_id = await db.select([db.StateDebuff.id]).where(db.StateDebuff.type_id == 1).order_by(db.StateDebuff.id.asc()).offset(number - 1).limit(1).gino.scalar()
            await db.Consequence.create(action_id=action_id, type=con_var, data={'type': 'add_debuff', 'debuff_id': debuff_id})
            await m.answer('Последствие успешно добавлено')
            await select_group_consequence(m)
            return
        case 2:
            count = await db.select([func.count(db.StateDebuff.id)]).where(db.StateDebuff.type_id == 2).gino.scalar()
            if not 0 < number <= count:
                await m.answer('Неправильно указан номер!')
                return
            debuff_id = await db.select([db.StateDebuff.id]).where(db.StateDebuff.type_id == 1).order_by(
                db.StateDebuff.id.asc()).offset(number - 1).limit(1).gino.scalar()
            await db.Consequence.create(action_id=action_id, type=con_var, data={'type': 'add_debuff', 'debuff_id': debuff_id})
            await m.answer('Последствие успешно добавлено')
            await select_group_consequence(m)
        case 3:
            injuries = [x[0] for x in await db.select([db.StateDebuff.id]).select_from(
                db.ExpeditorToDebuffs.join(db.StateDebuff, db.StateDebuff.id == db.ExpeditorToDebuffs.debuff_id)
            ).where(and_(db.ExpeditorToDebuffs.expeditor_id == expeditor_id, db.StateDebuff.type_id == 1)).order_by(
                db.ExpeditorToDebuffs.id.asc()).gino.all()]
            if not 0 < number <= len(injuries):
                await m.answer('Неправильно указан номер!')
                return
            row_id = injuries[number - 1]
            await db.Consequence.create(action_id=action_id, type=con_var, data={'type': 'delete_debuff', 'row_id': row_id})
            await m.answer('Последствие успешно добавлено')
            await select_group_consequence(m)
        case 4:
            injuries = [x[0] for x in await db.select([db.StateDebuff.id]).select_from(
                db.ExpeditorToDebuffs.join(db.StateDebuff, db.StateDebuff.id == db.ExpeditorToDebuffs.debuff_id)
            ).where(and_(db.ExpeditorToDebuffs.expeditor_id == expeditor_id, db.StateDebuff.type_id == 2)).order_by(
                db.ExpeditorToDebuffs.id.asc()).gino.all()]
            if not 0 < number <= len(injuries):
                await m.answer('Неправильно указан номер!')
                return
            row_id = injuries[number - 1]
            await db.Consequence.create(action_id=action_id, type=con_var, data={'type': 'delete_debuff', 'row_id': row_id})
            await m.answer('Последствие успешно добавлено')
            await select_group_consequence(m)
        case 8:
            if not -100 <= number <= 100:
                await m.answer('Необходимо указать число в диапазоне от -100 до 100 включительно')
                return
            await db.Consequence.create(action_id=action_id, type=con_var, data={'type': 'add_libido', 'bonus': number})
            await m.answer('Последствие успешно добавлено')
            await select_group_consequence(m)
        case 9:
            if not -100 <= number <= 100:
                await m.answer('Необходимо указать число в диапазоне от -100 до 100 включительно')
                return
            await db.Consequence.create(action_id=action_id, type=con_var, data={'type': 'add_subordination', 'bonus': number})
            await m.answer('Последствие успешно добавлено')
            await select_group_consequence(m)
        case 10:
            await db.Consequence.create(action_id=action_id, type=con_var, data={'type': 'set_pregnant', 'text': m.text})
            await m.answer('Последствие успешно добавлено')
            await select_group_consequence(m)
        case 12:
            items = [x[0] for x in await db.select([db.Item.id]).order_by(db.Item.id.asc()).gino.all()]
            if not 0 < number <= len(items):
                await m.answer('Неправильно указан номер!')
                return
            item_id = items[number - 1]
            await db.Consequence.create(action_id=action_id, type=con_var, data={'type': 'add_item', 'item_id': item_id})
            await m.answer('Последствие успешно добавлено')
            await select_group_consequence(m)
        case 13:
            items = [x[0] for x in await db.select([db.Item.id]).select_from(
                db.ExpeditorToItems.join(db.Item, db.ExpeditorToItems.item_id == db.Item.id)
            ).order_by(db.ExpeditorToItems.id.asc()).gino.all()]
            if not 0 < number <= len(items):
                await m.answer('Неправильно указан номер!')
                return
            item_id = items[number - 1]
            await db.Consequence.create(action_id=action_id, type=con_var, data={'type': 'delete_item', 'row_id': item_id})
            await m.answer('Последствие успешно добавлено')
            await select_group_consequence(m)
        case 14:
            items = [x[0] for x in await db.select([db.Item.id]).select_from(
                db.ActiveItemToExpeditor.join(db.ExpeditorToItems,
                                              db.ActiveItemToExpeditor.row_item_id == db.ExpeditorToItems.id)
                .join(db.Item, db.ExpeditorToItems.item_id == db.Item.id)
            ).order_by(db.ActiveItemToExpeditor.id.asc()).gino.all()]
            if not 0 < number <= len(items):
                await m.answer('Неправильно указан номер!')
                return
            item_id = items[number - 1]
            await db.Consequence.create(action_id=action_id, type=con_var,
                                        data={'type': 'desactivate_item', 'row_id': item_id})
            await m.answer('Последствие успешно добавлено')
            await select_group_consequence(m)
        case x:
            attribute_id = await db.select([db.Attribute.id]).where(db.Attribute.id == x - 15).gino.scalar()
            if not attribute_id:
                return
            await db.Consequence.create(action_id=action_id, type=con_var,
                                        data={'type': 'add_attribute', 'bonus': number, 'attribute_id': attribute_id})
            await m.answer('Последствие успешно добавлено')
            await select_group_consequence(m)


@bot.on.private_message(StateRule(Judge.SET_CONSEQUENCES), PayloadRule({'group_consequences': 'delete'}))
async def select_to_delete_consequences(m: Message):
    _, action_id, con_var = states.get(m.from_id).split('*')
    action_id = int(action_id)
    con_var = int(con_var)
    con_data = [x[0] for x in await db.select([db.Consequence.data]).where(and_(db.Consequence.action_id == action_id, db.Consequence.type == con_var)).order_by(db.Consequence.id.asc()).gino.all()]
    reply = 'Выберите номер последствия, которое хотите удалить:\n\n'
    for i, data in enumerate(con_data):
        reply += f'{i + 1}. {await serialize_consequence(data)}\n'
    states.set(m.from_id, f'{Judge.DELETE_CONSEQUENCES}*{action_id}*{con_var}')
    keyboard = Keyboard().add(
        Text('Назад', {'set_consequence_type': 'back'}), KeyboardButtonColor.NEGATIVE
    )
    await m.answer(reply, keyboard=keyboard)


@bot.on.private_message(StateRule(Judge.DELETE_CONSEQUENCES), NumericRule(), JudgeRule())
async def delete_consequence(m: Message, value: int):
    _, action_id, con_var = states.get(m.from_id).split('*')
    action_id = int(action_id)
    con_var = int(con_var)
    con_id = await db.select([db.Consequence.id]).where(and_(db.Consequence.action_id == action_id, db.Consequence.type == con_var)).order_by(db.Consequence.id.asc()).offset(value - 1).limit(1).gino.scalar()
    if not con_id:
        await m.answer('Неправильно указан номер!')
        return
    await db.Consequence.delete.where(db.Consequence.id == con_id).gino.status()
    await m.answer('Последствие успешно удалено')
    await select_consequence_type(m)


@bot.on.private_message(StateRule(Judge.SET_CONSEQUENCES), PayloadRule({'action_check': 'finish'}), JudgeRule())
async def finish_action_check(m: Message):
    action_id = int(states.get(m.from_id).split('*')[1])
    post_id = await db.select([db.Action.post_id]).where(db.Action.id == action_id).gino.scalar()
    can_decline, user_id, diffucult = await db.select([db.Post.decline_check, db.Post.user_id, db.Post.difficult]).where(db.Post.id == post_id).gino.first()
    keyboard = Keyboard(inline=True).add(
        Callback('Принять проверку', {'action_check': 'accept', 'action_id': action_id}), KeyboardButtonColor.POSITIVE
    )
    if can_decline:
        keyboard.row().add(
            Callback('Отказаться от проверки', {'action_check': 'decline', 'action_id': action_id}), KeyboardButtonColor.NEGATIVE
        )
    action = await db.Action.get(action_id)
    if action.data.get('type') == 'action':
        text = action.data['text']
    else:
        to_user_id = action.data['user_id']
        name = await db.select([db.Form.name]).where(db.Form.user_id == to_user_id).gino.scalar()
        user = (await bot.api.users.get(user_ids=[to_user_id]))[0]
        text = f'PvP с пользователем [id{to_user_id}|{name} / {user.first_name} {user.last_name}]'
    reply = f'Проверка действия «{text}»\n'
    attribute_name = await db.select([db.Attribute.name]).where(db.Attribute.id == action.attribute_id).gino.scalar()
    reply += f'Проверка по параметру «{attribute_name}»\n'
    reply += f'Базовая сложность: {type_difficulties[diffucult][0]}\n'
    difficult = await count_difficult(post_id)
    reply += f'Текущая сложность: {type_difficulties[difficult][0]}\n'
    if action.bonus == 0:
        value = 'Отсутсвует'
    elif 1 <= abs(action.bonus) <= 33:
        value = 'Низкий'
    elif 34 <= abs(action.bonus) <= 66:
        value = 'Обычный'
    else:
        value = 'Высокий'
    reply += f'{"Бонус" if action.bonus >= 0 else "Штраф"} судьи: {value}'
    await bot.api.messages.send(peer_id=user_id, message=reply, keyboard=keyboard)
    action_mode_id = await db.select([db.Post.action_mode_id]).where(db.Post.id == action.post_id).gino.scalar()
    finished = await db.select([db.ActionMode.finished]).where(db.ActionMode.id == action_mode_id).gino.scalar()
    if not finished:
        states.set(m.from_id, Judge.PANEL)
        await m.answer('Проверка успешно отправлена', keyboard=keyboards.action_mode_panel)
    else:
        states.set(m.from_id, Judge.WAIT_END_ACTION_MODE)
        await m.answer('Проверка успешно отправлена', keyboard=Keyboard())


@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent, PayloadMapRule({'action_check': 'decline', 'action_id': int}))
async def decline_check(m: MessageEvent):
    action_id = m.payload['action_id']
    data, post_id = await db.select([db.Action.data, db.Action.post_id]).where(db.Action.id == action_id).gino.first()
    if data.get('type') == 'action':
        text = data['text']
    else:
        user_id = data['user_id']
        name = await db.select([db.Form.name]).where(db.Form.user_id == user_id).gino.scalar()
        user = (await bot.api.users.get(user_ids=[user_id]))[0]
        text = f'PvP с пользователем [id{user_id}|{name} / {user.first_name} {user.last_name}]'
    await m.edit_message(f'Вы отказались от проверки действия «{text}»')
    action_mode_id = await db.select([db.Post.action_mode_id]).where(db.Post.id == post_id).gino.scalar()
    chat_id = await db.select([db.ActionMode.chat_id]).where(db.ActionMode.id == action_mode_id).gino.scalar()
    name = await db.select([db.Form.name]).where(db.Form.user_id == m.user_id).gino.scalar()
    user = (await bot.api.users.get(user_ids=[m.user_id]))[0]
    await bot.api.messages.send(peer_id=2000000000 + chat_id, message=f'Игрок [id{m.user_id}|{name} / {user.first_name} {user.last_name}] '
                                                                      f'отказался от дальнейших проверок')
    await db.ActionMode.update.values(check_status=False).where(db.ActionMode.id == action_mode_id).gino.status()
    await next_step(action_mode_id)


@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent, PayloadMapRule({'action_check': 'accept', 'action_id': int}))
async def accept_check(m: MessageEvent):
    action_id = m.payload['action_id']
    action = await db.Action.get(action_id)
    if action.data.get('type') == 'action':
        text = action.data['text']
    else:
        to_user_id = action.data['user_id']
        name = await db.select([db.Form.name]).where(db.Form.user_id == to_user_id).gino.scalar()
        user = (await bot.api.users.get(user_ids=[to_user_id]))[0]
        text = f'PvP с пользователем [id{to_user_id}|{name} / {user.first_name} {user.last_name}]'
    await m.edit_message(f'Вы приняли проверку действия «{text}»')
    difficult = await db.select([db.Post.difficult]).where(db.Post.id == action.post_id).gino.scalar()
    target_percentage = ((await count_attribute(m.user_id, action.attribute_id)) + action.bonus) * type_difficulties[difficult][1]
    x = random.randint(1, 100)
    if x <= target_percentage * 0.8:
        con_var = 4  # Критический успех
    elif x <= target_percentage:
        con_var = 3  # Успех
    elif x >= target_percentage * 1.2:
        con_var = 1  # Критический провал
    else:
        con_var = 2  # Провал
    await apply_consequences(action_id, con_var)
    action_mode_id = await db.select([db.Post.action_mode_id]).where(db.Post.id == action.post_id).gino.scalar()
    await db.ActionMode.update.values(check_status=False).where(db.ActionMode.id == action_mode_id).gino.status()
    await send_check(m, action.post_id)
