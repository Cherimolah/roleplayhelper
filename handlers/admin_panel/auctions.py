"""
Механика «Аукциона».

Судьи и администраторы могут:
- Создать публичный аукцион (объявление на стене ВК, ставки через комментарии к посту).
- Создать закрытый аукцион (рассылка через ЛС бота участникам, подходящим по фильтрам фракция/репутация).
- Просмотреть активные аукционы.
- Завершить аукцион досрочно.

Пользователи могут:
- Посмотреть активные аукционы через меню.
- Сделать ставку (в ЛС бота).
"""

import asyncio
import datetime
import re

from vkbottle.bot import Message, MessageEvent
from vkbottle.dispatch.rules.base import PayloadRule, PayloadMapRule
from vkbottle import Keyboard, Text, KeyboardButtonColor, Callback
from sqlalchemy import func

from loader import bot, user_bot
from service.custom_rules import AdminRule, JudgeRule, StateRule, NumericRule
from service.middleware import states
from service.states import Auction as AuctionState, Menu
from service.db_engine import db, now
from service.utils import get_current_form_id, create_mention
from config import GROUP_ID, DATETIME_FORMAT, ADMINS


# ─── Вспомогательные функции ──────────────────────────────────────────────────

def _can_manage_auction(admin: int, is_judge: bool) -> bool:
    return admin > 0 or is_judge


async def _get_lot_description(auction) -> str:
    """Формирует текст лота для поста / рассылки."""
    photo = auction.photo or ''
    title = auction.title or 'Без названия'
    desc = auction.description or ''
    start = auction.start_price
    min_bet = auction.min_bet
    end_at = auction.end_at.strftime(DATETIME_FORMAT) if auction.end_at else 'не указано'
    kind = '🔓 Публичный' if auction.is_public else '🔒 Закрытый'
    if auction.item_id:
        item = await db.Item.get(auction.item_id)
        if item:
            item_desc = f'Предмет: {item.name}\n'
    elif auction.shop_id:
        shop = await db.Shop.get(auction.shop_id)
        if shop:
            item_desc = f'Товар/услуга: {shop.name}\n'
    return (
        f'🏷 Аукцион: {title}\n\n'
        f'{item_desc if "item_desc" in locals() else ""}'
        f'{desc}\n\n'
        f'💰 Стартовая цена: {start}\n'
        f'📈 Минимальная ставка: {min_bet}\n'
        f'⏰ Завершение: {end_at}\n'
        f'Тип: {kind}'
    )


async def _get_top_bet(auction_id: int):
    """Возвращает (form_id, amount) наибольшей ставки или None."""
    row = (await db.select([db.AuctionBet.form_id, db.AuctionBet.amount])
           .where(db.AuctionBet.auction_id == auction_id)
           .order_by(db.AuctionBet.amount.desc())
           .limit(1).gino.first())
    return row


async def _finish_auction(auction_id: int):
    """Завершает аукцион: определяет победителя, уведомляет, обновляет пост."""
    auction = await db.Auction.get(auction_id)
    if not auction or auction.finished:
        return

    top = await _get_top_bet(auction_id)
    winner_form_id = top[0] if top else None
    winner_amount = top[1] if top else 0

    await db.Auction.update.values(finished=True, winner_form_id=winner_form_id).where(
        db.Auction.id == auction_id).gino.status()

    admins_all = list(set(
        [x[0] for x in await db.select([db.User.user_id]).where(db.User.admin > 0).gino.all()]
        + ADMINS
    ))

    if winner_form_id:
        winner_user_id = await db.select([db.Form.user_id]).where(db.Form.id == winner_form_id).gino.scalar()
        winner_name = await db.select([db.Form.name]).where(db.Form.id == winner_form_id).gino.scalar()
        result_text = (
            f'🏆 Аукцион «{auction.title}» завершён!\n\n'
            f'Победитель: [id{winner_user_id}|{winner_name}]\n'
            f'Итоговая ставка: {winner_amount}'
        )
        # Уведомляем победителя
        try:
            await bot.api.messages.send(
                peer_id=winner_user_id,
                message=f'🏆 Поздравляем! Вы выиграли аукцион «{auction.title}» со ставкой {winner_amount}.\n'
                        f'Свяжитесь с администрацией для получения лота.',
                random_id=0
            )
        except Exception:
            pass
    else:
        result_text = f'Аукцион «{auction.title}» завершён без ставок.'

    # Уведомляем администраторов/создателя
    try:
        await bot.api.messages.send(peer_ids=admins_all, message=result_text, random_id=0)
    except Exception:
        pass

    # Для публичного аукциона — публикуем пост об окончании
    if auction.is_public and auction.vk_post_id:
        try:
            await user_bot.api.wall.post(
                owner_id=GROUP_ID,
                message=result_text,
                attachments=auction.photo or '',
            )
        except Exception:
            pass


