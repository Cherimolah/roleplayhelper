import datetime

from vkbottle.bot import Message
from vkbottle.dispatch.rules import OrRule
from vkbottle.dispatch.rules.base import PayloadRule
from vkbottle import Keyboard

from loader import bot, states
from service.custom_rules import StateRule, AdminRule, JudgeRule, NumericRule
from service.states import Admin
from service.db_engine import db, now
from service.utils import parse_period, create_mention, allow_edit_content, parse_ids, send_content_page, get_current_form_id
from service.serializers import info_target_reward, parse_reward, FormatDataException, info_quest_penalty
from service import keyboards
from handlers.questions import start
from config import DATETIME_FORMAT


@bot.on.private_message(StateRule(f"{Admin.SELECT_ACTION}_MandatoryQuest"), PayloadRule({"MandatoryQuest": "add"}), AdminRule())
async def create_quest(m: Message):
    """
    Создание нового предмета.

    Инициализирует процесс добавления нового предмета, создает запись в БД
    и переводит пользователя в состояние ввода названия.

    Args:
        m (Message): Входящее сообщение от пользователя
    """
    form_id = await get_current_form_id(m)
    quest = await db.MandatoryQuest.create(from_form_id=form_id)
    states.set(m.from_id, f"{Admin.MANDATORY_QUEST_NAME}*{quest.id}")
    await m.answer('Напишите название обязательного квеста', keyboard=Keyboard())


@bot.on.private_message(StateRule(Admin.MANDATORY_QUEST_NAME), AdminRule())
@allow_edit_content('MandatoryQuest', state=Admin.MANDATORY_QUEST_FORM_IDS,
                    text='Название обязательного квеста установлено\n'
                         'Отправьте ссылки/упоминания/пересланные сообщения пользователей, которым хотите выдать обязательный квест')
async def set_name_mandatory_quest(m: Message, item_id: int, editing_content: bool):
    await db.MandatoryQuest.update.values(name=m.text).where(db.MandatoryQuest.id == item_id).gino.status()


@bot.on.private_message(StateRule(Admin.MANDATORY_QUEST_FORM_IDS), AdminRule())
@allow_edit_content('MandatoryQuest', state=Admin.MANDATORY_QUEST_DESCRIPTION)
async def set_form_ids_mandatory_quest(m: Message, item_id: int, editing_content: bool):
    user_ids = await parse_ids(m)
    if not user_ids:
        raise FormatDataException('Не найдено пользователей')
    form_ids = [x[0] for x in await db.select([db.Form.id]).where(db.Form.user_id.in_(user_ids)).gino.all()]
    await db.MandatoryQuest.update.values(form_ids=form_ids).where(db.MandatoryQuest.id == item_id).gino.status()
    if not editing_content:
        await m.answer('Пользователи успешно зафиксированы\n'
                       'Укажите название обязательного квеста')



@bot.on.private_message(StateRule(Admin.MANDATORY_QUEST_DESCRIPTION), OrRule(AdminRule(), JudgeRule()))
@allow_edit_content('MandatoryQuest', state=Admin.MANDATORY_QUEST_EXPIRED_AT,
                    text='Описание квеста установлено.\n'
                   'Теперь напишите сколько времени дается на выполнение квеста\n'
                   'Например: 1 неделя 2 дня 3 часа 5 минут')
async def set_description(m: Message, item_id: int, editing_content: bool):
    await db.MandatoryQuest.update.values(description=m.text).where(db.MandatoryQuest.id == item_id).gino.status()


@bot.on.private_message(StateRule(Admin.MANDATORY_QUEST_EXPIRED_AT), OrRule(AdminRule(), JudgeRule()))
@allow_edit_content('MandatoryQuest', state=Admin.MANDATORY_QUEST_REWARD)
async def set_expired_at(m: Message, item_id: int, editing_content: bool):
    if not editing_content:
        period = parse_period(m.text)
        if period <= 0:
            raise FormatDataException('Не удалось распознать время выполнения')
        expired_at = now() + datetime.timedelta(seconds=period)
        await db.MandatoryQuest.update.values(expired_at=expired_at).where(db.MandatoryQuest.id == item_id).gino.status()
        await m.answer('Время выполнения квеста успешно установлено. Теперь необходимо указать награду за выполнение квеста')
        reply, _ = await info_target_reward()
        await m.answer(reply)
    else:
        try:
            end_date = datetime.datetime.strptime(m.text, DATETIME_FORMAT).astimezone(datetime.timezone(datetime.timedelta(hours=3)))
        except ValueError:
            raise FormatDataException('Неверный формат даты!')
        if now() >= end_date:
            raise FormatDataException('Указана дата в прошлом!')
        await db.MandatoryQuest.update.values(expired_at=end_date).where(db.MandatoryQuest.id == item_id).gino.status()



