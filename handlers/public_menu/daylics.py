"""
Модуль ежедневных заданий (дейликов).
Обрабатывает систему ежедневных заданий: активация, выполнение и отправка отчетов.
"""
import datetime

from vkbottle.bot import Message
from vkbottle.dispatch.rules.base import PayloadRule, PayloadMapRule
from vkbottle import Keyboard, Text, KeyboardButtonColor, Callback
from sqlalchemy import and_
from loader import bot
from service.custom_rules import StateRule
from service.states import Menu
from service.db_engine import db
from service.utils import get_current_form_id, now, parse_cooldown
from service.middleware import states
from config import ADMINS, OWNER
from handlers.public_menu.other import quests_or_daylics


@bot.on.private_message(PayloadRule({"menu": "daylics"}), StateRule(Menu.MAIN))
async def send_daylics(m: Message):
    """Показать информацию о текущем дейлике пользователя"""
    form_id = await get_current_form_id(m.from_id)

    # Проверка наличия непроверенных отчётов
    exist_completed = await db.select([db.CompletedDaylic.id]).where(
        and_(db.CompletedDaylic.form_id == form_id, db.CompletedDaylic.is_checked.is_(False))
    ).gino.scalar()

    if exist_completed:
        await m.answer("Прежде, чем приступить к выполнению новых еженедельных заданий дождитесь проверки отчёта")
        return

    # Проверка выполнения текущего дейлика
    completed_daylic = await db.select([db.Form.daylic_completed]).where(db.Form.id == form_id).gino.scalar()
    if completed_daylic:
        await m.answer('На текущий момент еженедельное задание выполнено успешно выполнен. Дождитесь обновления')
        return

    # Получение активного дейлика
    daylic_id = await db.select([db.Form.activated_daylic]).where(db.Form.user_id == m.from_id).gino.scalar()

    if daylic_id:
        states.set(m.from_id, Menu.DAYLICS)
        daylic = await db.select([*db.Daylic]).where(db.Daylic.id == daylic_id).gino.first()

        # Создание клавиатуры для управления дейликом
        keyboard = Keyboard().add(
            Text("Отправить отчёт о выполнении", {"daylic_ready": daylic_id}), KeyboardButtonColor.PRIMARY
        ).row().add(
            Text("Назад", {"menu": "quests and daylics"}), KeyboardButtonColor.NEGATIVE
        )

        today = now()
        if 0 <= today.weekday() <= 2:
            end_date = today + datetime.timedelta(days=2-today.weekday())
            end_date = datetime.datetime(end_date.year, end_date.month, end_date.day, 23, 59, 59,
                                         tzinfo=datetime.timezone(datetime.timedelta(hours=3)))
        else:
            end_date = today + datetime.timedelta(days=6 - today.weekday())
            end_date = datetime.datetime(end_date.year, end_date.month, end_date.day, 23, 59, 59,
                                         tzinfo=datetime.timezone(datetime.timedelta(hours=3)))

        await m.answer(f"У вас активировано еженедельное задание «{daylic.name}»\n"
                       f"Описание: {daylic.description}\n"
                       f"Награда: {daylic.reward}\n"
                       f"Время на выполнение: {parse_cooldown((end_date - today).total_seconds())}", keyboard=keyboard)
    else:
        await m.answer('У вас нет активного еженедельного задания')


@bot.on.private_message(StateRule(Menu.DAYLICS), PayloadMapRule({"daylic_ready": int}))
async def send_ready_daylic(m: Message):
    """Отправка отчета о выполнении дейлика на проверку"""
    daylic_id = m.payload['daylic_ready']
    form_id = await get_current_form_id(m.from_id)

    # Проверка существования непроверенного отчета
    exist = await db.select([db.CompletedDaylic.id]).where(
        and_(db.CompletedDaylic.daylic_id == daylic_id,
             db.CompletedDaylic.form_id == form_id,
             db.CompletedDaylic.is_checked.is_(False))
    ).gino.scalar()

    if exist:
        await m.answer("Вы уже отправили отчёт о выполненном еженедельном задании, дождитесь, когда администрация "
                       "его примет")
        return

    # Создание записи о выполнении дейлика
    response = await db.CompletedDaylic.create(form_id=form_id, daylic_id=daylic_id)

    # Отправка уведомления администраторам
    name = await db.select([db.Form.name]).where(db.Form.id == form_id).gino.scalar()
    daylic_name, reward, description = await db.select([db.Daylic.name, db.Daylic.reward, db.Daylic.description]).where(
        db.Daylic.id == daylic_id).gino.first()

    keyboard = Keyboard(inline=True).add(
        Callback("Подтвердить", {"daylic_check": response.id, "action": "accept"}), KeyboardButtonColor.POSITIVE
    ).add(
        Callback("Отклонить", {"daylic_check": response.id, "action": "decline"}), KeyboardButtonColor.NEGATIVE
    )

    await bot.api.messages.send(
        peer_ids=ADMINS + [OWNER],
        message=f"Отчёт игрока [id{m.from_id}|{name}] о выполненном ежедневном задании {daylic_name}\n"
                f"Описание: {description}\n"
                f"Награда: {reward}",
        keyboard=keyboard
    )

    await m.answer(f"Ваш отчёт о выполнении {daylic_name} отправлен администрации")
    await quests_or_daylics(m)
