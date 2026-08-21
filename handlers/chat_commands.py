"""
Модуль обработки команд в чатах.
Содержит обработчики для покупок, переводов, перемещений
и других действий, доступных в групповых беседах.
"""

import re
import random

from vkbottle.bot import Message
from vkbottle import Keyboard, Callback, KeyboardButtonColor
from vkbottle_types.objects import UtilsDomainResolvedType
from vkbottle.dispatch.rules import OrRule
from fuzzywuzzy import process
from sqlalchemy import and_

from loader import bot, user_bot
from service.custom_rules import ChatAction, AdminRule, ChatInviteMember, RegexRule, UserFree, JudgeRule, \
    MentionQuestRule, NotAdminOrJudgeRule
from service.db_engine import db, Attribute
from handlers.public_menu.bank import ask_salary
from handlers.public_menu.daylics import send_ready_daylic
from handlers.public_menu.quests import send_ready_quest
from service.utils import move_user, create_mention, get_current_form_id, soft_divide, convert_bot_chat_id_to_user, \
    mention_regex, count_attribute
from service.states import Admin
from config import HALL_CHAT_ID

# Регулярные выражения для обработки команд
moving_pattern = re.compile(r'\[\s*\s*перемещение\s+в\s+[«"](.+?)[»"]\s*\]', re.IGNORECASE)
moving_pattern2 = re.compile(r'\[\s*\s*перемещение\s+в\s+(.+)\s*\]', re.IGNORECASE)
forced_move_pattern = re.compile(
    r'\[\s*переместить\s+((?:\[id\d+\|[^\]]+\]\s*)+)[«"](.+?)[»"]\s*\]',
    re.IGNORECASE
)
donate_pattern = re.compile(r'\[\s*пожертвовать\s+в\s+храм\s+(\d+)\s*\]', re.IGNORECASE)
deal_pattern = re.compile(r"\[\s*совершить\s+сделку\s+\[id(\d+)\|[^\]]+\]\s+(\d+)\s*\]", re.IGNORECASE)
deal_pattern_link = re.compile(r"\[\s*совершить\s+сделку\s+https://vk.com/(\w*)\s+(\d+)\s*\]", re.IGNORECASE)
message_pattern = re.compile(r'\[\s*отправить\s+сообщение\s+\[id(\d+)\|[^\]]+\]\s+[«"](.+?)[»"]\s*\]', re.IGNORECASE)
message_pattern_link = re.compile(r'\[\s*отправить\s+сообщение\s+https://vk.com/(\w*)\s+[«"](.+?)[»"]\s*\]', re.IGNORECASE)


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
async def submit_report_command(m: Message):
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
@bot.on.chat_message(RegexRule(re.compile(r"\[\s*перевести\s+деньги\s+https://vk.com/(\w*)\s+(\d+)\s*\]", re.IGNORECASE)), blocking=False)
@bot.on.chat_message(RegexRule(re.compile(r"\[\s*отправить\s+деньги\s+https://vk.com/(\w*)\s+(\d+)\s*\]", re.IGNORECASE)), blocking=False)
@bot.on.chat_message(RegexRule(re.compile(r"\[\s*перевести\s+валюту\s+https://vk.com/(\w*)\s+(\d+)\s*\]", re.IGNORECASE)), blocking=False)
@bot.on.chat_message(RegexRule(re.compile(r"\[\s*сделка\s+с\s+https://vk.com/(\w*)\s+(\d+)\s*\]", re.IGNORECASE)), blocking=False)
@bot.on.chat_message(RegexRule(re.compile(r"\[\s*передать\s+деньги\s+https://vk.com/(\w*)\s+(\d+)\s*\]", re.IGNORECASE)), blocking=False)
@bot.on.chat_message(RegexRule(re.compile(r"\[\s*отдать\s+сумму\s+https://vk.com/(\w*)\s+(\d+)\s*\]", re.IGNORECASE)), blocking=False)
@bot.on.chat_message(RegexRule(re.compile(r"\[\s*перечислить\s+сумму\s+https://vk.com/(\w*)\s+(\d+)\s*\]", re.IGNORECASE)), blocking=False)
@bot.on.chat_message(RegexRule(re.compile(r"\[\s*перевести\s+деньги\s+\[id(\d+)\|[^\]]+\]\s+(\d+)\s*\]", re.IGNORECASE)), blocking=False)
@bot.on.chat_message(RegexRule(re.compile(r"\[\s*отправить\s+деньги\s+\[id(\d+)\|[^\]]+\]\s+(\d+)\s*\]", re.IGNORECASE)), blocking=False)
@bot.on.chat_message(RegexRule(re.compile(r"\[\s*сделка\s+с\s+\[id(\d+)\|[^\]]+\]\s+(\d+)\s*\]", re.IGNORECASE)), blocking=False)
@bot.on.chat_message(RegexRule(re.compile(r"\[\s*передать\s+деньги\s+\[id(\d+)\|[^\]]+\]\s+(\d+)\s*\]", re.IGNORECASE)), blocking=False)
@bot.on.chat_message(RegexRule(re.compile(r"\[\s*отдать\s+сумму\s+\[id(\d+)\|[^\]]+\]\s+(\d+)\s*\]", re.IGNORECASE)), blocking=False)
@bot.on.chat_message(RegexRule(re.compile(r"\[\s*перечислить\s+сумму\s+\[id(\d+)\|[^\]]+\]\s+(\d+)\s*\]", re.IGNORECASE)), blocking=False)
@bot.on.chat_message(RegexRule(re.compile(r"\[\s*перевести\s+валюту\s+\[id(\d+)\|[^\]]+\]\s+(\d+)\s*\]", re.IGNORECASE)), blocking=False)
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
@bot.on.chat_message(RegexRule(re.compile(r'\[\s*отдать\s+в\s+храм\s+(\d+)\s*\]', re.IGNORECASE)), blocking=False)
@bot.on.chat_message(RegexRule(re.compile(r'\[\s*внести\s+пожертвование\s+(\d+)\s*\]', re.IGNORECASE)), blocking=False)
@bot.on.chat_message(RegexRule(re.compile(r'\[\s*жертва\s+храму\s+(\d+)\s*\]', re.IGNORECASE)), blocking=False)
@bot.on.chat_message(RegexRule(re.compile(r'\[\s*подношение\s+храму\s+(\d+)\s*\]', re.IGNORECASE)), blocking=False)
@bot.on.chat_message(RegexRule(re.compile(r'\[\s*сделать\s+пожертвование\s+(\d+)\s*\]', re.IGNORECASE)), blocking=False)
@bot.on.chat_message(RegexRule(re.compile(r'\[\s*отдать\s+сумму\s+в\s+храм\s+(\d+)\s*\]', re.IGNORECASE)), blocking=False)
async def create_donate_command(m: Message, match: tuple[str]):
    """
    Создание пожертвования в храм

    Args:
        m: Сообщение с командой пожертвования
        match: Результат регулярного выражения (сумма пожертвования)
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
        await user_bot.api.request('messages.changeConversationMemberRestrictions',
                              {'peer_id': 2000000000 + await convert_bot_chat_id_to_user(m.chat_id),
                               'member_ids': member_id, 'action': 'ro'})


@bot.on.message(RegexRule(moving_pattern), UserFree(), blocking=False)
@bot.on.message(RegexRule(moving_pattern2), UserFree(), blocking=False)
@bot.on.message(RegexRule(re.compile(r'\[\s*переместиться\s+в\s+(.+)\s*\]', re.IGNORECASE)), UserFree(), blocking=False)
@bot.on.message(RegexRule(re.compile(r'\[\s*перейти\s+в\s+(.+)\s*\]', re.IGNORECASE)), UserFree(), blocking=False)
@bot.on.message(RegexRule(re.compile(r'\[\s*идти\s+в\s+(.+)\s*\]', re.IGNORECASE)), UserFree(), blocking=False)
@bot.on.message(RegexRule(re.compile(r'\[\s*отправиться\s+в\s+(.+)\s*\]', re.IGNORECASE)), UserFree(), blocking=False)
@bot.on.message(RegexRule(re.compile(r'\[\s*телепорт\s+в\s+(.+)\s*\]', re.IGNORECASE)), UserFree(), blocking=False)
@bot.on.message(RegexRule(re.compile(r'\[\s*хочу\s+в\s+(.+)\s*\]', re.IGNORECASE)), UserFree(), blocking=False)
@bot.on.message(RegexRule(re.compile(r'\[\s*локация\s+(.+)\s*\]', re.IGNORECASE)), UserFree(), blocking=False)
async def move_to_location(m: Message, match: tuple[str]):
    """
    Перемещение пользователя между чатами-локациями

    Args:
        m: Сообщение с командой перемещения
        match: Результат регулярного выражения (название локации)
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
                         await db.select([db.Form.user_id]).where(and_(db.Form.profession.in_(profession_ids), db.Form.is_request.is_(False))).gino.all()]
        for admin_id in list(set(admin_ids)):
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


