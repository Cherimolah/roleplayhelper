"""
Модуль квестов для дочерей.
Обрабатывает систему квестов для персонажей-дочерей: просмотр, выполнение и подтверждение квестов.
"""

import datetime
from vkbottle.bot import Message
from vkbottle.dispatch.rules.base import PayloadRule, PayloadMapRule
from vkbottle import Keyboard, Text, KeyboardButtonColor, Callback
from sqlalchemy import and_
from loader import bot, states
from service.custom_rules import StateRule, DaughterRule
from service.states import Menu
from service.db_engine import db, now
from service.utils import get_current_form_id, serialize_target_reward, parse_cooldown, get_available_daughter_target_ids
from config import ADMINS


@bot.on.private_message(StateRule(Menu.MAIN), PayloadRule({"menu": 'daughter_quests'}), DaughterRule())
async def daughter_quest(m: Message):
    """
    Показать активный квест дочери.
    Отображает информацию о текущем квесте, дополнительные цели и статус выполнения.
    """
    form_id = await get_current_form_id(m.from_id)

    # Получение активного квеста
    quest = await db.select([*db.DaughterQuest]).where(db.DaughterQuest.to_form_id == form_id).gino.first()
    if not quest:
        await m.answer('Для вас пока не создано квеста')
        return

    # Проверка выполнения квеста на сегодня
    confirmed = await db.select([db.DaughterQuestRequest.confirmed]).where(and_(
        db.DaughterQuestRequest.form_id == form_id,
        db.DaughterQuestRequest.created_at == datetime.date.today()
    )).gino.scalar()

    if confirmed:
        await m.answer('На сегодня вы выполнили квест, приходите завтра!')
        return

    # Расчет времени до сброса квестов
    tomorrow = now() + datetime.timedelta(days=1)
    next_day = datetime.datetime(tomorrow.year, tomorrow.month, tomorrow.day, 0, 0, 0,
                                 tzinfo=datetime.timezone(datetime.timedelta(hours=3)))
    cooldown = (next_day - now()).total_seconds()

    # Формирование информации о квесте
    reply = ('У вас активен квест:\n\n'
             f'Название: {quest.name}\n'
             f'Описание: {quest.description}\n'
             f'Награда: {await serialize_target_reward(quest.reward)}\n'
             f'Штраф: {await serialize_target_reward(quest.penalty)}\n'
             f'Остаётся на выполнение: {parse_cooldown(cooldown)}\n\n')

    # Обработка дополнительных целей
    target_ids = await get_available_daughter_target_ids(m.from_id)

    # Добавление информации о дополнительных целях
    if target_ids:
        reply += 'Дополнительные цели:\n'
        for i, target_id in enumerate(target_ids):
            target = await db.DaughterTarget.get(target_id)
            reply += (f'{i + 1}. {target.name}\n'
                      f'Описание: {target.description}\n'
                      f'Награда: {await serialize_target_reward(target.reward)}\n'
                      f'Штраф: {await serialize_target_reward(target.penalty)}\n\n')

    # Формирование статуса выполнения
    reply += 'Статус выполнения квеста:\n✅ - выполнено; ⚠ - на проверке; ❌ - не выполнено\n'
    keyboard = Keyboard()
    quest_available = True

    # Обработка статусов дополнительных целей
    for i, target_id in enumerate(target_ids):
        confirmed = await db.select([db.DaughterTargetRequest.confirmed]).where(
            and_(db.DaughterTargetRequest.form_id == form_id,
                 db.DaughterTargetRequest.created_at == now().date(),
                 db.DaughterTargetRequest.target_id == target_id)
        ).gino.scalar()

        target_name = await db.select([db.DaughterTarget.name]).where(db.DaughterTarget.id == target_id).gino.scalar()

        if confirmed is None:
            emoji = '❌'
            keyboard.add(Text(f'Завершить доп. цель №{i + 1}', {'daughter_target_complete': target_id}),
                         KeyboardButtonColor.PRIMARY).row()
            quest_available = False
        elif not confirmed:
            emoji = '⚠'
            quest_available = False
        else:
            emoji = '✅'

        reply += f'{i + 1}. {emoji} (Доп. цель) {target_name}\n'

    # Обработка статуса основного квеста
    quest_request = await db.select([db.DaughterQuestRequest.confirmed]).where(
        and_(db.DaughterQuestRequest.form_id == form_id,
             db.DaughterQuestRequest.quest_id == quest.id,
             db.DaughterQuestRequest.created_at == datetime.date.today())
    ).gino.scalar()

    emoji = '❌' if quest_request is None else '⚠' if not quest_request else '✅'

    if quest_request is None and quest_available:
        keyboard.add(Text('Завершить квест', {'daughter_quest_complete': quest.id}),
                     KeyboardButtonColor.PRIMARY).row()

    reply += f'{len(target_ids) + 1}. {emoji} (Квест) {quest.name}'

    states.set(m.from_id, Menu.DAUGHTER_QUEST_MENU)
    keyboard.add(Text('Назад', {"daughter_quests": "back"}), KeyboardButtonColor.NEGATIVE)
    await m.answer(reply, keyboard=keyboard)


