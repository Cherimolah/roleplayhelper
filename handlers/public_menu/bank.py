from datetime import datetime, timedelta, timezone

from vkbottle.bot import Message, MessageEvent
from vkbottle.dispatch.rules.base import PayloadRule, PayloadMapRule
from vkbottle import GroupEventType, Keyboard, Text, KeyboardButtonColor, Callback
from sqlalchemy import and_, or_, func

import messages
from loader import bot
from service.custom_rules import StateRule, NumericRule, ValidateAccount
from service.states import Menu
import service.keyboards as keyboards
from service.middleware import states
from service.db_engine import db
from service.utils import get_current_form_id
from config import ADMINS


@bot.on.private_message(PayloadRule({"menu": "bank"}))
async def send_bank_menu(m: Message):
    states.set(m.from_id, Menu.BANK_MENU)
    await m.answer(messages.bank_menu, keyboard=keyboards.bank)


@bot.on.private_message(StateRule(Menu.BANK_MENU), PayloadRule({"bank_menu": "balance"}))
async def send_balance(m: Message):
    balance = (await db.select([db.Form.balance])
               .where(db.Form.user_id == m.from_id).gino.scalar())
    await m.answer(messages.balance.format(balance))


@bot.on.private_message(StateRule(Menu.BANK_MENU), PayloadRule({"bank_menu": "history"}))
async def send_transfer_history(m: Message):
    form_id = (await db.select([db.Form.id])
               .select_from(db.Form.join(db.User, db.User.user_id == db.Form.user_id))
               .where(and_(db.Form.user_id == m.from_id)).gino.scalar())
    transactions = await db.select([*db.Transactions]).where(
        or_(db.Transactions.from_user == form_id, db.Transactions.to_user == form_id)
    ).order_by(db.Transactions.id.desc()).limit(10).gino.all()
    if not transactions:
        await m.answer(messages.not_transactions)
        return
    reply = ""
    for i, trans in enumerate(transactions):
        from_name, from_user_id = await db.select([db.Form.name, db.Form.user_id]).where(
            db.Form.id == trans.from_user
        ).gino.first()
        to_name, to_user_id = await db.select([db.Form.name, db.Form.user_id]).where(
            db.Form.id == trans.to_user
        ).gino.first()
        reply = f"{reply}{i + 1}. От [id{from_user_id}|{from_name}] к [id{to_user_id}|{to_name}] сумма {trans.amount}\n"
    await m.answer(messages.history_transactions.format(reply))


@bot.on.private_message(StateRule(Menu.BANK_MENU), PayloadRule({"bank_menu": "transfer"}), ValidateAccount())
async def send_create_transactions(m: Message):
    form_id = await db.select([db.Form.id]).where(db.Form.user_id == m.from_id).gino.scalar()
    forms = await db.select([db.Form.user_id, db.Form.name]).where(
        and_(db.Form.is_request.is_(False), db.Form.id != form_id)
    ).limit(15).gino.all()
    if not forms:
        await m.answer("Пока анкет нет")
        return
    states.set(m.from_id, Menu.SELECT_USER_TO_TRANSFER)
    count_forms = await db.func.count(db.Form.id).gino.scalar()
    keyboard = Keyboard().add(Text("Назад", {"menu": "bank"}), KeyboardButtonColor.NEGATIVE)
    await m.answer(messages.select_users_to_transfers, keyboard=keyboard)
    keyboard = None
    if count_forms > 15:
        keyboard = Keyboard(inline=True).add(Callback("->", {"users_page": 2}), KeyboardButtonColor.PRIMARY)
    reply = ""
    for i, form in enumerate(forms):
        reply = f"{reply}{i + 1}. [id{form.user_id}|{form.name}]\n"
    await m.answer(reply, keyboard=keyboard)


