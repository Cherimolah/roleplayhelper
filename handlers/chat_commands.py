"""
Модуль обработки команд в чатах.
Содержит обработчики для покупок, переводов, перемещений
и других действий, доступных в групповых беседах.
"""

import re
import random

from vkbottle.bot import Message
from vkbottle import Keyboard, Callback, KeyboardButtonColor, VKAPIError
from vkbottle.dispatch.rules.abc import OrRule
from vkbottle_types.objects import UtilsDomainResolvedType
from fuzzywuzzy import process

<<<<<<< Updated upstream
from loader import bot
from service.custom_rules import ChatAction, AdminRule, ChatInviteMember, RegexRule, ForwardablePostRule
from service.db_engine import db
from handlers.public_menu.bank import ask_salary
from handlers.public_menu.daylics import send_ready_daylic
from handlers.public_menu.quests import send_ready_quest
from service.utils import move_user, create_mention, get_current_form_id, soft_divide
from service.text_processors import apply_text_effects, is_forwardable_post
from config import HALL_CHAT_ID
=======
from loader import bot, states
from service.custom_rules import ChatAction, AdminRule, JudgeRule, OwnerRule, ChatInviteMember, RegexRule, ForwardablePostRule
from service.db_engine import db, Attribute, now
from handlers.public_menu.bank import ask_salary
from handlers.public_menu.daylics import send_ready_daylic
from handlers.public_menu.quests import send_ready_quest
from service.utils import move_user, create_mention, get_current_form_id, soft_divide, count_attribute, can_view_classified
from service.text_processors import apply_text_effects, is_forwardable_post
from service.states import Admin
from service.serializers import info_target_reward
from service.auctions import place_bid, eligible_closed_auction_ids
from config import HALL_CHAT_ID, USER_ID, ADMINS, DATETIME_FORMAT

# Пост, переотправленный Юзерботом от лица игрока в его локацию (см. handlers/first_person_userbot.py)
pov_relay_label_pattern = re.compile(r'^\[id(\d+)\|([^\]]*)\]:\n([\s\S]*)$')
>>>>>>> Stashed changes

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
<<<<<<< Updated upstream
    
@bot.on.chat_message(ForwardablePostRule(), blocking=False)
async def handle_chat_message(m: Message):
    """
    Пересылка сообщений игрокам в режиме от первого лица (POV).
    """
    if not m.text or not m.from_id:
        return

=======


# Расширение команды "Сообщения": массовая отправка + интеграция с механикой "засекречено" (module admin_improvements, п.6)
mass_message_pattern = re.compile(r'\[\s*сообщения\s+(.+?)\s+"(.+)"(\s*засекречено)?\s*\]', re.IGNORECASE)


@bot.on.message(RegexRule(mass_message_pattern))
async def mass_transmitter(m: Message, match: tuple):
    """
    [сообщения [id1|Имя1], [id2|Имя2] "текст"] — отправка одного сообщения нескольким адресатам сразу.
    С флагом "засекречено" в конце команды сообщение доставляется только тем получателям, у которых
    есть допуск к секретным блокам анкеты отправителя (см. module classified_profiles /
    service.utils.can_view_classified) — остальные получают только уведомление о том, что письмо пришло.
    """
    mentions_part, text, secret_flag = match
    target_ids = [int(x) for x in mention_extract_pattern.findall(mentions_part)]
    if not target_ids:
        await m.answer('Не указаны получатели (укажите упоминания через @)')
        return

    is_secret = bool(secret_flag)
    sender_form = await db.select([*db.Form]).where(db.Form.user_id == m.from_id).gino.first() if is_secret else None
    sender_mention = await create_mention(m.from_id)

    sent = 0
    for user_id in target_ids:
        exist = await db.select([db.Form.id]).where(db.Form.user_id == user_id).gino.scalar()
        if not exist:
            continue
        if is_secret and sender_form:
            cleared = await can_view_classified(sender_form, user_id)
            if not cleared:
                await bot.api.messages.send(
                    peer_id=user_id,
                    message=f'🔒 Вам пришло засекреченное сообщение от {sender_mention}, '
                            f'но у вас нет допуска к его содержимому.',
                    random_id=0,
                )
                sent += 1
                continue
            message = f'🔒 Засекреченное сообщение от {sender_mention}:\n«{text}»'
        else:
            message = f'Новое сообщение от пользователя {sender_mention}:\n«{text}»'
        await bot.api.messages.send(peer_id=user_id, message=message, random_id=0)
        sent += 1

    await m.answer(f'Сообщение отправлено {sent} из {len(target_ids)} получателей')
    
