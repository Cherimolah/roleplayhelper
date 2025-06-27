import asyncio
import datetime
import os
from typing import List, Tuple, Optional, Union
import re

from sqlalchemy import and_, func
from vkbottle_types.objects import PhotosPhotoSizes
from vkbottle.bot import Message, MessageEvent
import aiofiles
from vkbottle import Keyboard, Callback, KeyboardButtonColor

from service.db_engine import db
from loader import bot, photo_message_uploader, states
from service.serializers import fields
import messages
from bot_extended import AioHTTPClientExtended
import service.states
import service.keyboards as keyboards
from config import OWNER
from service.serializers import fields_content, serialize_target_reward, parse_orientation, fraction_levels, parse_cooldown, FormatDataException

mention_regex = re.compile(r"\[(?P<type>id|club|public)(?P<id>\d*)\|(?P<text>.+)\]")
link_regex = re.compile(r"https:/(?P<type>/|/m.)vk.com/(?P<screen_name>\w*)")
daughter_params_regex = re.compile(r'^(?P<libido>\d+)\s*(?P<word>(или|и))\s*(?P<subordination>\d+)$')

client = AioHTTPClientExtended()


def get_max_size_url(sizes: List[PhotosPhotoSizes]) -> str:
    square = 0
    index = 0
    for i, size in enumerate(sizes):
        if size.height * size.width > square:
            square = size.height * size.width
            index = i
    return sizes[index].url


async def loads_form(user_id: int, from_user_id: int, is_request: bool = None, form_id: int = None, absolute_params: bool = False) -> Tuple[
    str, Optional[str]]:
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
            f"Репутация: {reputation} ({rep_fraction})"
    if form.status == 2:
        subordination, libido = await db.select([db.Form.subordination_level, db.Form.libido_level]).where(
            db.Form.id == form.id
        ).gino.first()
        if not absolute_params:
            if 1 <= subordination <= 33:
                reply += '\nУровень подчинения: Низкий'
            elif 34 <= subordination <= 66:
                reply += '\nУровень подчинения: Средний'
            elif 67 <= subordination <= 100:
                reply += '\nУровень подчинения: Высокий'
            if 1 <= libido <= 33:
                reply += '\nУровень либидо: Низкий'
            elif 34 <= libido <= 66:
                reply += '\nУровень либидо: Средний'
            elif 67 <= libido <= 100:
                reply += '\nУровень либидо: Высокий'
        else:
            reply += (f'\nУровень подчинения: {subordination}\n'
                      f'Уровень либидо: {libido}')
    return reply, form.photo


async def create_mention(user_id: int):
    user = (await bot.api.users.get(user_id))[0]
    nickname = await db.select([db.Form.name]).where(db.Form.user_id == user_id).gino.scalar()
    return f"[id{user.id}|{user.first_name} {user.last_name} / {nickname}]"


async def parse_ids(m: Message) -> List[int]:
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
    names = list(map(lambda x: x.lower(), m.text.split("\n")))
    user_ids.extend([x[0] for x in await db.select([db.Form.user_id]).where(
        func.lower(db.Form.name).in_(names)
    ).gino.all()])
    return user_ids


async def get_mention_from_message(m: Message, many_users=False) -> Optional[Union[int, List[int]]]:
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
    photo_url = get_max_size_url(attachment.photo.sizes)
    response = await client.request_content(photo_url)
    if not os.path.exists("/".join(name.split("/")[:-1])):
        os.mkdir("/".join(name.split("/")[:-1]))
    async with aiofiles.open(name, mode="wb") as file:
        await file.write(response)
    photo = await photo_message_uploader.upload(name, peer_id=OWNER)
    if delete:
        os.remove(name)
    return photo


def parse_daughter_params(text: str) -> tuple[int, int, int]:
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
    await asyncio.sleep(sleep)
    user_ids = [x[0] for x in await db.select([db.User.user_id]).gino.all()]
    for i in range(0, len(user_ids), 100):
        await bot.api.messages.send(peer_ids=user_ids[i:i + 100], forward_messages=message_id, random_id=0,
                                    is_notification=True)
    await db.Mailings.delete.where(db.Mailings.id == mailing_id).gino.status()