async def schedule_auction(auction_id: int):
    """Планирует завершение аукциона через delay_seconds секунд."""
    finished_at = await db.select([db.Auction.end_at]).where(db.Auction.id == auction_id).gino.scalar()
    await asyncio.sleep((finished_at - now()).total_seconds())
    await _finish_auction(auction_id)


async def public_auctions(auction_id: int):
    """Публикует пост о начале аукциона по времени"""
    start_at = await db.select([db.Auction.start_at]).where(db.Auction.id == auction_id).gino.scalar()
    await asyncio.sleep((now() - start_at).total_seconds())
    auction = await db.Auction.get(auction_id)
    lot_text = await _get_lot_description(auction)
    post_resp = await user_bot.api.wall.post(
        owner_id=GROUP_ID,
        message=f'🏦 Открыт аукцион!\n\n{lot_text}\n\n'
                f'Сделайте ставку в комментариях в формате: СТАВКА [сумма]\n'
                f'Например: СТАВКА 500',
        attachments=auction.photo or '',
        from_group=True
    )
    post_id = post_resp.post_id
    await db.Auction.update.values(vk_post_id=post_id).where(
        db.Auction.id == auction_id).gino.status()


# ─── Меню аукционов (для администратора/судьи) ────────────────────────────────

auction_menu_kb = Keyboard().add(
    Text('Создать аукцион', {'auction': 'create'}), KeyboardButtonColor.POSITIVE
).row().add(
    Text('Активные аукционы', {'auction': 'active'}), KeyboardButtonColor.PRIMARY
).row().add(
    Text('Назад', {'auction': 'back'}), KeyboardButtonColor.NEGATIVE
)

public_private_kb = Keyboard().add(
    Text('🔓 Публичный', {'auction_type': 'public'}), KeyboardButtonColor.PRIMARY
).row().add(
    Text('🔒 Закрытый', {'auction_type': 'private'}), KeyboardButtonColor.NEGATIVE
)

lot_type_kb = Keyboard().add(
    Text('Предмет карты экспедитора', {'lot_type': 'item'}), KeyboardButtonColor.PRIMARY
).row().add(
    Text('Товар/услуга из магазина', {'lot_type': 'shop'}), KeyboardButtonColor.PRIMARY
).row().add(
    Text('Свой лот (только описание)', {'lot_type': 'custom'}), KeyboardButtonColor.SECONDARY
)


def _admin_or_judge(m: Message) -> bool:
    """Быстрая заглушка — основная проверка вынесена в декораторы."""
    return True


# ─── Вход в меню аукционов ───────────────────────────────────────────────────

@bot.on.private_message(PayloadRule({'admin_menu': 'auctions'}), AdminRule())
@bot.on.private_message(PayloadRule({'judge_menu': 'auctions'}), JudgeRule())
@bot.on.private_message(StateRule(AuctionState.SELECT_AUCTION), PayloadRule({'auction': 'back_to_menu'}))
async def auction_main_menu(m: Message):
    """Главное меню аукционов."""
    states.set(m.from_id, AuctionState.MENU)
    await m.answer('🏦 Меню аукционов', keyboard=auction_menu_kb)


