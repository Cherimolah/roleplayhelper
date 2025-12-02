"""
Модуль, хранящий очень или не очень полезные функции, используемые много где
"""
import asyncio
import datetime
import os
from typing import List, Tuple, Optional, Union
import re
import random

from sqlalchemy import and_, func
from vkbottle_types.objects import PhotosPhotoSizes
from vkbottle.bot import Message, MessageEvent
import aiofiles
from vkbottle import Keyboard, Callback, KeyboardButtonColor, VKAPIError

from service.db_engine import db, now
from loader import bot, photo_message_uploader, states, user_bot
from service.serializers import fields, Field, RelatedTable, sex_types
import messages
from bot_extended import AioHTTPClientExtended
import service.states
import service.keyboards as keyboards
from config import OWNER, ADMINS
from service.serializers import fields_content, serialize_target_reward, parse_orientation, fraction_levels, parse_cooldown, FormatDataException, serialize_expeditor_debuffs, serialize_expeditor_items

# Регулярные выражения для поиска упоминаний и ссылок
mention_regex = re.compile(r"\[(?P<type>id|club|public)(?P<id>\d*)\|(?P<text>.+)\]")
link_regex = re.compile(r"https:/(?P<type>/|/m.)vk.com/(?P<screen_name>\w*)")
daughter_params_regex = re.compile(r'^(?P<libido>\d+)\s*(?P<word>(или|и))\s*(?P<subordination>\d+)$')
action_regex = re.compile(r'\[(?!id)([^]]+)\]')
mention_regex_cut = re.compile(r'\[id\d+\|')

# Кастомный клиент с отключенной проверкой ssl (подробнее в AioHTTPClientExtended.__help__)
client = AioHTTPClientExtended()


def get_max_size_url(sizes: List[PhotosPhotoSizes]) -> str:
    """
    Получает список размеров фотографии и возвращает ссылку на самую большую
    Т.к. вк использует свой формат объектов фотографии, который никому не понятен, чтобы найти картинку наилучшего
    качества, можно просто перебрать все варианты

    Используется для загрузки фотографии от пользователя
    """
    square = 0
    index = 0
    for i, size in enumerate(sizes):
        if size.height * size.width > square:
            square = size.height * size.width
            index = i
    return sizes[index].url


async def loads_form(user_id: int, from_user_id: int, is_request: bool = None, form_id: int = None, absolute_params: bool = False) -> Tuple[
    str, Optional[str]]:
    """
    Функция, которая сериализует анкету пользователя

    user_id: айди пользователя, чью анкету хотим вывести
    from_user_id: от какого лица просматривается анкета. Это необходимо так как разные игроки могут по разному видеть
    репутации других игроков
    is_request: True - чтобы получить анкету, которая была еще не принята. Используется, когда надо отправить анкету,
    которую пользователь отправил на проверку (после регистрации или редактирования). По умолчанию отправляется уже принятая (проверенная) анкета
    """
    if form_id:
        form = await db.select([*db.Form]).where(db.Form.id == form_id).gino.first()
    elif is_request:
        form = await db.select([*db.Form]).where(
            and_(db.Form.is_request.is_(True), db.Form.user_id == user_id)).gino.first()
    else:
        form = await db.select([*db.Form]).where(db.Form.user_id == user_id).gino.first()
    user = (await bot.api.users.get(user_id))[0]
    if form.profession:
        profession = await db.select([db.Profession.name]).where(db.Profession.id == form.profession).gino.scalar()
    else:
        profession = None
    if form.fraction_id:
        fraction = await db.select([db.Fraction.name]).where(db.Fraction.id == form.fraction_id).gino.scalar()
    else:
        fraction = None
    rep_fraction, reputation = await get_reputation(from_user_id, user_id)
    status = await db.select([db.Status.name]).where(db.Status.id == form.status).gino.scalar()
    reply = f"Анкета пользователя [id{user_id}|{user.first_name} {user.last_name}]:\n\n" \
            f"Имя персонажа: {form.name}\n" \
            f"Должность: {profession or 'не установлена'}\n" \
            f"Биологический возраст: {form.age} Земных лет\n" \
            f"Рост: {form.height} см\n" \
            f"Вес: {form.weight} кг\n" \
            f"Физиологические особенности: {form.features}\n" \
            f"Биография: {form.bio or 'не указана'}\n" \
            f"Харарктер: {form.character or 'не указан'}\n" \
            f"Мотивы нахождения на Space station: {form.motives or 'не указаны'}\n" \
            f"Сексуальная ориентация: {parse_orientation(form.orientation)}\n" \
            f"Фетиши: {form.fetishes or 'не указаны'}\n" \
            f"Табу: {form.taboo or 'не указаны'}\n" \
            f"Каюта: {form.cabin or 'не присвоена'}\n" \
            f"Тип каюты: {await db.select([db.Cabins.name]).where(db.Cabins.id == form.cabin_type).gino.scalar() or 'не указан'}\n" \
            f"Баланс: {form.balance}\n" \
            f"Статус: {status}\n" \
            f"Фракция: {fraction or 'не установлена'}\n" \
            f"Репутация: {reputation} ({rep_fraction})\n"
    # Добавляем специальные параметры для дочерей
    if form.status == 2:
        libido, subordination = await count_daughter_params(user_id)
        if not absolute_params:
            # Преобразуем числовые значения в текстовые диапазоны
            if 1 <= subordination <= 33:
                reply += 'Уровень подчинения: Низкий\n'
            elif 34 <= subordination <= 66:
                reply += 'Уровень подчинения: Средний\n'
            elif 67 <= subordination <= 100:
                reply += 'Уровень подчинения: Высокий\n'
            if 1 <= libido <= 33:
                reply += 'Уровень либидо: Низкий\n'
            elif 34 <= libido <= 66:
                reply += 'Уровень либидо: Средний\n'
            elif 67 <= libido <= 100:
                reply += 'Уровень либидо: Высокий\n'
        else:
            reply += (f'Уровень подчинения: {subordination}\n'
                      f'Уровень либидо: {libido}\n')
        # Показываем бонусные параметры для админов
        admin_request = await db.select([db.User.admin]).where(db.User.user_id == from_user_id).gino.scalar()
        if admin_request:
            reply += (f'Базовое либидо: {form.libido_level}\nБазовое подчинению: {form.subordination_level}\n'
                      f'Бонус к либидо: {form.libido_bonus}\nБонус к подчинению: {form.subordination_bonus}')
    return reply, form.photo


async def show_expeditor(expeditor_id: int, from_user_id) -> str:
    """
    Похоже как и loads_form() только выводит информацию о карте экспедитора
    expeditor_id: айди экспедитора из таблицы db.Expeditor
    from_user_id: айди пользователя, кто просматривает карту. Необходимо для правильного отображения репутации
    """
    expeditor = await db.Expeditor.get(expeditor_id)
    form = await db.Form.get(expeditor.form_id)
    user_id = form.user_id
    user = (await bot.api.users.get(user_id))[0]
    race = await db.select([db.Race.name]).where(db.Race.id == expeditor.race_id).gino.scalar()
    profession = await db.select([db.Profession.name]).where(db.Profession.id == form.profession).gino.scalar()
    fraction = await db.select([db.Fraction.name]).where(db.Fraction.id == form.fraction_id).gino.scalar()
    rep_fraction, reputation = await get_reputation(from_user_id, user_id)
    reply = (f'Карта экспедитора пользователя [id{user_id}|{user.first_name} {user.last_name}]:\n\n'
             f'Имя персонажа: {form.name}\n'
             f'Возраст: {form.age} Земных лет\n'
             f'Пол: {sex_types[expeditor.sex]}\n'
             f'Раса: {race}\n'
             f'Специальность: {profession}\n'
             f'Фракция: {fraction}\n'
             f'Репутация: {reputation} ({rep_fraction})\n\n')
    # Получаем атрибуты экспедитора
    attributes = await db.select([db.ExpeditorToAttributes.attribute_id, db.ExpeditorToAttributes.value]).where(db.ExpeditorToAttributes.expeditor_id == expeditor_id).gino.all()
    # Получаем бонусы от профессии и расы
    profession_bonuses = await db.select([db.ProfessionBonus.attribute_id, db.ProfessionBonus.bonus]).where(db.ProfessionBonus.profession_id == form.profession).gino.all()
    race_bonuses = await db.select([db.RaceBonus.attribute_id, db.RaceBonus.bonus]).where(db.RaceBonus.race_id == expeditor.race_id).gino.all()
    # Получаем активные предметы и дебафы
    active_items = [x[0] for x in await db.select([db.ExpeditorToItems.item_id]).select_from(
        db.ActiveItemToExpeditor.join(db.ExpeditorToItems, db.ActiveItemToExpeditor.row_item_id == db.ExpeditorToItems.id)
    ).where(
        db.ActiveItemToExpeditor.expeditor_id == expeditor_id).gino.all()]
    active_debuffs = [x[0] for x in await db.select([db.ExpeditorToDebuffs.debuff_id]).where(
        db.ExpeditorToDebuffs.expeditor_id == expeditor_id).gino.all()]

    # Здесь идет поиск всех бафов и дебафов, которые есть у игрока
    for attribute_id, value in attributes:
        attribute = await db.select([db.Attribute.name]).where(db.Attribute.id == attribute_id).gino.scalar()
        profession_bonus = 0
        for at_id, bonus in profession_bonuses:
            if at_id == attribute_id:
                profession_bonus = bonus
                break
        race_bonus = 0
        for at_id, bonus in race_bonuses:
            if at_id == attribute_id:
                race_bonus = bonus
                break
        summary = value + profession_bonus + race_bonus
        description = ''
        if profession_bonus:
            description += f' {"+" if profession_bonus >= 0 else "-"} {abs(profession_bonus)} от профессии'
        if race_bonus:
            description += f' {"+" if race_bonus >= 0 else "-"} {abs(race_bonus)} от расы'
        # Учитываем бонусы от активных предметов
        if active_items:
            for active_item_id in active_items:
                item_name, item_bonus = await db.select([db.Item.name, db.Item.bonus]).where(db.Item.id == active_item_id).gino.first()
                for bonus in item_bonus:
                    if bonus.get('type') == 'attribute' and bonus.get('attribute_id') == attribute_id:
                        description += f' {"+" if bonus['bonus'] >= 0 else "-"} {abs(bonus["bonus"])} от «{item_name}»'
                        summary += bonus['bonus']
                        break
        # Учитываем штрафы от активных дебафов
        if active_debuffs:
            for active_debuf_id in active_debuffs:
                attribute_type = await db.select([db.StateDebuff.attribute_id]).where(db.StateDebuff.id == active_debuf_id).gino.scalar()
                if attribute_id == attribute_type:
                    debuff_name, debuff_penalty = await db.select([db.StateDebuff.name, db.StateDebuff.penalty]).where(
                        db.StateDebuff.id == active_debuf_id).gino.first()
                    description += f' {"+" if debuff_penalty >= 0 else "-"} {abs(debuff_penalty)} от «{debuff_name}»'
                    summary += debuff_penalty

        # Учитываем штраф от невыполнения доп. целей дочерей
        penalties = sum([x[0] for x in await db.select([db.AttributePenalties.value]).where(
            and_(db.AttributePenalties.attribute_id == attribute_id, db.AttributePenalties.expeditor_id == expeditor_id)
        ).gino.all()])
        if penalties != 0:
            description += f' {"+" if penalties >= 0 else "-"} {abs(penalties)} от штрафов за невыполнение квестов дочерей'
            summary += penalties

        summary = min(max(0, summary), 200)

        reply += f'{attribute}: {summary} ({value} базовое{description})\n'
    # Добавляем информацию о дебафах и предметах
    reply += await serialize_expeditor_debuffs(expeditor_id)
    reply += '\n\n'
    reply += f'Оплодотворение: {expeditor.pregnant if expeditor.pregnant else 'Отсутствует'}\n\n'
    reply += await serialize_expeditor_items(expeditor_id)
    return reply


async def create_mention(user_id: int):
    """
    Утилита создающая упоминание из айди игрока
    """
    user = (await bot.api.users.get(user_id))[0]
    nickname = await db.select([db.Form.name]).where(db.Form.user_id == user_id).gino.scalar()
    return f"[id{user.id}|{user.first_name} {user.last_name} / {nickname}]"


