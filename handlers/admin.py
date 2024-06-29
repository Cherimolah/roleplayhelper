import asyncio
import datetime
import shutil

from vkbottle.bot import MessageEvent, Message
from vkbottle.dispatch.rules.base import PayloadMapRule, PayloadRule
from sqlalchemy import and_
import openpyxl
from vkbottle import DocMessagesUploader, Callback, KeyboardButtonColor, Keyboard, GroupEventType

from loader import bot
from service.db_engine import db
import messages
from service import keyboards
from service.states import Menu, Admin
from service.middleware import states
from service.custom_rules import StateRule, NumericRule, AdminRule
from service.utils import take_off_payments, parse_cooldown, parse_reputation, create_mention


@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent, PayloadMapRule({"form_accept": int}), AdminRule())
async def accept_form(m: MessageEvent):
    form_id = m.object.payload['form_accept']
    is_request = await db.select([db.Form.is_request]).where(db.Form.id == form_id).gino.scalar()
    if not is_request:
        await m.edit_message("Анкета уже была принята или отклонена другим администратором")
        return
    user_id = await db.select([db.Form.user_id]).where(db.Form.id == form_id).gino.scalar()
    await db.Form.delete.where(and_(db.Form.user_id == user_id, db.Form.is_request.is_(False))).gino.status()
    await db.Form.update.values(is_request=False).where(db.Form.id == form_id).gino.status()
    state = await db.select([db.User.state]).where(db.User.user_id == user_id).gino.scalar()
    if state == "wait":
        await db.User.update.values(state=Menu.MAIN).where(db.User.user_id == user_id).gino.status()
        await bot.api.messages.send(peer_ids=user_id, message=messages.form_accepted, keyboard=await keyboards.main_menu(user_id))
    else:
        await bot.api.messages.send(peer_ids=user_id, message="Заявка на редактирование анкеты была принята", is_notification=True)
    name = await db.select([db.Form.name]).where(db.Form.user_id == user_id).gino.scalar()
    await m.edit_message(f"Анкета участника [id{user_id}|{name}] принята")
    current_profession, cabin = await db.select([db.Form.profession, db.Form.cabin]).where(db.Form.user_id == user_id).gino.first()
    if not current_profession:
        reply = f"Укажите должность участника [id{user_id}|{name}]. Доступные должности:\n\n"
        professions = await db.select([db.Profession.name]).gino.all()
        for i, prof in enumerate(professions):
            reply = f"{reply}{i+1}. {prof.name}\n"
        await db.User.update.values(state=f"{Admin.SELECT_PROFESSION}*{user_id}").where(db.User.user_id == m.user_id).gino.status()
        await m.send_message(reply, keyboard=keyboards.another_profession_to_user(user_id))
        return
    if not cabin:
        await db.User.update.values(state=f"{Admin.SELECT_CABIN}*{user_id}").where(
            db.User.user_id == m.user_id).gino.status()
        free = []
        i = 1
        employed = {x[0] for x in await db.select([db.Form.cabin]).gino.all()}
        while not free:
            i += 100
            numbers = set(range(1, i))
            free = list(map(str, list(numbers - employed)))
        reply = f"Укажите номер кабины участника [id{user_id}|{name}]\n\n" \
                f"Свободные номера: {', '.join(free)}"
        await m.send_message(reply, keyboard=Keyboard().get_json())


@bot.on.private_message(StateRule(Admin.SELECT_PROFESSION), NumericRule(), AdminRule())
async def set_profession_to_user(m: Message, value: int = None):
    profession_id = await db.select([db.Profession.id]).offset(value - 1).limit(1).gino.scalar()
    user_id = int(states.get(m.from_id).split("*")[1])
    name = await db.select([db.Form.name]).where(
        and_(db.Form.user_id == user_id, db.Form.is_request.is_(True))
    ).gino.scalar()
    await db.Form.update.values(profession=profession_id).where(
        and_(db.Form.user_id == user_id, db.Form.is_request.is_(True))
    ).gino.status()
    states.set(m.from_id, f"{Admin.SELECT_CABIN}*{user_id}")
    free = []
    i = 1
    employed = {x[0] for x in await db.select([db.Form.cabin]).gino.all()}
    while not free:
        i += 100
        numbers = set(range(1, i))
        free = list(map(str, list(numbers - employed)))
    reply = f"Укажите номер кабины участника [id{user_id}|{name}]\n\n" \
            f"Свободные номера: {', '.join(free)}"
    await m.answer(reply, keyboard=Keyboard())