@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent, PayloadMapRule({"users_page": int}))
async def send_page(m: MessageEvent):
    new_page = int(m.payload['users_page'])
    count_forms = await db.func.count(db.Form.id).gino.scalar()
    keyboard = Keyboard(inline=True)
    if new_page > 1:
        keyboard.add(Callback("<-", {"users_page": new_page - 1}), KeyboardButtonColor.PRIMARY)
    if count_forms - new_page * 15 > 0:
        keyboard.add(Callback("->", {"users_page": new_page + 1}), KeyboardButtonColor.PRIMARY)
    forms = (await db.select([db.Form.user_id, db.Form.name]).where(db.Form.is_request.is_(False))
             .offset((new_page - 1) * 15).limit(15).gino.all())
    reply = ""
    for i, form in enumerate(forms):
        reply = f"{reply}{int(i * new_page) + 1}. [id{form.user_id}|{form.name}]\n"
    await m.edit_message(reply, keyboard=keyboard.get_json())


@bot.on.private_message(StateRule(Menu.SELECT_USER_TO_TRANSFER), ValidateAccount())
async def select_user_to_transfer(m: Message):
    if m.text.isdigit():
        user_form_id = await db.select([db.Form.id]).where(db.Form.user_id == m.from_id).gino.scalar()
        form_id = await db.select([db.Form.id]).where(
        and_(db.Form.is_request.is_(False), db.Form.id != user_form_id)
    ).offset(int(m.text) - 1).limit(1).gino.scalar()
    else:
        user_form_id = await db.select([db.Form.id]).select_from(
            db.Form.join(db.User, db.Form.user_id == db.User.user_id)
        ).gino.scalar()
        form_id = await db.select([db.Form.id]).where(
            and_(db.Form.id != user_form_id, func.lower(db.Form.name) == func.lower(m.text))
        ).where(db.Form.user_id == m.from_id).gino.scalar()
    if not form_id:
        await m.answer(messages.error_user_to_transfer)
        return
    states.set(m.from_id, f"{Menu.SELECT_AMOUNT_TO_TRANSFER}@{form_id}")
    await m.answer(messages.amount_transfer)


@bot.on.private_message(StateRule(Menu.SELECT_AMOUNT_TO_TRANSFER, True), NumericRule(), ValidateAccount())
async def set_amount_transfer(m: Message, value: int = None):
    if value < 1:
        await m.answer(messages.error_small_amount)
        return
    if value % 2 == 0:
        commission = value // 2
    else:
        commission = value // 2 + 1
    tax = 0 if value <= 25 else 100 + commission
    balance = (await db.select([db.Form.balance]).where(db.Form.user_id == m.from_id).gino.scalar())
    if balance < value + tax:
        states.set(m.from_id, Menu.BANK_MENU)
        await m.answer(messages.error_not_enogh_tokens.format(balance, value + tax),
                            keyboard=keyboards.bank)
        return
    form_id = int(states.get(m.from_id).split("@")[1])
    name, user_id = await db.select([db.Form.name, db.Form.user_id]).where(db.Form.id == form_id).gino.first()
    states.set(m.from_id, f"{Menu.CONFIRM_TRANSFER}@{form_id}@{user_id}@{value}@{value + tax}")
    keyboard = Keyboard().add(
        Text("Подтвердить", {"transfer": "accept"}), KeyboardButtonColor.POSITIVE
    ).row().add(
        Text("Отмена", {"transfer": "decline"}), KeyboardButtonColor.NEGATIVE
    )
    await m.answer(messages.confirm_transfer.format(f"[id{user_id}|{name}]", value, value + tax, tax),
                        keyboard=keyboard)


@bot.on.private_message(StateRule(Menu.CONFIRM_TRANSFER, True), PayloadRule({"transfer": "accept"}), ValidateAccount())
async def confirm_transaction(m: Message):
    state = states.get(m.from_id)
    form_id, user_id, amount, amount_with_tax = list(map(int, state.split("@")[1:]))
    current_form_id = await db.select([db.Form.id]).where(db.Form.user_id == m.from_id).gino.scalar()
    await db.Transactions.create(to_user=form_id, from_user=current_form_id, amount=amount)
    await db.Form.update.values(balance=db.Form.balance - amount_with_tax).where(
        and_(db.Form.user_id == m.from_id, db.Form.id == current_form_id)
    ).gino.status()
    await db.Form.update.values(balance=db.Form.balance + amount).where(db.Form.id == form_id).gino.status()
    name = await db.select([db.Form.name]).where(db.Form.id == form_id).gino.scalar()
    name = f"[id{user_id}|{name}]"
    from_name = await db.select([db.Form.name]).where(db.Form.user_id == m.from_id).gino.scalar()
    from_name = f"[id{m.from_id}|{from_name}]"
    await bot.api.messages.send(user_id, messages.trasaction_catch.format(name, amount, from_name), is_notification=True)
    states.set(m.from_id, Menu.BANK_MENU)
    await m.answer(messages.transfer_success, keyboard=keyboards.bank)