async def parse_ids(m: Message) -> List[int]:
    """
    Утилита, которая находит айди пользователя(-ей), котоыре указаны в сообщении.
    Если было переслано сообщение то возвращает айди чьё сообщение было переслано.
    Если пересланных не было ищет упоминания и ссылки, из них извлекает айди пользователей
    """
    if m.reply_message:
        return [m.reply_message.from_id]
    if m.fwd_messages:
        return [x.from_id for x in m.fwd_messages]
    user_ids = []
    text = m.text.lower()
    screen_names: List[str] = [x[1] for x in re.findall(link_regex, text)]
    screen_names.extend([x[1] for x in re.findall(mention_regex, text)])
    if screen_names:
        for screen_name in screen_names:
            if screen_name.isdigit():
                user_ids.append(int(screen_name))
            else:
                obj = await bot.api.utils.resolve_screen_name(screen_name)
                if obj.type == obj.type.USER:
                    user_ids.append(obj.object_id)
    # Ищем пользователей по имени персонажа
    names = list(map(lambda x: x.lower(), m.text.split("\n")))
    user_ids.extend([x[0] for x in await db.select([db.Form.user_id]).where(
        func.lower(db.Form.name).in_(names)
    ).gino.all()])
    return user_ids


async def get_mention_from_message(m: Message, many_users=False) -> Optional[Union[int, List[int]]]:
    """
    Функция обертка над parse_ids(), она дополнительно может вытащить айди пользователей по их имени персонажа.

    many_users: флаг одного пользователя вытащить или нескольких. Если одного возвращается int, если нескольких - list[int]
    """
    user_ids = [x for x in await parse_ids(m) if x > 0]
    names = m.text.split("\n")
    for name in names:
        user_id = await db.select([db.Form.user_id]).where(
            and_(func.lower(db.Form.name) == name.lower(), db.Form.is_request.is_(False))
        ).gino.scalar()
        if user_id:
            user_ids.append(user_id)
    if many_users:
        return user_ids
    if len(user_ids) > 0:
        return user_ids[0]
    return None


async def reload_image(attachment, name: str, delete: bool = False):
    """
    Функция, для "перезагрузки изображения". Т.к. айди фотографий пользователей со временем могут стать для бота
    недоступны, рекомендуется скачать и загрузить фото от лица бота
    """
    # Получаем URL самой большой версии фото
    photo_url = get_max_size_url(attachment.photo.sizes)
    # Скачиваем изображение
    response = await client.request_content(photo_url)
    # Создаем директорию если нужно
    if not os.path.exists("/".join(name.split("/")[:-1])):
        os.mkdir("/".join(name.split("/")[:-1]))
    # Сохраняем файл
    async with aiofiles.open(name, mode="wb") as file:
        await file.write(response)
    # Загружаем фото от имени бота
    photo = None
    for i in range(5):
        try:
            photo = await photo_message_uploader.upload(name, peer_id=OWNER)
            break
        except VKAPIError:
            await asyncio.sleep(2)
    if not photo:
        raise Exception("Photo upload failed")
    # Удаляем временный файл если нужно
    if delete:
        os.remove(name)
    return photo


def parse_daughter_params(text: str) -> tuple[int, int, int]:
    """
    Парсит параметры дочерей для установки этого значения в доп. целях у дочерей

    Строка должна состоять из 3 значений: уровень либидо, правило, уровень подчинения.
    Правилом может быть "или" или "и".
    Например: "1 или 20" , "5 и 10"
    """
    match = re.fullmatch(daughter_params_regex, text.lower())
    if not match:
        raise FormatDataException('Неправильный формат данных. Можно указать только один фильтр')
    libido = int(match.group('libido'))
    word = int(match.group('word') == 'или')
    subordination = int(match.group('subordination'))
    if not 0 <= libido <= 100 or not 0 <= subordination <= 100:
        raise FormatDataException('Либидо и подчинение должны находиться в диапазоне [0; 100]')
    return libido, word, subordination


async def send_mailing(sleep, message_id, mailing_id):
    """
    Делает рассылку через отведенное количество секунд

    sleep: количество секунд, через которое необходимо сделать рассылку
    message_id: айди сообщение, которое будет переслано
    mailing_id: айди рассылки из db.Mailing
    """
    await asyncio.sleep(sleep)
    # Получаем всех пользователей
    user_ids = [x[0] for x in await db.select([db.User.user_id]).gino.all()]
    # Отправляем сообщение пачками по 100 пользователей
    for i in range(0, len(user_ids), 100):
        await bot.api.messages.send(peer_ids=user_ids[i:i + 100], forward_messages=message_id, is_notification=True)
    # Удаляем запись о рассылке
    await db.Mailings.delete.where(db.Mailings.id == mailing_id).gino.status()


async def take_off_payments(form_id: int):
    """
    Функция, которая снимает арендную плату за проживание один раз в неделю. Работает в бэклоге
    """
    while True:
        info = await db.select([db.Form.balance, db.Form.freeze]).where(db.Form.id == form_id).gino.first()
        if not info:  # Анкета удалена
            return
        balance, freeze = info
        # Если баланс отрицательный или анкета заморожена - ждем сутки
        if not balance or balance < 0 or freeze:
            await asyncio.sleep(86400)  # Ждём сутки, вдруг появятся деньги или анкета разморозится
            continue
        last_payment: datetime.datetime = await db.select([db.Form.last_payment]).where(
            db.Form.id == form_id).gino.scalar()
        today = datetime.datetime.now()
        delta = today - last_payment
        user_id = await db.select([db.Form.user_id]).where(db.Form.id == form_id).gino.scalar()
        # Если прошло 7 дней или больше - списываем оплату
        if delta.days >= 7:
            cabin_type = await db.select([db.Form.cabin_type]).where(db.Form.id == form_id).gino.scalar()
            if cabin_type:
                # Считаем стоимость каюты и функционального декора
                price = await db.select([db.Cabins.cost]).where(db.Cabins.id == cabin_type).gino.scalar()
                func_price = sum([soft_divide(x[0], 10) for x in await db.select([db.Decor.price]).select_from(
                    db.UserDecor.join(db.Decor, db.UserDecor.decor_id == db.Decor.id)
                ).where(and_(db.UserDecor.user_id == user_id, db.Decor.is_func.is_(True))).gino.all()])
                price += func_price
                # Списание средств
                await db.Form.update.values(balance=db.Form.balance - price,
                                            last_payment=today - datetime.timedelta(seconds=20)).where(
                    db.Form.id == form_id
                ).gino.status()
                # Уведомление пользователя
                group_id = (await bot.api.groups.get_by_id()).groups[0].id
                if (await bot.api.messages.is_messages_from_group_allowed(group_id, user_id=user_id)).is_allowed:
                    await bot.api.messages.send(peer_id=user_id, message=f"Снята арендная плата в размере {price}\n"
                                                                         f"Доступно на балансе: {balance - price}",
                                                is_notification=True)
                await asyncio.sleep(604800)  # Следующее списание через неделю
            else:
                await asyncio.sleep(86400)  # Каюта может быть не присвоена подождём сутки, вдруг появится
                continue
        else:
            # Ждём пока не пройдёт неделя до следующего списания
            next_payment = last_payment + datetime.timedelta(days=7)
            await asyncio.sleep(int((next_payment - today).total_seconds()) + 1)


async def send_page_users(m: Union[Message, MessageEvent], page: int = 1):
    """
    Функция, которая выводит список пользователей с их роялми.
    Используется в админ панели -> управление администраторами
    """
    users = await db.select([db.User.user_id, db.User.admin, db.User.judge]).order_by(db.User.admin.desc()).order_by(db.User.judge.desc()).order_by(
        db.User.user_id.asc()).offset((page - 1) * 15).limit(15).gino.all()
    user_ids = [x[0] for x in users]
    users_info = await bot.api.users.get(user_ids)
    reply = messages.list_users
    for i, user in enumerate(users):
        reply = (f"{reply}{(page - 1) * 15 + i + 1}. {'👑' if user.admin == 2 else '🅰' if user.admin == 1 else ''}"
                 f"{'🧑‍⚖️' if user.judge else ''}"
                 f" [id{user.user_id}|{users_info[i].first_name} {users_info[i].last_name}]\n")
    keyboard = None
    count_users = await db.func.count(db.User.user_id).gino.scalar()
    if count_users % 15 == 0:
        count_pages = count_users // 15
    else:
        count_pages = count_users // 15 + 1
    reply = f"{reply}\n\nСтраница {page}/{count_pages}"
    # Создаем клавиатуру пагинации если нужно
    if page > 1 or page * 15 < count_users:
        keyboard = Keyboard(inline=True)
        if page > 1:
            keyboard.add(Callback("<-", {"users_list": page - 1}), KeyboardButtonColor.PRIMARY)
        if page * 15 < count_users:
            keyboard.add(Callback("->", {"users_list": page + 1}), KeyboardButtonColor.PRIMARY)
    if isinstance(m, Message):
        await m.answer(reply, keyboard=keyboard)
    elif isinstance(m, MessageEvent):
        await m.edit_message(reply, keyboard=keyboard)


async def get_current_form_id(user_id: int) -> int:
    """
    Функция, которая возвращает айди анкету по айди пользователя
    """
    return await db.select([db.Form.id]).where(db.Form.user_id == user_id).gino.scalar()


# Здесь указаны варианты написания временных промежутков. Они используются в parse_period()
years = [
    "год", "года", "лет"
]
months = [
    "мес", "месяцев", "месяц", "месяца"
]
weeks = [
    "неделя", "недель", "недели"
]
days = [
    "день", "дня", "дней",
]
hours = [
    "час", "часа", "часов"
]
minutes = [
    "минуты", "мин", "минут", "минута"
]
seconds = [
    "сек", "секунды", "секунда", "секунд", "секунду"
]


def parse_period(text: str) -> Optional[int]:
    """
    Функция для того чтобы преобразовать текст в количество секунд.
    Напримр, для указания того, сколько времени будет на выполнение дейлика, пользователь может написать "1 день",
    функция преобразует такую строку в 86400 секунд
    """
    params = text.lower().split(" ")
    last_number = 0
    total = 0
    for index, param in enumerate(params):
        if index % 2 == 0:
            if not param.isdigit():
                return
            last_number = int(param)
        else:
            if param.isdigit():
                return
            # Суммируем секунды в зависимости от единицы измерения
            if param in years:
                total += last_number * 31536000
            elif param in months:
                total += last_number * 2592000
            elif param in weeks:
                total += last_number * 604800
            elif param in days:
                total += last_number * 86400
            elif param in hours:
                total += last_number * 3600
            elif param in minutes:
                total += last_number * 60
            elif param in seconds:
                total += last_number
            last_number = 0
    return total


async def quest_over(seconds, form_id, quest_id):
    """
    Функция-таймер, которая по истечению времени выпишет штраф игроку, если он не выполнил квест
    """
    if not seconds:
        return
    await asyncio.sleep(seconds)
    # Проверяем что квест все еще активен
    active_quest = await db.select([db.QuestToForm.quest_id]).where(db.QuestToForm.form_id == form_id).gino.scalar()
    if active_quest != quest_id:
        return
    user_id = await db.select([db.Form.user_id]).where(db.Form.id == form_id).gino.scalar()
    name, penalty = await db.select([db.Quest.name, db.Quest.penalty]).where(db.Quest.id == quest_id).gino.first()
    # Удаляем квест из активных
    await db.QuestToForm.delete.where(db.QuestToForm.form_id == form_id).gino.status()
    reply = f"Время выполнения квеста «{name}» завершилось"
    # Применяем штраф если есть
    if penalty:
        reply += "\nВам выписан штраф:\n\n"
        await apply_reward(user_id, penalty)
        reply += await serialize_target_reward(penalty)
    await bot.api.messages.send(peer_id=user_id, message=reply, is_notification=True)


def calculate_time(quest: db.Quest, starts_at: datetime.datetime) -> int | None:
    """
    Функция необходима, чтобы вычислить сколько времени остается на выполнение дейлика у игрока
    Так как у дейлика есть время, когда он в принципе заканчивается и время, которое дается на выполнение.
    Нельзя выполнять дейлик, когда он уже завершился.

    Функция высчитывает сколько секунд остается до ближайшего события (конец дейлика / время на выполнение)
    """
    if not quest.closed_at:
        if quest.execution_time:
            ends_at = starts_at + datetime.timedelta(seconds=quest.execution_time)
            execution_time = (ends_at - datetime.datetime.now()).total_seconds()
        else:
            execution_time = None
    else:
        if not quest.execution_time:
            execution_time = (quest.closed_at - datetime.datetime.now()).total_seconds()
        else:
            ends_at = starts_at + datetime.timedelta(seconds=quest.execution_time)
            nearest = min(quest.closed_at.timestamp(), ends_at.timestamp())
            execution_time = nearest - datetime.datetime.now().timestamp()
    return execution_time