@bot.on.private_message(StateRule(Admin.SELECT_CABIN), NumericRule())
async def set_user_cabin(m: Message, value: int = None):
    employed = await db.select([db.Form.cabin]).where(db.Form.cabin == value).gino.scalar()
    if employed:
        await m.answer("Данная комната уже занята")
        return
    user_id = int(states.get(m.from_id).split("*")[1])
    await db.Form.update.values(cabin=value).where(db.Form.user_id == user_id).gino.status()
    states.set(m.from_id, f"{Admin.SELECT_CLASS_CABIN}*{user_id}")
    cabins = await db.select([db.Cabins.name]).gino.all()
    reply = messages.cabin_class
    for i, cabin in enumerate(cabins):
        reply = f"{reply}{i+1}. {cabin.name}\n"
    await m.answer(reply)


@bot.on.private_message(StateRule(Admin.SELECT_CLASS_CABIN),
                        NumericRule(), AdminRule())
async def set_cabin_class(m: Message, value: int):
    user_id = int(states.get(m.from_id).split("*")[1])
    cabin_id, price = await db.select([db.Cabins.id, db.Cabins.cost]).offset(value - 1).limit(1).gino.first()
    await db.Form.update.values(cabin_type=cabin_id,
                                balance=db.Form.balance-price,
                                last_payment=datetime.datetime.now()).where(
        db.Form.user_id == user_id).gino.status()
    form_id = await db.select([db.Form.id]).where(
        and_(db.Form.user_id == user_id, db.Form.is_request.is_(True))
    ).gino.scalar()
    await db.Form.update.values(is_request=False).where(
        and_(db.Form.user_id == user_id, db.Form.is_request.is_(True))
    ).gino.status()
    asyncio.get_event_loop().create_task(take_off_payments(form_id))
    states.set(m.from_id, Menu.MAIN)
    await m.answer(messages.cabin_class_succesful, keyboard=await keyboards.main_menu(m.from_id))


@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent, PayloadMapRule({"form_decline": int}), AdminRule())
async def decline_form(m: MessageEvent):
    form_id = m.object.payload['form_decline']
    is_request = await db.select([db.Form.is_request]).where(db.Form.id == form_id).gino.scalar()
    if not is_request:
        await m.edit_message("Анкета уже была принята или отклонена другим администратором")
        return
    user_id = await db.select([db.Form.user_id]).where(db.Form.id == form_id).gino.scalar()
    await db.User.update.values(state=f"{Admin.REASON_DECLINE}*{user_id}").where(db.User.user_id == m.user_id).gino.status()
    user = (await bot.api.users.get(user_id))[0]
    await m.edit_message(f"Укажите причину отказа от анкеты пользователя [id{user_id}|{user.first_name} {user.last_name}]",
                        keyboard=keyboards.reason_decline_form)


@bot.on.private_message(StateRule(Admin.REASON_DECLINE), AdminRule())
async def reason_decline_form(m: Message):
    state = states.get(m.from_id)
    user_id = int(state.split("*")[1])
    await db.Form.delete.where(and_(db.Form.user_id == user_id, db.Form.is_request.is_(True))).gino.status()
    main_form = await db.select([db.Form.id]).where(
        and_(db.Form.user_id == user_id, db.Form.is_request.is_(False))).gino.first()
    if not main_form:
        keyboard = keyboards.fill_quiz
        await db.User.update.values(state=None).where(db.User.user_id == user_id).gino.status()
        await bot.api.messages.send(user_id, f"{messages.form_decline}\n\n{m.text}", keyboard=keyboard,
                                    is_notification=True)
    else:
        await bot.api.messages.send(user_id, "Заявка на редактирование анкеты была отклонена", is_notification=True)
    user = (await bot.api.users.get(user_id))[0]
    states.set(m.from_id, Menu.MAIN)
    await m.answer(f"Анкета пользователя [id{user_id}|{user.first_name} {user.last_name}] отклонена",
                        keyboard=await keyboards.main_menu(m.from_id))