@bot.on.private_message(StateRule(AuctionState.MENU), PayloadRule({'auction': 'back'}))
async def auction_back(m: Message):
    """Назад из меню аукционов."""
    from service.keyboards import admin_menu
    states.set(m.from_id, 'Admin.admin_menu')
    await m.answer('Админ-панель', keyboard=admin_menu)


# ─── Создание аукциона ────────────────────────────────────────────────────────

@bot.on.private_message(StateRule(AuctionState.MENU), PayloadRule({'auction': 'create'}))
async def start_create_auction(m: Message):
    """Начало создания аукциона."""
    states.set(m.from_id, AuctionState.SELECT_LOT_TYPE)
    await m.answer('Выберите тип лота:', keyboard=lot_type_kb)


@bot.on.private_message(StateRule(AuctionState.SELECT_LOT_TYPE), PayloadRule({'lot_type': 'item'}))
async def auction_lot_item(m: Message):
    """Лот — предмет карты экспедитора."""
    items = await db.select([db.Item.id, db.Item.name]).order_by(db.Item.id.asc()).gino.all()
    if not items:
        await m.answer('Предметов не найдено. Сначала создайте предметы для карты экспедитора.')
        return
    reply = 'Выберите номер предмета:\n\n'
    for i, (iid, name) in enumerate(items):
        reply += f'{i + 1}. {name}\n'
    # Создаём черновик аукциона
    auction = await db.Auction.create(created_by=m.from_id)
    states.set(m.from_id, f'{AuctionState.SELECT_ITEM}*{auction.id}*item')
    await m.answer(reply, keyboard=Keyboard())


@bot.on.private_message(StateRule(AuctionState.SELECT_LOT_TYPE), PayloadRule({'lot_type': 'shop'}))
async def auction_lot_shop(m: Message):
    """Лот — товар/услуга из магазина."""
    items = await db.select([db.Shop.id, db.Shop.name]).order_by(db.Shop.id.asc()).gino.all()
    if not items:
        await m.answer('Товаров в магазине нет.')
        return
    reply = 'Выберите номер товара/услуги:\n\n'
    for i, (iid, name) in enumerate(items):
        reply += f'{i + 1}. {name}\n'
    auction = await db.Auction.create(created_by=m.from_id)
    states.set(m.from_id, f'{AuctionState.SELECT_ITEM}*{auction.id}*shop')
    await m.answer(reply, keyboard=Keyboard())


@bot.on.private_message(StateRule(AuctionState.SELECT_LOT_TYPE), PayloadRule({'lot_type': 'custom'}))
async def auction_lot_custom(m: Message):
    """Свой лот — только текстовое описание."""
    auction = await db.Auction.create(created_by=m.from_id)
    states.set(m.from_id, f'{AuctionState.ENTER_TITLE}*{auction.id}')
    await m.answer('Введите название лота:', keyboard=Keyboard())


@bot.on.private_message(StateRule(AuctionState.SELECT_ITEM), NumericRule())
async def auction_select_item_number(m: Message, value: int):
    """Выбор конкретного предмета/товара по номеру."""
    parts = states.get(m.from_id).split('*')
    auction_id = int(parts[1])
    lot_kind = parts[2]  # 'item' или 'shop'

    if lot_kind == 'item':
        rows = await db.select([db.Item.id, db.Item.photo, db.Item.fraction_id,
                                db.Item.reputation]).order_by(db.Item.id.asc()).gino.all()
        if value > len(rows):
            await m.answer('Неверный номер')
            return
        iid, photo, frac_id, rep = rows[value - 1]
        await db.Auction.update.values(item_id=iid, photo=photo,
                                       access_fraction_id=frac_id,
                                       access_reputation=rep or 0).where(
            db.Auction.id == auction_id).gino.status()
    else:
        rows = await db.select([db.Shop.id, db.Shop.photo]).order_by(db.Shop.id.asc()).gino.all()
        if value > len(rows):
            await m.answer('Неверный номер')
            return
        sid, photo = rows[value - 1]
        await db.Auction.update.values(shop_id=sid, photo=photo).where(
            db.Auction.id == auction_id).gino.status()

    states.set(m.from_id, f'{AuctionState.ENTER_TITLE}*{auction_id}')
    await m.answer('Введите название лота:', keyboard=Keyboard())


