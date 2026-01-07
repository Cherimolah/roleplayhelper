"""
Модуль обработки команд в чатах.
Содержит обработчики для покупок, переводов, перемещений
и других действий, доступных в групповых беседах.
"""

import re

from vkbottle.bot import Message
from vkbottle import Keyboard, Callback, KeyboardButtonColor
from vkbottle_types.objects import UtilsDomainResolvedType
from fuzzywuzzy import process

from loader import bot
from service.custom_rules import ChatAction, AdminRule, ChatInviteMember, RegexRule
from service.db_engine import db
from handlers.public_menu.bank import ask_salary
from handlers.public_menu.daylics import send_ready_daylic
from handlers.public_menu.quests import send_ready_quest
from service.utils import move_user, create_mention, get_current_form_id, soft_divide
from config import HALL_CHAT_ID

# Регулярные выражения для обработки команд
moving_pattern = re.compile(r'\[\s*перемещение в "(.+)"\s*\]', re.IGNORECASE)
moving_pattern2 = re.compile(r'\[\s*перемещение в (.+)\s*\]', re.IGNORECASE)
donate_pattern = re.compile(r'\[пожертвовать в храм (\d+)\]', re.IGNORECASE)
deal_pattern = re.compile(r"\[совершить сделку \[id(\d+)\|[^\]]+\] (\d+)\]", re.IGNORECASE)
deal_pattern_link = re.compile(r"\[совершить сделку https://vk.com/(\w*) (\d+)\]", re.IGNORECASE)
message_pattern = re.compile(r'\[отправить сообщение \[id(\d+)\|[^\]]+\] "(.+)"\]', re.IGNORECASE)
message_pattern_link = re.compile(r'\[отправить сообщение https://vk.com/(\w*) "(.+)"\]', re.IGNORECASE)


@bot.on.chat_message(AdminRule(), text='/chat_id')
async def get_peer_id(m: Message):
    """Получение ID чата (только для администраторов)"""
    await m.answer(str(m.chat_id))


@bot.on.chat_message(ChatAction('заказать коктейль'), blocking=False)
@bot.on.chat_message(ChatAction('взять коктейль'), blocking=False)
@bot.on.chat_message(ChatAction('купить коктейль'), blocking=False)
@bot.on.chat_message(ChatAction('налей коктейль'), blocking=False)
@bot.on.chat_message(ChatAction('хочу коктейль'), blocking=False)
@bot.on.chat_message(ChatAction('заказать напиток'), blocking=False)
@bot.on.chat_message(ChatAction('сделай коктейль'), blocking=False)
async def order_cocktail(m: Message):
    """
    Заказ обычного коктейля в баре

    Args:
        m: Сообщение с командой заказа
    """
    price = await db.select([db.Shop.price]).where(db.Shop.id == 1).gino.scalar()
    balance = await db.select([db.Form.balance]).where(db.Form.user_id == m.from_id).gino.scalar()
    if balance >= price:
        await db.Form.update.values(balance=db.Form.balance - price).where(db.Form.user_id == m.from_id).gino.status()
        await m.reply('Коктейль успешно заказан')
        return
    await m.reply('Недостаточно средств для оплаты коктейля')


@bot.on.chat_message(ChatAction('заказать премиальный коктейль'), blocking=False)
@bot.on.chat_message(ChatAction('премиум коктейль'), blocking=False)
@bot.on.chat_message(ChatAction('взять дорогой коктейль'), blocking=False)
@bot.on.chat_message(ChatAction('купить премиальный коктейль'), blocking=False)
@bot.on.chat_message(ChatAction('хочу премиальный напиток'), blocking=False)
@bot.on.chat_message(ChatAction('заказать элитный коктейль'), blocking=False)
@bot.on.chat_message(ChatAction('элитный коктейль'), blocking=False)
async def order_premium_cocktail(m: Message):
    """
    Заказ премиального коктейля в баре

    Args:
        m: Сообщение с командой заказа
    """
    price = await db.select([db.Shop.price]).where(db.Shop.id == 2).gino.scalar()
    balance = await db.select([db.Form.balance]).where(db.Form.user_id == m.from_id).gino.scalar()
    if balance >= price:
        await db.Form.update.values(balance=db.Form.balance - price).where(db.Form.user_id == m.from_id).gino.status()
        await m.reply('Премиальный коктейль успешно заказан')
        return
    await m.reply('Недостаточно средств для оплаты премиального коктейля')