@bot.on.private_message(StateRule(Admin.MENU), PayloadRule({"admin_menu": "back"}))
@bot.on.private_message(StateRule(Admin.MENU), text="назад")
async def back_to_admin_menu(m: Message):
    states.set(m.from_id, Menu.MAIN)
    await m.answer(messages.main_menu, keyboard=await keyboards.main_menu(m.from_id))


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
    await m.answer("Вот текущий экспорт базы данных", attachment=attachment)


@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent, PayloadMapRule({"quest_ready": bool,
                                                                              "request_id": int}))
async def verify_quest(m: MessageEvent):
    request_id = m.payload['request_id']
    exist = await db.select([db.ReadyQuest.id]).where(db.ReadyQuest.id == request_id).gino.scalar()
    if not exist:
        await m.edit_message("Другой администратор уже проверил этот запрос")
        return
    form_id, quest_id = await db.select([db.ReadyQuest.form_id, db.ReadyQuest.quest_id]).where(db.ReadyQuest.id == request_id).gino.first()
    form_name, user_id = await db.select([db.Form.name, db.Form.user_id]).where(db.Form.id == form_id).gino.first()
    if m.payload['quest_ready']:
        reward, name, fraction_id, reputation = await db.select(
            [db.Quest.reward, db.Quest.name, db.Quest.fraction_id, db.Quest.reputation]).where(
            db.Quest.id == quest_id).gino.first()
        await db.Form.update.values(balance=db.Form.balance + reward, active_quest=None).gino.status()
        await bot.api.messages.send(m.user_id, f"Вы получили награду {reward} монет за выполнение квеста «{name}»",
                                    is_notification=True)
        if fraction_id:
            await db.change_reputation(user_id, fraction_id, reputation)
        await m.edit_message(f"Квест «{name}» засчитан игроку [id{user_id}|{form_name}]")
    else:
        await db.ReadyQuest.delete.where(db.ReadyQuest.id == request_id).gino.status()
        await db.Form.update.values(active_quest=None).where(db.Form.user_id == user_id).gino.status()
        name = await db.select([db.Quest.name]).where(db.Quest.id == quest_id).gino.scalar()
        await bot.api.messages.send(m.user_id, f"К сожалению, администрация отменила вам прохождение квеста «{name}»",
                                    is_notification=True)
        await m.edit_message(f"Квест «{name}» не засчитан игроку [id{user_id}|{form_name}]")


@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent, PayloadMapRule({"salary_accept": int}), AdminRule())
async def accept_salary_request(m: MessageEvent):
    salary_id = m.payload['salary_accept']
    exist = await db.select([db.SalaryRequests.id]).where(db.SalaryRequests.id == salary_id).gino.scalar()
    if not exist:
        await m.edit_message("Зарплата уже была выдана или отклонена другим администратором!")
        return
    user_id = await db.select([db.SalaryRequests.user_id]).where(db.SalaryRequests.id == salary_id).gino.scalar()
    await db.SalaryRequests.delete.where(db.SalaryRequests.id == salary_id).gino.status()
    profession_id, name = await db.select([db.Form.profession, db.Form.name]).where(
        and_(db.Form.user_id == user_id)
    ).gino.first()
    salary = await db.select([db.Profession.salary]).where(db.Profession.id == profession_id).gino.scalar()
    await db.Form.update.values(balance=db.Form.balance + salary).where(
        and_(db.Form.user_id == user_id)
    ).gino.status()
    await m.edit_message(f"Зарплата выплачена участнику [id{user_id}|{name}]")
    await bot.api.messages.send(user_id, messages.salary_accepted.format(salary), is_notification=True)