@bot.on.chat_message(RegexRule(forced_move_pattern), OrRule(AdminRule(), JudgeRule()), blocking=False)
async def force_move_users(m: Message, match: tuple[str, str]):
    """
    Принудительно перемещает одного или нескольких игроков в существующий чат.

    Формат:
        [переместить [id123|Игрок] [id456|Игрок] "Название чата"]

    Команда доступна только администраторам и судьям. В отличие от обычного
    перемещения она не запрашивает доступ к приватному чату у владельца.
    """
    mentions, requested_chat_name = match
    user_ids = list(dict.fromkeys(
        int(user_id) for user_id in re.findall(r'\[id(\d+)\|[^\]]+\]', mentions, re.IGNORECASE)
    ))
    if not user_ids:
        await m.answer('Укажите хотя бы одного игрока через VK-упоминание.')
        return

    registered_ids = {
        row[0] for row in await db.select([db.Form.user_id]).where(
            db.Form.user_id.in_(user_ids)
        ).gino.all()
    }
    if not registered_ids:
        await m.answer('У указанных пользователей нет активных анкет.')
        return

    chat_rows = await db.select([db.Chat.chat_id]).where(
        db.Chat.chat_id.isnot(None)
    ).gino.all()
    peer_ids = [2000000000 + row[0] for row in chat_rows]
    if not peer_ids:
        await m.answer('В базе нет зарегистрированных чатов для перемещения.')
        return

    try:
        conversations = await bot.api.messages.get_conversations_by_id(peer_ids=peer_ids)
    except Exception:
        await m.answer('Не удалось получить список чатов. Проверьте права бота.')
        return

    chats_by_name = {
        item.chat_settings.title.lower(): item.peer.id - 2000000000
        for item in conversations.items
        if item.chat_settings and item.chat_settings.title
    }
    normalized_name = requested_chat_name.strip().lower()
    chat_id = chats_by_name.get(normalized_name)
    if chat_id is None:
        match_result = process.extractOne(normalized_name, list(chats_by_name))
        if not match_result or match_result[1] < 70:
            await m.answer(f'Чат «{requested_chat_name}» не найден.')
            return
        chat_id = chats_by_name[match_result[0]]

    moved_ids = []
    failed_ids = []
    for user_id in registered_ids:
        try:
            await move_user(user_id, chat_id)
            moved_ids.append(user_id)
        except Exception:
            failed_ids.append(user_id)

    if moved_ids:
        moved_mentions = ', '.join([await create_mention(user_id) for user_id in moved_ids])
        await m.answer(
            f'Принудительное перемещение в «{requested_chat_name}» выполнено для: {moved_mentions}.'
        )
    if failed_ids:
        failed_mentions = ', '.join([await create_mention(user_id) for user_id in failed_ids])
        await m.answer(
            f'Не удалось переместить: {failed_mentions}. Проверьте регистрацию чата и права юзербота.'
        )


