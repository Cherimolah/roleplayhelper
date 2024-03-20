import asyncio
import datetime
import shutil

from vkbottle import GroupEventType, Keyboard
from vkbottle.bot import MessageEvent, Message
from vkbottle.dispatch.rules.base import PayloadMapRule, PayloadRule
from sqlalchemy import and_
import openpyxl
from vkbottle import DocMessagesUploader

from loader import bot
from service.db_engine import db
import messages
from service import keyboards
from service.states import Menu, Admin
from service.middleware import states
from service.custom_rules import StateRule, NumericRule, AdminRule
from service.utils import take_off_payments, parse_cooldown


@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent, PayloadMapRule({"form_accept": int}), AdminRule())
async def accept_form(m: MessageEvent):
    user_id = m.object.payload['form_accept']
    number_form = await db.select([db.Form.number]).where(
        and_(db.Form.user_id == user_id, db.Form.is_request.is_(True))
    ).gino.scalar()
    if not number_form:
        await bot.edit_msg(m, "Анкета уже была принята или отклонена другим администратором")
        return
    await db.User.update.values(state=Menu.MAIN, activated_form=number_form).where(db.User.user_id == user_id).gino.status()
    await bot.write_msg(peer_ids=user_id, message=messages.form_accepted, keyboard=await keyboards.main_menu(user_id))
    name = await db.select([db.Form.name]).where(
        and_(db.Form.user_id == user_id, db.Form.is_request.is_(True))
    ).order_by(db.Form.number.desc()).gino.scalar()
    await bot.edit_msg(m, f"Анкета участника [id{user_id}|{name}] принята")
    current_profession = await db.select([db.Form.profession]).where(db.Form.user_id == user_id).gino.scalar()
    if not current_profession:
        reply = f"Укажите должность участника [id{user_id}|{name}]. Доступные должности:\n\n"
        professions = await db.select([db.Profession.name]).gino.all()
        for i, prof in enumerate(professions):
            reply = f"{reply}{i+1}. {prof.name}\n"
        await db.User.update.values(state=f"{Admin.SELECT_PROFESSION}@{user_id}").where(db.User.user_id == m.user_id).gino.status()
        await bot.write_msg(m.peer_id, reply, keyboard=keyboards.another_profession_to_user(user_id))
        return
    await db.User.update.values(state=f"{Admin.SELECT_CABIN}@{user_id}").where(db.User.user_id == m.user_id).gino.status()
    free = []
    i = 1
    employed = {x[0] for x in await db.select([db.Form.cabin]).gino.all()}
    while not free:
        i += 100
        numbers = set(range(1, i))
        free = list(map(str, list(numbers - employed)))
    reply = f"Укажите номер кабины участника [id{user_id}|{name}]\n\n" \
            f"Свободные номера: {', '.join(free)}"
    await bot.write_msg(m.peer_id, reply, keyboard=Keyboard())


@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent, PayloadMapRule({"form_accept_edit": int}), AdminRule())
async def accept_form_edit(m: MessageEvent):
    user_id = m.object.payload['form_accept_edit']
    name = await db.select([db.Form.name]).where(
        and_(db.Form.user_id == user_id, db.Form.is_edit.is_(True), db.Form.is_request.is_(True))
    ).gino.scalar()
    if not name:
        await bot.edit_msg(m, "Анкета уже принята или отклонена другим администратором")
        return
    await db.Form.delete.where(and_(
        db.Form.user_id == user_id, db.Form.is_request.is_(False), db.Form.is_edit.is_(True)
    )).gino.status()
    await db.Form.update.values(is_request=False, is_edit=False).where(and_(
        db.Form.user_id == user_id, db.Form.is_edit.is_(True), db.Form.is_request.is_(True)
    )).gino.status()
    await bot.edit_msg(m, f"Анкета участника [id{user_id}|{name}] принята")
    await bot.write_msg(user_id, messages.edit_request_accept.format(name))