@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent, PayloadMapRule({"salary_decline": int}), AdminRule())
async def decline_salary_request(m: MessageEvent):
    salary_id = m.payload['salary_decline']
    exist = await db.select([db.SalaryRequests.id]).where(db.SalaryRequests.id == salary_id).gino.scalar()
    if not exist:
        await m.edit_message("Зарплата уже была выдана или отклонена другим администратором!")
        return
    user_id = await db.select([db.SalaryRequests.user_id]).where(db.SalaryRequests.id == salary_id).gino.scalar()
    await db.SalaryRequests.delete.where(db.SalaryRequests.id == salary_id).gino.status()
    name = await db.select([db.Form.name]).where(db.Form.user_id == user_id).gino.scalar()
    await m.edit_message(f"Зарплата отклонена участнику [id{user_id}|{name}]")
    await bot.api.messages.send(user_id, messages.salary_decline, is_notification=True)


@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent, PayloadMapRule({"daylic_confirm": int}), AdminRule())
async def confirm_daylic(m: MessageEvent):
    response_id = m.payload.get("daylic_confirm")
    exist = await db.select([db.CompletedDaylic.daylic_id,
                                          db.CompletedDaylic.form_id]).where(db.CompletedDaylic.id == response_id).gino.first()
    if not exist:
        await m.edit_message("Другой администратор уже проверил выполнение дейлика")
        return
    daylic_id, form_id = exist
    reward, daylic_name, cooldown = await db.select([db.Daylic.reward, db.Daylic.name, db.Daylic.cooldown]).where(db.Daylic.id == daylic_id).gino.first()
    await (db.Form.update.values(balance=db.Form.balance + reward,
                                deactivated_daylic=datetime.datetime.now()+datetime.timedelta(seconds=cooldown),
                                 activated_daylic=None)
           .where(db.Form.id == form_id).gino.status())
    await db.CompletedDaylic.delete.where(db.CompletedDaylic.id == response_id).gino.status()
    name, user_id = await db.select([db.Form.name, db.Form.user_id]).where(db.Form.id == form_id).gino.first()
    await bot.api.messages.send(user_id, f"Вам засчитано выполнения дейлика {daylic_name}\n"
                                 f"Вы получили награду в размере {reward} монет\n"
                                 f"На вас наложен кулдаун {parse_cooldown(cooldown)}", is_notification=True)
    await m.edit_message(f"Дейлик {daylic_name} засчитан игроку [id{user_id}|{name}], выдана награда {reward} монет")


@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent, PayloadMapRule({"daylic_reject": int}), AdminRule())
async def reject_daylic(m: MessageEvent):
    response_id = m.payload.get("daylic_reject")
    exist = await db.select([db.CompletedDaylic.daylic_id,
                             db.CompletedDaylic.form_id]).where(db.CompletedDaylic.id == response_id).gino.first()
    if not exist:
        await m.edit_message("Другой администратор уже проверил выполнение дейлика")
        return
    daylic_id, form_id = exist
    daylic_name = await db.select([db.Daylic.name]).where(db.Daylic.id == daylic_id).gino.scalar()
    user_id, name = await db.select([db.Form.user_id, db.Form.name]).where(db.Form.id == form_id).gino.first()
    await db.CompletedDaylic.delete.where(db.CompletedDaylic.id == response_id).gino.status()
    await bot.api.messages.send(user_id, f"К сожалению вам отклонили выполнение дейлика {daylic_name}", is_notification=True)
    await m.edit_message(f"Отклонено выполнение дейлика {daylic_name} участнику [id{user_id}|{name}]")