@bot.on.chat_message(RegexRule(forced_move_pattern), NotAdminOrJudgeRule(), blocking=False)
async def force_move_users_player(m: Message, match: tuple[str, str]):
    """
    Та же команда [переместить ...], но доступная обычным игрокам —
    только во время активного экшен-режима в текущем чате (в свою очередь,
    это уже гарантируется ActionModeMiddleware) и при успешной проверке
    Ловкость инициатора против Восприятия цели (аналогично скрытным действиям).
    """
    action_mode_row = await db.select([db.ActionMode.started, db.ActionMode.finished]).where(
        db.ActionMode.chat_id == m.chat_id
    ).gino.first()
    if not action_mode_row or not action_mode_row[0] or action_mode_row[1]:
        await m.answer('Принудительное перемещение доступно игрокам только во время активного экшен-режима в этом чате.')
        return

    mentions, requested_chat_name = match
    user_ids = list(dict.fromkeys(
        int(user_id) for user_id in re.findall(r'\[id(\d+)\|[^\]]+\]', mentions, re.IGNORECASE)
    ))
    if not user_ids:
        await m.answer('Укажите хотя бы одного игрока через VK-упоминание.')
        return

    initiator_form_id = await get_current_form_id(m.from_id)
    initiator_expedition = await db.select([db.Expeditor.id]).where(
        db.Expeditor.form_id == initiator_form_id
    ).gino.scalar()
    if not initiator_expedition:
        await m.answer('Для принудительного перемещения нужна созданная карта экспедитора.')
        return

    registered_ids = {
        row[0] for row in await db.select([db.Form.user_id]).where(
            db.Form.user_id.in_(user_ids)
        ).gino.all()
    }
    if not registered_ids:
        await m.answer('У указанных пользователей нет активных анкет.')
        return

    chat_rows = await db.select([db.Chat.chat_id]).where(
        db.Chat.chat_id.isnot(None)
    ).gino.all()
    peer_ids = [2000000000 + row[0] for row in chat_rows]
    if not peer_ids:
        await m.answer('В базе нет зарегистрированных чатов для перемещения.')
        return

    try:
        conversations = await bot.api.messages.get_conversations_by_id(peer_ids=peer_ids)
    except Exception:
        await m.answer('Не удалось получить список чатов. Проверьте права бота.')
        return

    chats_by_name = {
        item.chat_settings.title.lower(): item.peer.id - 2000000000
        for item in conversations.items
        if item.chat_settings and item.chat_settings.title
    }
    normalized_name = requested_chat_name.strip().lower()
    chat_id = chats_by_name.get(normalized_name)
    if chat_id is None:
        match_result = process.extractOne(normalized_name, list(chats_by_name))
        if not match_result or match_result[1] < 70:
            await m.answer(f'Чат «{requested_chat_name}» не найден.')
            return
        chat_id = chats_by_name[match_result[0]]

    initiator_dexterity = await count_attribute(m.from_id, Attribute.DEXTERITY)
    moved_ids = []
    resisted_ids = []
    failed_ids = []
    for user_id in registered_ids:
        target_form_id = await get_current_form_id(user_id)
        target_expedition = await db.select([db.Expeditor.id]).where(
            db.Expeditor.form_id == target_form_id
        ).gino.scalar()
        if not target_expedition:
            failed_ids.append(user_id)
            continue

        target_perception = await count_attribute(user_id, Attribute.PERCEPTION)
        initiator_roll = initiator_dexterity + random.randint(1, 100)
        target_roll = target_perception + random.randint(1, 100)
        if initiator_roll <= target_roll:
            resisted_ids.append(user_id)
            continue

        try:
            await move_user(user_id, chat_id)
            moved_ids.append(user_id)
        except Exception:
            failed_ids.append(user_id)

    if moved_ids:
        moved_mentions = ', '.join([await create_mention(user_id) for user_id in moved_ids])
        await m.answer(
            f'Принудительное перемещение в «{requested_chat_name}» выполнено для: {moved_mentions}.'
        )
    if resisted_ids:
        resisted_mentions = ', '.join([await create_mention(user_id) for user_id in resisted_ids])
        await m.answer(f'Цель(и) успешно сопротивлялись перемещению: {resisted_mentions}.')
    if failed_ids:
        failed_mentions = ', '.join([await create_mention(user_id) for user_id in failed_ids])
        await m.answer(
            f'Не удалось переместить (нет карты экспедитора или ошибка): {failed_mentions}.'
        )