@bot.on.private_message(StateRule(AuctionState.ENTER_TITLE))
async def auction_enter_title(m: Message):
    parts = states.get(m.from_id).split('*')
    auction_id = int(parts[1])
    await db.Auction.update.values(title=m.text).where(db.Auction.id == auction_id).gino.status()
    states.set(m.from_id, f'{AuctionState.ENTER_DESCRIPTION}*{auction_id}')
    await m.answer('Введите описание лота:', keyboard=Keyboard())


@bot.on.private_message(StateRule(AuctionState.ENTER_DESCRIPTION))
async def auction_enter_description(m: Message):
    parts = states.get(m.from_id).split('*')
    auction_id = int(parts[1])
    await db.Auction.update.values(description=m.text).where(db.Auction.id == auction_id).gino.status()
    states.set(m.from_id, f'{AuctionState.ENTER_START_PRICE}*{auction_id}')
    await m.answer('Введите стартовую цену (целое число):', keyboard=Keyboard())


@bot.on.private_message(StateRule(AuctionState.ENTER_START_PRICE), NumericRule(min_number=0))
async def auction_enter_start_price(m: Message, value: int):
    parts = states.get(m.from_id).split('*')
    auction_id = int(parts[1])
    await db.Auction.update.values(start_price=value).where(db.Auction.id == auction_id).gino.status()
    states.set(m.from_id, f'{AuctionState.ENTER_MIN_BET}*{auction_id}')
    await m.answer('Введите минимальную ставку (целое число):', keyboard=Keyboard())


@bot.on.private_message(StateRule(AuctionState.ENTER_MIN_BET), NumericRule(min_number=1))
async def auction_enter_min_bet(m: Message, value: int):
    parts = states.get(m.from_id).split('*')
    auction_id = int(parts[1])
    await db.Auction.update.values(min_bet=value).where(db.Auction.id == auction_id).gino.status()
    states.set(m.from_id, f'{AuctionState.ENTER_START_AT}*{auction_id}')
    await m.answer(f'Введите дату и время начала аукциона\n(формат: ДД.ММ.ГГГГ чч:мм:сс)\n\n'
                   f'Или нажмите кнопку для немедленного начала:',
                   keyboard=Keyboard().add(Text('Начать сейчас', {'auction_start': 'now'}), KeyboardButtonColor.PRIMARY))


@bot.on.private_message(StateRule(AuctionState.ENTER_START_AT), PayloadRule({'auction_start': 'now'}))
async def auction_start_now(m: Message):
    parts = states.get(m.from_id).split('*')
    auction_id = int(parts[1])
    await db.Auction.update.values(start_at=datetime.datetime.now()).where(
        db.Auction.id == auction_id).gino.status()
    states.set(m.from_id, f'{AuctionState.ENTER_END_AT}*{auction_id}')
    await m.answer(f'Введите дату и время завершения аукциона\n(формат: ДД.ММ.ГГГГ чч:мм:сс):',
                   keyboard=Keyboard())