async def take_off_payments(form_id: int):
    while True:
        info = await db.select([db.Form.balance, db.Form.freeze]).where(db.Form.id == form_id).gino.first()
        if not info:  # Анкета удалена
            return
        balance, freeze = info
        if not balance or balance < 0 or freeze:
            await asyncio.sleep(86400)  # Ждём сутки, вдруг появятся деньги или анкета разморозиться
            continue
        last_payment: datetime.datetime = await db.select([db.Form.last_payment]).where(
            db.Form.id == form_id).gino.scalar()
        today = datetime.datetime.now()
        delta = today - last_payment
        user_id = await db.select([db.Form.user_id]).where(db.Form.id == form_id).gino.scalar()
        if delta.days >= 7:
            cabin_type = await db.select([db.Form.cabin_type]).where(db.Form.id == form_id).gino.scalar()
            if cabin_type:
                price = await db.select([db.Cabins.cost]).where(db.Cabins.id == cabin_type).gino.scalar()
                func_price = sum([soft_divide(x[0], 10) for x in await db.select([db.Decor.price]).select_from(
                    db.UserDecor.join(db.Decor, db.UserDecor.decor_id == db.Decor.id)
                ).where(and_(db.UserDecor.user_id == user_id, db.Decor.is_func.is_(True))).gino.all()])
                price += func_price
                await db.Form.update.values(balance=db.Form.balance - price,
                                            last_payment=today - datetime.timedelta(seconds=20)).where(
                    db.Form.id == form_id
                ).gino.status()
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
    users = await db.select([db.User.user_id, db.User.admin]).order_by(db.User.admin.desc()).order_by(
        db.User.user_id.asc()).offset((page - 1) * 15).limit(15).gino.all()
    user_ids = [x[0] for x in users]
    users_info = await bot.api.users.get(user_ids)
    reply = messages.list_users
    for i, user in enumerate(users):
        reply = f"{reply}{(page - 1) * 15 + i + 1}. {'👑' if user.admin == 2 else '🅰' if user.admin == 1 else ''}" \
                f" [id{user.user_id}|{users_info[i].first_name} {users_info[i].last_name}]\n"
    keyboard = None
    count_users = await db.func.count(db.User.user_id).gino.scalar()
    if count_users % 15 == 0:
        count_pages = count_users // 15
    else:
        count_pages = count_users // 15 + 1
    reply = f"{reply}\n\nСтраница {page}/{count_pages}"
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
    return await db.select([db.Form.id]).where(db.Form.user_id == user_id).gino.scalar()


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
    "день", "дня", "дней", "день"
]
hours = [
    "час", "часа", "часов"
]
minutes = [
    "минуты", "мин", "минут", "мин", "минута"
]
seconds = [
    "сек", "секунды", "сек", "секунда", "секунд", "секунду"
]


def parse_period(text: str) -> Optional[int]:
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
    if not seconds:
        return
    await asyncio.sleep(seconds)
    active_quest = await db.select([db.QuestToForm.quest_id]).where(db.QuestToForm.form_id == form_id).gino.scalar()
    if active_quest != quest_id:
        return
    user_id = await db.select([db.Form.user_id]).where(db.Form.id == form_id).gino.scalar()
    name, penalty = await db.select([db.Quest.name, db.Quest.penalty]).where(db.Quest.id == quest_id).gino.first()
    await db.QuestToForm.delete.where(db.QuestToForm.form_id == form_id).gino.status()
    reply = f"Время выполнения квеста «{name}» завершилось"
    if penalty:
        reply += "\nВам выписан штраф:\n\n"
        await apply_reward(user_id, penalty)
        reply += await serialize_target_reward(penalty)
    await bot.api.messages.send(peer_id=user_id, message=reply, is_notification=True)


def calculate_time(quest: db.Quest, starts_at: datetime.datetime) -> int | None:
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
    quest_id, target_ids = await db.select([db.QuestToForm.quest_id, db.QuestToForm.active_targets]).where(
        db.QuestToForm.form_id == form_id
    ).gino.first()
    ready_quest = await db.select([db.ReadyQuest.id]).where(
        and_(db.ReadyQuest.quest_id == quest_id, db.ReadyQuest.form_id == form_id, db.ReadyQuest.is_claimed.is_(True))
    ).gino.scalar()
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
    today = datetime.datetime.now()
    expected = datetime.datetime(today.year, today.month, today.day, hours, minutes, seconds)
    if today > expected:
        expected = expected + datetime.timedelta(days=1)
    return (expected - today).total_seconds()