@bot.on.message(RegexRule(message_pattern), blocking=False)
@bot.on.message(RegexRule(message_pattern_link), blocking=False)
@bot.on.message(RegexRule(re.compile(r'\[\s*написать\s+сообщение\s+\[id(\d+)\|[^\]]+\]\s+[«"](.+?)[»"]\s*\]', re.IGNORECASE)), blocking=False)
@bot.on.message(RegexRule(re.compile(r'\[\s*написать\s+\[id(\d+)\|[^\]]+\]\s+[«"](.+?)[»"]\s*\]', re.IGNORECASE)), blocking=False)
@bot.on.message(RegexRule(re.compile(r'\[\s*сказать\s+\[id(\d+)\|[^\]]+\]\s+[«"](.+?)[»"]\s*\]', re.IGNORECASE)), blocking=False)
@bot.on.message(RegexRule(re.compile(r'\[\s*отправь\s+текст\s+\[id(\d+)\|[^\]]+\]\s+[«"](.+?)[»"]\s*\]', re.IGNORECASE)), blocking=False)
@bot.on.message(RegexRule(re.compile(r'\[\s*сообщение\s+для\s+\[id(\d+)\|[^\]]+\]\s+[«"](.+?)[»"]\s*\]', re.IGNORECASE)), blocking=False)
@bot.on.message(RegexRule(re.compile(r'\[\s*передать\s+сообщение\s+\[id(\d+)\|[^\]]+\]\s+[«"](.+?)[»"]\s*\]', re.IGNORECASE)), blocking=False)
@bot.on.message(RegexRule(re.compile(r'\[\s*написать\s+сообщение\s+https://vk.com/(\w*)\s+[«"](.+?)[»"]\s*\]', re.IGNORECASE)), blocking=False)
@bot.on.message(RegexRule(re.compile(r'\[\s*написать\s+https://vk.com/(\w*)\s+[«"](.+?)[»"]\s*\]', re.IGNORECASE)), blocking=False)
@bot.on.message(RegexRule(re.compile(r'\[\s*сказать\s+https://vk.com/(\w*)\s+[«"](.+?)[»"]\s*\]', re.IGNORECASE)), blocking=False)
@bot.on.message(RegexRule(re.compile(r'\[\s*отправь\s+текст\s+https://vk.com/(\w*)\s+[«"](.+?)[»"]\s*\]', re.IGNORECASE)), blocking=False)
@bot.on.message(RegexRule(re.compile(r'\[\s*сообщение\s+для\s+https://vk.com/(\w*)\s+[«"](.+?)[»"]\s*\]', re.IGNORECASE)), blocking=False)
@bot.on.message(RegexRule(re.compile(r'\[\s*передать\s+сообщение\s+https://vk.com/(\w*)\s+[«"](.+?)[»"]\s*\]', re.IGNORECASE)), blocking=False)
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