@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent, PayloadMapRule({"freeze": str, "user_id": int}))
async def accept_freeze(m: MessageEvent):
    has_req = await db.select([db.Form.freeze_request]).where(db.Form.user_id == m.payload['user_id']).gino.scalar()
    if not has_req:
        await m.edit_message("Запрос уже принял другой администратор")
        return
    name, freeze = await db.select([db.Form.name, db.Form.freeze]).where(db.Form.user_id == m.payload['user_id']).gino.first()
    if m.payload['freeze'] == "accept":
        await db.Form.update.values(freeze_request=False, freeze=not freeze).where(db.Form.user_id == m.payload['user_id']).gino.status()
        await bot.api.messages.send(m.payload['user_id'],
                                    f"Ваша анкета была {'разморожена' if freeze else 'заморожена'}",
                                    is_notification=True)
        await m.edit_message(f"Анкета [id{m.payload['user_id']}|{name}] была заморожена")
    else:
        await db.Form.update.values(freeze_request=False).where(db.Form.user_id == m.payload['user_id']).gino.status()
        await bot.api.messages.send(m.payload['user_id'],
                                    f"Ваш запрос на {'разморозку' if freeze else 'заморозку'} был отклонён",
                                    is_notification=True)
        await m.edit_message(f"Запрос на {'разморозку' if freeze else 'заморозку'} "
                             f"анкеты [id{m.payload['user_id']}|{name}] отклонён")


@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent, PayloadMapRule({"delete": str, "user_id": int}))
async def accept_delete(m: MessageEvent):
    has_req = await db.select([db.Form.delete_request]).where(db.Form.user_id == m.payload['user_id']).gino.scalar()
    if not has_req:
        await m.edit_message("Запрос уже принял другой администратор")
        return
    name = await db.select([db.Form.name]).where(db.Form.user_id == m.payload['user_id']).gino.scalar()
    if m.payload['delete'] == "accept":
        await db.User.delete.where(db.User.user_id == m.payload['user_id']).gino.status()
        await bot.api.messages.send(m.payload['user_id'],
                                    f"Ваша анкета в боте была удалена! Приятно было с вами общаться, "
                                    f"если захотите вернуться напишите «Начать»", keyboard=Keyboard())
        await m.edit_message(f"Анкета [id{m.payload['user_id']}|{name}] была удалена!")
    else:
        await db.Form.update.values(delete_request=False).where(db.Form.user_id == m.payload['user_id']).gino.status()
        await bot.api.messages.send(m.payload['user_id'], "Ваша запрос на удаление анкеты был отклонён", is_notification=True)
        await m.edit_message(f"Запрос на удаление анкеты [id{m.payload['user_id']}|{name}] отклонён")


@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent, PayloadMapRule({"form_delete": int}), AdminRule())
async def delete_form(m: MessageEvent):
    user_id, name = await db.select([db.Form.user_id, db.Form.name]).where(db.Form.id == m.payload['form_delete']).gino.first()
    user = (await bot.api.users.get(user_ids=user_id))[0]
    user_name = f"{user.first_name} {user.last_name}"
    await db.Form.delete.where(db.Form.id == m.payload['form_delete']).gino.status()
    await m.edit_message(f"Анкета [id{user_id}|{name} / {user_name}] была удалена")


@bot.on.private_message(PayloadMapRule({"form_reputation": int}), StateRule(Menu.SHOW_FORM), AdminRule())
async def form_reputation_all(m: Message):
    if m.payload:
        user_id = m.payload['form_reputation']
    else:
        user_id = int(states.get(m.from_id).split("*")[1])
        states.set(user_id, Menu.SHOW_FORM)
    reputations = await db.get_reputations(user_id)
    mention = await create_mention(user_id)
    reply = f"Список репутаций {mention}:\n\n"
    for fraction_id, reputation in reputations:
        fraction_name = await db.select([db.Fraction.name]).where(db.Fraction.id == fraction_id).gino.scalar()
        reputation_level = parse_reputation(reputation)
        reply += f"{fraction_name}: {reputation_level}\n"
    keyboard = Keyboard(inline=True).add(
        Callback("Добавить", {"reputation_add": user_id}), KeyboardButtonColor.POSITIVE
    ).add(
        Callback("Редактировать", {"reputation_edit": user_id}), KeyboardButtonColor.PRIMARY
    ).row().add(
        Callback("Удалить", {"reputation_delete": user_id}), KeyboardButtonColor.NEGATIVE
    )
    await m.answer(reply, keyboard=keyboard)