@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent, PayloadMapRule({"form_decline_edit": int}), AdminRule())
async def accept_form_edit(m: MessageEvent):
    user_id = m.object.payload['form_decline_edit']
    name = await db.select([db.Form.name]).where(
        and_(db.Form.user_id == user_id, db.Form.is_edit.is_(True), db.Form.is_request.is_(False))
    ).gino.scalar()
    if not name:
        await bot.edit_msg(m, "Анкета уже принята или отклонена другим администратором")
        return
    await db.Form.delete.where(and_(
        db.Form.user_id == user_id, db.Form.is_request.is_(True), db.Form.is_edit.is_(True)
    )).gino.status()
    await db.Form.update.values(is_edit=False).where(and_(
        db.Form.user_id == user_id, db.Form.is_request.is_(False), db.Form.is_edit.is_(True)
    )).gino.status()
    await bot.edit_msg(m, f"Анкета участника [id{user_id}|{name}] отклонена")
    await bot.write_msg(user_id, messages.edit_request_accept.format(name))


@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent, PayloadMapRule({"form_accept_edit_all": int,
                                                                              "number": int}), AdminRule())
async def accept_form_edit(m: MessageEvent):
    user_id = m.object.payload['form_accept_edit_all']
    number = int(m.payload['number'])
    name = await db.select([db.Form.name]).where(
        and_(db.Form.user_id == user_id, db.Form.number == number)).gino.scalar()
    if not name:
        await bot.edit_msg(m, "Анкета уже принята или отклонена другим администратором")
        return
    await db.Form.delete.where(and_(
        db.Form.user_id == user_id, db.Form.is_request.is_(False), db.Form.is_edit.is_(True)
    )).gino.status()
    await db.Form.update.values(is_request=False, is_edit=False).where(and_(
        db.Form.user_id == user_id, db.Form.is_edit.is_(False), db.Form.is_request.is_(True)
    )).gino.status()
    await bot.edit_msg(m, f"Анкета участника [id{user_id}|{name}] принята")
    await bot.write_msg(user_id, messages.edit_request_accept.format(name))


@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent, PayloadMapRule({"form_decline_edit_all": int,
                                                                              "number": int}), AdminRule())
@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent, PayloadMapRule({"form_decline_edit_all": int,
                                                                              "number": str}), AdminRule())
async def accept_form_edit(m: MessageEvent):
    user_id = m.object.payload['form_decline_edit_all']
    try:
        number = int(m.payload['number'])
    except ValueError:
        number = 1
    name = await db.select([db.Form.name]).where(
        and_(db.Form.user_id == user_id, db.Form.number == number)).gino.scalar()
    if not name:
        await bot.edit_msg(m, "Анкета уже принята или отклонена другим администратором")
        return
    await db.Form.delete.where(and_(
        db.Form.user_id == user_id, db.Form.is_request.is_(True), db.Form.is_edit.is_(True)
    )).gino.status()
    await db.Form.update.values(is_edit=False).where(and_(
        db.Form.user_id == user_id, db.Form.is_request.is_(False), db.Form.is_edit.is_(True)
    )).gino.status()
    await bot.edit_msg(m, f"Анкета участника [id{user_id}|{name}] отклонена")
    await bot.write_msg(user_id, messages.edit_request_decline.format(name))


@bot.on.private_message(StateRule(Admin.SELECT_PROFESSION, True), NumericRule(), AdminRule())
async def set_profession_to_user(m: Message, value: int = None):
    profession_id = await db.select([db.Profession.id]).offset(value - 1).limit(1).gino.scalar()
    user_id = int(states.get(m.from_id).split("@")[1])
    name = await db.select([db.Form.name]).where(
        and_(db.Form.user_id == user_id, db.Form.is_request.is_(True))
    ).gino.scalar()
    await db.Form.update.values(profession=profession_id).where(
        and_(db.Form.user_id == user_id, db.Form.is_request.is_(True))
    ).gino.status()
    states.set(m.from_id, f"{Admin.SELECT_CABIN}@{user_id}")
    free = []
    i = 1
    employed = {x[0] for x in await db.select([db.Form.cabin]).gino.all()}
    while not free:
        i += 100
        numbers = set(range(1, i))
        free = list(map(str, list(numbers - employed)))
    reply = f"Укажите номер кабины участника [id{user_id}|{name}]\n\n" \
            f"Свободные номера: {', '.join(free)}"
    await bot.write_msg(m.peer_id, reply, keyboard=Keyboard())