@bot.on.chat_message(ChatAction('заказать бутылку дорогого алкоголя'), blocking=False)
@bot.on.chat_message(ChatAction('купить дорогую бутылку'), blocking=False)
@bot.on.chat_message(ChatAction('взять алкоголь'), blocking=False)
@bot.on.chat_message(ChatAction('хочу алкоголь'), blocking=False)
@bot.on.chat_message(ChatAction('заказать бутылку'), blocking=False)
@bot.on.chat_message(ChatAction('заказать элитный алкоголь'), blocking=False)
@bot.on.chat_message(ChatAction('купить дорогой алкоголь'), blocking=False)
async def order_expensive_alcohol(m: Message):
    """
    Заказ бутылки дорогого алкоголя в баре

    Args:
        m: Сообщение с командой заказа
    """
    price = await db.select([db.Shop.price]).where(db.Shop.id == 3).gino.scalar()
    balance = await db.select([db.Form.balance]).where(db.Form.user_id == m.from_id).gino.scalar()
    if balance >= price:
        await db.Form.update.values(balance=db.Form.balance - price).where(db.Form.user_id == m.from_id).gino.status()
        await m.reply('Бутылка дорогого алкоголя успешно оплачена')
        return
    await m.reply('Недостаточно средств для оплаты дорогого алкоголя')


@bot.on.chat_message(ChatAction('запросить сверхурочные'), blocking=False)
@bot.on.chat_message(ChatAction('получить сверхурочные'), blocking=False)
@bot.on.chat_message(ChatAction('выдать сверхурочные'), blocking=False)
@bot.on.chat_message(ChatAction('хочу сверхурочные'), blocking=False)
@bot.on.chat_message(ChatAction('сверхурочные'), blocking=False)
@bot.on.chat_message(ChatAction('начислить сверхурочные'), blocking=False)
@bot.on.chat_message(ChatAction('дай деньги'), blocking=False)
async def ask_salary_command(m: Message):
    """Запрос выплаты зарплаты"""
    return await ask_salary(m)


@bot.on.chat_message(ChatAction('сдать отчёт'), blocking=False)
@bot.on.chat_message(ChatAction('отчет готов'), blocking=False)
@bot.on.chat_message(ChatAction('отправить отчет'), blocking=False)
@bot.on.chat_message(ChatAction('вот отчет'), blocking=False)
@bot.on.chat_message(ChatAction('выполнить отчет'), blocking=False)
@bot.on.chat_message(ChatAction('закончить отчет'), blocking=False)
@bot.on.chat_message(ChatAction('сдать еженедельник'), blocking=False)
async def ask_salary_command(m: Message):
    """
    Сдача отчета о выполнении дейлика или квеста

    Args:
        m: Сообщение с командой сдачи отчета
    """
    daylic = await db.select([db.Form.activated_daylic]).where(db.Form.user_id == m.from_id).gino.scalar()
    if daylic:
        m.payload = {"daylic_ready": daylic}
        await send_ready_daylic(m)
        return
    quest = await db.select([db.Form.active_quest]).where(db.Form.user_id == m.from_id).gino.scalar()
    if quest:
        return await send_ready_quest(m)
    return await m.reply('У вас нет активного еженедельника или квеста')