async def send_daylics():
    await asyncio.sleep(5)  # Wait for initialize gino
    while True:
        last_daylic = await db.select([db.Metadata.last_daylic_date]).gino.scalar()
        if not last_daylic:
            seconds = calculate_wait_time(hours=18)
        else:
            next_time = last_daylic + datetime.timedelta(days=3)
            seconds = (next_time - datetime.datetime.now()).total_seconds()
        await asyncio.sleep(seconds)
        data = await db.select([db.Form.id, db.Form.user_id]).where(
            db.Form.deactivated_daylic < datetime.datetime.now()).gino.all()
        for form_id, user_id in data:
            profession_id = await db.select([db.Form.profession]).where(db.Form.id == form_id).gino.scalar()
            daylic_used = [x[0] for x in await db.select([db.DaylicHistory.daylic_id]).where(db.DaylicHistory.form_id == form_id).gino.all()]
            daylic = await db.select([db.Daylic.id]).where(and_(db.Daylic.profession_id == profession_id, db.Daylic.id.notin_(daylic_used))).order_by(
                func.random()).gino.scalar()
            if not daylic:  # all daylics used, try clean pool
                await db.DaylicHistory.delete.where(db.DaylicHistory.form_id == form_id).gino.status()
                daylic = await db.select([db.Daylic.id]).where(db.Daylic.profession_id == profession_id).order_by(func.random()).gino.scalar()
            if daylic:
                await db.DaylicHistory.create(form_id=form_id, daylic_id=daylic)
                await db.Form.update.values(activated_daylic=daylic).where(db.Form.id == form_id).gino.status()
                await bot.api.messages.send(peer_id=user_id, message="Вам доступно новое ежедневное задание!",
                                            is_notification=True)
        await db.Metadata.update.values(last_daylic_date=datetime.datetime.now()).gino.status()
        await asyncio.sleep(5)


async def show_fields_edit(user_id: int, new=True):
    if new:
        form = dict(await db.select([*db.Form]).where(db.Form.user_id == user_id).gino.first())
        params = {k: v for k, v in form.items() if k not in ("id", "is_request")}
        params['is_request'] = True
        await db.Form.create(**params)
        await db.User.update.values(editing_form=True).where(db.User.user_id == user_id).gino.status()
    await db.User.update.values(state=service.states.Menu.SELECT_FIELD_EDIT_NUMBER).where(
        db.User.user_id == user_id).gino.status()
    states.set(user_id, service.states.Menu.SELECT_FIELD_EDIT_NUMBER)
    reply = ("Выберите поле для редактирования. "
             "Когда закончите нажмите кнопку «Подтвердить изменения»\n\n")
    for i, field in enumerate(fields):
        reply += f"{i + 1}. {field.name}\n"
    await bot.api.messages.send(message=reply, keyboard=keyboards.confirm_edit_form, peer_id=user_id)


async def page_content(table_name, page: int) -> Tuple[str, Optional[Keyboard]]:
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
    if page > 1:
        keyboard.add(Callback("<-", {"content_page": page - 1, "content": table_name}), KeyboardButtonColor.SECONDARY)
    if page * 15 < count:
        keyboard.add(Callback("->", {"content_page": page + 1, "content": table_name}), KeyboardButtonColor.SECONDARY)
    if pages > 1:
        reply += f"\nСтраница {page}/{pages}\n\n"
    return reply, keyboard


async def send_content_page(m: Union[Message, MessageEvent], table_name: str, page: int):
    reply, keyboard = await page_content(table_name, page)
    if isinstance(m, Message):
        await m.answer(messages.select_action, keyboard=keyboards.gen_type_change_content(table_name))
        await m.answer(reply, keyboard=keyboard)
    else:
        await m.send_message(reply, keyboard=keyboard)


def parse_reputation(rep_level: int) -> str:
    for level, name in fraction_levels.items():
        if rep_level >= level:
            return name
    return 'Не опознаный уровень'


async def get_reputation(from_user_id: int, to_user_id: int) -> Tuple[str, str]:
    fraction_id = await db.select([db.Form.fraction_id]).where(db.Form.user_id == to_user_id).gino.scalar()
    has_rep = await db.select([db.UserToFraction.id]).where(
        and_(db.UserToFraction.user_id == from_user_id, db.UserToFraction.fraction_id == fraction_id)
    ).gino.scalar()
    if has_rep:
        reputation = await db.select([db.UserToFraction.reputation]).where(
            and_(db.UserToFraction.user_id == to_user_id, db.UserToFraction.fraction_id == fraction_id)
        ).gino.scalar()
        name = await db.select([db.Fraction.name]).where(db.Fraction.id == fraction_id).gino.scalar()
        return name, parse_reputation(reputation)
    else:
        max_rep, fraction_id = await db.select([db.UserToFraction.reputation, db.UserToFraction.fraction_id]).where(
            and_(db.UserToFraction.user_id == to_user_id, db.UserToFraction.fraction_id == fraction_id)
        ).order_by(db.UserToFraction.reputation.desc()).gino.first()
        name = await db.select([db.Fraction.name]).where(db.Fraction.id == fraction_id).gino.scalar()
        return name, parse_reputation(max_rep)