@bot.on.private_message(StateRule(Admin.SELECT_CABIN, True), NumericRule())
async def set_user_cabin(m: Message, value: int = None):
    employed = await db.select([db.Form.cabin]).where(db.Form.cabin == value).gino.scalar()
    if employed:
        await bot.write_msg(m.peer_id, "Данная комната уже занята")
        return
    user_id = int(states.get(m.from_id).split("@")[1])
    await db.Form.update.values(cabin=value).where(
        and_(db.Form.user_id == user_id, db.Form.is_request.is_(True))
    ).gino.status()
    states.set(m.from_id, f"{Admin.SELECT_CLASS_CABIN}@{user_id}")
    cabins = await db.select([db.Cabins.name]).gino.all()
    reply = messages.cabin_class
    for i, cabin in enumerate(cabins):
        reply = f"{reply}{i+1}. {cabin.name}\n"
    await bot.write_msg(m.peer_id, reply)


@bot.on.private_message(StateRule(Admin.SELECT_CLASS_CABIN, True),
                        NumericRule(), AdminRule())
async def set_cabin_class(m: Message, value: int):
    user_id = int(states.get(m.from_id).split("@")[1])
    cabin_id, price = await db.select([db.Cabins.id, db.Cabins.cost]).offset(value - 1).limit(1).gino.first()
    await db.Form.update.values(cabin_type=cabin_id,
                                balance=db.Form.balance-price,
                                last_payment=datetime.datetime.now()).where(
        and_(db.Form.user_id == user_id, db.Form.is_request.is_(True))).gino.status()
    form_id = await db.select([db.Form.id]).where(
        and_(db.Form.user_id == user_id, db.Form.is_request.is_(True))
    ).gino.scalar()
    await db.Form.update.values(is_request=False).where(
        and_(db.Form.user_id == user_id, db.Form.is_request.is_(True))
    ).gino.status()
    asyncio.get_event_loop().create_task(take_off_payments(form_id))
    states.set(m.from_id, Menu.MAIN)
    await bot.write_msg(m.peer_id, messages.cabin_class_succesful, keyboard=await keyboards.main_menu(m.from_id))


@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent, PayloadMapRule({"form_decline": int}), AdminRule())
async def decline_form(m: MessageEvent):
    user_id = m.object.payload["form_decline"]
    await db.User.update.values(state=f"{Admin.REASON_DECLINE}@{user_id}").where(db.User.user_id == m.user_id).gino.status()
    user = (await bot.api.users.get(user_id))[0]
    await bot.edit_msg(m, f"Укажите причину отказа от анкеты пользователя [id{user_id}|{user.first_name} {user.last_name}]",
                        keyboard=keyboards.reason_decline_form)


@bot.on.private_message(StateRule(Admin.REASON_DECLINE, True), AdminRule())
async def reason_decline_form(m: Message):
    state = states.get(m.from_id)
    user_id = int(state.split("@")[1])
    main_form = await db.select([db.Form.id]).where(
        and_(db.Form.user_id == user_id, db.Form.is_request.is_(False))).gino.first()
    if not main_form:
        keyboard = keyboards.fill_quiz
    else:
        keyboard = None
    await db.Form.delete.where(and_(db.Form.user_id == user_id, db.Form.is_request.is_(True))).gino.status()
    await bot.write_msg(user_id, f"{messages.form_decline}\n\n{m.text}", keyboard=keyboard)
    user = (await bot.api.users.get(user_id))[0]
    states.set(m.from_id, Menu.MAIN)
    await bot.write_msg(m.peer_id, f"Анкета пользователя [id{user_id}|{user.first_name} {user.last_name}] отклонена",
                        keyboard=await keyboards.main_menu(m.from_id))


@bot.on.private_message(StateRule(Admin.MENU), PayloadRule({"admin_menu": "back"}))
@bot.on.private_message(StateRule(Admin.MENU), text="назад")
async def back_to_admin_menu(m: Message):
    states.set(m.from_id, Menu.MAIN)
    await bot.write_msg(m.peer_id, messages.main_menu, keyboard=await keyboards.main_menu(m.from_id))