@bot.on.chat_message(ForwardablePostRule(), blocking=False)
async def handle_chat_message(m: Message):
    """
    Пересылка сообщений игрокам в режиме от первого лица (POV).
    """
    if not m.text or not m.from_id:
        return

>>>>>>> Stashed changes
    # На всякий случай оставляем быстрый гард (правило уже фильтрует)
    if not is_forwardable_post(m.text):
        return

    chat_id = m.chat_id
    if not chat_id:
        return

    # Получаем имя чата (для шапки)
    try:
        chat_title = (
            await bot.api.messages.get_conversations_by_id(peer_ids=[2000000000 + chat_id])
        ).items[0].chat_settings.title
    except Exception:
        chat_title = f"чат {chat_id}"

<<<<<<< Updated upstream
    # Имя отправителя
    try:
        sender = (await bot.api.users.get([m.from_id]))[0]
        sender_name = f"{sender.first_name} {sender.last_name}"
    except Exception:
        sender_name = str(m.from_id)

    # Ищем всех POV-игроков, которые "находятся" в этой же локации
=======
    # Если сообщение переслано Юзерботом от лица POV-игрока (см. handlers/first_person_userbot.py),
    # настоящий автор поста и текст поста находятся внутри метки "[id..|Имя]:\n...", а не в m.from_id
    author_id = m.from_id
    body_text = m.text
    if m.from_id == USER_ID:
        relay_match = pov_relay_label_pattern.match(m.text)
        if not relay_match:
            return
        author_id = int(relay_match.group(1))
        sender_name = relay_match.group(2).strip() or str(author_id)
        body_text = relay_match.group(3)
    else:
        # Имя отправителя
        try:
            sender = (await bot.api.users.get([m.from_id]))[0]
            sender_name = f"{sender.first_name} {sender.last_name}"
        except Exception:
            sender_name = str(m.from_id)

    # Ищем всех POV-игроков, которые "находятся" в этой же локации (кроме автора поста)
>>>>>>> Stashed changes
    pov_users = await (
        db.select([db.FirstPersonMode.user_id])
        .select_from(db.FirstPersonMode.join(db.UserToChat, db.UserToChat.user_id == db.FirstPersonMode.user_id))
        .where((db.FirstPersonMode.is_active == True) & (db.UserToChat.chat_id == chat_id))
        .gino.all()
    )
<<<<<<< Updated upstream
    pov_user_ids = [x[0] for x in pov_users if x and x[0] != m.from_id]
=======
    pov_user_ids = [x[0] for x in pov_users if x and x[0] != author_id]
>>>>>>> Stashed changes
    if not pov_user_ids:
        return

    for receiver_id in pov_user_ids:
<<<<<<< Updated upstream
        processed = await apply_text_effects(m.text, user_id=receiver_id, db=db)
=======
        processed = await apply_text_effects(body_text, user_id=receiver_id, db=db)
>>>>>>> Stashed changes

        header = f"📍 {chat_title}\n"
        if not processed.get("remove_sender"):
            header += f"От: {sender_name}\n\n"
        else:
            header += "\n"

        await bot.api.messages.send(
            user_id=receiver_id,
            message=header + processed["text"],
            random_id=0,
            is_notification=True,
        )
<<<<<<< Updated upstream
=======


# Команды скрытного действия (sub_module stealth_mode)
stealth_pattern = re.compile(r'\[скрытно "(.+)"\]', re.IGNORECASE)
stealth_pattern2 = re.compile(r'\[скрытное действие "(.+)"\]', re.IGNORECASE)


async def _has_confirmed_expeditor(user_id: int) -> bool:
    form_id = await get_current_form_id(user_id)
    if not form_id:
        return False
    confirmed = await db.select([db.Expeditor.is_confirmed]).where(db.Expeditor.form_id == form_id).gino.scalar()
    return bool(confirmed)