def allow_edit_content(content_type: str, end: bool = False, text: str = None, state: str = None, keyboard=None):
    def decorator(function):
        async def wrapper(m: Message, value=None, form=None, *args, **kwargs):
            kwargs["m"] = m
            if value:
                kwargs["value"] = value
            if form:
                kwargs["form"] = form
            item_id = int(states.get(m.from_id).split("*")[1])
            editing_content = await db.select([db.User.editing_content]).where(
                db.User.user_id == m.from_id).gino.scalar()
            kwargs['editing_content'] = editing_content
            kwargs['item_id'] = item_id
            try:
                data = await function(**kwargs)
            except FormatDataException as e:
                await m.answer(f"Неправильный формат данных!\n{e}")
                return
            if editing_content:
                await m.answer("Новое значение успешно установлено")
                await send_edit_item(m.from_id, item_id, content_type)
            else:
                if state:
                    states.set(m.from_id, f"{state}*{item_id}")
                if text:
                    await m.answer(text, keyboard=keyboard)
                if end:
                    await send_content_page(m, content_type, 1)
                    states.set(m.from_id, service.states.Admin.SELECT_ACTION + "_" + content_type)
            return data

        return wrapper

    return decorator


async def send_edit_item(user_id: int, item_id: int, item_type: str):
    await db.User.update.values(editing_content=True).where(db.User.user_id == user_id).gino.status()
    item = await db.select([*getattr(db, item_type)]).where(getattr(db, item_type).id == item_id).gino.first()
    reply = "Выберите поле для редактирования\n\n"
    attachment = None
    for i, data in enumerate(fields_content[item_type]['fields']):
        if data.name == "Фото":
            attachment = item[i + 1]
        if not data.serialize_func:
            reply += f"{i + 1}. {data.name}: {item[i + 1]}\n"
        else:
            reply += f"{i + 1}. {data.name}: {await data.serialize_func(item[i + 1])}\n"
    keyboard = keyboards.get_edit_content(item_type)
    await db.User.update.values(state=f"{service.states.Admin.EDIT_CONTENT}_{item_type}*{item.id}").where(
        db.User.user_id == user_id).gino.status()
    states.set(user_id, f"{service.states.Admin.EDIT_CONTENT}_{item_type}*{item.id}")
    await bot.api.messages.send(message=reply, keyboard=keyboard.get_json(), peer_id=user_id, attachment=attachment)


