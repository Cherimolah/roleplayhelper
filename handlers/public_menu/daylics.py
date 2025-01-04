import datetime

from vkbottle.bot import Message, MessageEvent
from vkbottle.dispatch.rules.base import PayloadRule, PayloadMapRule
from vkbottle import Keyboard, Text, KeyboardButtonColor, Callback, GroupEventType
from sqlalchemy import and_, func

from loader import bot
from service.custom_rules import StateRule
from service.states import Menu
from service.db_engine import db
from service.utils import get_current_form_id, parse_cooldown
from service.middleware import states
from config import ADMINS, OWNER
from handlers.public_menu.other import quests_or_daylics


async def send_daylic_page(obj: Message | MessageEvent, page: int):
    if isinstance(obj, Message):
        user_id = obj.from_id
    else:
        user_id = obj.user_id
    profession_id = await db.select([db.Form.profession]).where(db.Form.user_id == user_id).gino.scalar()
    daylic = await db.select([*db.Daylic]).where(db.Daylic.profession_id == profession_id).order_by(
        db.Daylic.id.asc()).offset(page - 1).limit(1).gino.first()
    if not daylic:
        if isinstance(obj, Message):
            await obj.answer("На данный момент дейликов для вашей профессии нету")
        else:
            await obj.edit_message("На данный момент дейликов для вашей профессии нету")
        return
    count_daylics = await db.select([func.count(db.Daylic.id)]).where(
        db.Daylic.profession_id == profession_id).gino.scalar()
    keyboard = Keyboard(inline=True)
    if page > 1:
        keyboard.add(Callback("<-", {"daylic_page": page - 1}), KeyboardButtonColor.PRIMARY)
    if page < count_daylics:
        keyboard.add(Callback("->", {"daylic_page": page + 1}), KeyboardButtonColor.PRIMARY)
    if keyboard.buttons:
        keyboard.row()
    keyboard.add(Callback("Принять", {"daylic_accept": daylic.id}), KeyboardButtonColor.POSITIVE)
    reply = f"Страница {page}/{count_daylics}:\nНазвание: {daylic.name}\nНаграда: {daylic.reward}\nОписание: {daylic.description}\n" \
            f"Кулдаун: {parse_cooldown(daylic.cooldown)}"
    if daylic.fraction_id:
        fraction_name = await db.select([db.Fraction.name]).where(db.Fraction.id == daylic.fraction_id).gino.scalar()
        reply += f"\nБонусная фракция: {fraction_name}\nБонус к репутации: {daylic.reputation}"
    else:
        reply += "\nБез бонусов к фракциям"
    if isinstance(obj, Message):
        await obj.answer(reply, keyboard=keyboard)
    else:
        await obj.edit_message(reply, keyboard=keyboard.get_json())


@bot.on.private_message(PayloadRule({"menu": "daylics"}), StateRule(Menu.MAIN))
async def send_daylics(m: Message):
    form_id = await get_current_form_id(m.from_id)
    exist_completed = await db.select([db.CompletedDaylic.id]).where(
        and_(db.CompletedDaylic.form_id == form_id, db.CompletedDaylic.is_checked.is_(False))
    ).gino.scalar()
    if exist_completed:
        await m.answer("Прежде, чем приступить к выполнению новых дейликов дождитесь проверки отчёта")
        return
    deactivated = await db.select([db.Form.deactivated_daylic]).where(db.Form.user_id == m.from_id).gino.scalar()
    if deactivated > datetime.datetime.now():
        await m.answer("Вы не можете получать дейлики так как на вас перезарядка ещё "
                                       f"{parse_cooldown((deactivated - datetime.datetime.now()).total_seconds())}")
        return
    daylic_id = await db.select([db.Form.activated_daylic]).where(db.Form.user_id == m.from_id).gino.scalar()
    if daylic_id:
        states.set(m.from_id, Menu.DAYLICS)
        daylic = await db.select([*db.Daylic]).where(db.Daylic.id == daylic_id).gino.first()
        keyboard = Keyboard().add(
            Text("Отправить отчёт о выполнении", {"daylic_ready": daylic_id}), KeyboardButtonColor.PRIMARY
        ).row().add(
            Text("Назад", {"menu": "quests and daylics"}), KeyboardButtonColor.NEGATIVE
        )
        await m.answer("У вас активирован дейлик:\n"
                       f"{daylic.name}\n"
                       f"{daylic.description}\n"
                       f"Награда: {daylic.reward}\n"
                       f"Кулдаун: {parse_cooldown(daylic.cooldown)}", keyboard=keyboard)
        return
    await send_daylic_page(m, 1)


@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent, PayloadMapRule({"daylic_page": int}))
async def daylic_page(m: MessageEvent):
    page = int(m.payload['daylic_page'])
    await send_daylic_page(m, page)


@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent, PayloadMapRule({"daylic_accept": int}))
async def accept_daylic(m: MessageEvent):
    daylic_id = int(m.payload['daylic_accept'])
    await db.Form.update.values(activated_daylic=daylic_id).where(db.Form.user_id == m.user_id).gino.status()
    daylic = await db.Daylic.get(daylic_id)
    reply = f"Название: {daylic.name}\nНаграда: {daylic.reward}\nОписание: {daylic.description}\n" \
            f"Кулдаун: {parse_cooldown(daylic.cooldown)}"
    if daylic.fraction_id:
        fraction_name = await db.select([db.Fraction.name]).where(db.Fraction.id == daylic.fraction_id).gino.scalar()
        reply += f"\nБонусная фракция: {fraction_name}\nБонус к репутации: {daylic.reputation}"
    else:
        reply += "\nБез бонусов к фракциям"
    reply += "\n\nВы взяли этот дейлик на исполнение"
    await m.edit_message(message=reply)


@bot.on.private_message(StateRule(Menu.DAYLICS), PayloadMapRule({"daylic_ready": int}))
async def send_ready_daylic(m: Message):
    daylic_id = m.payload['daylic_ready']
    form_id = await get_current_form_id(m.from_id)
    exist = await db.select([db.CompletedDaylic.id]).where(
        and_(db.CompletedDaylic.daylic_id == daylic_id, db.CompletedDaylic.form_id == form_id, db.CompletedDaylic.is_checked.is_(False)
             )).gino.scalar()
    if exist:
        await m.answer("Вы уже отправили отчёт о выполненном дейлике, дождитесь, когда администрация "
                                       "его примет")
        return
    response = await db.CompletedDaylic.create(form_id=form_id, daylic_id=daylic_id)
    name = await db.select([db.Form.name]).where(db.Form.id == form_id).gino.scalar()
    daylic_name, reward = await db.select([db.Daylic.name, db.Daylic.reward]).where(db.Daylic.id == daylic_id).gino.first()
    keyboard = Keyboard(inline=True).add(
        Callback("Подтвердить", {"daylic_check": response.id, "action": "accept"}), KeyboardButtonColor.POSITIVE
    ).add(
        Callback("Отклонить", {"daylic_check": response.id, "action": "decline"}), KeyboardButtonColor.NEGATIVE
    )
    await bot.api.messages.send(peer_ids=ADMINS + [OWNER], message=f"Отчёт игрока [id{m.from_id}|{name}] о выполненном дейлике {daylic_name}\n"
                                          f"Награда: {reward}", keyboard=keyboard)
    await m.answer(f"Ваш отчёт о выполнении {daylic_name} отправлен администрации")
    await quests_or_daylics(m)

