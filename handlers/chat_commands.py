import re

from vkbottle.bot import Message
from vkbottle_types.objects import MessagesMessageActionStatus
from vkbottle.dispatch.rules.base import RegexRule
from vkbottle import Keyboard, Callback, KeyboardButtonColor
from vkbottle_types.objects import UtilsDomainResolvedType
from fuzzywuzzy import process

from loader import bot
from service.custom_rules import ChatAction, AdminRule, ChatInviteMember
from service.db_engine import db
from handlers.public_menu.bank import ask_salary
from handlers.public_menu.daylics import send_ready_daylic
from handlers.public_menu.quests import send_ready_quest
from service.utils import move_user, create_mention, get_current_form_id, soft_divide


moving_pattern = re.compile(r'\[перемещение в "([^"]+)"\]', re.IGNORECASE)
donate_pattern = re.compile(r'\[пожертвовать в храм (\d+)\]', re.IGNORECASE)
deal_pattern = re.compile(r"\[совершить сделку \[id(\d+)\|[^\]]+\] (\d+)\]", re.IGNORECASE)
deal_pattern_link = re.compile(r"\[совершить сделку https://vk.com/(\w*) (\d+)\]", re.IGNORECASE)
message_pattern = re.compile(r'\[отправить сообщение \[id(\d+)\|[^\]]+\] "([^"]+)"\]', re.IGNORECASE)
message_pattern_link = re.compile(r'\[отправить сообщение https://vk.com/(\w*) "([^"]+)"\]', re.IGNORECASE)


@bot.on.chat_message(AdminRule(), text='/chat_id')
async def get_peer_id(m: Message):
    await m.answer(str(m.chat_id))


@bot.on.chat_message(ChatAction('заказать коктейль'), blocking=False)
async def order_cocktail(m: Message):
    price = await db.select([db.Shop.price]).where(db.Shop.id == 1).gino.scalar()
    balance = await db.select([db.Form.balance]).where(db.Form.user_id == m.from_id).gino.scalar()
    if balance >= price:
        await db.Form.update.values(balance=db.Form.balance - price).where(db.Form.user_id == m.from_id).gino.status()
        await m.reply('Коктейль успешно заказан')
        return
    await m.reply('Недостаточно средств для оплаты коктейля')


@bot.on.chat_message(ChatAction('заказать премиальный коктейль'), blocking=False)
async def order_premium_cocktail(m: Message):
    price = await db.select([db.Shop.price]).where(db.Shop.id == 2).gino.scalar()
    balance = await db.select([db.Form.balance]).where(db.Form.user_id == m.from_id).gino.scalar()
    if balance >= price:
        await db.Form.update.values(balance=db.Form.balance - price).where(db.Form.user_id == m.from_id).gino.status()
        await m.reply('Премиальный коктейль успешно заказан')
        return
    await m.reply('Недостаточно средств для оплаты премиального коктейля')


@bot.on.chat_message(ChatAction('заказать бутылку дорогого алкоголя'), blocking=False)
async def order_expensive_alcohol(m: Message):
    price = await db.select([db.Shop.price]).where(db.Shop.id == 3).gino.scalar()
    balance = await db.select([db.Form.balance]).where(db.Form.user_id == m.from_id).gino.scalar()
    if balance >= price:
        await db.Form.update.values(balance=db.Form.balance - price).where(db.Form.user_id == m.from_id).gino.status()
        await m.reply('Бутылка дорогого алкоголя успешно оплачена')
        return
    await m.reply('Недостаточно средств для оплаты дорогого алкоголя')


@bot.on.chat_message(ChatAction('запросить зарплату'), blocking=False)
async def ask_salary_command(m: Message):
    return await ask_salary(m)


@bot.on.chat_message(ChatAction('сдать отчёт'), blocking=False)
@bot.on.chat_message(ChatAction('сдать отчет'), blocking=False)
async def ask_salary_command(m: Message):
    daylic = await db.select([db.Form.activated_daylic]).where(db.Form.user_id == m.from_id).gino.scalar()
    if daylic:
        m.payload = {"daylic_ready": daylic}
        await send_ready_daylic(m)
        return
    quest = await db.select([db.Form.active_quest]).where(db.Form.user_id == m.from_id).gino.scalar()
    if quest:
        return await send_ready_quest(m)
    return await m.reply('У вас нет активного дейлика или квеста')


@bot.on.chat_message(RegexRule(deal_pattern), blocking=False)
@bot.on.chat_message(RegexRule(deal_pattern_link), blocking=False)
async def create_transaction(m: Message, match: tuple[str]):
    user_id = match[0]
    if not user_id.isdigit():
        response = await bot.api.utils.resolve_screen_name(user_id)
        if response.type != UtilsDomainResolvedType.USER:
            await m.answer('Указана ссылка не на пользователя!')
            return
        user_id = response.object_id
    else:
        user_id = int(user_id)
    exist = await db.select([db.Form.id]).where(db.Form.user_id == user_id).gino.scalar()
    if not exist:
        await m.answer('У указанного пользователя отсутсвует анкета')
        return
    if user_id == m.from_id:
        await m.answer('Нельзя совершить сделку с самим собой')
        return
    amount = int(match[1])
    if amount <= 0:
        await m.answer('Сделка на отрицательное число? Звучит как накрутка валюты')
        return
    commission = soft_divide(amount, 2)
    tax = 0 if amount <= 25 else 100 + commission
    amount_with_tax = amount + tax
    balance = await db.select([db.Form.balance]).where(db.Form.user_id == user_id).gino.scalar()
    if balance < amount:
        await m.answer('Недостаточно средств на балансе!\n'
                       f'Сумма с учетом коммиссии: {amount_with_tax}\n'
                       f'Доступно на счете: {balance}')
        return
    await db.Form.update.values(balance=db.Form.balance - amount_with_tax).where(db.Form.user_id == m.from_id).gino.status()
    await db.Form.update.values(balance=db.Form.balance + amount).where(db.Form.user_id == user_id).gino.status()
    from_user = await get_current_form_id(m.from_id)
    to_user = await get_current_form_id(user_id)
    await db.Transactions.create(from_user=from_user, to_user=to_user, amount=amount)
    await m.answer(f'Успешно отправлено {amount} валюты пользователю {await create_mention(user_id)}')