@bot.on.private_message(StateRule(Menu.CONFIRM_TRANSFER, True), PayloadRule({"transfer": "decline"}))
async def decline_transfer(m: Message):
    states.set(m.from_id, Menu.BANK_MENU)
    await m.answer(messages.bank_menu, keyboard=keyboards.bank)


@bot.on.private_message(StateRule(Menu.BANK_MENU), PayloadRule({"bank_menu": "ask_salary"}))
async def ask_salary(m: Message):
    request = await db.select([db.SalaryRequests.id]).where(db.SalaryRequests.user_id == m.from_id).gino.scalar()
    if request:
        await m.answer(messages.many_salary_requests)
        return
    salary = await db.SalaryRequests.create(user_id=m.from_id)
    admins = [x[0] for x in await db.select([db.User.user_id]).where(db.User.admin > 0).gino.all()]
    admins = list(set(admins).union(ADMINS))
    name, profession_id = await db.select([db.Form.name, db.Form.profession]).where(db.Form.user_id == m.from_id).gino.first()
    name = f"[id{m.from_id}|{name}]"
    profession = await db.select([db.Profession.name]).where(db.Profession.id == profession_id).gino.scalar()
    day = datetime.now(timezone(timedelta(hours=3))).strftime("%d.%m.%Y %H:%M:%S")
    keyboard = Keyboard(inline=True).add(
        Callback("Принять", {"salary_accept": salary.id}), KeyboardButtonColor.POSITIVE
    ).add(
        Callback("Отклонить", {"salary_decline": salary.id}), KeyboardButtonColor.NEGATIVE
    )
    await bot.api.messages.send(admins, messages.salery_request.format(name, profession, day),
                        keyboard=keyboard)
    await m.answer(messages.salary_request_send)


@bot.on.private_message(StateRule(Menu.BANK_MENU), PayloadRule({"bank_menu": "fixed_costs"}))
async def send_permanent_costs(m: Message):
    cabin_lux = await db.select([db.Form.cabin_type]).where(db.Form.user_id == m.from_id).gino.scalar()
    price = await db.select([db.Cabins.cost]).where(db.Cabins.id == cabin_lux).gino.scalar()
    await m.answer(messages.permament_costs.format(price))


@bot.on.private_message(StateRule(Menu.BANK_MENU), PayloadRule({"bank_menu": "donate"}))
@bot.on.private_message(StateRule(Menu.ENTER_AMOUNT_DONATE), PayloadRule({"bank_menu": "donate"}))
@bot.on.private_message(StateRule(Menu.CONFIRM_DONATE, True), PayloadRule({"bank_menu": "donate"}))
@bot.on.private_message(StateRule(Menu.CONFIRM_DONATE, True), PayloadRule({"donate": "decline"}))
async def show_piggy_bank(m: Message):
    summary = await db.select([func.sum(db.Donate.amount)]).gino.scalar()
    if summary is None:
        summary = 0
    await m.answer(f"Всего пожертвовано: {summary}", keyboard=keyboards.donate_menu)
    count = await db.select([func.count(db.Donate.id)]).gino.scalar()
    donates = await (db.select([db.Donate.amount, db.Donate.form_id, db.Form.name, db.Form.user_id])
                     .select_from(db.Donate.join(db.Form, db.Donate.form_id == db.Form.id))
                     .order_by(db.Donate.amount.desc())
                     .limit(15).gino.all())
    states.set(m.from_id, Menu.DONATE_MENU)
    if count == 0:
        return "На данный момент, ещё никто не пожертвовал"
    kb = None
    if count > 15:
        kb = Keyboard(inline=True).add(
            Callback("->", {"donate_page": 2}), KeyboardButtonColor.PRIMARY
        )
    pages = count // 15
    if count % 15 != 0:
        pages += 1
    reply = f"Список пожертвований:\nСтраница 1/{pages}\n\n"
    for i, donate in enumerate(donates):
        amount, form_id, name, user_id = donate
        reply = f"{reply}{i+1}. [id{user_id}|{name}] {amount}\n"
    await m.answer(reply, keyboard=kb)