@bot.on.private_message(AdminRule(), text="/export")
@bot.on.private_message(PayloadRule({"admin_menu": "export"}), AdminRule())
async def export(m: Message):
    today = datetime.datetime.now().strftime("%Y.%m.%d %H.%M.%S")
    shutil.copy("template.xlsx", f"exports")
    wb = openpyxl.load_workbook(f"exports/template.xlsx")
    tables = (db.Cabins, db.Form, db.Mailings, db.Profession, db.SalaryRequests, db.Shop, db.Transactions, db.User,
              db.Donate, db.Status)
    data = [await db.select([*x]).gino.all() for x in tables]
    sheets = wb.sheetnames
    for i, sheet in enumerate(sheets):
        ws = wb[sheet]
        for query in data[i]:
            if tables[i] == db.Form:
                query = list(query)
                query[3] = await db.select([db.Profession.name]).where(db.Profession.id == query[3]).gino.scalar()
                query[16] = await db.select([db.Cabins.name]).where(db.Cabins.id == query[16]).gino.scalar()
                query[23] = await db.select([db.Status.name]).where(db.Status.id == query[23]).gino.scalar()
            if tables[i] == db.Donate:
                query = list(query)
                query[1] = await db.select([db.Form.name]).where(db.Form.id == query[1]).gino.scalar()
            ws.append(list(query))
    wb.save(f"exports/Экспорт {today}.xlsx")
    doc_uploader = DocMessagesUploader(bot.api)
    attachment = await doc_uploader.upload(f"Экспорт {today}.xlsx", f"exports/Экспорт {today}.xlsx", peer_id=m.peer_id)
    await bot.write_msg(m.peer_id, "Вот текущий экспорт базы данных", attachment=attachment)


@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent, PayloadMapRule({"quest_ready": bool,
                                                                              "request_id": int}))
async def verify_quest(m: MessageEvent):
    request_id = m.payload['request_id']
    exist = await db.select([db.ReadyQuest.id]).where(db.ReadyQuest.id == request_id).gino.scalar()
    if not exist:
        await bot.change_msg(m, "Другой администратор уже проверил этот запрос")
        return
    form_id, quest_id = await db.select([db.ReadyQuest.form_id, db.ReadyQuest.quest_id]).where(db.ReadyQuest.id == request_id).gino.first()
    form_name, user_id = await db.select([db.Form.name, db.Form.user_id]).where(db.Form.id == form_id).gino.first()
    if m.payload['quest_ready']:
        reward, name = await db.select([db.Quest.reward, db.Quest.name]).where(db.Quest.id == quest_id).gino.first()
        await db.Form.update.values(balance=db.Form.balance + reward).gino.status()
        await bot.write_msg(m.peer_id, f"Вы получили награду {reward} монет за выполнение квеста «{name}»")
        await bot.change_msg(m, f"Квест «{name}» засчитан игроку [id{user_id}|{form_name}]")
    else:
        await db.ReadyQuest.delete.where(db.ReadyQuest.id == request_id).gino.status()
        name = await db.select([db.Quest.name]).where(db.Quest.id == quest_id).gino.scalar()
        await bot.write_msg(m.peer_id, f"К сожалению, администрация отменила вам прохождение квеста «{name}»")
        await bot.change_msg(m, f"Квест «{name}» засчитан игроку [id{user_id}|{form_name}]")


@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent, PayloadMapRule({"salary_accept": int}), AdminRule())
async def accept_salary_request(m: MessageEvent):
    salary_id = m.payload['salary_accept']
    exist = await db.select([db.SalaryRequests.id]).where(db.SalaryRequests.id == salary_id).gino.scalar()
    if not exist:
        await bot.change_msg(m, "Зарплата уже была выдана или отклонена другим администратором!")
        return
    user_id = await db.select([db.SalaryRequests.user_id]).where(db.SalaryRequests.id == salary_id).gino.scalar()
    await db.SalaryRequests.delete.where(db.SalaryRequests.id == salary_id).gino.status()
    form_id = await db.select([db.User.activated_form]).where(db.User.user_id == user_id).gino.scalar()
    profession_id, name = await db.select([db.Form.profession, db.Form.name]).where(
        and_(db.Form.user_id == user_id, db.Form.number == form_id)
    ).gino.first()
    salary = await db.select([db.Profession.salary]).where(db.Profession.id == profession_id).gino.scalar()
    await db.Form.update.values(balance=db.Form.balance + salary).where(
        and_(db.Form.user_id == user_id, db.Form.number == form_id)
    ).gino.status()
    await bot.edit_msg(m, f"Зарплата выплачена участнику [id{user_id}|{name}]")
    await bot.write_msg(user_id, messages.salary_accepted.format(salary))


