import datetime

from vkbottle.bot import Message
from vkbottle.dispatch.rules.base import PayloadRule, PayloadMapRule
from vkbottle import Keyboard, Text, KeyboardButtonColor

import service.keyboards as keyboards
from loader import bot
from service.custom_rules import AdminRule, StateRule, NumericRule
from service.middleware import states
from service.states import Admin
from service.db_engine import db
from service.utils import parse_period, send_content_page, allow_edit_content, FormatDataException, parse_ids
from service.serializers import info_quest_penalty, parse_reward, info_target_reward
from config import DATETIME_FORMAT


@bot.on.private_message(StateRule(f"{Admin.SELECT_ACTION}_Quest"), PayloadRule({"Quest": "add"}), AdminRule())
async def create_quest(m: Message):
    """Начало создания квеста"""
    quest = await db.Quest.create()
    states.set(m.from_id, f"{Admin.QUEST_NAME}*{quest.id}")
    await m.answer("Напишите название квеста", keyboard=Keyboard())


@bot.on.private_message(StateRule(Admin.QUEST_NAME), AdminRule())
@allow_edit_content("Quest", state=Admin.QUEST_DESCRIPTION,
                    text="Название квеста установлено. Теперь пришлите описание квеста")
async def name_quest(m: Message, item_id: int, editing_content: bool):
    """Установка названия квеста"""
    await db.Quest.update.values(name=m.text).where(db.Quest.id == item_id).gino.status()


@bot.on.private_message(StateRule(Admin.QUEST_DESCRIPTION), AdminRule())
@allow_edit_content("Quest", state=Admin.QUEST_REWARD)
async def description_quest(m: Message, item_id: int, editing_content: bool):
    """Установка описания квеста"""
    await db.Quest.update.values(description=m.text).where(db.Quest.id == item_id).gino.status()
    if not editing_content:
        await m.answer("Укажите награду для квеста\n\n" + (await info_target_reward())[0])


@bot.on.private_message(StateRule(Admin.QUEST_REWARD), AdminRule())
@allow_edit_content("Quest", state=Admin.QUEST_START_DATE,
                    text="Награда за квест установлена. Укажите дату и время начала квеста в формате "
                         "ДД.ММ.ГГГГ чч:мм:сс")
async def reward_quest(m: Message, item_id: int, editing_content: bool):
    """Установка награды за квест"""
    data = await parse_reward(m.text.lower())
    await db.Quest.update.values(reward=data).where(db.Quest.id == item_id).gino.status()


@bot.on.private_message(StateRule(Admin.QUEST_START_DATE), AdminRule())
@allow_edit_content("Quest", state=Admin.QUEST_END_DATE, text="Дата начала установлена. Укажите дату и время окончания квеста в формате "
                   "ДД.ММ.ГГГГ чч:мм:сс", keyboard=Keyboard().add(
        Text("Навсегда", {"quest_always": True})
    ))
async def start_date_quest(m: Message, item_id: int, editing_content: bool):
    """Установка даты начала квеста"""
    try:
        day = datetime.datetime.strptime(m.text, DATETIME_FORMAT)
    except:
        raise FormatDataException("Неправильный формат даты время")
    if day < datetime.datetime.now():
        raise FormatDataException("Укажите время в будущем")
    end_at = await db.select([db.Quest.closed_at]).where(db.Quest.id == item_id).gino.scalar()
    if end_at and day >= end_at:
        raise FormatDataException("Начало квеста позже, чем его начало")
    await db.Quest.update.values(start_at=day).where(db.Quest.id == item_id).gino.status()


@bot.on.private_message(StateRule(Admin.QUEST_END_DATE), PayloadRule({"quest_always": True}), AdminRule())
@allow_edit_content("Quest", state=Admin.QUEST_EXECUTION_TIME, text="Время окончание квеста установлено. Теперь напишите время, которое будет даваться "
                   "на выполнение квеста. Например: 2 дня 1 час 32 сек", keyboard=Keyboard().add(
        Text("Бессрочно", {"quest_forever": True})
    ))
async def set_quest_always(m: Message, item_id: int, editing_content: bool):
    """Установка бессрочного квеста"""
    await db.Quest.update.values(closed_at=None).where(db.Quest.id == item_id).gino.status()


@bot.on.private_message(StateRule(Admin.QUEST_END_DATE), AdminRule())
@allow_edit_content("Quest", state=Admin.QUEST_EXECUTION_TIME, text="Время окончание квеста установлено. Теперь напишите время, которое будет даваться "
                   "на выполнение квеста. Например: 2 дня 1 час 32 сек", keyboard=Keyboard().add(
        Text("Бессрочно", {"quest_forever": True})
    ))