@bot.on.chat_message(RegexRule(stealth_pattern))
@bot.on.chat_message(RegexRule(stealth_pattern2))
async def stealth_action(m: Message, match: tuple[str]):
    """
    Скрытное действие: соревновательная проверка Ловкости автора против лучшего
    Восприятия остальных участников локации.

    Провал — действие пересылается в чат как обычное сообщение (сокрытие отменяется).
    Успех — действие не показывается игрокам, а логируется и отправляется только
    судьям/администраторам (автор, дата/время, локация).
    """
    text = match[0]
    chat_id = m.chat_id
    if not chat_id:
        return

    # Прячем исходное сообщение из чата — иначе его уже увидят все участники
    try:
        await bot.api.messages.delete(cmids=[m.conversation_message_id], peer_id=m.peer_id, delete_for_all=True)
    except VKAPIError:
        pass

    if not await _has_confirmed_expeditor(m.from_id):
        await bot.api.messages.send(
            peer_id=m.from_id,
            message='Для скрытных действий необходима подтверждённая Карта экспедитора',
            random_id=0,
        )
        return

    attacker_roll = await count_attribute(m.from_id, Attribute.DEXTERITY) + random.randint(1, 100)

    other_user_ids = [x[0] for x in await db.select([db.UserToChat.user_id]).where(
        (db.UserToChat.chat_id == chat_id) & (db.UserToChat.user_id != m.from_id)
    ).gino.all()]

    best_defender_roll = 0
    for user_id in other_user_ids:
        if not await _has_confirmed_expeditor(user_id):
            continue
        roll = await count_attribute(user_id, Attribute.PERCEPTION) + random.randint(1, 100)
        best_defender_roll = max(best_defender_roll, roll)

    success = attacker_roll > best_defender_roll
    await db.StealthLog.create(user_id=m.from_id, chat_id=chat_id, text=text, success=success)

    if not success:
        mention = await create_mention(m.from_id)
        await bot.api.messages.send(peer_id=m.peer_id, message=f'{mention}: {text}', random_id=0)
        await bot.api.messages.send(
            peer_id=m.from_id,
            message='Скрытное действие провалено — оно замечено остальными и переслано в чат как обычное',
            random_id=0,
            is_notification=True,
        )
        return

    await bot.api.messages.send(
        peer_id=m.from_id,
        message='Скрытное действие выполнено незаметно для остальных',
        random_id=0,
        is_notification=True,
    )

    chat_name = (await bot.api.messages.get_conversations_by_id(peer_ids=[2000000000 + chat_id])).items[0].chat_settings.title
    mention = await create_mention(m.from_id)
    staff_ids = list(set(
        [x[0] for x in await db.select([db.User.user_id]).where(
            (db.User.admin > 0) | (db.User.judge.is_(True))
        ).gino.all()]
    ).union(ADMINS))
    report = (f'🕵️ Скрытное действие\nАвтор: {mention}\nЛокация: «{chat_name}»\n'
              f'Дата: {now().strftime(DATETIME_FORMAT)}\nДействие: «{text}»')
    for i in range(0, len(staff_ids), 100):
        await bot.api.messages.send(peer_ids=staff_ids[i:i + 100], message=report, random_id=0, is_notification=True)


# Административный инструмент принудительного перемещения (module admin_improvements, п.1)
forced_move_pattern = re.compile(r'\[\s*принудительное перемещение(.+)\]', re.IGNORECASE)
mention_extract_pattern = re.compile(r'\[id(\d+)\|[^\]]+\]')


@bot.on.chat_message(RegexRule(forced_move_pattern), OrRule(AdminRule(), JudgeRule()))
async def forced_movement(m: Message, match: tuple[str]):
    """
    [принудительное перемещение @тег1 @тег2] — доступно только админам/судьям: мгновенно
    перемещает указанных игроков в чат, где написана команда.

    Если тот же текст пишет обычный игрок во время своего поста в активном экшен-режиме,
    правило AdminRule/JudgeRule не пропустит его сюда — вместо этого пост целиком уже
    обрабатывается стандартным парсером экшен-режима (service.utils.parse_actions) как
    обычное действие, требующее проверки судьи (см. handlers/action_mode/checking.py).
    После проверки судья, уже обладая нужными правами, может выполнить перемещение этой
    же командой.
    """
    target_ids = [int(x) for x in mention_extract_pattern.findall(match[0])]
    if not target_ids:
        await m.answer('Не указаны игроки для перемещения (укажите упоминания через @)')
        return
    chat_id = m.chat_id
    moved = []
    for user_id in target_ids:
        exist = await db.select([db.Form.id]).where(db.Form.user_id == user_id).gino.scalar()
        if not exist:
            continue
        await move_user(user_id, chat_id)
        moved.append(user_id)
    if not moved:
        await m.answer('Не удалось найти анкеты указанных игроков')
        return
    mentions = ', '.join([await create_mention(x) for x in moved])
    await m.answer(f'Принудительно перемещены в этот чат: {mentions}')


# Команды задач (module admin_improvements, п.9 и п.10). Обе запускают тот же пошаговый
# мастер настройки квеста, что и "Изменение контента -> Квесты" в админ-панели
# (handlers/admin_panel/edit_content/quests.py), продолжающийся уже в личных сообщениях бота.
force_task_pattern = re.compile(r'\[\s*выдать задачу\s+([^"]+?)\s*"(.+)"\s*\]', re.IGNORECASE)
voluntary_task_pattern = re.compile(r'\[\s*выдать задачу\s*"(.+)"\s*\]', re.IGNORECASE)
staff_rule = OrRule(AdminRule(), JudgeRule(), OwnerRule())