@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent, PayloadMapRule({"salary_decline": int}), AdminRule())
async def decline_salary_request(m: MessageEvent):
    salary_id = m.payload['salary_decline']
    exist = await db.select([db.SalaryRequests.id]).where(db.SalaryRequests.id == salary_id).gino.scalar()
    if not exist:
        await bot.change_msg(m, "Зарплата уже была выдана или отклонена другим администратором!")
        return
    user_id = await db.select([db.SalaryRequests.user_id]).where(db.SalaryRequests.id == salary_id).gino.scalar()
    await db.SalaryRequests.delete.where(db.SalaryRequests.id == salary_id).gino.status()
    form_id = await db.select([db.User.activated_form]).where(db.User.user_id == user_id).gino.scalar()
    name = await db.select([db.Form.name]).where(
        and_(db.Form.user_id == user_id, db.Form.number == form_id)
    ).gino.scalar()
    await bot.edit_msg(m, f"Зарплата отклонена участнику [id{user_id}|{name}]")
    await bot.write_msg(user_id, messages.salary_decline)


@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent, PayloadMapRule({"daylic_confirm": int}), AdminRule())
async def confirm_daylic(m: MessageEvent):
    response_id = m.payload.get("daylic_confirm")
    exist = await db.select([db.CompletedDaylic.daylic_id,
                                          db.CompletedDaylic.form_id]).where(db.CompletedDaylic.id == response_id).gino.first()
    if not exist:
        await bot.change_msg(m, "Другой администратор уже проверил выполнение дейлика")
        return
    daylic_id, form_id = exist
    reward, daylic_name, cooldown = await db.select([db.Daylic.reward, db.Daylic.name, db.Daylic.cooldown]).where(db.Daylic.id == daylic_id).gino.first()
    await (db.Form.update.values(balance=db.Form.balance + reward,
                                deactivated_daylic=datetime.datetime.now()+datetime.timedelta(seconds=cooldown),
                                 activated_daylic=None)
           .where(db.Form.id == form_id).gino.status())
    await db.CompletedDaylic.delete.where(db.CompletedDaylic.id == response_id).gino.status()
    name, user_id = await db.select([db.Form.name, db.Form.user_id]).where(db.Form.id == form_id).gino.first()
    await bot.write_msg(user_id, f"Вам засчитано выполнения дейлика {daylic_name}\n"
                                 f"Вы получили награду в размере {reward} монет\n"
                                 f"На вас наложен кулдаун {parse_cooldown(cooldown)}")
    await bot.change_msg(m, f"Дейлик {daylic_name} засчитан игроку [id{user_id}|{name}], выдана награда {reward} монет")


@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent, PayloadMapRule({"daylic_reject": int}), AdminRule())
async def reject_daylic(m: MessageEvent):
    response_id = m.payload.get("daylic_reject")
    exist = await db.select([db.CompletedDaylic.daylic_id,
                             db.CompletedDaylic.form_id]).where(db.CompletedDaylic.id == response_id).gino.first()
    if not exist:
        await bot.change_msg(m, "Другой администратор уже проверил выполнение дейлика")
        return
    daylic_id, form_id = exist
    daylic_name = await db.select([db.Daylic.name]).where(db.Daylic.id == daylic_id).gino.scalar()
    user_id, name = await db.select([db.Form.user_id, db.Form.name]).where(db.Form.id == form_id).gino.first()
    await db.CompletedDaylic.delete.where(db.CompletedDaylic.id == response_id).gino.status()
    await bot.write_msg(user_id, f"К сожалению вам отклонили выполнение дейлика {daylic_name}")
    await bot.change_msg(m, f"Отклонено выполнение дейлика {daylic_name} участнику [id{user_id}|{name}]")