@bot.on.chat_message(RegexRule(deal_pattern), blocking=False)
@bot.on.chat_message(RegexRule(deal_pattern_link), blocking=False)
@bot.on.chat_message(RegexRule(re.compile(r"\[перевести деньги https://vk.com/(\w*) (\d+)\]", re.IGNORECASE)), blocking=False)
@bot.on.chat_message(RegexRule(re.compile(r"\[отправить деньги https://vk.com/(\w*) (\d+)\]", re.IGNORECASE)), blocking=False)
@bot.on.chat_message(RegexRule(re.compile(r"\[перевести валюту https://vk.com/(\w*) (\d+)\]", re.IGNORECASE)), blocking=False)
@bot.on.chat_message(RegexRule(re.compile(r"\[сделка с https://vk.com/(\w*) (\d+)\]", re.IGNORECASE)), blocking=False)
@bot.on.chat_message(RegexRule(re.compile(r"\[передать деньги https://vk.com/(\w*) (\d+)\]", re.IGNORECASE)), blocking=False)
@bot.on.chat_message(RegexRule(re.compile(r"\[отдать сумму https://vk.com/(\w*) (\d+)\]", re.IGNORECASE)), blocking=False)
@bot.on.chat_message(RegexRule(re.compile(r"\[перечислить сумму https://vk.com/(\w*) (\d+)\]", re.IGNORECASE)), blocking=False)
@bot.on.chat_message(RegexRule(re.compile(r"\[перевести деньги \[id(\d+)\|[^\]]+\] (\d+)\]", re.IGNORECASE)), blocking=False)
@bot.on.chat_message(RegexRule(re.compile(r"\[отправить деньги \[id(\d+)\|[^\]]+\] (\d+)\]", re.IGNORECASE)), blocking=False)
@bot.on.chat_message(RegexRule(re.compile(r"\[сделка с \[id(\d+)\|[^\]]+\] (\d+)\]", re.IGNORECASE)), blocking=False)
@bot.on.chat_message(RegexRule(re.compile(r"\[передать деньги \[id(\d+)\|[^\]]+\] (\d+)\]", re.IGNORECASE)), blocking=False)
@bot.on.chat_message(RegexRule(re.compile(r"\[отдать сумму \[id(\d+)\|[^\]]+\] (\d+)\]", re.IGNORECASE)), blocking=False)
@bot.on.chat_message(RegexRule(re.compile(r"\[перечислить сумму \[id(\d+)\|[^\]]+\] (\d+)\]", re.IGNORECASE)), blocking=False)
@bot.on.chat_message(RegexRule(re.compile(r"\[перевести валюту \[id(\d+)\|[^\]]+\] (\d+)\]", re.IGNORECASE)), blocking=False)
async def create_transaction(m: Message, match: tuple[str]):
    """
    Создание транзакции между пользователями

    Args:
        m: Сообщение с командой перевода
        match: Результат匹配 регулярного выражения (ID пользователя и сумма)
    """
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
@bot.on.chat_message(RegexRule(re.compile(r'\[отдать в храм (\d+)\]', re.IGNORECASE)), blocking=False)
@bot.on.chat_message(RegexRule(re.compile(r'\[внести пожертвование (\d+)\]', re.IGNORECASE)), blocking=False)
@bot.on.chat_message(RegexRule(re.compile(r'\[жертва храму (\d+)\]', re.IGNORECASE)), blocking=False)
@bot.on.chat_message(RegexRule(re.compile(r'\[подношение храму (\d+)\]', re.IGNORECASE)), blocking=False)
@bot.on.chat_message(RegexRule(re.compile(r'\[сделать пожертвование (\d+)\]', re.IGNORECASE)), blocking=False)
@bot.on.chat_message(RegexRule(re.compile(r'\[отдать сумму в храм (\d+)\]', re.IGNORECASE)), blocking=False)
async def create_donate_command(m: Message, match: tuple[str]):
    """
    Создание пожертвования в храм

    Args:
        m: Сообщение с командой пожертвования
        match: Результат匹配 регулярного выражения (сумма пожертвования)
    """
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
    """
    Обработка приглашения новых участников в чат

    Args:
        m: Сообщение с событием приглашения
        member_id: ID приглашенного пользователя
    """
    if member_id < 0:
        return
    chat_allowed = await db.select([db.UserToChat.chat_id]).where(db.UserToChat.user_id == member_id).gino.scalar()
    if not chat_allowed or m.chat_id != chat_allowed:
        await bot.api.request('messages.changeConversationMemberRestrictions',
                              {'peer_id': m.peer_id, 'member_ids': member_id, 'action': 'ro'})