@bot.on.private_message(StateRule(AuctionState.ENTER_START_AT))
async def auction_enter_start_at(m: Message):
    try:
        dt = datetime.datetime.strptime(m.text, DATETIME_FORMAT)
    except ValueError:
        await m.answer(f'Неверный формат. Используйте: {DATETIME_FORMAT}')
        return
    parts = states.get(m.from_id).split('*')
    auction_id = int(parts[1])
    await db.Auction.update.values(start_at=dt).where(db.Auction.id == auction_id).gino.status()
    states.set(m.from_id, f'{AuctionState.ENTER_END_AT}*{auction_id}')
    await m.answer(f'Введите дату и время завершения аукциона\n(формат: ДД.ММ.ГГГГ чч:мм:сс):',
                   keyboard=Keyboard())


@bot.on.private_message(StateRule(AuctionState.ENTER_END_AT))
async def auction_enter_end_at(m: Message):
    try:
        dt = datetime.datetime.strptime(m.text, DATETIME_FORMAT)
    except ValueError:
        await m.answer(f'Неверный формат. Используйте: {DATETIME_FORMAT}')
        return
    if dt <= datetime.datetime.now():
        await m.answer('Время окончания должно быть в будущем.')
        return
    parts = states.get(m.from_id).split('*')
    auction_id = int(parts[1])
    await db.Auction.update.values(end_at=dt).where(db.Auction.id == auction_id).gino.status()
    states.set(m.from_id, f'{AuctionState.SELECT_TYPE}*{auction_id}')
    await m.answer('Выберите тип аукциона:', keyboard=public_private_kb)


@bot.on.private_message(StateRule(AuctionState.SELECT_TYPE), PayloadRule({'auction_type': 'public'}))
async def auction_set_public(m: Message):
    await _finalize_auction_type(m, is_public=True)


@bot.on.private_message(StateRule(AuctionState.SELECT_TYPE), PayloadRule({'auction_type': 'private'}))
async def auction_set_private(m: Message):
    await _finalize_auction_type(m, is_public=False)


async def _finalize_auction_type(m: Message, is_public: bool):
    """Финализация создания аукциона — сохраняет тип и запускает."""
    parts = states.get(m.from_id).split('*')
    auction_id = int(parts[1])
    await db.Auction.update.values(is_public=is_public).where(db.Auction.id == auction_id).gino.status()

    auction = await db.Auction.get(auction_id)
    lot_text = await _get_lot_description(auction)

    kb = Keyboard().add(
        Text('✅ Подтвердить создание', {'auction_confirm': auction_id}), KeyboardButtonColor.POSITIVE
    ).row().add(
        Text('❌ Отменить', {'auction_cancel': auction_id}), KeyboardButtonColor.NEGATIVE
    )
    states.set(m.from_id, f'{AuctionState.CONFIRM_CREATE}*{auction_id}')
    await m.answer(f'Проверьте данные аукциона:\n\n{lot_text}', keyboard=kb)


@bot.on.private_message(StateRule(AuctionState.CONFIRM_CREATE), PayloadMapRule({'auction_confirm': int}))
async def confirm_auction_create(m: Message):
    """Подтверждение и запуск аукциона."""
    auction_id = m.payload['auction_confirm']
    auction = await db.Auction.get(auction_id)
    if not auction:
        await m.answer('Аукцион не найден.')
        return

    lot_text = await _get_lot_description(auction)

    if auction.is_public:
        if auction.start_at > now():
            asyncio.get_event_loop().create_task(public_auctions(auction_id))
        else:
            # Публикуем пост на стене
            try:
                post_resp = await user_bot.api.wall.post(
                    owner_id=GROUP_ID,
                    message=f'🏦 Открыт аукцион!\n\n{lot_text}\n\n'
                            f'Сделайте ставку в комментариях в формате: СТАВКА [сумма]\n'
                            f'Например: СТАВКА 500',
                    attachments=auction.photo or '',
                    from_group=True
                )
                post_id = post_resp.post_id
                await db.Auction.update.values(vk_post_id=post_id).where(
                    db.Auction.id == auction_id).gino.status()
            except Exception as e:
                await m.answer(f'Ошибка при публикации поста: {e}')
    else:
        # Закрытый аукцион — рассылка участникам по фильтрам
        await _send_private_auction_invite(auction_id, lot_text)

    # Планируем завершение
    if auction.end_at:
        delay = (auction.end_at - now()).total_seconds()
        if delay > 0:
            asyncio.get_event_loop().create_task(schedule_auction(auction_id))

    states.set(m.from_id, AuctionState.MENU)
    await m.answer('✅ Аукцион успешно создан и запущен!', keyboard=auction_menu_kb)