async def end_date_quest(m: Message, item_id: int, editing_content: bool):
    """Установка даты окончания квеста"""
    try:
        day = datetime.datetime.strptime(m.text, DATETIME_FORMAT)
    except:
        raise FormatDataException("Неправильный формат даты время")
    if day < datetime.datetime.now():
        raise FormatDataException("Укажите время в будущем")
    start_date = await db.select([db.Quest.start_at]).where(db.Quest.id == item_id).gino.scalar()
    if start_date >= day:
        raise FormatDataException("Квест заканчивается раньше, чем начинается. Не логично, как-то что ли")
    await db.Quest.update.values(closed_at=day).where(db.Quest.id == item_id).gino.status()


@bot.on.private_message(StateRule(Admin.QUEST_EXECUTION_TIME), PayloadMapRule({"quest_forever": bool}), AdminRule())
@allow_edit_content("Quest", text="Пришлите ссылки на участников для которых будет распространяться квест",
                    state=Admin.QUEST_USERS_ALLOWED,
                    keyboard=Keyboard().add(Text('Без ограничений по игрокам', {"quest_for_all": True}),
                                            KeyboardButtonColor.PRIMARY))
async def quest_forever(m: Message, item_id: int, editing_content: bool):
    """Установка бессрочного времени выполнения квеста"""
    await db.Quest.update.values(execution_time=None).where(db.Quest.id == item_id).gino.status()


@bot.on.private_message(StateRule(Admin.QUEST_EXECUTION_TIME), AdminRule())
@allow_edit_content("Quest", text="Пришлите ссылки на участников для которых будет распространяться квест",
                    state=Admin.QUEST_USERS_ALLOWED,
                    keyboard=Keyboard().add(Text('Без ограничений по игрокам', {"quest_for_all": True}),
                                            KeyboardButtonColor.PRIMARY))
async def quest_expiration_time(m: Message, item_id: int, editing_content: bool):
    """Установка времени выполнения квеста"""
    seconds = parse_period(m.text)
    if not seconds:
        raise FormatDataException("Формат периода неверный")
    start_at, end_at = await db.select([db.Quest.start_at, db.Quest.closed_at]).where(db.Quest.id == item_id).gino.first()
    if end_at and seconds > (end_at - start_at).total_seconds():
        raise FormatDataException("Время на выполнение квеста больше, чем время жизни квеста")
    await db.Quest.update.values(execution_time=seconds).where(db.Quest.id == item_id).gino.scalar()


@bot.on.private_message(StateRule(Admin.QUEST_USERS_ALLOWED), PayloadRule({"quest_for_all": True}), AdminRule())
@allow_edit_content('Quest', state=Admin.QUEST_FRACTION_ALLOWED)
async def quest_users_all_allowed(m: Message, item_id: int, editing_content: bool):
    """Разрешение квеста для всех пользователей"""
    await db.Quest.update.values(allowed_forms=[]).where(db.Quest.id == item_id).gino.status()
    if not editing_content:
        reply = ("Квест установлен без ограничений по пользователям\n\n"
                 "Укажите номер фракции, для которой будет доступен квест:\n\n")
        fractions = [x[0] for x in await db.select([db.Fraction.name]).order_by(db.Fraction.id.asc()).gino.all()]
        for i, fraction in enumerate(fractions):
            reply += f"{i + 1}. {fraction}\n"
        keyboard = Keyboard().add(
            Text('Без ограничения по фракциям', {"quest_for_all_fractions": True})
        )
        await m.answer(reply, keyboard=keyboard)


@bot.on.private_message(StateRule(Admin.QUEST_USERS_ALLOWED), AdminRule())
@allow_edit_content('Quest', state=Admin.QUEST_FRACTION_ALLOWED)
async def quest_users_allowed(m: Message, item_id: int, editing_content: bool):
    """Установка ограничений по пользователям для квеста"""
    user_ids = list(set(await parse_ids(m)))
    if not user_ids:
        raise FormatDataException('Пользователи не указаны')
    form_ids = [x[0] for x in await db.select([db.Form.id]).where(db.Form.user_id.in_(user_ids)).gino.all()]
    if not form_ids:
        raise FormatDataException('Указанные пользователи не найдены в базе')
    await db.Quest.update.values(allowed_forms=form_ids).where(db.Quest.id == item_id).gino.status()
    if not editing_content:
        reply = ("Ограничения по пользователям установлены.\n\n"
                 "Укажите номер фракции, для которой будет доступен квест:\n\n")
        fractions = [x[0] for x in await db.select([db.Fraction.name]).order_by(db.Fraction.id.asc()).gino.all()]
        for i, fraction in enumerate(fractions):
            reply += f"{i + 1}. {fraction}\n"
        keyboard = Keyboard().add(
            Text('Без ограничения по фракциям', {"quest_for_all_fractions": True})
        )
        await m.answer(reply, keyboard=keyboard)