@bot.on.message(RegexRule(moving_pattern))
@bot.on.message(RegexRule(moving_pattern2))
@bot.on.message(RegexRule(re.compile(r'\[\s*переместиться в (.+)\s*\]', re.IGNORECASE)))
@bot.on.message(RegexRule(re.compile(r'\[\s*перейти в (.+)\s*\]', re.IGNORECASE)))
@bot.on.message(RegexRule(re.compile(r'\[\s*идти в (.+)\s*\]', re.IGNORECASE)))
@bot.on.message(RegexRule(re.compile(r'\[\s*отправиться в (.+)\s*\]', re.IGNORECASE)))
@bot.on.message(RegexRule(re.compile(r'\[\s*телепорт в (.+)\s*\]', re.IGNORECASE)))
@bot.on.message(RegexRule(re.compile(r'\[\s*хочу в (.+)\s*\]', re.IGNORECASE)))
@bot.on.message(RegexRule(re.compile(r'\[\s*локация (.+)\s*\]', re.IGNORECASE)))
async def move_to_location(m: Message, match: tuple[str]):
    """
    Перемещение пользователя между чатами-локациями

    Args:
        m: Сообщение с командой перемещения
        match: Результат匹配 регулярного выражения (название локации)
    """
    find_name = match[0]
    if find_name.lower().startswith('каюта ') or find_name.lower().startswith('каюту '):  # Алиас для написания каюты
        try:
            number = int(find_name[6:])
        except ValueError:
            await m.answer('Неверный номер каюты')
            return
        user_id = await db.select([db.Form.user_id]).where(db.Form.cabin == number).gino.scalar()
        chat_id = await db.select([db.Chat.chat_id]).where(db.Chat.cabin_user_id == user_id).gino.scalar()
    elif find_name.lower() == 'холл':  # Алиас для холла
        chat_id = HALL_CHAT_ID
    else:
        peer_ids = [2000000000 + x[0] for x in await db.select([db.Chat.chat_id]).gino.all() if x[0] is not None]
        chat_names = [(x.chat_settings.title.lower(), x.peer.id) for x in
                      (await bot.api.messages.get_conversations_by_id(peer_ids=peer_ids)).items]
        for chat_name, peer_id in chat_names:
            if chat_name == find_name.lower():
                chat_id = peer_id - 2000000000
                break
        else:
            extract = process.extractOne(find_name, chat_names)
            if not extract:
                await m.answer('Не удалось найти подходящий чат')
                return
            chat_name = extract[0]
            chat_id = peer_ids[chat_names.index(chat_name)] - 2000000000
    chat_name = (await bot.api.messages.get_conversations_by_id(peer_ids=[2000000000 + chat_id])).items[
        0].chat_settings.title
    is_private = await db.select([db.Chat.is_private]).where(db.Chat.chat_id == chat_id).gino.scalar()
    if is_private:
        owner_cabin = await db.select([db.Chat.cabin_user_id]).where(db.Chat.chat_id == chat_id).gino.scalar()
        if owner_cabin and owner_cabin != m.from_id:
            admin_ids = [owner_cabin]
        else:
            profession_ids = [x[0] for x in await db.select([db.ChatToProfessions.profession_id]).where(
                db.ChatToProfessions.chat_id == chat_id).gino.all()]
            profession_id = await db.select([db.Form.profession]).where(db.Form.user_id == m.from_id).gino.scalar()
            if profession_id in profession_ids:
                await move_user(m.from_id, chat_id)
                return
            admin_ids = [x[0] for x in
                         await db.select([db.Form.user_id]).where(db.Form.profession.in_(profession_ids)).gino.all()]
        for admin_id in admin_ids:
            request = await db.ChatRequest.create(chat_id=chat_id, admin_id=admin_id, user_id=m.from_id)
            reply = f'Пользователь {await create_mention(m.from_id)} запрашивает доступ в чат «{chat_name}»'
            keyboard = Keyboard(inline=True).add(
                Callback('Разрешить', {'chat_action': 'accept', 'request_id': request.id}), KeyboardButtonColor.POSITIVE
            ).row().add(
                Callback('Отклонить', {'chat_action': 'decline', 'request_id': request.id}),
                KeyboardButtonColor.NEGATIVE
            )
            message = (await bot.api.messages.send(peer_id=admin_id, message=reply, keyboard=keyboard))[0]
            await db.ChatRequest.update.values(message_id=message.conversation_message_id).where(
                db.ChatRequest.id == request.id).gino.status()
            await m.answer(f'Запрос на перемещение в чат «{chat_name}» успешно отправлен')
            return
    await move_user(m.from_id, chat_id)