@bot.on.private_message(PayloadMapRule({'daughter_target_complete': int}), StateRule(Menu.DAUGHTER_QUEST_MENU))
async def confirm_daughter_target(m: Message):
    """Подтверждение выполнения дополнительной цели дочернего квеста"""
    form_id = await get_current_form_id(m.from_id)
    target_id = m.payload['daughter_target_complete']

    # Создание запроса на подтверждение цели
    request = await db.DaughterTargetRequest.create(form_id=form_id, target_id=target_id)

    # Отправка уведомления администраторам
    admins = [x[0] for x in await db.select([db.User.user_id]).where(db.User.admin > 0).gino.all()]
    admins = list(set(admins) | set(ADMINS))
    target_name = await db.select([db.DaughterTarget.name]).where(db.DaughterTarget.id == target_id).gino.scalar()
    name = await db.select([db.Form.name]).where(db.Form.id == form_id).gino.scalar()
    user = (await bot.api.users.get(user_ids=m.from_id))[0]

    keyboard = Keyboard(inline=True).add(
        Callback('Подтвердить', {'confirm_daughter_target_request': request.id}),
        KeyboardButtonColor.POSITIVE
    ).row().add(
        Callback('Отклонить', {'decline_daughter_target_request': request.id}),
        KeyboardButtonColor.NEGATIVE
    )

    await bot.api.messages.send(
        peer_ids=admins,
        message=f'Отчёт о выполнении дочери [id{m.from_id}|{name} / '
                f'{user.first_name} {user.last_name}] доп. цели  «{target_name}»',
        keyboard=keyboard
    )

    await m.answer('Поздравляем с выполнением доп. цели! Дождитесь проверки администрацией')
    await daughter_quest(m)


@bot.on.private_message(PayloadMapRule({'daughter_quest_complete': int}), StateRule(Menu.DAUGHTER_QUEST_MENU))
async def confirm_daughter_target(m: Message):
    """Подтверждение выполнения основного дочернего квеста"""
    form_id = await get_current_form_id(m.from_id)
    quest_id = m.payload['daughter_quest_complete']

    # Проверим, что все доп. цели выполнены
    target_ids = await get_available_daughter_target_ids(m.from_id)
    for target_id in target_ids:
        confirmed = await db.select([db.DaughterTargetRequest.confirmed]).where(
            and_(db.DaughterTargetRequest.target_id == target_id,
                 db.DaughterTargetRequest.form_id == form_id,
                 db.DaughterTargetRequest.created_at == now().date()
                 )
        ).gino.scalar()
        if not confirmed:
            await m.answer('❌Не все дополнительные цели были выполнены')
            return

    # Создание запроса на подтверждение квеста
    request = await db.DaughterQuestRequest.create(form_id=form_id, quest_id=quest_id)

    # Отправка уведомления администраторам
    admins = [x[0] for x in await db.select([db.User.user_id]).where(db.User.admin > 0).gino.all()]
    admins = list(set(admins) | set(ADMINS))
    quest_name = await db.select([db.DaughterQuest.name]).where(db.DaughterQuest.id == quest_id).gino.scalar()
    name = await db.select([db.Form.name]).where(db.Form.id == form_id).gino.scalar()
    user = (await bot.api.users.get(user_ids=m.from_id))[0]

    keyboard = Keyboard(inline=True).add(
        Callback('Подтвердить', {'confirm_daughter_quest_request': request.id}),
        KeyboardButtonColor.POSITIVE
    ).row().add(
        Callback('Отклонить', {'decline_daughter_quest_request': request.id}),
        KeyboardButtonColor.NEGATIVE
    )

    await bot.api.messages.send(
        peer_ids=admins,
        message=f'Отчёт о выполнении дочери [id{m.from_id}|{name} / '
                f'{user.first_name} {user.last_name}] квеста «{quest_name}»',
        keyboard=keyboard
    )

    await m.answer('Поздравляем с выполнением квеста! Дождитесь проверки администрацией')
    await daughter_quest(m)