@bot.on.private_message(StateRule(Admin.QUEST_FRACTION_ALLOWED), PayloadRule({"quest_for_all_fractions": True}), AdminRule())
@allow_edit_content('Quest', state=Admin.QUEST_PROFESSION_ALLOWED)
async def quest_fraction_all_allowed(m: Message, item_id: int, editing_content: bool):
    """Разрешение квеста для всех фракций"""
    await db.Quest.update.values(allowed_fraction=None).where(db.Quest.id == item_id).gino.status()
    if not editing_content:
        reply = ("Квест установлен без ограничений по фракциям\n\n"
                 "Укажите номер профессии, у которой будет доступен квест:\n\n")
        professions = [x[0] for x in await db.select([db.Profession.name]).order_by(db.Profession.id.asc()).gino.all()]
        for i, fraction in enumerate(professions):
            reply += f"{i + 1}. {fraction}\n"
        keyboard = Keyboard().add(
            Text('Без ограничения по профессиям', {"quest_for_all_professions": True})
        )
        await m.answer(reply, keyboard=keyboard)


@bot.on.private_message(StateRule(Admin.QUEST_FRACTION_ALLOWED), NumericRule(), AdminRule())
@allow_edit_content('Quest', state=Admin.QUEST_PROFESSION_ALLOWED)
async def quest_fractions_allowed(m: Message, value: int, item_id: int, editing_content: bool):
    """Установка ограничения по фракциям для квеста"""
    fractions = [x[0] for x in await db.select([db.Fraction.id]).order_by(db.Fraction.id.asc()).gino.all()]
    if value > len(fractions):
        raise FormatDataException("Номер фракции слишком большой")
    fraction_id = fractions[value - 1]
    await db.Quest.update.values(allowed_fraction=fraction_id).where(db.Quest.id == item_id).gino.status()
    if not editing_content:
        fraction = await db.select([db.Fraction.name]).where(db.Fraction.id == fraction_id).gino.scalar()
        reply = (f"Квест установлен для фракции {fraction}\n\n"
                 "Укажите номер профессии, у которой будет доступен квест:\n\n")
        professions = [x[0] for x in await db.select([db.Profession.name]).order_by(db.Profession.id.asc()).gino.all()]
        for i, fraction in enumerate(professions):
            reply += f"{i + 1}. {fraction}\n"
        keyboard = Keyboard().add(
            Text('Без ограничения по профессиям', {"quest_for_all_professions": True})
        )
        await m.answer(reply, keyboard=keyboard)


@bot.on.private_message(StateRule(Admin.QUEST_PROFESSION_ALLOWED), PayloadRule({"quest_for_all_professions": True}), AdminRule())
@allow_edit_content('Quest', state=Admin.QUEST_ADDITIONAL_TARGETS)
async def quest_allow_all_professions(m: Message, item_id: int, editing_content: bool):
    """Разрешение квеста для всех профессий"""
    await db.Quest.update.values(allowed_profession=None).where(db.Quest.id == item_id).gino.status()
    if not editing_content:
        targets = [x[0] for x in await db.select([db.AdditionalTarget.name]).order_by(db.AdditionalTarget.id.asc()).gino.all()]
        reply = 'Укажите номера дополнительных целей через запятую:\n\n'
        if not targets:
            reply += 'Дополнительных целей на данный момент не создано'
        else:
            for i, target in enumerate(targets):
                reply += f"{i + 1}. {target}\n"
        await m.answer(reply, keyboard=Keyboard().add(Text('Без дополнительных целей', {"quest_without_targets": True})))


@bot.on.private_message(StateRule(Admin.QUEST_PROFESSION_ALLOWED), NumericRule(), AdminRule())
@allow_edit_content('Quest', state=Admin.QUEST_ADDITIONAL_TARGETS)
async def quest_allow_professions(m: Message, value: int, item_id: int, editing_content: bool):
    """Установка ограничения по профессиям для квеста"""
    professions = [x[0] for x in await db.select([db.Profession.id]).order_by(db.Profession.id.asc()).gino.all()]
    if value > len(professions):
        raise FormatDataException("Номер профессии слишком большой")
    profession_id = professions[value - 1]
    await db.Quest.update.values(allowed_profession=profession_id).where(db.Quest.id == item_id).gino.status()
    if not editing_content:
        targets = [x[0] for x in
                   await db.select([db.AdditionalTarget.name]).order_by(db.AdditionalTarget.id.asc()).gino.all()]
        reply = 'Укажите номера дополнительных целей через запятую:\n\n'
        if not targets:
            reply += 'Дополнительных целей на данный момент не создано'
        else:
            for i, target in enumerate(targets):
                reply += f"{i + 1}. {target}\n"
        await m.answer(reply,
                       keyboard=Keyboard().add(Text('Без дополнительных целей', {"quest_without_targets": True})))