async def check_quest_completed(form_id: int) -> bool:
    """
    Проверяет все ли элементы квеста (сам квест и доп. цели к нему) выполнены
    Необходимо, чтобы понять можно ли квест удалять из активного у игрока или нет
    """
    quest_id, target_ids = await db.select([db.QuestToForm.quest_id, db.QuestToForm.active_targets]).where(
        db.QuestToForm.form_id == form_id
    ).gino.first()
    # Проверяем выполнен ли основной квест
    ready_quest = await db.select([db.ReadyQuest.id]).where(
        and_(db.ReadyQuest.quest_id == quest_id, db.ReadyQuest.form_id == form_id, db.ReadyQuest.is_claimed.is_(True))
    ).gino.scalar()
    # Проверяем выполнены ли все цели
    completed_targets = set()
    for target_id in target_ids:
        is_claimed = await db.select([db.ReadyTarget.is_claimed]).where(
            and_(db.ReadyTarget.form_id == form_id, db.ReadyTarget.target_id == target_id, db.ReadyTarget.is_claimed.is_(True))).gino.scalar()
        if is_claimed:
            completed_targets.add(target_id)
    target_ids = set(target_ids)
    ready_targets = target_ids == completed_targets
    return ready_quest and ready_targets


def calculate_wait_time(hours: int = 0, minutes: int = 0, seconds: int = 0) -> float:
    """
    Функция, которая расчитывает сколько секунд до следующего тайминга.
    Примерно как вы ставите будильник, если времени сейчас уже поздно, то следующий звонок завтра
    """
    today = now()
    expected = datetime.datetime(today.year, today.month, today.day, hours, minutes, seconds, tzinfo=datetime.timezone(datetime.timedelta(hours=3)))
    if today > expected:
        expected = expected + datetime.timedelta(days=1)
    return (expected - today).total_seconds()


async def send_daylics():
    """
    Функция, которая записывает новый дейлик пользователям и рассылает уведомление о новом дейлике
    """
    await asyncio.sleep(5)  # Wait for initialize gino
    while True:
        # Считаем время до следующего обновления.
        today = now()
        if 0 <= today.weekday() <= 2:
            next_time = today + datetime.timedelta(days=3-today.weekday())
        else:
            next_time = today + datetime.timedelta(days=7 - today.weekday())
        next_time = datetime.datetime(next_time.year, next_time.month, next_time.day, 0, 0, 0,
                                      tzinfo=datetime.timezone(datetime.timedelta(hours=3)))
        await asyncio.sleep((next_time - now()).total_seconds())
        data = await db.select([db.Form.id, db.Form.user_id]).where(db.Form.is_request.is_(False)).gino.all()
        for form_id, user_id in data:
            profession_id = await db.select([db.Form.profession]).where(db.Form.id == form_id).gino.scalar()
            # Получаем использованные дейлики
            daylic_used = [x[0] for x in await db.select([db.DaylicHistory.daylic_id]).where(db.DaylicHistory.form_id == form_id).gino.all()]
            # Ищем новый дейлик
            # Если сейчас день недели пн-ср берем Выходной дейлик (см. README)
            # Если сейчас день недели чт-вс берем Обычный дейлик
            if 0 <= next_time.weekday() <= 2:
                daylic = await db.select([db.Daylic.id]).where(and_(db.Daylic.profession_id == profession_id,
                                                                             db.Daylic.chill.is_(True))).order_by(func.random()).gino.scalar()
            else:
                daylic = await db.select([db.Daylic.id]).where(and_(
                    db.Daylic.profession_id == profession_id, db.Daylic.id.notin_(daylic_used), db.Daylic.chill.is_(False))).order_by(
                    func.random()).gino.scalar()
                if not daylic:  # all daylics used, try clean pool
                    await db.DaylicHistory.delete.where(db.DaylicHistory.form_id == form_id).gino.status()
                    daylic = await db.select([db.Daylic.id]).where(
                        and_(db.Daylic.profession_id == profession_id, db.Daylic.chill.is_(False))).order_by(func.random()).gino.scalar()
            if daylic:
                await db.DaylicHistory.create(form_id=form_id, daylic_id=daylic)
                await db.Form.update.values(activated_daylic=daylic, daylic_completed=False).where(db.Form.id == form_id).gino.status()
                # У кого анкета заморожена присылать уведомление не будем
                freeze = await db.select([db.Form.freeze]).where(db.Form.id == form_id).gino.scalar()
                if not freeze:
                    await bot.api.messages.send(peer_id=user_id, message="Вам доступно новое еженедельное задание!",
                                                is_notification=True)
        await db.Metadata.update.values(last_daylic_date=datetime.datetime.now()).gino.status()
        await asyncio.sleep(5)


async def show_fields_edit(user_id: int, new=True):
    """
    Отправляет анкету, отредактированный пользователем вариант
    Используется, когда пользователь редактирует свою анкету, выводить промежуточный вариант

    new: флаг, если True - создаст новую анкету
    """
    if new:
        # Создаем копию анкеты для редактирования
        form = dict(await db.select([*db.Form]).where(db.Form.user_id == user_id).gino.first())
        params = {k: v for k, v in form.items() if k not in ("id", "is_request")}
        params['is_request'] = True
        await db.Form.create(**params)
        await db.User.update.values(editing_form=True).where(db.User.user_id == user_id).gino.status()
    states.set(user_id, service.states.Menu.SELECT_FIELD_EDIT_NUMBER)
    reply = ("Выберите поле для редактирования. "
             "Когда закончите нажмите кнопку «Подтвердить изменения»\n\n")
    for i, field in enumerate(fields):
        reply += f"{i + 1}. {field.name}\n"
    await bot.api.messages.send(message=reply, keyboard=keyboards.confirm_edit_form, peer_id=user_id)


async def page_content(table_name, page: int) -> Tuple[str, Optional[Keyboard]]:
    """
    Функция для пагинации по типу контента в админ панели -> редактирование контента
    """
    table = getattr(db, table_name)
    names = [x[0] for x in
             await db.select([table.name]).order_by(table.id.asc()).offset((page - 1) * 15).limit(15).gino.all()]
    count = await db.select([func.count(table.id)]).gino.scalar()
    if count % 15 == 0:
        pages = count // 15
    else:
        pages = count // 15 + 1
    keyboard = Keyboard(inline=True)
    if not names:
        return "На данный момент ничего не создано", keyboard
    reply = f"Отправьте число, для редактирования:\n\n"
    for i, name in enumerate(names):
        reply += f"{(page - 1) * 15 + i + 1}. {name}\n"
    # Добавляем кнопки пагинации
    if page > 1:
        keyboard.add(Callback("<-", {"content_page": page - 1, "content": table_name}), KeyboardButtonColor.SECONDARY)
    if page * 15 < count:
        keyboard.add(Callback("->", {"content_page": page + 1, "content": table_name}), KeyboardButtonColor.SECONDARY)
    if pages > 1:
        reply += f"\nСтраница {page}/{pages}\n\n"
    return reply, keyboard


async def send_content_page(m: Union[Message, MessageEvent], table_name: str, page: int):
    """
    Эта функция отправляет страницу контента с названиями элементов
    Используется при пагинации и после удаления элемента
    """
    reply, keyboard = await page_content(table_name, page)
    if isinstance(m, Message):
        await m.answer(messages.select_action, keyboard=keyboards.gen_type_change_content(table_name))
        await m.answer(reply, keyboard=keyboard)
    else:
        await m.send_message(reply, keyboard=keyboard)


def parse_reputation(rep_level: int) -> str:
    """
    Переводит уровень репутации из числа в строковое название
    """
    for level, name in fraction_levels.items():
        if rep_level >= level:
            return name
    return 'Не опознанный уровень'


async def get_reputation(from_user_id: int, to_user_id: int) -> Tuple[str, str]:
    """
    Функция для определения какую репутацию показывать пользователю при просмотре анкеты.

    from_user_id: айди пользователя, кто смотрит анкету
    to_user_id: айди пользователя, ЧЬЮ анкету смотрят

    Правило: если пользователь, который просматривает анкету, имеет репутацию во фракции, в которой состоит
    пользователь, чью анкету просматривают, показывать следует репутацию в этой фракции
    В ином случае, показывается репутация (и фракция) с самым большим уровнем
    """
    # Фракция пользователя, чью анкету просматривают
    fraction_id = await db.select([db.Form.fraction_id]).where(db.Form.user_id == to_user_id).gino.scalar()
    # Есть ли репутация у того, кто смотрит анкету в этой фракции
    has_rep = await db.select([db.UserToFraction.id]).where(
        and_(db.UserToFraction.user_id == from_user_id, db.UserToFraction.fraction_id == fraction_id)
    ).gino.scalar()
    if has_rep:
        # Если есть, то показывается репутация во фракции, в которой состоит пользователь, чью анкету смотрят
        reputation = await db.select([db.UserToFraction.reputation]).where(
            and_(db.UserToFraction.user_id == to_user_id, db.UserToFraction.fraction_id == fraction_id)
        ).gino.scalar()
        name = await db.select([db.Fraction.name]).where(db.Fraction.id == fraction_id).gino.scalar()
        return name, parse_reputation(reputation)
    else:
        # Если же нет репутации показывается максимальная репутация
        max_rep, fraction_id = await db.select([db.UserToFraction.reputation, db.UserToFraction.fraction_id]).where(
            and_(db.UserToFraction.user_id == to_user_id, db.UserToFraction.fraction_id == fraction_id)
        ).order_by(db.UserToFraction.reputation.desc()).gino.first()
        name = await db.select([db.Fraction.name]).where(db.Fraction.id == fraction_id).gino.scalar()
        return name, parse_reputation(max_rep)


def allow_edit_content(content_type: str, end: bool = False, text: str = None, state: str = None, keyboard=None):
    """
    Функция помогающая в редактировании характеристик контента
    """
    def decorator(function):
        async def wrapper(m: Message, value=None, form=None, *args, **kwargs):
            # value и form аргументы прокидываются дальше после фильтров
            # В хендлере могут стоять фильтры, которые передают эти аргументы, поэтому их нужно прокинуть в функцию
            kwargs["m"] = m
            if value:
                kwargs["value"] = value
            if form:
                kwargs["form"] = form
            # Айди объекта, который создается/редактируется
            item_id = int(states.get(m.from_id).split("*")[1])
            editing_content = await db.select([db.User.editing_content]).where(
                db.User.user_id == m.from_id).gino.scalar()
            # Флаг того редактируется ли объект или нет
            # Это передается в функцию обработчик для удобства, чтобы каждый раз не вытягивать это из стейта
            # По айди можно понять в каком объекте что-то редактируется, а по флагу editing_content определить надо
            # переходить к следующему стейту (при создании) или вернуться к выбору полей для редактирования (при редактировании)
            kwargs['editing_content'] = editing_content
            kwargs['item_id'] = item_id
            # Вызывается функция обработчик, ловится ошибка FormatDataException
            # Это специальный тип исключения, который следует вызывать если пользователь ввел неверные данные
            # Когда ловится эта ошибка мы сообщаем о том, что пользователь ввел неверные данные и не переключаем стейт
            try:
                data = await function(**kwargs)
            except FormatDataException as e:
                await m.answer(f"Неправильный формат данных!\n{e}")
                return
            # Если редактировался контент, сообщаем о том, что поле изменено и отправляем описание объекта
            if editing_content:
                await m.answer("Новое значение успешно установлено")
                await send_edit_item(m.from_id, item_id, content_type)
            # Если же нет, то переносим стейт на следующий и, если передан текст следующего сообщения отправляем его
            else:
                if state:
                    states.set(m.from_id, f"{state}*{item_id}")
                if text:
                    await m.answer(text, keyboard=keyboard)
                if end:
                    # При завершении возвращаем пользователя в меню выбора контента
                    await send_content_page(m, content_type, 1)
                    states.set(m.from_id, str(service.states.Admin.SELECT_ACTION) + "_" + content_type)
            return data

        return wrapper
    return decorator