@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent, PayloadMapRule({"donate_page": int}))
async def send_donate_page(m: MessageEvent):
    page = m.payload['donate_page']
    donates = await (db.select([db.Donate.amount, db.Donate.form_id, db.Form.name, db.Form.user_id])
                     .select_from(db.Donate.join(db.Form, db.Donate.form_id == db.Form.id))
                     .order_by(db.Donate.amount.desc())
                     .offset((page - 1) * 15).limit(15).gino.all())
    count = await db.select([func.count(db.Donate.id)]).gino.scalar()
    pages = count // 15
    if count % 15 > 0:
        pages += 1
    reply = f"Список пожертвований:\nСтраница {page}/{pages}\n\n"
    for i, donate in enumerate(donates):
        amount, form_id, name, user_id = donate
        reply = f"{reply}{(page - 1) * 15 + i + 1}. [id{user_id}|{name}] {amount}\n"
    kb = Keyboard(inline=True)
    if page > 1:
        kb.add(Callback("<-", {"donate_page": page - 1}), KeyboardButtonColor.PRIMARY)
    if count - page * 15 > 0:
        kb.add(Callback("->", {"donate_page": page + 1}), KeyboardButtonColor.PRIMARY)
    await m.edit_message(reply, keyboard=kb)


@bot.on.private_message(StateRule(Menu.DONATE_MENU), PayloadRule({"bank": "create_donate"}))
async def create_donate(m: Message):
    states.set(m.from_id, Menu.ENTER_AMOUNT_DONATE)
    kb = Keyboard()
    kb.add(Text("Назад", {"bank_menu": "donate"}), KeyboardButtonColor.NEGATIVE)
    await m.answer("Введите сумму для пожертвования", keyboard=kb)


@bot.on.private_message(StateRule(Menu.ENTER_AMOUNT_DONATE), NumericRule())
async def enter_amount_donate(m: Message, value: int):
    form_id = await get_current_form_id(m.from_id)
    balance = await db.select([db.Form.balance]).where(db.Form.id == form_id).gino.scalar()
    if balance < value:
        await m.answer("На балансе недостаточно средств!")
        states.set(m.from_id, Menu.BANK_MENU)
        await m.answer(messages.bank_menu, keyboard=keyboards.bank)
        return
    states.set(m.from_id, f"{Menu.CONFIRM_DONATE}*{value}")
    kb = Keyboard()
    kb.add(Text("Подтвердить", {"donate": "confirm"}), KeyboardButtonColor.POSITIVE)
    kb.add(Text("Отклонить", {"donate": "decline"}), KeyboardButtonColor.NEGATIVE)
    kb.row()
    kb.add(Text("Назад", {"bank_menu": "donate"}), KeyboardButtonColor.NEGATIVE)
    await m.answer(f"Подтверждаете пожертвование в храм в сумме {value}?", keyboard=kb)


@bot.on.private_message(StateRule(Menu.CONFIRM_DONATE, True), PayloadRule({"donate": "confirm"}))
async def confirm_donate(m: Message):
    amount = int(states.get(m.from_id).split("*")[1])
    form_id = await (db.select([db.Form.id]).where(db.Form.user_id == m.from_id).gino.scalar())
    donat_id = await db.select([db.Donate.id]).where(db.Donate.form_id == form_id).gino.scalar()
    if not donat_id:
        await db.Donate.create(amount=amount, form_id=form_id)
    else:
        await db.Donate.update.values(amount=db.Donate.amount + amount).where(
            db.Form.id == form_id
        ).gino.status()
    await db.Form.update.values(balance=db.Form.balance - amount).where(db.Form.id == form_id).gino.status()
    states.set(m.peer_id, Menu.BANK_MENU)
    await m.answer(f"Успешно пожертвовано в храм {amount} монет", keyboard=keyboards.bank)