async def _send_private_auction_invite(auction_id: int, lot_text: str):
    """Рассылает приглашение к закрытому аукциону подходящим игрокам."""
    auction = await db.Auction.get(auction_id)
    frac_id = auction.access_fraction_id
    min_rep = auction.access_reputation or 0

    if frac_id:
        # Только участники с нужной репутацией во фракции
        form_ids = [x[0] for x in
                    await db.select([db.UserToFraction.user_id])
                    .where(
                        (db.UserToFraction.fraction_id == frac_id) &
                        (db.UserToFraction.reputation >= min_rep)
                    ).gino.all()]
    else:
        # Все игроки
        form_ids = [x[0] for x in await db.select([db.Form.user_id]).gino.all()]

    kb = Keyboard(inline=True).add(
        Callback('💰 Сделать ставку', {'auction_bet': auction_id}), KeyboardButtonColor.POSITIVE
    )

    for user_id in form_ids:
        try:
            await bot.api.messages.send(
                peer_id=user_id,
                message=f'🔒 Закрытый аукцион!\n\n{lot_text}',
                keyboard=kb,
                random_id=0
            )
            await asyncio.sleep(0.07)  # Лимиты VK API
        except Exception:
            pass


@bot.on.private_message(StateRule(AuctionState.CONFIRM_CREATE), PayloadMapRule({'auction_cancel': int}))
async def cancel_auction_create(m: Message):
    """Отмена создания аукциона."""
    auction_id = m.payload['auction_cancel']
    await db.AuctionBet.delete.where(db.AuctionBet.auction_id == auction_id).gino.status()
    await db.Auction.delete.where(db.Auction.id == auction_id).gino.status()
    states.set(m.from_id, AuctionState.MENU)
    await m.answer('Создание аукциона отменено.', keyboard=auction_menu_kb)


# ─── Просмотр активных аукционов ─────────────────────────────────────────────

@bot.on.private_message(StateRule(AuctionState.MENU), PayloadRule({'auction': 'active'}))
async def list_active_auctions(m: Message):
    """Список активных (незавершённых) аукционов."""
    auctions = await db.select([db.Auction.id, db.Auction.title, db.Auction.is_public,
                                db.Auction.end_at]).where(
        db.Auction.finished.is_(False)).order_by(db.Auction.id.asc()).gino.all()

    if not auctions:
        await m.answer('Активных аукционов нет.')
        return

    reply = 'Активные аукционы:\n\n'
    for i, (aid, title, is_pub, end_at) in enumerate(auctions):
        kind = '🔓' if is_pub else '🔒'
        ea = end_at.strftime(DATETIME_FORMAT) if end_at else '—'
        reply += f'{i + 1}. {kind} {title} (до {ea})\n'

    kb = Keyboard()
    for i, (aid, title, is_pub, end_at) in enumerate(auctions):
        if i % 2 == 0:
            kb.row()
        kb.add(Text(str(i + 1), {'view_auction': aid}), KeyboardButtonColor.SECONDARY)

    kb.row().add(Text('Назад', {'auction': 'back_to_menu'}), KeyboardButtonColor.NEGATIVE)
    states.set(m.from_id, f'{AuctionState.SELECT_AUCTION}')
    await m.answer(reply, keyboard=kb)