@bot.on.chat_message(MentionQuestRule(), OrRule(AdminRule(), JudgeRule()), blocking=False)
async def required_quest(m: Message, match: tuple):
    """
    Команда [выдать задачу @user1 @user2 «название»] — создаёт обязательный квест.
    Если указан @all/@все — создаёт добровольный квест для всех участников чата.
    """
    user_ids, name = match
    # user_ids — список int-айди игроков или ['@all'/'@все']
    is_all = any(isinstance(uid, str) and uid in ('@all', '@все') for uid in user_ids)

    if not is_all:
        # Принудительный квест конкретным игрокам
        form_ids = [x[0] for x in await db.select([db.Form.id]).where(db.Form.user_id.in_(user_ids)).gino.all()]
        if not form_ids:
            await m.answer('Не найдено анкет у указанных пользователей')
            return
        from_form_id = await get_current_form_id(m.from_id)
        quest = await db.MandatoryQuest.create(form_ids=form_ids, name=name, from_form_id=from_form_id)
        # Уведомляем каждого игрока в ЛС о новом квесте
        for uid in user_ids:
            try:
                await bot.api.messages.send(
                    peer_id=uid,
                    message=f'Панель обязательных квестов в меню бота.',
                    random_id=0
                )
            except Exception:
                pass  # пользователь заблокировал бота — не критично
        await db.User.update.values(state=f'{Admin.MANDATORY_QUEST_DESCRIPTION}*{quest.id}').where(
            db.User.user_id == m.from_id).gino.status()
        # Одно итоговое сообщение с перечнем игроков
        mentions = []
        for uid in user_ids:
            mentions.append(await create_mention(uid))
        await m.answer('Перейдите в личные сообщения для продолжения создания обязательного квеста')
        await bot.api.messages.send(
            peer_id=m.from_id,
            message=f'Вы создаёте обязательный квест «{name}» для: {", ".join(mentions)}\n\n'
                    f'Напишите описание квеста 👇',
            keyboard=Keyboard()
        )
        return

    # Добровольный квест для всех участников чата
    users = await bot.api.messages.get_conversation_members(m.peer_id)
    all_user_ids = [x.member_id for x in users.items if x.member_id > 0]
    form_ids = [x[0] for x in await db.select([db.Form.id]).where(db.Form.user_id.in_(all_user_ids)).gino.all()]
    if not form_ids:
        await m.answer('В чате нет игроков с анкетами — некому выдавать квест')
        return
    quest = await db.Quest.create(allowed_forms=form_ids, name=name)
    await db.User.update.values(
        state=f'{Admin.QUEST_DESCRIPTION}*{quest.id}',
        editing_content=False,
        special_quest=True
    ).where(db.User.user_id == m.from_id).gino.status()
    await m.answer('Перейдите в личные сообщения для продолжения создания добровольного квеста')
    await bot.api.messages.send(
        peer_id=m.from_id,
        message=f'Вы создаёте добровольный квест «{name}» для всех участников чата.\n\n'
                f'Напишите описание квеста 👇',
        keyboard=Keyboard()
    )