@bot.on.private_message(StateRule(Admin.QUEST_ADDITIONAL_TARGETS), PayloadRule({"quest_without_targets": True}), AdminRule())
@allow_edit_content('Quest', state=Admin.QUEST_PENALTY)
async def quest_without_targets(m: Message, item_id: int, editing_content: bool):
    """Создание квеста без дополнительных целей"""
    await db.Quest.update.values(target_ids=[]).where(db.Quest.id == item_id).gino.status()
    if not editing_content:
        reply, keyboard = await info_quest_penalty()
        await m.answer("Укажите штраф для квеста\n\n" + reply, keyboard=keyboard)


@bot.on.private_message(StateRule(Admin.QUEST_ADDITIONAL_TARGETS), AdminRule())
@allow_edit_content('Quest', state=Admin.QUEST_PENALTY)
async def quest_additional_targets(m: Message, item_id: int, editing_content: bool):
    """Добавление дополнительных целей к квесту"""
    try:
        numbers = list(set(map(int, m.text.replace(' ', '').split(','))))
    except:
        raise FormatDataException('Необходимо указать номера доп. целей через запятую. Например: 1, 2, 3')
    target_ids = [x[0] for x in await db.select([db.AdditionalTarget.id]).order_by(db.AdditionalTarget.id.asc()).gino.all()]
    numbers = list(map(lambda x: target_ids[x - 1], numbers))
    await db.Quest.update.values(target_ids=numbers).where(db.Quest.id == item_id).gino.status()
    if not editing_content:
        reply, keyboard = await info_quest_penalty()
        await m.answer("Укажите штраф для квеста\n\n" + reply, keyboard=keyboard)


@bot.on.private_message(StateRule(Admin.QUEST_PENALTY), PayloadRule({"without_penalty": True}), AdminRule())
@allow_edit_content('Quest', end=True, text='Квест успешно создан')
async def quest_without_penalty(m: Message, item_id: int, editing_content: bool):
    """Создание квеста без штрафа"""
    await db.Quest.update.values(penalty=None).where(db.Quest.id == item_id).gino.status()


@bot.on.private_message(StateRule(Admin.QUEST_PENALTY), AdminRule())
@allow_edit_content('Quest', end=True, text='Квест успешно создан')
async def quest_without_penalty(m: Message, item_id: int, editing_content: bool):
    """Установка штрафа для квеста"""
    data = await parse_reward(m.text.lower())
    await db.Quest.update.values(penalty=data).where(db.Quest.id == item_id).gino.status()


@bot.on.private_message(StateRule(f"{Admin.SELECT_ACTION}_Quest"), PayloadRule({"Quest": "delete"}), AdminRule())
async def select_delete_quest(m: Message):
    """Выбор квеста для удаления"""
    quests = await db.select([db.Quest.name]).order_by(db.Quest.id.asc()).gino.all()
    if not quests:
        return "Квесты ещё не созданы"
    reply = "Выберите квест для удаления:\n\n"
    for i, quest in enumerate(quests):
        reply = f"{reply}{i + 1}. {quest.name}\n"
    states.set(m.peer_id, Admin.QUEST_DELETE)
    await m.answer(reply, keyboard=Keyboard())


@bot.on.private_message(StateRule(Admin.QUEST_DELETE), NumericRule(), AdminRule())
async def delete_quest(m: Message, value: int):
    """Удаление выбранного квеста и связанных данных"""
    quest_id = await db.select([db.Quest.id]).order_by(db.Quest.id.asc()).offset(value - 1).limit(1).gino.scalar()
    await db.ReadyQuest.delete.where(db.ReadyQuest.quest_id == quest_id).gino.status()
    await db.QuestToForm.delete.where(db.QuestToForm.quest_id == quest_id).gino.status()
    await db.QuestHistory.delete.where(db.QuestHistory.quest_id == quest_id).gino.status()
    await db.Quest.delete.where(db.Quest.id == quest_id).gino.status()
    states.set(m.peer_id, f"{Admin.SELECT_ACTION}_Quest")
    await m.answer("Квест успешно удалён", keyboard=keyboards.gen_type_change_content("Quest"))
    await send_content_page(m, "Quest", 1)