@bot.on.private_message(StateRule(AuctionState.SELECT_AUCTION), PayloadMapRule({'view_auction': int}))
async def view_auction_detail(m: Message):
    """Детали конкретного аукциона + кнопка завершения."""
    auction_id = m.payload['view_auction']
    auction = await db.Auction.get(auction_id)
    if not auction:
        await m.answer('Аукцион не найден.')
        return

    lot_text = await _get_lot_description(auction)
    top = await _get_top_bet(auction_id)
    if top:
        top_form_id, top_amount = top
        top_user_id = await db.select([db.Form.user_id]).where(db.Form.id == top_form_id).gino.scalar()
        top_name = await db.select([db.Form.name]).where(db.Form.id == top_form_id).gino.scalar()
        top_text = f'\n\n🏆 Лидер: [id{top_user_id}|{top_name}] — {top_amount}'
    else:
        top_text = '\n\nСтавок пока нет.'

    kb = Keyboard(inline=True).add(
        Callback('🛑 Завершить аукцион', {'finish_auction': auction_id}), KeyboardButtonColor.NEGATIVE
    )
    await m.answer(lot_text + top_text, keyboard=kb)


@bot.on.raw_event('message_event', MessageEvent, PayloadMapRule({'finish_auction': int}))
async def finish_auction_button(m: MessageEvent):
    """Досрочное завершение аукциона."""
    admin = await db.select([db.User.admin]).where(db.User.user_id == m.user_id).gino.scalar()
    is_judge = await db.select([db.User.judge]).where(db.User.user_id == m.user_id).gino.scalar()
    if not (admin or is_judge):
        await m.show_snackbar('Нет прав')
        return
    auction_id = m.payload['finish_auction']
    await _finish_auction(auction_id)
    await m.show_snackbar('Аукцион завершён!')


# ─── Ставки от пользователей (ЛС бота) ───────────────────────────────────────

@bot.on.raw_event('message_event', MessageEvent, PayloadMapRule({'auction_bet': int}))
async def start_auction_bet(m: MessageEvent):
    """Начало процесса ставки на аукцион."""
    auction_id = m.payload['auction_bet']
    auction = await db.Auction.get(auction_id)
    if not auction or auction.finished:
        await m.show_snackbar('Аукцион уже завершён или не найден.')
        return

    top = await _get_top_bet(auction_id)
    min_allowed = auction.start_price
    if top:
        min_allowed = top[1] + auction.min_bet

    states.set(m.user_id, f'{AuctionState.ENTER_BET}*{auction_id}')
    max_bet = await db.select([*db.AuctionBet]).where(db.AuctionBet.auction_id == auction_id).order_by(db.AuctionBet.amount.desc()).gino.first()
    if max_bet:
        user_id = await db.select([db.Form.user_id]).where(db.Form.id == max_bet.form_id).gino.scalar()
        mention = await create_mention(user_id)
        bet = f'Текущая ставка: {max_bet.amount} {mention}\n'
    else:
        bet = f'Текущая ставка: {auction.start_price} (начальная цена)\n'
    await bot.api.messages.send(
        peer_id=m.user_id,
        message=f'Введите вашу ставку на аукцион «{auction.title}»\n'
                f'{bet}\n'
                f'Минимальная ставка: {min_allowed}',
        random_id=0,
        keyboard=Keyboard().add(
            Text('Отмена', {'auction_bet_cancel': True}), KeyboardButtonColor.NEGATIVE
        )
    )