@bot.on.chat_message(RegexRule(donate_pattern), blocking=False)
async def create_donate_command(m: Message, match: tuple[str]):
    amount = int(match[0])
    form_id = await get_current_form_id(m.from_id)
    balance = await db.select([db.Form.balance]).where(db.Form.id == form_id).gino.scalar()
    if amount <= 0:
        await m.answer('Пожертвовать в храм отрицательное число? Звучит как накрутка валюты')
        return
    if balance < amount:
        await m.answer('На балансе недостаточно средств!\n'
                       f'Баланс: {balance}')
        return
    await db.Form.update.values(balance=db.Form.balance - amount).where(db.Form.id == form_id).gino.status()
    await db.Donate.create(form_id=form_id, amount=amount)
    await m.answer(f'Вы успешно пожертвовали в храм {amount} валюты')


@bot.on.chat_message(ChatInviteMember())
async def test(m: Message, member_id: int):
    if m.action.type == MessagesMessageActionStatus.CHAT_INVITE_USER:
        member_id = m.action.member_id
    elif m.action.type == MessagesMessageActionStatus.CHAT_INVITE_USER_BY_LINK:
        member_id = m.from_id
    else:
        return
    if member_id < 0:
        return
    chat_allowed = await db.select([db.UserToChat.chat_id]).where(db.UserToChat.user_id == member_id).gino.scalar()
    if not chat_allowed or m.chat_id != chat_allowed:
        await bot.api.request('messages.changeConversationMemberRestrictions',
                          {'peer_id': m.peer_id, 'member_ids': member_id, 'action': 'ro'})


@bot.on.message(RegexRule(moving_pattern))
async def move_to_location(m: Message, match: tuple[str]):
    find_name = match[0]
    peer_ids = [2000000000 + x[0] for x in await db.select([db.Chat.chat_id]).gino.all()]
    chat_names = [x.chat_settings.title.lower() for x in (await bot.api.messages.get_conversations_by_id(peer_ids=peer_ids)).items]
    extract = process.extractOne(find_name, chat_names)
    if not extract:
        await m.answer('Не удалось найти подходящий чат')
        return
    chat_name = extract[0]
    chat_id = peer_ids[chat_names.index(chat_name)] - 2000000000
    is_private = await db.select([db.Chat.is_private]).where(db.Chat.chat_id == chat_id).gino.scalar()
    if is_private:
        owner_cabin = await db.select([db.Chat.cabin_user_id]).where(db.Chat.chat_id == chat_id).gino.scalar()
        if owner_cabin and owner_cabin != m.from_id:
            admin_ids = [owner_cabin]
        else:
            profession_ids = [x[0] for x in await db.select([db.ChatToProfessions.profession_id]).where(db.ChatToProfessions.chat_id == chat_id).gino.all()]
            profession_id = await db.select([db.Form.profession]).where(db.Form.user_id == m.from_id).gino.scalar()
            if profession_id in profession_ids:
                await move_user(m.from_id, chat_id)
                return
            admin_ids = [x[0] for x in await db.select([db.Form.user_id]).where(db.Form.profession.in_(profession_ids)).gino.all()]
        for admin_id in admin_ids:
            request = await db.ChatRequest.create(chat_id=chat_id, admin_id=admin_id, user_id=m.from_id)
            reply = f'Пользователь {await create_mention(m.from_id)} запрашивает доступ в чат «{chat_name}»'
            keyboard = Keyboard(inline=True).add(
                Callback('Разрешить', {'chat_action': 'accept', 'request_id': request.id}), KeyboardButtonColor.POSITIVE
            ).row().add(
                Callback('Отклонить', {'chat_action': 'accept', 'request_id': request.id}), KeyboardButtonColor.NEGATIVE
            )
            message = (await bot.api.messages.send(peer_id=admin_id, message=reply, keyboard=keyboard))[0]
            await db.ChatRequest.update.values(message_id=message.conversation_message_id).where(db.ChatRequest.id == request.id).gino.status()
            await m.answer(f'Запрос на перемещение в чат «{chat_name}» успешно отправлен')
            return
    await move_user(m.from_id, chat_id)


@bot.on.message(RegexRule(message_pattern))
@bot.on.message(RegexRule(message_pattern_link))
async def transmitter(m: Message, match: tuple[str]):
    user_id, message = match
    if not user_id.isdigit():
        response = await bot.api.utils.resolve_screen_name(user_id)
        if response.type != UtilsDomainResolvedType.USER:
            await m.answer('Указана ссылка не на пользователя!')
            return
        user_id = response.object_id
    else:
        user_id = int(user_id)
    exist = await db.select([db.Form.id]).where(db.Form.user_id == user_id).gino.scalar()
    if not exist:
        await m.answer('У указанного пользователя отсутсвует анкета')
        return
    message = (f'Новое сообщение от пользователя {await create_mention(m.from_id)}:\n'
               f'«{message}»')
    await bot.api.messages.send(peer_id=user_id, message=message)
    await m.answer('Сообщение успешно отправлено')