@bot.on.message(RegexRule(message_pattern))
@bot.on.message(RegexRule(message_pattern_link))
@bot.on.message(RegexRule(re.compile(r'\[написать сообщение \[id(\d+)\|[^\]]+\] "(.+)"\]', re.IGNORECASE)))
@bot.on.message(RegexRule(re.compile(r'\[написать \[id(\d+)\|[^\]]+\] "(.+)"\]', re.IGNORECASE)))
@bot.on.message(RegexRule(re.compile(r'\[сказать \[id(\d+)\|[^\]]+\] "(.+)"\]', re.IGNORECASE)))
@bot.on.message(RegexRule(re.compile(r'\[отправь текст \[id(\d+)\|[^\]]+\] "(.+)"\]', re.IGNORECASE)))
@bot.on.message(RegexRule(re.compile(r'\[сообщение для \[id(\d+)\|[^\]]+\] "(.+)"\]', re.IGNORECASE)))
@bot.on.message(RegexRule(re.compile(r'\[передать сообщение \[id(\d+)\|[^\]]+\] "(.+)"\]', re.IGNORECASE)))
@bot.on.message(RegexRule(re.compile(r'\[написать сообщение https://vk.com/(\w*) "(.+)"\]', re.IGNORECASE)))
@bot.on.message(RegexRule(re.compile(r'\[написать https://vk.com/(\w*) "(.+)"\]', re.IGNORECASE)))
@bot.on.message(RegexRule(re.compile(r'\[сказать https://vk.com/(\w*) "(.+)"\]', re.IGNORECASE)))
@bot.on.message(RegexRule(re.compile(r'\[отправь текст https://vk.com/(\w*) "(.+)"\]', re.IGNORECASE)))
@bot.on.message(RegexRule(re.compile(r'\[сообщение для https://vk.com/(\w*) "(.+)"\]', re.IGNORECASE)))
@bot.on.message(RegexRule(re.compile(r'\[передать сообщение https://vk.com/(\w*) "(.+)"\]', re.IGNORECASE)))
async def transmitter(m: Message, match: tuple[str, str]):
    """
    Отправка приватного сообщения другому пользователю через бота

    Args:
        m: Сообщение с командой отправки
        match: Результат регулярного выражения (ID пользователя и текст сообщения)
    """
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
        await m.answer('У указанного пользователя отсутствует анкета')
        return
    message = (f'Новое сообщение от пользователя {await create_mention(m.from_id)}:\n'
               f'«{message}»')
    await bot.api.messages.send(peer_id=user_id, message=message)
    await m.answer('Сообщение успешно отправлено')
    
async def handle_chat_message(m: Message):
    
    users_in_first_person = await db.FirstPersonMode.query.where(
        db.FirstPersonMode.is_active == True
    ).gino.all()
    
    for user_mode in users_in_first_person:
        user = await db.User.query.where(db.User.vk_id == user_mode.user_id).gino.first()
        if user and user.current_chat_id == chat_id:
            # Пользователь в этом чате и в режиме от первого лица
            # Применяем эффекты к тексту
            processed_text = await apply_text_effects(
                m.text, 
                user_mode.user_id,
                db
            )
            
            # Отправляем обработанное сообщение пользователю
            await bot.api.messages.send(
                user_id=user_mode.user_id,
                message=f"📍 {chat.name} | От {sender_name}:\n\n{processed_text}",
                random_id=0
            )
        