@bot.on.private_message(StateRule(AuctionState.ENTER_BET))
async def process_auction_bet(m: Message):
    """Обработка введённой ставки."""
    if not m.text.isdigit():
        await m.answer('Введите целое число — размер ставки.')
        return

    parts = states.get(m.from_id).split('*')
    auction_id = int(parts[1])
    amount = int(m.text)

    auction = await db.Auction.get(auction_id)
    if not auction or auction.finished:
        states.set(m.from_id, Menu.MAIN)
        await m.answer('Аукцион уже завершён.')
        return

    top = await _get_top_bet(auction_id)
    min_allowed = auction.start_price
    if top:
        min_allowed = top[1] + auction.min_bet

    if amount < min_allowed:
        await m.answer(f'Ставка слишком маленькая. Минимум: {min_allowed}')
        return

    form_id = await get_current_form_id(m.from_id)
    balance = await db.select([db.Form.balance]).where(db.Form.id == form_id).gino.scalar()
    if balance < amount:
        await m.answer('Недостаточно средств на балансе.')
        return

    # Удаляем предыдущую ставку этого игрока (если была)
    prev = (await db.select([db.AuctionBet.id, db.AuctionBet.amount])
            .where((db.AuctionBet.auction_id == auction_id) &
                   (db.AuctionBet.form_id == form_id)).gino.first())
    if prev:
        await db.AuctionBet.delete.where(db.AuctionBet.id == prev[0]).gino.status()

    await db.AuctionBet.create(auction_id=auction_id, form_id=form_id, amount=amount)

    states.set(m.from_id, Menu.MAIN)
    from service.keyboards import main_menu
    await m.answer(f'✅ Ваша ставка {amount} принята!', keyboard=await main_menu(m.from_id))

    # Уведомляем создателя
    try:
        name = await create_mention(m.from_id)
        creator_id = auction.created_by
        if creator_id:
            await bot.api.messages.send(
                peer_id=creator_id,
                message=f'💰 Новая ставка на аукцион «{auction.title}»: {amount} от {name}',
                random_id=0
            )
    except Exception:
        pass


@bot.on.private_message(StateRule(AuctionState.ENTER_BET), PayloadRule({'auction_bet_cancel': True}))
async def cancel_auction_bet(m: Message):
    """Отмена ставки."""
    states.set(m.from_id, Menu.MAIN)
    from service.keyboards import main_menu
    await m.answer('Ставка отменена.', keyboard=await main_menu(m.from_id))


# ─── Обработка ставок из комментариев к публичному посту ─────────────────────
# Комментарий формата: СТАВКА 500 (или ставка 500)
# Обрабатывается в handlers/chat_commands.py (см. интеграцию ниже)

async def handle_wall_comment_bet(user_id: int, post_id: int, text: str):
    """
    Вызывается из обработчика wall_reply_new.
    Ищет аукцион по post_id и обрабатывает ставку.
    """
    match = re.search(r'ставка\s+(\d+)', text, re.IGNORECASE)
    if not match:
        return
    amount = int(match.group(1))

    auction = await db.select([*db.Auction]).where(
        (db.Auction.vk_post_id == post_id) & (db.Auction.finished.is_(False))
    ).gino.first()
    if not auction:
        return

    form_id = await get_current_form_id(user_id)
    if not form_id:
        return

    top = await _get_top_bet(auction.id)
    min_allowed = auction.start_price
    if top:
        min_allowed = top[1] + auction.min_bet

    if amount < min_allowed:
        try:
            await bot.api.messages.send(
                peer_id=user_id,
                message=f'❌ Ставка {amount} отклонена. Минимально допустимая: {min_allowed}',
                random_id=0
            )
        except Exception:
            pass
        return

    balance = await db.select([db.Form.balance]).where(db.Form.id == form_id).gino.scalar()
    if balance < amount:
        try:
            await bot.api.messages.send(
                peer_id=user_id,
                message='❌ Недостаточно средств на балансе для этой ставки.',
                random_id=0
            )
        except Exception:
            pass
        return

    prev = (await db.select([db.AuctionBet.id]).where(
        (db.AuctionBet.auction_id == auction.id) & (db.AuctionBet.form_id == form_id)
    ).gino.first())
    if prev:
        await db.AuctionBet.delete.where(db.AuctionBet.id == prev[0]).gino.status()

    await db.AuctionBet.create(auction_id=auction.id, form_id=form_id, amount=amount)
    try:
        await bot.api.messages.send(
            peer_id=user_id,
            message=f'✅ Ставка {amount} на аукцион «{auction.title}» принята!',
            random_id=0
        )
    except Exception:
        pass