@bot.on.private_message(StateRule(Admin.MANDATORY_QUEST_REWARD), OrRule(AdminRule(), JudgeRule()))
@allow_edit_content('MandatoryQuest', state=Admin.MANDATORY_QUEST_PENALTY)
async def set_reward(m: Message, item_id: int, editing_content: bool):
    reward = await parse_reward(m.text)
    await db.MandatoryQuest.update.values(reward=reward).where(db.MandatoryQuest.id == item_id).gino.status()
    if not editing_content:
        await m.answer('Награда квеста успешно установлена.\n'
                       'Теперь напишите штраф за невыполнение квеста')
        reply, keyboard = await info_quest_penalty()
        await m.answer(reply, keyboard=keyboard)


@bot.on.private_message(StateRule(Admin.MANDATORY_QUEST_PENALTY), OrRule(AdminRule(), JudgeRule()), PayloadRule({"without_penalty": True}))
@allow_edit_content('MandatoryQuest', end=True)
async def save_mandatory_quest(m: Message, item_id: int, editing_content: bool):
    if not editing_content:
        await m.answer('Квест успешно создан')
        await start(m)
        form_ids, name = await db.select([db.MandatoryQuest.form_ids, db.MandatoryQuest.name]).where(
            db.MandatoryQuest.id == item_id
        ).gino.first()
        for form_id in form_ids:
            user_id = await db.select([db.Form.user_id]).where(db.Form.id == form_id).gino.scalar()
            await bot.api.messages.send(peer_id=user_id, message=f'Игрок {await create_mention(m.from_id)} создал вам '
                                                                 f'обязательный квест «{name}»')


@bot.on.private_message(StateRule(Admin.MANDATORY_QUEST_PENALTY), OrRule(AdminRule(), JudgeRule()))
@allow_edit_content('MandatoryQuest', end=True)
async def set_penalty(m: Message, item_id: int, editing_content: bool):
    penalty = await parse_reward(m.text)
    await db.MandatoryQuest.update.values(penalty=penalty).where(db.MandatoryQuest.id == item_id).gino.status()
    if not editing_content:
        await save_mandatory_quest(m)


@bot.on.private_message(StateRule(f"{Admin.SELECT_ACTION}_MandatoryQuest"), PayloadRule({"MandatoryQuest": "delete"}),
                        OrRule(JudgeRule(), AdminRule()))
async def select_delete_quest(m: Message):
    """
    Выбор предмета для удаления.

    Показывает список всех предметов для выбора того, который нужно удалить.

    Args:
        m (Message): Входящее сообщение

    Returns:
        str: Сообщение об отсутствии предметов, если таковых нет
    """
    items = await db.select([db.MandatoryQuest.name]).order_by(db.MandatoryQuest.id.asc()).gino.all()
    if not items:
        return "Обязательные квесты ещё не созданы"
    reply = "Выберите обязательный квест для удаления:\n\n"
    for i, item in enumerate(items):
        reply = f"{reply}{i + 1}. {item.name}\n"
    states.set(m.peer_id, Admin.MANDATORY_QUEST_DELETE)
    await m.answer(reply, keyboard=Keyboard())


@bot.on.private_message(StateRule(Admin.MANDATORY_QUEST_DELETE), NumericRule(), OrRule(JudgeRule(), AdminRule()))
async def delete_quest(m: Message, value: int):
    """
    Удаление выбранного предмета.

    Удаляет предмет из базы данных и все его упоминания в связанных таблицах.

    Args:
        m (Message): Входящее сообщение с номером предмета для удаления
        value (int): Номер предмета в списке
    """
    item_id = await db.select([db.MandatoryQuest.id]).order_by(db.MandatoryQuest.id.asc()).offset(value - 1).limit(1).gino.scalar()
    await db.MandatoryQuest.delete.where(db.MandatoryQuest.id == item_id).gino.status()
    states.set(m.peer_id, f"{Admin.SELECT_ACTION}_Item")
    await m.answer("Обязательный квест успешно удален", keyboard=keyboards.gen_type_change_content("MandatoryQuest"))
    await send_content_page(m, "MandatoryQuest", 1)