def soft_divide(num: int, den: int) -> int:
    if num % den == 0:
        return int(num // den)
    return int(num // den) + 1


async def page_fractions(page: int) -> Tuple[str, Keyboard, str]:
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
    if user_id == 32650977:
        return
    time_to_freeze: int = await db.select([db.Metadata.time_to_freeze]).gino.scalar()
    await asyncio.sleep(time_to_freeze)
    last_activity: datetime.datetime = await db.select([db.User.last_activity]).where(
        db.User.user_id == user_id).gino.scalar()
    time_to_freeze: int = await db.select([db.Metadata.time_to_freeze]).gino.scalar()  # Can be updated after sleeping
    freeze = await db.select([db.Form.freeze]).where(db.Form.user_id == user_id).gino.scalar()
    if (datetime.datetime.now() - last_activity).total_seconds() >= time_to_freeze and not freeze:
        await db.Form.update.values(freeze=True).where(db.Form.user_id == user_id).gino.status()
        await bot.api.messages.send(message="❗ В связи с отсутствием вашей активности в течение "
                                            f"{parse_cooldown(time_to_freeze)} ваша анкета автоматически заморожена",
                                    peer_id=user_id, is_notification=True)
        name = await db.select([db.Form.name]).where(db.Form.user_id == user_id).gino.scalar()
        user = (await bot.api.users.get(user_id=user_id))[0]
        admins = [x[0] for x in await db.select([db.User.user_id]).where(db.User.admin > 0).gino.all()]
        await bot.api.messages.send(message=f"❗ Анкета [id{user_id}|{name} / {user.first_name} {user.last_name}] "
                                            f"автоматически заморожена",
                                    peer_ids=admins)

        time_to_delete = await db.select([db.Metadata.time_to_delete]).gino.scalar()
        await asyncio.sleep(time_to_delete - time_to_freeze)
        last_activity: datetime.datetime = await db.select([db.User.last_activity]).where(
            db.User.user_id == user_id).gino.scalar()
        time_to_delete: int = await db.select([db.Metadata.time_to_delete]).gino.scalar()
        is_exists = await db.select([db.Form.id]).where(db.Form.user_id == user_id).gino.scalar()
        freeze = await db.select([db.Form.freeze]).where(db.Form.user_id == user_id).gino.scalar()
        if last_activity and freeze and (
                datetime.datetime.now() - last_activity).total_seconds() >= time_to_delete and is_exists:
            await bot.api.messages.send(message=f"❗ В связми с отсутствием вашей активности в течение "
                                                f"{parse_cooldown(time_to_delete)} ваша анкета автоматичкески удалена",
                                        peer_id=user_id, is_notification=True)
            name = await db.select([db.Form.name]).where(db.Form.user_id == user_id).gino.scalar()
            await db.Form.delete.where(db.Form.user_id == user_id).gino.status()
            user = (await bot.api.users.get(user_id=user_id))[0]
            admins = [x[0] for x in await db.select([db.User.user_id]).where(db.User.admin > 0).gino.all()]
            await bot.api.messages.send(message=f"❗ Анкета [id{user_id}|{name} / {user.first_name} {user.last_name}] "
                                                f"была автоматически удалена",
                                        peer_ids=admins)


async def apply_reward(user_id: int, data: dict):
    if not data:
        return
    for reward in data:
        if reward['type'] == 'fraction_bonus':
            fraction_id = reward['fraction_id']
            reputation_bonus = reward['reputation_bonus']
            await db.change_reputation(user_id, fraction_id, reputation_bonus)
        elif reward['type'] == 'value_bonus':
            bonus = reward['bonus']
            await db.Form.update.values(balance=db.Form.balance + bonus).gino.status()
        elif reward['type'] == 'daughter_params':
            libido, subordination = await db.select([db.Form.libido_level, db.Form.subordination_level]).where(db.Form.user_id == user_id).gino.first()
            sub_level = min(100, max(0, subordination + reward['subordination']))
            lib_level = min(100, max(0, libido + reward['libido']))
            await db.Form.update.values(libido_level=lib_level).where(db.Form.user_id == user_id).gino.status()
            await db.Form.update.values(subordination_level=sub_level).where(db.Form.user_id == user_id).gino.status()


async def update_daughter_levels(user_id: int):
    while True:
        now = datetime.datetime.now()
        tomorrow = now + datetime.timedelta(days=1)
        tomorrow = datetime.datetime(tomorrow.year, tomorrow.month, tomorrow.day, 0, 0, 0)
        await asyncio.sleep((tomorrow - now).total_seconds() - 2)
        form_id = await get_current_form_id(user_id)
        quest = await db.select([*db.DaughterQuest]).where(db.DaughterQuest.to_form_id == form_id).gino.first()
        if quest:
            confirmed = await db.select([db.DaughterQuestRequest.confirmed]).where(
                and_(db.DaughterQuestRequest.quest_id == quest.id, db.DaughterQuestRequest.form_id == form_id,
                     db.DaughterQuestRequest.created_at == datetime.date.today())
            ).gino.scalar()
            if confirmed is None:
                await apply_reward(user_id, quest.penalty)
                reply = f' ❌ Вам выписан штраф за невыполнение квеста  «{quest.name}»:\n'
                reply += await serialize_target_reward(quest.penalty)
                await bot.api.messages.send(peer_id=user_id, message=reply, is_notification=True)
        bonus, sub_level, lib_level, fraction_id = await db.select(
            [db.Form.daughter_bonus, db.Form.subordination_level, db.Form.libido_level, db.Form.fraction_id]).where(
            db.Form.user_id == user_id).gino.first()
        multiplier = await db.select([db.Fraction.daughter_multiplier]).where(
            db.Fraction.id == fraction_id).gino.scalar()
        sub_level = min(100, max(0, int(sub_level + 2 + 2 * multiplier + bonus)))
        lib_level = min(100, max(0, int(lib_level + 2 + 2 * multiplier + bonus)))
        await db.Form.update.values(subordination_level=sub_level, libido_level=lib_level).where(
            db.Form.user_id == user_id).gino.status()
        await asyncio.sleep(15)