async def send_edit_item(user_id: int, item_id: int, item_type: str):
    """
    Здесь происходит сериализация контента
    """
    await db.User.update.values(editing_content=True).where(db.User.user_id == user_id).gino.status()
    # Получаем нужный объект по указанному типу и его айди
    item = await db.select([*getattr(db, item_type)]).where(getattr(db, item_type).id == item_id).gino.first()
    reply = "Выберите поле для редактирования\n\n"
    attachment = None
    # Проходимся по всем его столбцам, указанным в serializers.fields_content и вызываем функцию serialized_func() (если она указана)
    # для того, чтобы получить сериализованное значение
    for i, data in enumerate(fields_content[item_type]['fields']):
        # Для связанных таблиц вызываем функцию с сериализации с указанием айди объекта (как и указано в документации)
        if isinstance(data, RelatedTable):
            if not data.serialize_func:
                reply += f"{i + 1}. {data.name}: {item[i + 1]}\n"
            else:
                reply += f"{i + 1}. {data.name}: {await data.serialize_func(item.id)}\n"
        # Для обычных полей все просто вызываем функцию сериализации если есть
        elif isinstance(data, Field):
            # За исключением специального название "Фото". Чтобы было видно, какая именно фотография прикреплена к объекту
            # значение столбца "Фото" (аттач строка) прикрепляется к сообщению
            if data.name == "Фото":
                attachment = item[i + 1]
            if not data.serialize_func:
                reply += f"{i + 1}. {data.name}: {item[i + 1]}\n"
            else:
                reply += f"{i + 1}. {data.name}: {await data.serialize_func(item[i + 1])}\n"
    # Получаем клавиатуру, устанавливаем стейт и наконец отправляем сообщение пользователю
    keyboard = keyboards.get_edit_content(item_type)
    states.set(user_id, f"{service.states.Admin.EDIT_CONTENT}_{item_type}*{item.id}")
    await bot.api.messages.send(message=reply, keyboard=keyboard.get_json(), peer_id=user_id, attachment=attachment)