@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent, PayloadMapRule({"reputation_add": int}), StateRule(Menu.SHOW_FORM), AdminRule())
async def select_add_reputation(m: MessageEvent):
    user_id = m.payload['reputation_add']
    fractions_all = {x[0] for x in await db.select([db.Fraction.id]).gino.all()}
    fractions_user = {x[0] for x in await db.select([db.UserToFraction.fraction_id]).where(db.UserToFraction.user_id == user_id).gino.all()}
    fractions_empty = list(fractions_all - fractions_user)
    if not fractions_empty:
        await m.show_snackbar("Сейчас нет доступных фракций")
        return
    fractions = [x[0] for x in await db.select([db.Fraction.name]).where(db.Fraction.id.in_(fractions_empty)).order_by(db.Fraction.id.asc()).gino.all()]
    reply = f"Укажите номер какой фракции добавить к репутации {await create_mention(user_id)}:\n\n"
    for i, name in enumerate(fractions):
        reply += f"{i + 1}. {name}\n"
    await db.User.update.values(state=f"{Admin.ADDING_REPUTATION}*{user_id}").where(db.User.user_id == m.user_id).gino.status()
    await m.edit_message(reply)


@bot.on.private_message(StateRule(Admin.ADDING_REPUTATION), NumericRule(), AdminRule())
async def add_reputation(m: Message):
    user_id = int(states.get(m.from_id).split("*")[1])
    fractions_all = {x[0] for x in await db.select([db.Fraction.id]).gino.all()}
    fractions_user = {x[0] for x in await db.select([db.UserToFraction.fraction_id]).where(
        db.UserToFraction.user_id == user_id).gino.all()}
    fractions_empty = list(fractions_all - fractions_user)
    if int(m.text) > len(fractions_empty):
        await m.answer("Номер фракции слишком большой")
        return
    fractions = [x[0] for x in await db.select([db.Fraction.id]).where(db.Fraction.id.in_(fractions_empty)).order_by(
        db.Fraction.id.asc()).gino.all()]
    fraction_id = fractions[int(m.text) - 1]
    await db.change_reputation(user_id, fraction_id, 0)
    name = await db.select([db.Fraction.name]).where(db.Fraction.id == fraction_id).gino.scalar()
    await m.answer(f"Фракция {name} успешно добавлена к {await create_mention(user_id)}")
    await form_reputation_all(m)


@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent, PayloadMapRule({"reputation_edit": int}), StateRule(Menu.SHOW_FORM), AdminRule())
async def select_fraction_to_edit_rep(m: MessageEvent):
    user_id = m.payload['reputation_edit']
    fractions = await db.select([db.UserToFraction.fraction_id, db.UserToFraction.reputation]).where(db.UserToFraction.user_id == user_id).order_by(db.UserToFraction.reputation.desc()).gino.all()
    reply = "Выберите номер фракции для редактирования:\n\n"
    for i, data in enumerate(fractions):
        fraction_id, reputation = data
        name = await db.select([db.Fraction.name]).where(db.Fraction.id == fraction_id).gino.scalar()
        reply += f"{i + 1}. {name} ({reputation})\n"
    await db.User.update.values(state=f"{Admin.SELECT_USER_FRACTION}*{user_id}").where(db.User.user_id == m.user_id).gino.status()
    await m.edit_message(reply)