# ─── Групповая отправка сообщений нескольким игрокам + «засекречено» (Доработка 5) ────────────

@bot.on.message(RegexRule(re.compile(
    r'\[\s*(?:засекречено\s+)?(?:групповое|множественное)\s+сообщение\s+(?:\[id\d+\|[^\]]+\]\s*)+[«"„]',
    re.IGNORECASE
)), blocking=False)
async def multi_transmitter(m: Message):
    """
    Отправка сообщения нескольким игрокам с возможной анонимизацией.

    Форматы:
      [групповое сообщение [id123|name] [id456|name] «текст»]
      [засекречено групповое сообщение [id123|name] «текст»]
        — отправитель не раскрывается получателю
    """
    text = m.text or ''
    is_classified = bool(re.search(r'\[\s*засекречено', text, re.IGNORECASE))

    mention_ids = [int(uid) for uid in re.findall(r'\[id(\d+)\|[^\]]+\]', text)]
    msg_match = re.search(r'[«"„](.*?)[»"]', text, re.DOTALL)
    if not msg_match or not mention_ids:
        return
    message_text = msg_match.group(1).strip()

    valid_ids = []
    for uid in mention_ids:
        exists = await db.select([db.Form.id]).where(db.Form.user_id == uid).gino.scalar()
        if exists:
            valid_ids.append(uid)

    if not valid_ids:
        await m.answer('Ни у одного из указанных пользователей нет анкеты')
        return

    if is_classified:
        out_message = f'Секретное сообщение от неизвестного источника:\n«{message_text}»'
    else:
        out_message = f'Новое сообщение от {await create_mention(m.from_id)}:\n«{message_text}»'

    sent = 0
    for uid in valid_ids:
        try:
            await bot.api.messages.send(peer_id=uid, message=out_message, random_id=0)
            sent += 1
        except Exception:
            pass

    skipped = len(mention_ids) - sent
    result = f'Сообщение отправлено {sent} игроку(/кам)'
    if skipped:
        result += f', {skipped} — нет анкеты'
    await m.answer(result)