def soft_divide(num: int, den: int) -> int:
    """
    Небольшая функция для деления с округлением в большую сторону.
    Эта функция применяется для подсчета количества необходимых страниц по количеству контента

    Существует проблема, если число делится без остатка, то прибавление 1 к целой части числа будет лишним.
    Допустим у нас 30 объектов и мы располагаем на странице по 15 объектов. Нам нужно 2 страницы,
    но если объектов 33, то уже 3 странницы.
    Дефолтный int(num // den) + 1 с этим не справляется:
    int(5 // 2) + 1 == 3  # True
    int(4 // 2) + 1 == 2  # False
    """
    if num % den == 0:
        return int(num // den)
    return int(num // den) + 1


async def page_fractions(page: int) -> Tuple[str, Keyboard, str]:
    """
    Эта функция пагинирует по одной фракции
    Нужна при регистрации, когда пользователь выбирает в какую фракцию вступить
    """
    fraction = await db.select([*db.Fraction]).order_by(db.Fraction.id.desc()).offset(page - 1).limit(1).gino.first()
    if fraction.leader_id:
        leader_nick = await db.select([db.Form.name]).where(db.Form.user_id == fraction.leader_id).gino.scalar()
        leader = (await bot.api.users.get(user_id=fraction.leader_id))[0]
        leader_mention = f"[id{fraction.leader_id}|{leader_nick} / {leader.first_name} {leader.last_name}]"
    else:
        leader_mention = "Без лидера"
    reply = (f"Название: {fraction.name}\n"
             f"Описание: {fraction.description}\n"
             f"Текущий лидер: {leader_mention}")
    count = await db.select([func.count(db.Fraction.id)]).gino.scalar()
    kb = Keyboard(inline=True)
    # Добавляем кнопки пагинации
    if page > 1:
        kb.add(
            Callback("<-", {"fraction_page": page - 1}), KeyboardButtonColor.SECONDARY
        )
    if count > page:
        kb.add(
            Callback("->", {"fraction_page": page + 1}), KeyboardButtonColor.SECONDARY
        )
    if len(kb.buttons) > 0 and len(kb.buttons[0]) > 0:
        kb.row()
    kb.add(
        Callback("Вступить", {"fraction_select": fraction.id}), KeyboardButtonColor.POSITIVE
    )
    return reply, kb, fraction.photo


async def check_last_activity(user_id: int):
    """
    Функция проверяет последнюю активность пользователей
    Запускается в event_loop после каждого сообщения
    Если пользователь долгое время не писал его анкета замораживается
    Если пользователь с замороженной анкетой еще дольше не писал его анкета удаляется
    """
    if user_id == 32650977:  # Исключение для конкретного пользователя
        return
    time_to_freeze: int = await db.select([db.Metadata.time_to_freeze]).gino.scalar()
    await asyncio.sleep(time_to_freeze)
    last_activity: datetime.datetime = await db.select([db.User.last_activity]).where(
        db.User.user_id == user_id).gino.scalar()
    time_to_freeze: int = await db.select([db.Metadata.time_to_freeze]).gino.scalar()  # Can be updated after sleeping
    freeze, is_request = await db.select([db.Form.freeze, db.Form.is_request]).where(db.Form.user_id == user_id).gino.first()
    # Замораживаем анкету если время без активности превышено
    if (datetime.datetime.now() - last_activity).total_seconds() >= time_to_freeze and not freeze and not is_request:
        await db.Form.update.values(freeze=True).where(db.Form.user_id == user_id).gino.status()
        await bot.api.messages.send(message="❗ В связи с отсутствием вашей активности в течение "
                                            f"{parse_cooldown(time_to_freeze)} ваша анкета автоматически заморожена",
                                    peer_id=user_id, is_notification=True)
        name = await db.select([db.Form.name]).where(db.Form.user_id == user_id).gino.scalar()
        user = (await bot.api.users.get(user_id=user_id))[0]
        admins = [x[0] for x in await db.select([db.User.user_id]).where(db.User.admin > 0).gino.all()]
        await bot.api.messages.send(message=f"❗ Анкета [id{user_id}|{name} / {user.first_name} {user.last_name}] "
                                            f"автоматически заморожена",
                                    peer_ids=admins, is_notification=True)

        # Ждем время до удаления
        time_to_delete = await db.select([db.Metadata.time_to_delete]).gino.scalar()
        await asyncio.sleep(time_to_delete - time_to_freeze)
        last_activity: datetime.datetime = await db.select([db.User.last_activity]).where(
            db.User.user_id == user_id).gino.scalar()
        time_to_delete: int = await db.select([db.Metadata.time_to_delete]).gino.scalar()
        freeze = await db.select([db.Form.freeze]).where(db.Form.user_id == user_id).gino.scalar()
        # Удаляем анкету если время без активности превышено
        if last_activity and freeze and (
                datetime.datetime.now() - last_activity).total_seconds() >= time_to_delete and not is_request:
            await bot.api.messages.send(message=f"❗ В связи с отсутствием вашей активности в течение "
                                                f"{parse_cooldown(time_to_delete)} ваша анкета автоматически удалена",
                                        peer_id=user_id, is_notification=True)
            name = await db.select([db.Form.name]).where(db.Form.user_id == user_id).gino.scalar()
            await db.Form.delete.where(db.Form.user_id == user_id).gino.status()
            user = (await bot.api.users.get(user_id=user_id))[0]
            admins = [x[0] for x in await db.select([db.User.user_id]).where(db.User.admin > 0).gino.all()]
            await bot.api.messages.send(message=f"❗ Анкета [id{user_id}|{name} / {user.first_name} {user.last_name}] "
                                                f"была автоматически удалена",
                                        peer_ids=admins, is_notification=True)


async def apply_reward(user_id: int, data: dict, save_penalty=False):
    """
    Эта функция применяет награду/штраф для пользователя

    data: словарь с описанием награды, формат данных смотреть в README
    save_penalty: параметр сохранять ли штраф в таблице штрафов. По умолчанию False - применяется штраф к базовому значению,
    если True - записывается в таблицу, чтобы потом была возможность отменить
    """
    if not data:
        return
    for reward in data:
        if reward['type'] == 'fraction_bonus':
            fraction_id = reward['fraction_id']
            reputation_bonus = reward['reputation_bonus']
            await db.change_reputation(user_id, fraction_id, reputation_bonus)
        elif reward['type'] == 'value_bonus':
            bonus = reward['bonus']
            await db.Form.update.values(balance=db.Form.balance + bonus).where(db.Form.user_id == user_id).gino.status()
        elif reward['type'] == 'daughter_params':
            libido, subordination = await db.select([db.Form.libido_level, db.Form.subordination_level]).where(db.Form.user_id == user_id).gino.first()
            sub_level = min(100, max(0, subordination + reward['subordination']))
            lib_level = min(100, max(0, libido + reward['libido']))
            await update_daughter_levels(user_id, lib_level, sub_level)
        elif reward['type'] == 'item':
            item_id = reward['item_id']
            count = reward['count']
            form_id = await get_current_form_id(user_id)
            expeditor_id = await db.select([db.Expeditor.id]).where(db.Expeditor.form_id == form_id).gino.scalar()
            if not expeditor_id:
                continue
            for i in range(count):
                await db.ExpeditorToItems.create(expeditor_id=expeditor_id, item_id=item_id)
        elif reward['type'] == 'attribute':
            attribute_id = reward['attribute_id']
            value = reward['value']
            form_id = await get_current_form_id(user_id)
            expeditor_id = await db.select([db.Expeditor.id]).where(db.Expeditor.form_id == form_id).gino.scalar()
            if not expeditor_id:
                continue
            if not save_penalty:
                current_value = await db.select([db.ExpeditorToAttributes.value]).where(
                    and_(db.ExpeditorToAttributes.attribute_id == attribute_id, db.ExpeditorToAttributes.expeditor_id == expeditor_id)
                ).gino.scalar()
                await db.ExpeditorToAttributes.update.values(value=min(max(current_value + value, 0), 200)).where(
                    and_(db.ExpeditorToAttributes.expeditor_id == expeditor_id, db.ExpeditorToAttributes.attribute_id == attribute_id)
                ).gino.scalar()
            else:
                await db.AttributePenalties.create(attribute_id=attribute_id, expeditor_id=expeditor_id, value=value)


async def update_daughter_tasks(user_id: int):
    """
    Функция для проверки выполнения квестов для дочерей у конкретной дочери
    """
    # Тут короче надо получить в конце дня список задач, которые нужно было выполнить
    # Поэтому за 3 секунды до конца дня получаем его
    target_ids = await get_available_daughter_target_ids(user_id)
    # Потом, чтобы точно понимать, что мы находимся в новом дне, ждем 5 секунд
    await asyncio.sleep(5)
    form_id = await get_current_form_id(user_id)
    # Замороженные анкеты пропускаем
    # Проверяем выполнение квеста дочери
    quest = await db.select([*db.DaughterQuest]).where(db.DaughterQuest.to_form_id == form_id).gino.first()
    if quest:
        confirmed = await db.select([db.DaughterQuestRequest.confirmed]).where(
            and_(db.DaughterQuestRequest.quest_id == quest.id, db.DaughterQuestRequest.form_id == form_id,
                 db.DaughterQuestRequest.created_at == (now().date() - datetime.timedelta(days=1)))
        ).gino.scalar()
        # Если квест не выполнен - применяем штраф
        if confirmed is None:
            await apply_reward(user_id, quest.penalty, True)
            reply = f' ❌ Вам выписан штраф за невыполнение квеста «{quest.name}»:\n'
            reply += await serialize_target_reward(quest.penalty)
            await bot.api.messages.send(peer_id=user_id, message=reply, is_notification=True)
            for target_id in target_ids:
                # Проверяем выполнение доп. цели
                confirmed = await db.select([db.DaughterTargetRequest.confirmed]).where(
                    and_(db.DaughterTargetRequest.target_id == target_id,
                         db.DaughterTargetRequest.form_id == form_id,
                         db.DaughterTargetRequest.created_at == (now().date() - datetime.timedelta(days=1))
                         )
                ).gino.scalar()
                if confirmed:
                    continue
                name, penalty = await db.select([db.DaughterTarget.name, db.DaughterTarget.penalty]).where(
                    db.DaughterTarget.id == target_id
                ).gino.first()
                reply = f' ❌ Вам выписан штраф за невыполнение доп. цели «{name}»:\n'
                reply += await serialize_target_reward(penalty)
                await apply_reward(user_id, penalty, save_penalty=True)
                await bot.api.messages.send(peer_id=user_id, message=reply, is_notification=True)
    # Обновляем параметры дочерей
    sub_bonus, lib_bonus, sub_level, lib_level, fraction_id = await db.select(
        [db.Form.subordination_bonus, db.Form.libido_bonus, db.Form.subordination_level, db.Form.libido_level,
         db.Form.fraction_id]).where(
        db.Form.user_id == user_id).gino.first()
    libido_multiplier = await db.select([db.Fraction.libido_koef]).where(
        db.Fraction.id == fraction_id).gino.scalar()
    sub_koef = await db.select([db.Fraction.subordination_koef]).where(
        db.Fraction.id == fraction_id).gino.scalar()
    sub_level = min(100, max(0, int(sub_level + 2 * sub_koef + sub_bonus)))
    lib_level = min(100, max(0, int(lib_level + 2 * libido_multiplier + lib_bonus)))
    await update_daughter_levels(user_id, lib_level, sub_level)


async def timer_daughter_levels():
    """
    Функция таймер для обновления параметров всех дочерей и проверке выполнения обязательного квеста для дочерей

    Каждый день у дочерей вырастают параметры либидо и подчинения

    Формула:
    sub_level = sub_level + 2 * multiplier + sub_bonus

    Где:
    sub_level - текущий уровень подчинения, принадлежит промежутку [0; 100]
    multiplier - множитель фракции
    sub_bonus - набранные очки при регистрации

    Для либидо формула такая же
    """
    while True:
        tomorrow = now() + datetime.timedelta(days=1)
        tomorrow = datetime.datetime(tomorrow.year, tomorrow.month, tomorrow.day, 0, 0, 0,
                                     tzinfo=datetime.timezone(datetime.timedelta(hours=3)))
        await asyncio.sleep((tomorrow - now()).total_seconds() - 3)
        user_ids = [x[0] for x in await db.select([db.Form.user_id]).where(
            and_(db.Form.status == 2, db.Form.freeze.isnot(True))
        ).gino.all()]
        tasks = [update_daughter_tasks(user_id) for user_id in user_ids]
        await asyncio.gather(*tasks)
        await asyncio.sleep(15)


async def get_available_daughter_target_ids(user_id: int) -> list[int]:
    form_id = await get_current_form_id(user_id)
    quest = await db.select([*db.DaughterQuest]).where(db.DaughterQuest.to_form_id == form_id).gino.first()
    target_ids = []
    if not quest:
        return []
    for target_id in quest.target_ids:
        params = await db.select([db.DaughterTarget.params]).where(db.DaughterTarget.id == target_id).gino.scalar()
        libido, subordination = await count_daughter_params(user_id)

        # Проверка условий доступа к цели
        if params[1]:  # или
            if libido >= params[0] or subordination >= params[2]:
                target_ids.append(target_id)
        else:
            if libido >= params[0] and subordination >= params[2]:
                target_ids.append(target_id)

    # Получение подтвержденных целей
    confirmed_target_ids = {x[0] for x in await db.select([db.DaughterTargetRequest.target_id]).where(
        and_(db.DaughterTargetRequest.confirmed.is_(True),
             db.DaughterTargetRequest.created_at == now().date(),
             db.DaughterTargetRequest.form_id == form_id)).gino.all()}

    target_ids = list(set(target_ids) | confirmed_target_ids)
    return target_ids


async def get_admin_ids():
    """
    Прстая функция для получения айди всех админов (из конфига и из базы), потмоу что бывают ситуации, когда админ
    не зареган в боте, а функции админа нужны. Например, при первой регистрации
    """
    admins = set([OWNER] + ADMINS)
    admins_db = {x[0] for x in await db.select([db.User.user_id]).where(db.User.admin > 0).gino.all()}
    admins = list(admins | admins_db)
    return admins


async def filter_users_expeditors(user_ids: list[int], chat_id: int) -> list[int]:
    """
    Отфильтровывает список пользователей, у кого есть карта экспедитора
    """
    members = await bot.api.messages.get_conversation_members(peer_id=2000000000 + chat_id)
    member_ids = {x.member_id for x in members.items if x.member_id > 0}
    user_ids = list(set(user_ids) & member_ids)  # users in chat
    form_ids = [x[0] for x in await db.select([db.Form.id]).where(db.Form.user_id.in_(user_ids)).gino.all()]
    form_ids = [x[0] for x in await db.select([db.Expeditor.form_id]).where(db.Expeditor.form_id.in_(form_ids)).gino.all()]
    user_ids = [x[0] for x in await db.select([db.Form.user_id]).where(db.Form.id.in_(form_ids)).gino.all()]
    return user_ids


async def update_initiative(action_mode_id: int):
    """
    Во время экшен режима обновляет уровни инициативы

    К текущему уровню скорости прибавляется случайное число от 1 до 100
    """
    user_ids = [x[0] for x in await db.select([db.UsersToActionMode.user_id]).where(
        db.UsersToActionMode.action_mode_id == action_mode_id).gino.all()]
    for user_id in user_ids:
        perception = await count_attribute(user_id, 5)
        random_bonus = random.randint(1, 100)
        initiative = random_bonus + perception
        await db.UsersToActionMode.update.values(initiative=initiative).where(
            and_(db.UsersToActionMode.user_id == user_id, db.UsersToActionMode.action_mode_id == action_mode_id)
        ).gino.status()


async def next_round(action_mode_id: int):
    """
    Функция, которая вызывается когда наступает новый цикл постов участников в экшен-режиме
    """
    # Айди чата в котором идет экшен-режим
    chat_id = await db.select([db.ActionMode.chat_id]).where(db.ActionMode.id == action_mode_id).gino.scalar()
    # Ставим очередь 0, потому что со следующим шагом добавится один и будет очередь писать первого участника
    await db.ActionMode.update.values(number_step=0).where(db.ActionMode.id == action_mode_id).gino.status()
    # Удаляем посты, которые были в прошлом, чтобы не засорять базу
    await db.Post.delete.where(db.Post.action_mode_id == action_mode_id).gino.status()
    # Удаляем пользователей, который выходят в этом раунде из экшен-режима
    await db.UsersToActionMode.delete.where(and_(db.UsersToActionMode.action_mode_id == action_mode_id, db.UsersToActionMode.exited.is_(True))).gino.status()
    # Добавляем пользователей, которые входят в экшен-режим с новым раундом
    await db.UsersToActionMode.update.values(participate=True).where(
        db.UsersToActionMode.action_mode_id == action_mode_id).gino.all()
    # Обновляем инициативу у всех участников экшен-режима
    await update_initiative(action_mode_id)
    # Получаем имена тех, кто участвует в экшен-режиме, чтобы в ответном сообщении написать очередность постов
    users_data = await db.select([db.UsersToActionMode.user_id, db.Form.name]).select_from(
        db.UsersToActionMode.join(db.User, db.UsersToActionMode.user_id == db.User.user_id)
        .join(db.Form, db.User.user_id == db.Form.user_id)
    ).where(db.UsersToActionMode.action_mode_id == action_mode_id).order_by(
        db.UsersToActionMode.initiative.desc()).gino.all()
    form_ids = [x[0] for x in await db.select([db.Form.id]).where(db.Form.user_id.in_([x[0] for x in users_data])).gino.all()]
    expeditor_ids = [x[0] for x in await db.select([db.Expeditor.id]).where(db.Expeditor.form_id.in_(form_ids)).gino.all()]
    # Проверяем первый ли это цикл постов в экшен-режиме. Если не первый, то нужно вычесть использование раунда у предметов
    first_cycle = await db.select([db.ActionMode.first_cycle]).where(db.ActionMode.id == action_mode_id).gino.scalar()
    # Вычитаем использование предметов
    if not first_cycle:
        # Активные (дающие эффект) предметы у игрока
        active_row_ids = [x[0] for x in await db.select([db.ActiveItemToExpeditor.id]).select_from(
            db.ActiveItemToExpeditor.join(db.ExpeditorToItems, db.ActiveItemToExpeditor.row_item_id == db.ExpeditorToItems.id)
            .join(db.Item, db.ExpeditorToItems.item_id == db.Item.id)
        ).where(
            and_(db.ActiveItemToExpeditor.expeditor_id.in_(expeditor_ids), db.Item.action_time > 0)
        ).gino.all()]
        # Снимаем по одному использованию
        await db.ActiveItemToExpeditor.update.values(remained_use=db.ActiveItemToExpeditor.remained_use - 1).where(db.ActiveItemToExpeditor.id.in_(active_row_ids)).gino.status()
        # Предметы, которые закончили свое действие (по количеству раундов или по времени)
        disabled_row_ids = [x[0] for x in await db.select([db.ActiveItemToExpeditor.id]).select_from(
            db.ActiveItemToExpeditor.join(db.ExpeditorToItems,
                                          db.ActiveItemToExpeditor.row_item_id == db.ExpeditorToItems.id)
            .join(db.Item, db.ExpeditorToItems.item_id == db.Item.id)
        ).where(
            and_(db.ActiveItemToExpeditor.expeditor_id.in_(expeditor_ids), db.Item.action_time > 0, db.ActiveItemToExpeditor.remained_use <= 0)
        ).gino.all()]
        # Проходим по таким предметам и снимаем их (удаляются из активных)
        for row_id in disabled_row_ids:
            await take_off_item(row_id)
        # Устанавливаем флаг о том, что больше первого цикла не будет
        await db.ActionMode.update.values(first_cycle=False).where(db.ActionMode.id == action_mode_id).gino.status()
    # Отправляем сообщение с очередностью участников писать посты (по убыванию уровня инициативы)
    users = await bot.api.users.get(user_ids=[x[0] for x in users_data])
    reply = f'Новый цикл постов\nТекущая очередь участников:\n\n'
    for i in range(len(users)):
        reply += f'{i + 1}. [id{users_data[i][0]}|{users_data[i][1]} / {users[i].first_name} {users[i].last_name}]\n'
    await bot.api.messages.send(peer_id=2000000000 + chat_id, message=reply)
    # Применяем следующий шаг в экшен-режиме
    await next_step(action_mode_id)


async def get_current_turn(action_mode_id: int) -> int | None:
    """
    Функция вовзвращает номер участника, чья очередь писать пост по айди экшен-режима
    """
    user_ids = [x[0] for x in await db.select([db.UsersToActionMode.user_id]).where(
        and_(db.UsersToActionMode.action_mode_id == action_mode_id,
             db.UsersToActionMode.participate.is_(True))).order_by(db.UsersToActionMode.initiative.desc()).gino.all()]
    number_step = await db.select([db.ActionMode.number_step]).where(db.ActionMode.id == action_mode_id).gino.scalar()
    if number_step == 0:  # Очередь судьи писать пост
        return
    try:
        return user_ids[number_step - 1]
    except IndexError:
        return


async def next_step(action_mode_id: int):
    """
    Функция для принятия следующего шага в экшен-режиме
    """
    # Информация об экшен-режиме
    chat_id, finished, judge_id, time_to_post = await db.select(
        [db.ActionMode.chat_id, db.ActionMode.finished, db.ActionMode.judge_id, db.ActionMode.time_to_post]).where(
        db.ActionMode.id == action_mode_id).gino.first()
    # Если экшен-режим закончился, то нужно снять все предметы, которые имеют ограничение на использование по количеству раундов
    if finished:
        user_ids = [x[0] for x in await db.select([db.UsersToActionMode.user_id]).where(db.UsersToActionMode.action_mode_id == action_mode_id).gino.all()]
        form_ids = [x[0] for x in await db.select([db.Form.id]).where(db.Form.user_id.in_(user_ids)).gino.all()]
        expeditor_ids = [x[0] for x in await db.select([db.Expeditor.id]).where(db.Expeditor.form_id.in_(form_ids)).gino.all()]
        row_ids = [x[0] for x in await db.select([db.ActiveItemToExpeditor.id]).select_from(
            db.ActiveItemToExpeditor.join(db.ExpeditorToItems, db.ActiveItemToExpeditor.row_item_id == db.ExpeditorToItems.id)
            .join(db.Item, db.ExpeditorToItems.item_id == db.Item.id)
        ).where(
            and_(db.ActiveItemToExpeditor.expeditor_id.in_(expeditor_ids), db.Item.action_time > 0)).gino.all()]
        for row_id in row_ids:
            await take_off_item(row_id)
        await db.ActionMode.delete.where(db.ActionMode.id == action_mode_id).gino.status()
        await bot.api.messages.send(peer_id=2000000000 + chat_id, message='Экшен-режим завершен',
                                    keyboard=keyboards.request_action_mode)
        # Возвращаем судью в стейт главного меню
        if states.contains(judge_id):
            states.set(judge_id, service.states.Menu.MAIN)
        await db.User.update.values(state=str(service.states.Menu.MAIN), check_action_id=None).where(db.User.user_id == judge_id).gino.status()
        await bot.api.messages.send(peer_id=judge_id, message='Экшен режим завершен',
                                    keyboard=await keyboards.main_menu(judge_id))
        return
    # Если экшен режим не закончился то прописываем следующему пользователю писать пост
    await db.ActionMode.update.values(number_step=db.ActionMode.number_step + 1, number_check=0).where(
        db.ActionMode.id == action_mode_id).gino.scalar()
    user_id = await get_current_turn(action_mode_id)
    if not user_id:  # Если все участники написали свой пост, то теперь очередь судьи писать свой пост
        await db.ActionMode.update.values(number_step=0, number_check=0).where(
            db.ActionMode.id == action_mode_id).gino.scalar()
        await bot.api.request('messages.changeConversationMemberRestrictions',
                              {'peer_id': 2000000000 + chat_id, 'member_ids': judge_id, 'action': 'rw'})
        await bot.api.messages.send(peer_id=2000000000 + chat_id, message='Сейчас очередь судьи писать свой пост')
        return
    # Отправляем сообщение о том, чья очередь писать свой пост
    name = await db.select([db.Form.name]).where(db.Form.user_id == user_id).gino.scalar()
    user = (await bot.api.users.get(user_ids=[user_id]))[0]
    await bot.api.request('messages.changeConversationMemberRestrictions',
                          {'peer_id': 2000000000 + chat_id, 'member_ids': user_id, 'action': 'rw'})
    reply = f'Сейчас очередь участника [id{user.id}|{name} / {user.first_name} {user.last_name}] писать свой пост'
    await bot.api.messages.send(peer_id=2000000000 + chat_id, message=reply)
    post = await db.Post.create(user_id=user_id, action_mode_id=action_mode_id)
    # Ставим таймер на написание поста
    asyncio.get_event_loop().create_task(wait_users_post(post.id))


async def wait_users_post(post_id: int):
    """
    Функция таймер, ожидающая написание поста участником экшен-режима

    Если за отведенное время участник не написал свой пост, он пропускает свой ход
    """
    action_mode_id, created_at = await db.select([db.Post.action_mode_id, db.Post.created_at]).where(db.Post.id == post_id).gino.first()
    time_to_post = await db.select([db.ActionMode.time_to_post]).where(db.ActionMode.id == action_mode_id).gino.scalar()
    # Если нет временного ограничения на написание поста, то просто выходим
    if not time_to_post:
        return  # Нет ограничения на написание поста
    if now() < created_at + datetime.timedelta(seconds=time_to_post):  # Проверяем, что еще надо ждать
        seconds = (created_at + datetime.timedelta(seconds=time_to_post) - now()).total_seconds()
        await asyncio.sleep(seconds)
    exist = await db.select([db.Post.id]).where(db.Post.id == post_id).gino.scalar()
    if not exist:
        return  # Экшен-режим мог закончиться либо начался новый круг
    actions = await db.select([db.Action.id]).where(db.Action.post_id == post_id).gino.all()
    if actions:
        return   # Пользователь таки написал свой пост
    chat_id = await db.select([db.ActionMode.chat_id]).where(db.ActionMode.id == action_mode_id).gino.scalar()
    user_id = await db.select([db.Post.user_id]).where(db.Post.id == post_id).gino.scalar()
    turn = await get_current_turn(action_mode_id)
    if user_id == turn:  # На всякий проверим, что очередь человека (+ прошлая проверка он ничего не написал)
        name = await db.select([db.Form.name]).where(db.Form.user_id == user_id).gino.scalar()
        user = (await bot.api.users.get(user_ids=[user_id]))[0]
        await bot.api.messages.send(peer_id=2000000000 + chat_id,
                                    message=f'Пользователь [id{user.id}|{name} / {user.first_name} {user.last_name}] '
                                            f'не написал свой пост, поэтому пропускает очередь')
        await next_step(action_mode_id)


async def wait_take_off_item(row_id: int):
    """
    Таймер для снятия предмета, который заканчивает свое действие по времени
    """
    row = await db.select([*db.ActiveItemToExpeditor]).where(db.ActiveItemToExpeditor.id == row_id).gino.first()
    item_id = await db.select([db.ExpeditorToItems.item_id]).where(db.ExpeditorToItems.id == row.row_item_id).gino.scalar()
    time_use = await db.select([db.Item.time_use]).where(db.Item.id == item_id).gino.scalar()
    if not time_use:  # Нет ограничения по времени
        return
    if now() < row.created_at + datetime.timedelta(seconds=time_use):
        seconds = (row.created_at + datetime.timedelta(seconds=time_use) - now()).total_seconds()
        await asyncio.sleep(seconds)
    exist = await db.select([db.ExpeditorToItems.id]).where(db.ExpeditorToItems.id == row_id).gino.scalar()
    if not exist:
        return
    await take_off_item(row_id)


async def take_off_item(active_row_id: int):
    """
    Функция снимающая предмет с игрока

    Если предмет, одноразовый, то он удаляется из инвентаря (нельзя переиспользовать)
    Если предмет многоразовый/постоянный его можно повторно переиспользовать
    """
    item_type, row_id, expeditor_id, item_name = await db.select([db.Item.type_id, db.ExpeditorToItems.id, db.ExpeditorToItems.expeditor_id, db.Item.name]).select_from(
        db.ActiveItemToExpeditor.join(db.ExpeditorToItems, db.ActiveItemToExpeditor.row_item_id == db.ExpeditorToItems.id)
        .join(db.Item, db.ExpeditorToItems.item_id == db.Item.id)
    ).where(db.ActiveItemToExpeditor.id == active_row_id).gino.first()
    if item_type == 1:  # Одноразовый
        await db.ExpeditorToItems.delete.where(db.ExpeditorToItems.id == row_id).gino.status()
    else:  # Многоразовый/постоянный
        await db.ActiveItemToExpeditor.delete.where(db.ActiveItemToExpeditor.id == active_row_id).gino.status()
    form_id = await db.select([db.Expeditor.form_id]).where(db.Expeditor.id == expeditor_id).gino.scalar()
    user_id = await db.select([db.Form.user_id]).where(db.Form.id == form_id).gino.scalar()
    await bot.api.messages.send(peer_id=user_id, message=f'Предмет «{item_name}» закончил свое действие', is_notification=True)


async def wait_disable_debuff(row_id: int):
    """
    Таймер для снятия дебафа
    """
    row = await db.select([*db.ExpeditorToDebuffs]).where(db.ExpeditorToDebuffs.id == row_id).gino.first()
    time_use = await db.select([db.StateDebuff.time_use]).where(db.StateDebuff.id == row.debuff_id).gino.scalar()
    if not time_use:  # Нет ограничения по времени
        return
    if now() < row.created_at + datetime.timedelta(seconds=time_use):
        seconds = (row.created_at + datetime.timedelta(seconds=time_use) - now()).total_seconds()
        await asyncio.sleep(seconds)
    exist = await db.select([db.ExpeditorToDebuffs.id]).where(db.ExpeditorToDebuffs.id == row_id).gino.scalar()
    if not exist:
        return
    form_id = await db.select([db.Expeditor.form_id]).where(db.Expeditor.id == row.expeditor_id).gino.scalar()
    user_id = await db.select([db.Form.user_id]).where(db.Form.id == form_id).gino.scalar()
    item_name = await db.select([db.StateDebuff.name]).where(db.StateDebuff.id == row.debuff_id).gino.scalar()
    await db.ExpeditorToDebuffs.delete.where(db.ExpeditorToDebuffs.id == row_id).gino.status()
    await bot.api.messages.send(peer_id=user_id, message=f'Закончилось время действия дебафа «{item_name}»', is_notification=True)


async def parse_actions(text: str, expeditor_id: int) -> list[dict]:
    """
    Функция которая парсит действия игрока из текста поста во время экшен-режима

    Формат объекта действия смотреть в README
    """
    text = text.lower()
    matches = re.findall(action_regex, text)
    actions = []
    for match in matches:
        aliases = ('использовать ', "применить ", "активировать ", "задействовать ", "юзнуть ", "достать ")
        for alias in aliases:
            if match.startswith(alias):
                break
        else:
            continue
        # Если написано использовать значит это предмет
        if match.startswith(alias):
            item_name = match[len(alias):].strip()
            # Ищем предмет по похожести названия
            distance = func.levenshtein(func.lower(db.Item.name), item_name)
            similarity = func.similarity(func.lower(db.Item.name), item_name).label('similarity')
            item_id = (await db.select([db.Item.id])
                       .where(db.Item.name.op('%')(item_name))
                      .order_by(similarity.desc())
                      .order_by(distance.asc()).limit(1).gino.scalar())
            if not item_id:
                continue
            # Проверяем что предмет есть в инвентаре и не активирован
            active_row_ids = [x[0] for x in await db.select([db.ActiveItemToExpeditor.row_item_id]).where(db.ActiveItemToExpeditor.expeditor_id == expeditor_id).gino.all()]
            exist = await db.select([db.ExpeditorToItems.id]).where(and_(db.ExpeditorToItems.expeditor_id == expeditor_id, db.ExpeditorToItems.id.notin_(active_row_ids), db.ExpeditorToItems.item_id == item_id)).order_by(db.ExpeditorToItems.id.asc()).gino.scalar()
            if not exist:
                continue
            # Проверяем лимит использований
            used = await db.select([db.ExpeditorToItems.count_use]).where(db.ExpeditorToItems.id == exist).gino.scalar()
            count_use = await db.select([db.Item.count_use]).where(db.Item.id == item_id).gino.scalar()
            if count_use - used <= 0:
                continue
            actions.append({'type': 'use_item', 'row_id': exist})
        # Если указано упоминание на кого-то то это PvP, требует проверки судьи с двумя последствиями
        elif x := re.search(mention_regex_cut, match):
            user_id = int(x.group(0)[3:-1])
            actions.append({'type': 'pvp', 'user_id': user_id})
        # В ином случае текстовое действие которое требуется проверки судьи
        else:
            actions.append({'type': 'action', 'text': match})
    return actions


async def count_attribute(user_id: int, attribute_id: int) -> int:
    """
    Функция которая рассчитывает текущий показатель уровня характеристики с учетом бафов предметов и дебафов (травм и безумий)
    """
    form_id = await db.select([db.Form.id]).where(db.Form.user_id == user_id).gino.scalar()
    expeditor_id = await db.select([db.Expeditor.id]).where(db.Expeditor.form_id == form_id).gino.scalar()
    base = await db.select([db.ExpeditorToAttributes.value]).where(and_(db.ExpeditorToAttributes.expeditor_id == expeditor_id, db.ExpeditorToAttributes.attribute_id == attribute_id)).gino.scalar()
    # Считаем бонусы от активных предметов
    active_item_ids = [x[0] for x in await db.select([db.ExpeditorToItems.item_id]).select_from(
        db.ActiveItemToExpeditor.join(db.ExpeditorToItems, db.ActiveItemToExpeditor.row_item_id == db.ExpeditorToItems.id)
    ).where(db.ActiveItemToExpeditor.expeditor_id == expeditor_id).gino.all()]
    bonuses = [x[0] for x in await db.select([db.Item.bonus]).where(db.Item.id.in_(active_item_ids)).gino.all()]
    item_bonus = 0
    for data in bonuses:
        for bonus in data:
            if bonus.get('type') == 'attribute' and bonus.get('attribute_id') == attribute_id:
                item_bonus += bonus['bonus']
                continue
    # Считаем штрафы от активных дебафов
    active_debuff_ids = [x[0] for x in await db.select([db.ExpeditorToDebuffs.debuff_id]).where(db.ExpeditorToDebuffs.expeditor_id == expeditor_id).gino.all()]
    penalty_debuff = sum([x[0] for x in await db.select([db.StateDebuff.penalty]).where(and_(db.StateDebuff.id.in_(active_debuff_ids), db.StateDebuff.attribute_id == attribute_id)).gino.all()])

    # Считаем штрафы от невыполнения квестов дочерей
    penalties = sum([x[0] for x in await db.select([db.AttributePenalties.value]).where(
        and_(db.AttributePenalties.attribute_id == attribute_id, db.AttributePenalties.expeditor_id == expeditor_id)
    ).gino.all()])

    return max(0, min(200, base + item_bonus + penalty_debuff + penalties))


# Типы последствий
types_consequences = {
    1: 'Критический провал',
    2: 'Провал',
    3: 'Успех',
    4: 'Критический успех',
    5: 'Критический провал (противник)',
    6: 'Провал (противник)',
    7: 'Успех (противник)',
    8: 'Критический успех (противник)'
}

# Типы сложностей
type_difficulties = {
    1: ['Легкая', 1.2],
    2: ['Нормальная', 1.0],
    3: ['Сложная', 0.8],
    4: ['Очень сложная', 0.6],
    5: ['Почти невозможная', 0.4],
    6: ['Невозможная', 0.2]
}


async def show_consequences(action_id: int) -> str:
    """
    Функция выводит все привязанные последствия по айди действия
    """
    data = await db.select([db.Action.data]).where(db.Action.id == action_id).gino.scalar()
    reply = 'Тип действия: '
    if data['type'] == 'action':
        reply += 'текстовое действие\n'
        reply += f'Действие: {data["text"]}\n\n'
    else:
        reply += 'PvP\n'
        user_id = data['user_id']
        name = await db.select([db.Form.name]).where(db.Form.user_id == user_id).gino.scalar()
        user = (await bot.api.users.get(user_ids=[user_id]))[0]
        reply += f'Сражение с [id{user_id}|{name} / {user.first_name} {user.last_name}]\n\n'
    consequences = await db.select([*db.Consequence]).where(db.Consequence.action_id == action_id).gino.all()
    data = {}
    for con in consequences:
        if con.type not in data:
            data[con.type] = [con]
        else:
            data[con.type].append(con)
    reply += 'Установленные последствия:\n'
    for i in types_consequences:
        if i in data:
            description = ", ".join([await serialize_consequence(x.data) for x in data[i]])
        else:
            description = 'Не указано'
        reply += f'{types_consequences[i]}: {description}\n'
    return reply


async def serialize_consequence(data: dict) -> str:
    """
    Функция сериализует последствие

    Формат данных смотреть в README
    """
    type_ = data['type']
    if type_ == 'add_debuff':
        debuff_id = data['debuff_id']
        name = await db.select([db.StateDebuff.name]).where(db.StateDebuff.id == debuff_id).gino.scalar()
        return f'Добавить дебаф «{name}»'
    elif type_ == 'delete_debuff':
        row_id = data['row_id']
        name = await db.select([db.StateDebuff.name]).select_from(
            db.ExpeditorToDebuffs.join(db.StateDebuff, db.ExpeditorToDebuffs.debuff_id == db.StateDebuff.id)
        ).where(db.ExpeditorToDebuffs.id == row_id).gino.scalar()
        return f'Удалить дебаф «{name}»'
    elif type_ == 'delete_debuff_type':
        debuff_type_id = data['debuff_type_id']
        name = await db.select([db.DebuffType.name]).where(db.DebuffType.id == debuff_type_id).gino.scalar()
        return f'Снять все дебафы типа «{name}»'
    elif type_ == 'delete_all_debuffs':
        return 'Снятие всех дебафов'
    elif type_ in ('add_libido', 'add_subordination'):
        bonus = data['bonus']
        if type_ == 'add_libido':
            return f'Изменение Либидо на {"+" if bonus >= 0 else ""}{bonus}'
        else:
            return f'Изменение Подчинение на {"+" if bonus >= 0 else ""}{bonus}'
    elif type_ == 'set_pregnant':
        text = data['text']
        return f'Установить статус оплодотворение «{text}»'
    elif type_ == 'delete_pregnant':
        return 'Удалить статус оплодотворение'
    elif type_ == 'add_item':
        item_id = data['item_id']
        name = await db.select([db.Item.name]).where(db.Item.id == item_id).gino.scalar()
        return f'Выдать предмет «{name}»'
    elif type == 'delete_item':
        row_id = data['row_id']
        name = await db.select([db.Item.name]).select_from(
            db.ExpeditorToItems.join(db.Item, db.ExpeditorToItems.item_id == db.Item.id)
        ).where(db.ExpeditorToItems.id == row_id).gino.scalar()
        return f'Удалить предмет «{name}»'
    elif type_ == 'desactivate_item':
        row_id = data['row_id']
        name = await db.select([db.Item.name]).select_from(
            db.ActiveItemToExpeditor.join(db.ExpeditorToItems, db.ActiveItemToExpeditor.row_item_id == db.ExpeditorToItems.id)
            .join(db.Item, db.ExpeditorToItems.item_id == db.Item.id)
        ).where(db.ActiveItemToExpeditor.id == row_id).gino.scalar()
        return f'Отключить предмет «{name}»'
    elif type_ == 'add_attribute':
        attribute_id = data['attribute_id']
        bonus = data['bonus']
        name = await db.select([db.Attribute.name]).where(db.Attribute.id == attribute_id).gino.scalar()
        return f'Изменение «{name}» на {"+" if bonus >= 0 else ""}{bonus}'
    else:
        return data['text']


async def count_available_actions(user_id: int) -> int:
    """
    Функция для расчета доступных действий в экшен режим
    """
    speed = await count_attribute(user_id, 2)  # Уровень скорости
    return min(5, 1 + int(speed / 50))


async def count_difficult(post_id: int) -> int:
    """
    Функция возвращает номер сложности из type_difficulties

    Правило расчета уровня сложности:
    Для 1-ого действия: базовая сложность устанавливаемая судьёй в начале проверки поста
    Для каждого последующего действия: +1 к сложности (в пределах лимита)
    Количество доступных действий без штрафа: int(Скорость / 50) + 1
    Если игрок выходит за рамки, минимальная сложность становится Сложная (3)
    За каждое действие сверх лимита +1 к сложности

    Пример: доступно действий 1, базовая сложность 1, распределение:
    Номер действия - Сложность
    1 - 1
    2 - 4  # Перескакиваем на Очень сложную сложность
    3 - 5

    Пример: доступно действий 1, базовая сложность 2, распределение:
    Номер действия - Сложность
    1 - 2
    2 - 4  # Перескакиваем на Очень сложную сложность
    3 - 5

    Пример: доступно действий 1, сложность 3, распределение:
    Номер действия - Сложность
    1 - 3
    2 - 4  # Перескакиваем на Очень сложную сложность (но здесь она и так следующей идет)
    3 - 5

    Пример: доступно действий 5, сложность 1:
    Номер действия - Сложность
    1 - 1
    2 - 2
    3 - 3  # За лимит не выходим просто прибавляем +1

    Пример: доступно действий 1, сложность 4:
    Номер действия - Сложность
    1 - 4
    2 - 5  # Выходим за лимит, но из-за высокой сложности прибавляется +1
    3 - 6
    """
    difficult, action_mode_id, user_id = await db.select([db.Post.difficult, db.Post.action_mode_id, db.Post.user_id]).where(db.Post.id == post_id).gino.first()
    number_check = await db.select([db.ActionMode.number_check]).where(db.ActionMode.id == action_mode_id).gino.scalar()
    available = await count_available_actions(user_id)
    if number_check > available:
        return min(6, 3 + number_check - available + max(0, difficult - 3))  # Формула для расчета сложности сверх лимита (я проверил она рабочая)
    return min(6, difficult + number_check - 1)  # Формула расчета сложности в пределах лимита


async def apply_consequences(action_id: int, con_var: int):
    """
    Функция применяет последствие по айди действия и айди типа (успех/провал)
    """
    post_id = await db.select([db.Action.post_id]).where(db.Action.id == action_id).gino.scalar()
    action_mode_id = await db.select([db.Post.action_mode_id]).where(db.Post.id == post_id).gino.scalar()
    # Определяем на кого применяются последствия
    if con_var <= 4:
        user_id = await db.select([db.Post.user_id]).where(db.Post.id == post_id).gino.scalar()
    else:
        action = await db.select([db.Action.data]).where(db.Action.id == action_id).gino.scalar()
        user_id = action['user_id']
    form_id = await db.select([db.Form.id]).where(db.Form.user_id == user_id).gino.scalar()
    expeditor_id = await db.select([db.Expeditor.id]).where(db.Expeditor.form_id == form_id).gino.scalar()
    chat_id = await db.select([db.ActionMode.chat_id]).where(db.ActionMode.id == action_mode_id).gino.scalar()
    data = [x[0] for x in await db.select([db.Consequence.data]).where(and_(db.Consequence.action_id == action_id, db.Consequence.type == con_var)).gino.all()]
    # Применяем все последствия
    for con in data:
        type = con['type']
        match type:
            case 'add_debuff':
                debuff_id = con['debuff_id']
                await db.ExpeditorToDebuffs.create(expeditor_id=expeditor_id, debuff_id=debuff_id)
            case 'delete_debuff':
                row_id = con['row_id']
                await db.ExpeditorToDebuffs.delete.where(db.ExpeditorToDebuffs.id == row_id).gino.status()
            case 'delete_debuff_type':
                debuff_type_id = con['debuff_type_id']
                debuff_ids = [x[0] for x in await db.select([db.ExpeditorToDebuffs.debuff_id]).where(db.ExpeditorToDebuffs.expeditor_id == expeditor_id).gino.all()]
                debuff_ids = [x[0] for x in await db.select([db.StateDebuff.id]).where(and_(db.StateDebuff.type_id == debuff_type_id, db.StateDebuff.id.in_(debuff_ids))).gino.all()]
                await db.ExpeditorToDebuffs.delete.where(and_(db.ExpeditorToDebuffs.debuff_id.in_(debuff_ids), db.ExpeditorToDebuffs.expeditor_id == expeditor_id)).gino.status()
            case 'delete_all_debuffs':
                await db.ExpeditorToDebuffs.delete.where(db.ExpeditorToDebuffs.expeditor_id == expeditor_id).gino.status()
            case 'add_libido':
                bonus = con['bonus']
                current = await db.select([db.Form.libido_level]).where(db.Form.user_id == user_id).gino.scalar()
                await update_daughter_levels(user_id, libido_level=current + bonus)
            case 'add_subordination':
                bonus = con['bonus']
                current = await db.select([db.Form.subordination_level]).where(db.Form.user_id == user_id).gino.scalar()
                await update_daughter_levels(user_id, subordination_level=current + bonus)
            case 'set_pregnant':
                text = con['text']
                await db.Expeditor.update.values(pregnant=text).where(db.Expeditor.id == expeditor_id).gino.status()
            case 'delete_pregnant':
                await db.Expeditor.update.values(pregnant=None).where(db.Expeditor.id == expeditor_id).gino.status()
            case 'add_item':
                item_id = con['item_id']
                await db.ExpeditorToItems.create(expeditor_id=expeditor_id, item_id=item_id)
            case 'delete_item':
                row_id = con['row_id']
                await db.ExpeditorToItems.delete.where(db.ExpeditorToItems.id == row_id).gino.status()
            case 'desactivate_item':
                row_id = con['row_id']
                await take_off_item(row_id)
            case 'add_attribute':
                bonus = con['bonus']
                attribute_id = con['attribute_id']
                await db.ExpeditorToAttributes.update.values(value=db.ExpeditorToAttributes.value + bonus).where(and_(db.ExpeditorToAttributes.expeditor_id == expeditor_id, db.ExpeditorToAttributes.attribute_id == attribute_id)).gino.status()
    # Формируем сообщение о результате
    if not data:
        description = 'не указаны'
    else:
        description = ', '.join([await serialize_consequence(x) for x in data])
    action_data = await db.select([db.Action.data]).where(db.Action.id == action_id).gino.scalar()
    if action_data.get('type') == 'action':
        text = action_data['text']
    else:
        to_user_id = action_data['user_id']
        name = await db.select([db.Form.name]).where(db.Form.user_id == to_user_id).gino.scalar()
        user = (await bot.api.users.get(user_ids=[to_user_id]))[0]
        text = f'PvP с пользователем [id{to_user_id}|{name} / {user.first_name} {user.last_name}]'
    user_id = await db.select([db.Post.user_id]).where(db.Post.id == post_id).gino.scalar()
    user = (await bot.api.users.get(user_ids=[user_id]))[0]
    name = await db.select([db.Form.name]).where(db.Form.user_id == user_id).gino.scalar()
    reply = (f'Игрок [id{user_id}|{name} / {user.first_name} {user.last_name}] пытаетается совершить действие «{text}»\n'
             f'Результат проверки: {types_consequences[con_var]}\n'
             f'Полученные последствия: {description}')
    await bot.api.messages.send(peer_id=2000000000 + chat_id, message=reply)


async def apply_item(row_id: int):
    """
    Функция применяет предмет и записывает его действующие эффекты
    """
    expeditor_id, action_time, data = await db.select([db.ExpeditorToItems.expeditor_id, db.Item.action_time, db.Item.bonus]).select_from(
        db.ExpeditorToItems.join(db.Item, db.ExpeditorToItems.item_id == db.Item.id)
    ).where(db.ExpeditorToItems.id == row_id).gino.first()
    # Увеличиваем счетчик использований
    await db.ExpeditorToItems.update.values(count_use=db.ExpeditorToItems.count_use + 1).where(db.ExpeditorToItems.id == row_id).gino.status()
    # Активируем предмет
    await db.ActiveItemToExpeditor.create(expeditor_id=expeditor_id, remained_use=action_time, row_item_id=row_id)
    # Применяем все бонусы предмета
    # !!! Здесь не применяется сексуальное состояние и характеристики КЭ, т.к. они влияют не на базовые характеристики, а рассчитываются дополнительно
    for bonus in data:
        if bonus['type'] == 'state':
            if bonus.get('action', '') in ('add', 'delete'):
                debuff_id = bonus['debuff_id']
                if bonus['action'] == 'add':
                    row = await db.ExpeditorToDebuffs.create(expeditor_id=expeditor_id, debuff_id=debuff_id)
                    asyncio.get_event_loop().create_task(wait_disable_debuff(row.id))
                else:
                    await db.ExpeditorToDebuffs.delete.where(and_(db.ExpeditorToDebuffs.expeditor_id == expeditor_id, db.ExpeditorToDebuffs.debuff_id == debuff_id)).gino.status()
            elif bonus.get('action', '') == 'delete_type':
                type_id = bonus['type_id']
                row_ids = [x[0] for x in await db.select([db.ExpeditorToDebuffs.id]).select_from(
                    db.ExpeditorToDebuffs.join(db.StateDebuff, db.ExpeditorToDebuffs.debuff_id == db.StateDebuff.id)
                ).where(and_(db.ExpeditorToItems.expeditor_id == expeditor_id), db.StateDebuff.type_id == type_id).gino.all()]
                await db.ExpeditorToDebuffs.delete.where(db.ExpeditorToDebuffs.id.in_(row_ids)).gino.status()
            elif bonus['action'] == 'delete_all':
                await db.ExpeditorToDebuffs.delete.where(db.ExpeditorToDebuffs.expeditor_id == expeditor_id).gino.all()
        elif bonus['type'] == 'sex_state':
            if bonus.get('action', '') == 'set_pregnant':
                text = bonus['text']
                await db.Expeditor.update.values(pregnant=text).where(db.Expeditor.id == expeditor_id).gino.status()
            elif bonus.get('action', '') == 'delete_pregnant':
                await db.Expeditor.update.values(pregnant=None).where(db.Expeditor.id == expeditor_id).gino.status()


async def count_daughter_params(user_id: int) -> tuple[int, int]:
    """
    Функция рассчитывает уровень либидо и подчинения с учетом действующих бафов и дебафов
    """
    form_id = await get_current_form_id(user_id)
    libido, subordination = await db.select([db.Form.libido_level, db.Form.subordination_level]).where(db.Form.id == form_id).gino.first()
    expeditor_id = await db.select([db.Expeditor.id]).where(db.Expeditor.form_id == form_id).gino.scalar()
    if not expeditor_id:
        return libido, subordination
    # Учитываем бонусы от активных предметов
    active_items_data = [x[0] for x in await db.select([db.Item.bonus]).select_from(
        db.ActiveItemToExpeditor.join(db.ExpeditorToItems, db.ActiveItemToExpeditor.row_item_id == db.ExpeditorToItems.id)
        .join(db.Item, db.ExpeditorToItems.item_id == db.Item.id)
    ).where(db.ActiveItemToExpeditor.expeditor_id == expeditor_id).gino.all()]
    for data in active_items_data:
        for bonus in data:
            if bonus.get('type') == 'sex_state':
                if bonus.get('attribute') == 'libido':
                    libido += bonus['bonus']
                elif bonus.get('attribute') == 'subordination':
                    subordination += bonus['bonus']
    libido = min(100, max(0, libido))
    subordination = min(100, max(0, subordination))
    return libido, subordination


async def move_user(user_id: int, chat_id: int):
    """
    Перемещает пользователя из одного чата в другой

    При перемещении в публичный чат бот присылает ссылку на это чат
    При выходе из публичного чата бот ставит запрет писать сообщения в этом чате

    При перемещении в приватный чат бот приглашает участника
    При перемещении из приватного чата бот кикает участника
    (кроме случаев, когда чат приватный и у пользователя есть постоянный доступ именно по профессии,
    в этом случае также ставится запрет писать сообщения)
    """
    old_chat_id = await db.select([db.UserToChat.chat_id]).where(db.UserToChat.user_id == user_id).gino.scalar()
    if not old_chat_id:
        await db.UserToChat.create(chat_id=chat_id, user_id=user_id)
    else:
        await db.UserToChat.update.values(chat_id=chat_id).where(db.UserToChat.user_id == user_id).gino.status()
        is_old_private = await db.select([db.Chat.is_private]).where(db.Chat.chat_id == old_chat_id).gino.scalar()
        professions = [x[0] for x in await db.select([db.ChatToProfessions.profession_id]).where(db.ChatToProfessions.chat_id == old_chat_id).gino.all()]
        user_profession = await db.select([db.Form.profession]).where(db.Form.user_id == user_id).gino.scalar()
        # Если старый чат приватный и у пользователя нет постоянного доступа - кикаем
        if is_old_private and ((professions and user_profession not in professions) or not professions):
            try:
                await bot.api.messages.remove_chat_user(chat_id=old_chat_id, member_id=user_id)
            except:
                pass
        else:
            # Иначе ставим запрет на отправку сообщений
            await bot.api.request('messages.changeConversationMemberRestrictions',
                                  {'peer_id': old_chat_id + 2000000000, 'member_ids': user_id, 'action': 'ro'})
    is_private, count, user_chat_id = await db.select([db.Chat.is_private, db.Chat.visible_messages, db.Chat.user_chat_id]).where(db.Chat.chat_id == chat_id).gino.first()
    chat_name = (await bot.api.messages.get_conversations_by_id(peer_ids=[2000000000 + chat_id])).items[0].chat_settings.title
    states.set(user_id, service.states.Menu.MAIN)
    await db.User.update.values(state=str(service.states.Menu.MAIN)).where(db.User.user_id == user_id).gino.status()
    # Уведомляем о перемещении
    if old_chat_id:
        await bot.api.messages.send(message=f'Пользователь {await create_mention(user_id)} будет перемещен в чат «{chat_name}»',
                                    peer_id=old_chat_id + 2000000000)
    # Обрабатываем новый чат
    if not is_private:
        await bot.api.request('messages.changeConversationMemberRestrictions',
                              {'peer_id': chat_id + 2000000000, 'member_ids': user_id, 'action': 'rw'})
        link = (await bot.api.messages.get_invite_link(peer_id=2000000000 + chat_id, visible_messages_count=count)).link
        await bot.api.messages.send(message=f'Вы успешно перешли в чат «{chat_name}»\n'
                                            f'Ссылка на чат: {link}', keyboard=await keyboards.main_menu(user_id),
                                    peer_id=user_id)
    else:
        try:
            await user_bot.api.messages.add_chat_user(chat_id=user_chat_id, user_id=user_id, visible_messages_count=count)
        except:
            pass
        await bot.api.request('messages.changeConversationMemberRestrictions',
                              {'peer_id': chat_id + 2000000000, 'member_ids': user_id, 'action': 'rw'})
        await bot.api.messages.send(message=f'Вы успешно перешли в чат «{chat_name}»\n',
                                    keyboard=await keyboards.main_menu(user_id), peer_id=user_id)


async def create_cabin_chat(user_id: int):
    """
    Функция создает чат с локацией каюты пользователя. Добавляет туда бота и дает ему админку
    """
    cabin_number = await db.select([db.Form.cabin]).where(db.Form.user_id == user_id).gino.scalar()
    response = await user_bot.api.messages.create_chat(title=f'RP Among Us Каюта/Кельи № {cabin_number}')
    await asyncio.sleep(0.5)
    group_id = (await bot.api.groups.get_by_id()).groups[0].id
    await user_bot.api.request('bot.addBotToChat', {'peer_id': response.chat_id + 2000000000, 'bot_id': -(abs(group_id))})
    await asyncio.sleep(0.5)
    await user_bot.api.request('messages.setMemberRole', {'peer_id': response.chat_id + 2000000000, 'member_id': -(abs(group_id)), 'role': 'admin'})
    await asyncio.sleep(0.5)
    await user_bot.api.messages.edit_chat(chat_id=response.chat_id, permissions={"see_invite_link": "owner_and_admins",
                                                                                 'invite': 'owner_and_admins',
                                                                                 'change_info': 'owner_and_admins',
                                                                                 'change_pin': 'owner_and_admins',
                                                                                 'change_style': 'owner_and_admins',
                                                                                 'use_mass_mentions': 'owner_and_admins'})
    await asyncio.sleep(0.5)
    await db.Chat.create(is_private=True, visible_messages=10, cabin_user_id=user_id, user_chat_id=response.chat_id, chat_id=None)
    message = await user_bot.api.messages.send(message=f'/каюта {cabin_number}', peer_id=response.chat_id + 2000000000,
                                           random_id=0)
    await asyncio.sleep(0.5)
    await user_bot.api.messages.delete(message_ids=[message], delete_for_all=True)


async def update_daughter_levels(user_id: int, libido_level: int | None = None, subordination_level: int | None = None):
    """
    Функция обновляет параметры дочерей и отсылает информацию о том, что параметры пришли к нулю
    Также отправляет инфу о том, что у игрока появилась новая доп. цель

    Надо отслеживать, когда они придут в ноль поэтому лучше использовать эту функцию, чем менять параметры напрямую
    """
    old_target_ids = await get_available_daughter_target_ids(user_id)

    if libido_level is not None and subordination_level is not None:
        libido_level = min(max(0, libido_level), 100)
        subordination_level = min(max(0, subordination_level), 100)
        await db.Form.update.values(subordination_level=subordination_level, libido_level=libido_level).where(db.Form.user_id == user_id).gino.status()
    elif libido_level is None and subordination_level is not None:
        subordination_level = min(max(0, subordination_level), 100)
        await db.Form.update.values(subordination_level=subordination_level).where(db.Form.user_id == user_id).gino.status()
    elif libido_level is not None and subordination_level is None:
        libido_level = min(max(0, libido_level), 100)
        await db.Form.update.values(libido_level=libido_level).where(db.Form.user_id == user_id).gino.status()

    if subordination_level == 0:
        reply = f'Пользователь {await create_mention(user_id)} достиг уровня 0 по параметру «Подчинение»'
        await user_bot.api.messages.send(message=reply, random_id=0, peer_id=OWNER)
    if libido_level == 0:
        reply = f'Пользователь {await create_mention(user_id)} достиг уровня 0 по параметру «Либидо»'
        await user_bot.api.messages.send(message=reply, random_id=0, peer_id=OWNER)

    new_target_ids = await get_available_daughter_target_ids(user_id)

    if len(new_target_ids) > len(old_target_ids):
        target_id = new_target_ids[-1]
        target_name = await db.select([db.DaughterTarget.name]).where(db.DaughterTarget.id == target_id).gino.scalar()
        reply = f'Пользователь {await create_mention(user_id)} достиг доп. цели «{target_name}»'
        await user_bot.api.messages.send(message=reply, random_id=0, peer_id=OWNER)