@bot.on.private_message(StateRule(Admin.SELECT_USER_FRACTION), AdminRule())
async def set_new_reputation(m: Message):
    user_id = int(states.get(m.from_id).split("*")[1])
    fractions = await db.select([db.UserToFraction.fraction_id]).where(db.UserToFraction.user_id == user_id).order_by(db.UserToFraction.reputation.desc()).gino.all()
    if int(m.text) > len(fractions):
        await m.answer("Номер фракции слишком большой")
        return
    fraction_id = fractions[int(m.text) - 1][0]
    states.set(m.from_id, f"{Admin.SET_NEW_REPUTATION}*{user_id}*{fraction_id}")
    name = await db.select([db.Fraction.name]).where(db.Fraction.id == fraction_id).gino.scalar()
    await m.answer(f"Пришлите новый уровень репутации во фракции {name} пользователя {await create_mention(user_id)} от -100 до 100")


@bot.on.private_message(StateRule(Admin.SET_NEW_REPUTATION), AdminRule())
async def new_reputation(m: Message):
    try:
        int(m.text)
    except ValueError:
        await m.answer("Необходимо ввести число от -100 до 100")
        return
    if not -100 <= int(m.text) <= 100:
        await m.answer("Репутация должна находится в интервале от -100 до 100")
        return
    user_id = int(states.get(m.from_id).split("*")[1])
    fraction_id = int(states.get(m.from_id).split("*")[2])
    name = await db.select([db.Fraction.name]).where(db.Fraction.id == fraction_id).gino.scalar()
    await db.UserToFraction.update.values(reputation=int(m.text)).where(
        and_(db.UserToFraction.fraction_id == fraction_id, db.UserToFraction.user_id == user_id)
    ).gino.status()
    await m.answer(f"Установлена репутация {m.text} во фракции {name} пользователю {await create_mention(user_id)}")
    await form_reputation_all(m)


@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent, PayloadMapRule({"reputation_delete": int}), StateRule(Menu.SHOW_FORM), AdminRule())
async def select_reputation_delete(m: MessageEvent):
    user_id = int(m.payload['reputation_delete'])
    fractions_user = await db.select([db.UserToFraction.fraction_id, db.UserToFraction.reputation]).where(db.UserToFraction.user_id == user_id).order_by(db.UserToFraction.reputation).gino.all()
    reply = f"Выберите фракцию для удаления репутации у пользователя {await create_mention(user_id)}\n\n"
    for i, data in enumerate(fractions_user):
        fraction_id, reputation = data
        name = await db.select([db.Fraction.name]).where(db.Fraction.id == fraction_id).gino.scalar()
        reply += f"{i + 1}. {name} ({reputation})\n"
    await db.User.update.values(state=f"{Admin.DELETE_USER_REPUTATION}*{user_id}").where(db.User.user_id == m.user_id).gino.status()
    await m.edit_message(reply)


@bot.on.private_message(StateRule(Admin.DELETE_USER_REPUTATION), NumericRule(), AdminRule())
async def delete_reputation(m: Message, value: int):
    user_id = int(states.get(m.from_id).split("*")[1])
    fractions_user = [x[0] for x in await db.select([db.UserToFraction.fraction_id]).where(db.UserToFraction.user_id == user_id).order_by(db.UserToFraction.reputation).gino.all()]
    if value > len(fractions_user):
        await m.answer("Номер фракции слишком большой")
        return
    fraction_id = fractions_user[value - 1]

    fraction_joined = await db.select([db.Form.fraction_id]).where(db.Form.user_id == user_id).gino.scalar()
    if fraction_joined == fraction_id:
        await m.answer("Нельзя удалить репутацию во фракции которой человек состоит. "
                       "Переведите сначала его во фракцию «Без фракции»")
        return

    await db.UserToFraction.delete.where(
        and_(db.UserToFraction.fraction_id == fraction_id, db.UserToFraction.user_id == user_id)
    ).gino.status()
    name = await db.select([db.Fraction.name]).where(db.Fraction.id == fraction_id).gino.scalar()
    await m.answer(f"Репутация во фракции {name} удалена у пользователя {await create_mention(user_id)}")
    await form_reputation_all(m)