async def _start_quest_wizard(m: Message, description: str, force_assign_forms: list | None, intro: str):
    quest = await db.Quest.create(name=description[:100], description=description,
                                  force_assign_forms=force_assign_forms or None)
    states.set(m.from_id, f"{Admin.QUEST_REWARD}*{quest.id}")
    reply, keyboard = await info_target_reward()
    await bot.api.messages.send(
        peer_id=m.from_id,
        message=f'{intro}\n\nУкажите награду для квеста\n\n{reply}',
        keyboard=keyboard,
        random_id=0,
    )


@bot.on.message(RegexRule(force_task_pattern), staff_rule)
async def force_individual_task(m: Message, match: tuple[str, str]):
    """
    [выдать задачу @user1, @user2 "описание"] — принудительная индивидуальная задача.
    Доступно только судьям, админам и владельцу бота.
    """
    mentions_part, description = match
    target_ids = [int(x) for x in mention_extract_pattern.findall(mentions_part)]
    if not target_ids:
        await m.answer('Не указаны получатели задачи (укажите упоминания через @)')
        return
    form_ids = [x[0] for x in await db.select([db.Form.id]).where(db.Form.user_id.in_(target_ids)).gino.all()]
    if not form_ids:
        await m.answer('Анкеты указанных игроков не найдены')
        return
    await _start_quest_wizard(m, description, form_ids,
                              f'Создание индивидуальной задачи для {len(form_ids)} игроков начато в личных сообщениях с ботом.')
    await m.answer('Настройка задачи продолжится в личных сообщениях с ботом')


@bot.on.message(RegexRule(voluntary_task_pattern), staff_rule)
async def voluntary_task(m: Message, match: tuple[str]):
    """
    [выдать задачу "описание"] — то же самое, но без тегов: квест создаётся доступным
    для добровольного взятия игроками, а не выдаётся принудительно.
    Доступно только судьям, админам и владельцу бота.
    """
    description = match[0]
    await _start_quest_wizard(m, description, None,
                              'Создание добровольной задачи начато в личных сообщениях с ботом.')
    await m.answer('Настройка задачи продолжится в личных сообщениях с ботом')


# Ставки на закрытых аукционах в ЛС боту (module auction_system). Ставки на публичных аукционах
# делаются комментариями к посту на стене — см. handlers/group_events.py: wall_auction_bid
auction_bid_pattern = re.compile(r'\[\s*ставка\s+(\d+)\s+аукцион\s+(\d+)\s*\]', re.IGNORECASE)
auction_bid_pattern_single = re.compile(r'\[\s*ставка\s+(\d+)\s*\]', re.IGNORECASE)


@bot.on.private_message(RegexRule(auction_bid_pattern))
async def dm_auction_bid_with_id(m: Message, match: tuple[str, str]):
    """[ставка СУММА аукцион ID] — ставка на конкретный закрытый аукцион (если их несколько активно)"""
    amount, auction_id = int(match[0]), int(match[1])
    eligible_ids = await eligible_closed_auction_ids(m.from_id)
    if auction_id not in eligible_ids:
        await m.answer('Этот аукцион недоступен для вас (не активен или нет допуска)')
        return
    success, message = await place_bid(auction_id, m.from_id, amount)
    await m.answer(message)


@bot.on.private_message(RegexRule(auction_bid_pattern_single))
async def dm_auction_bid(m: Message, match: tuple[str]):
    """[ставка СУММА] — ставка на единственный доступный игроку активный закрытый аукцион"""
    amount = int(match[0])
    eligible_ids = await eligible_closed_auction_ids(m.from_id)
    if not eligible_ids:
        await m.answer('У вас нет доступных закрытых аукционов для ставки')
        return
    if len(eligible_ids) > 1:
        lines = []
        for auction_id in eligible_ids:
            item_name = await db.select([db.Item.name]).select_from(
                db.Auction.join(db.Item, db.Auction.item_id == db.Item.id)
            ).where(db.Auction.id == auction_id).gino.scalar()
            lines.append(f'{auction_id}. {item_name}')
        await m.answer('У вас несколько активных закрытых аукционов, уточните командой '
                       '[ставка СУММА аукцион ID]:\n' + '\n'.join(lines))
        return
    success, message = await place_bid(eligible_ids[0], m.from_id, amount)
    await m.answer(message)
>>>>>>> Stashed changes
