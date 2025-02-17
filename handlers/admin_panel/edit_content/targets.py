import json
import re

from vkbottle.bot import Message
from vkbottle.dispatch.rules.base import PayloadRule, PayloadMapRule
from vkbottle import Keyboard, Text, KeyboardButtonColor

import service.keyboards as keyboards
from loader import bot
from service.custom_rules import AdminRule, StateRule, NumericRule
from service.middleware import states
from service.states import Admin
from service.db_engine import db
from service.utils import send_content_page, allow_edit_content, FormatDataException, parse_ids, info_target_reward


daughter_params_regex = re.compile(r'^(?P<libido>\d+)\s*(?P<word>(или|и))\s*(?P<subordination>\d+)$')


@bot.on.private_message(StateRule(f"{Admin.SELECT_ACTION}_AdditionalTarget"), PayloadRule({"AdditionalTarget": "add"}), AdminRule())
async def create_quest(m: Message):
    target = await db.AdditionalTarget.create()
    states.set(m.from_id, f"{Admin.TARGET_NAME}*{target.id}")
    await m.answer("Напишите название дополнительной цели", keyboard=Keyboard())


@bot.on.private_message(StateRule(Admin.TARGET_NAME), AdminRule())
@allow_edit_content('AdditionalTarget', state=Admin.TARGET_DESCRIPTION,
                    text='Напишите описание доп. цели')
async def name_quest(m: Message):
    target_id = int(states.get(m.peer_id).split("*")[1])
    await db.AdditionalTarget.update.values(name=m.text).where(db.AdditionalTarget.id == target_id).gino.status()


@bot.on.private_message(StateRule(Admin.TARGET_DESCRIPTION), AdminRule())
@allow_edit_content('AdditionalTarget', state=Admin.TARGET_FRACTION_REPUTATION)
async def target_description(m: Message):
    target_id = int(states.get(m.peer_id).split("*")[1])
    await db.AdditionalTarget.update.values(description=m.text).where(db.AdditionalTarget.id == target_id).gino.status()
    status = await db.select([db.User.editing_content]).where(db.User.user_id == m.from_id).gino.scalar()
    if not status:
        fractions = [x[0] for x in await db.select([db.Fraction.name]).order_by(db.Fraction.id.asc()).gino.all()]
        reply = ("Имя для доп. цели установлено. Если хотите чтобы доп. цель выдавалась с определенного уровня "
                 "репутации, укажите сначала необходимую фракцию\n\n")
        for i, name in enumerate(fractions):
            reply += f"{i + 1}. {name}\n"
        keyboard = Keyboard().add(
            Text('Без выдачи по уровню репутации', {"target_reputation": False})
        )
        await m.answer(reply, keyboard=keyboard)


@bot.on.private_message(StateRule(Admin.TARGET_FRACTION_REPUTATION), PayloadRule({"target_reputation": False}), AdminRule())
@allow_edit_content('AdditionalTarget', state=Admin.TARGET_FRACTION)
async def target_without_reputation(m: Message):
    target_id = int(states.get(m.peer_id).split("*")[1])
    await db.AdditionalTarget.update.values(fraction_reputation=None, reputation=None).where(db.AdditionalTarget.id == target_id).gino.status()
    status = await db.select([db.User.editing_content]).where(db.User.user_id == m.from_id).gino.scalar()
    if not status:
        fractions = [x[0] for x in await db.select([db.Fraction.name]).order_by(db.Fraction.id.asc()).gino.all()]
        reply = "Укажите для какой фракции будет доступна доп. цель\n\n"
        for i, name in enumerate(fractions):
            reply += f"{i + 1}. {name}\n"
        keyboard = Keyboard().add(
            Text('Без выдачи по фракции', {"target_fraction": False})
        )
        await m.answer(reply, keyboard=keyboard)


@bot.on.private_message(StateRule(Admin.TARGET_FRACTION_REPUTATION), NumericRule(), AdminRule())
@allow_edit_content('AdditionalTarget', state=Admin.TARGET_REPUTATION,
                    text='Укажите уровень репутации с которого будет доступна доп. цель',
                    keyboard=Keyboard())
async def target_fraction_reputation(m: Message, value: int):
    target_id = int(states.get(m.peer_id).split("*")[1])
    fractions = [x[0] for x in await db.select([db.Fraction.id]).order_by(db.Fraction.id.asc()).gino.all()]
    if value > len(fractions):
        raise FormatDataException('Номер фракции слишком большой')
    fraction_id = fractions[value - 1]
    await db.AdditionalTarget.update.values(fraction_reputation=fraction_id).where(db.AdditionalTarget.id == target_id).gino.status()


@bot.on.private_message(StateRule(Admin.TARGET_REPUTATION), NumericRule(), AdminRule())
@allow_edit_content('AdditionalTarget', state=Admin.TARGET_FRACTION)
async def target_reputation(m: Message, value: int):
    if not -100 <= value <= 100:
        raise FormatDataException('Диапазон значений [-100; 100]')
    target_id = int(states.get(m.peer_id).split("*")[1])
    await db.AdditionalTarget.update.values(reputation=value).where(db.AdditionalTarget.id == target_id).gino.status()
    status = await db.select([db.User.editing_content]).where(db.User.user_id == m.from_id).gino.scalar()
    if not status:
        fractions = [x[0] for x in await db.select([db.Fraction.name]).order_by(db.Fraction.id.asc()).gino.all()]
        reply = "Укажите для какой фракции будет доступна доп. цель\n\n"
        for i, name in enumerate(fractions):
            reply += f"{i + 1}. {name}\n"
        keyboard = Keyboard().add(
            Text('Без выдачи по фракции', {"target_fraction": False})
        )
        await m.answer(reply, keyboard=keyboard)


@bot.on.private_message(StateRule(Admin.TARGET_FRACTION), PayloadRule({"target_fraction": False}), AdminRule())
@allow_edit_content('AdditionalTarget', state=Admin.TARGET_PROFESSION)
async def target_without_fractions(m: Message):
    target_id = int(states.get(m.peer_id).split("*")[1])
    await db.AdditionalTarget.update.values(fraction=None).where(db.AdditionalTarget.id == target_id).gino.status()
    status = await db.select([db.User.editing_content]).where(db.User.user_id == m.from_id).gino.scalar()
    if not status:
        professions = [x[0] for x in await db.select([db.Profession.name]).order_by(db.Profession.id.asc()).gino.all()]
        reply = "Укажите для какой фракции будет доступна доп. цель\n\n"
        for i, name in enumerate(professions):
            reply += f"{i + 1}. {name}\n"
        keyboard = Keyboard().add(
            Text('Без выдачи по профессии', {"target_profession": False})
        )
        await m.answer(reply, keyboard=keyboard)


@bot.on.private_message(StateRule(Admin.TARGET_FRACTION), NumericRule(), AdminRule())
@allow_edit_content('AdditionalTarget', state=Admin.TARGET_PROFESSION)
async def target_fraction(m: Message, value: int):
    target_id = int(states.get(m.peer_id).split("*")[1])
    fractions = [x[0] for x in await db.select([db.Fraction.id]).order_by(db.Fraction.id.asc()).gino.all()]
    if value > len(fractions):
        raise FormatDataException('Номер фракции слишком большой')
    fraction_id = fractions[value - 1]
    await db.AdditionalTarget.update.values(fraction=fraction_id).where(
        db.AdditionalTarget.id == target_id).gino.status()
    status = await db.select([db.User.editing_content]).where(db.User.user_id == m.from_id).gino.scalar()
    if not status:
        professions = [x[0] for x in await db.select([db.Profession.name]).order_by(db.Profession.id.asc()).gino.all()]
        reply = "Укажите для какой фракции будет доступна доп. цель\n\n"
        for i, name in enumerate(professions):
            reply += f"{i + 1}. {name}\n"
        keyboard = Keyboard().add(
            Text('Без выдачи по профессии', {"target_profession": False})
        )
        await m.answer(reply, keyboard=keyboard)


@bot.on.private_message(StateRule(Admin.TARGET_PROFESSION), PayloadRule({"target_profession": False}), AdminRule())
@allow_edit_content('AdditionalTarget', state=Admin.TARGET_DAUGHTER_PARAMS,
                    text='Укажите значения для необходимых параметров дочери.\n{Либидо} {и/или} {Подчинение}\n'
                         'Примеры:\n\n'
                         '10 и 15\n10 или 5\n\n',
                    keyboard=Keyboard().add(Text('Без выдачи по параметрам', {"target_params": False})))
async def target_without_profession(m: Message):
    target_id = int(states.get(m.peer_id).split("*")[1])
    await db.AdditionalTarget.update.values(profession=None).where(db.AdditionalTarget.id == target_id).gino.status()


@bot.on.private_message(StateRule(Admin.TARGET_PROFESSION), NumericRule(), AdminRule())
@allow_edit_content('AdditionalTarget', state=Admin.TARGET_DAUGHTER_PARAMS,
                    text='Укажите значения для необходимых параметров дочери.\n{Либидо} {и/или} {Подчинение}\n'
                         'Примеры:\n\n'
                         '10 и 15\n10 или 5\n\n',
                    keyboard=Keyboard().add(Text('Без выдачи по параметрам', {"target_params": False})))
async def target_profession(m: Message, value: int = None):
    target_id = int(states.get(m.peer_id).split("*")[1])
    professions = [x[0] for x in await db.select([db.Profession.id]).order_by(db.Profession.id.asc()).gino.all()]
    if value > len(professions):
        raise FormatDataException('Номер профессии слишком большой')
    profession_id = professions[value - 1]
    await db.AdditionalTarget.update.values(profession=profession_id).where(db.AdditionalTarget.id == target_id).gino.status()


@bot.on.private_message(StateRule(Admin.TARGET_DAUGHTER_PARAMS), PayloadRule({"target_params": False}), AdminRule())
@bot.on.private_message(StateRule(Admin.TARGET_DAUGHTER_PARAMS), AdminRule())
@allow_edit_content('AdditionalTarget', state=Admin.TARGET_FORMS,
                    text='Пришлите ссылки на пользователей, которым будет доступна доп. цель',
                    keyboard=Keyboard().add(Text('Без выдачи определённым пользователям', {"target_forms": False})))
async def target_daughter_params(m: Message):
    target_id = int(states.get(m.peer_id).split("*")[1])
    if m.payload:
        await db.AdditionalTarget.update.values(daughter_params=[]).where(db.AdditionalTarget.id == target_id).gino.status()
        return
    match = re.fullmatch(daughter_params_regex, m.text.lower())
    if not match:
        raise FormatDataException('Неправильный формат')
    libido = int(match.group('libido'))
    word = int(match.group('word') == 'или')
    subordination = int(match.group('subordination'))
    if not 0 <= libido <= 100 or not 0 <= subordination <= 100:
        raise FormatDataException('Либидо и подчинение должны находиться в диапазоне [0; 100]')
    await db.AdditionalTarget.update.values(daughter_params=[libido, subordination, word]).where(db.AdditionalTarget.id == target_id).gino.status()


@bot.on.private_message(StateRule(Admin.TARGET_FORMS), PayloadRule({"target_forms": False}), AdminRule())
@allow_edit_content('AdditionalTarget',  state=Admin.TARGET_REWARD, keyboard=Keyboard())
async def target_without_forms(m: Message):
    target_id = int(states.get(m.peer_id).split("*")[1])
    await db.AdditionalTarget.update.values(forms=[]).where(db.AdditionalTarget.id == target_id).gino.status()
    editing_content = await db.select([db.User.editing_content]).where(db.User.user_id == m.from_id).gino.scalar()
    if not editing_content:
        await m.answer((await info_target_reward())[0])


@bot.on.private_message(StateRule(Admin.TARGET_FORMS), AdminRule())
@allow_edit_content('AdditionalTarget', state=Admin.TARGET_REWARD)
async def target_forms(m: Message):
    user_ids = list(set(await parse_ids(m)))
    if not user_ids:
        raise FormatDataException('Пользователи не указаны')
    form_ids = [x[0] for x in await db.select([db.Form.id]).where(db.Form.user_id.in_(user_ids)).gino.all()]
    if not form_ids:
        raise FormatDataException('Указанные пользователи не найдены в базе')
    target_id = int(states.get(m.peer_id).split("*")[1])
    await db.AdditionalTarget.update.values(forms=form_ids).where(db.AdditionalTarget.id == target_id).gino.status()
    editing_content = await db.select([db.User.editing_content]).where(db.User.user_id == m.from_id).gino.scalar()
    if not editing_content:
        await m.answer((await info_target_reward())[0])


@bot.on.private_message(StateRule(Admin.TARGET_REWARD), AdminRule())
@allow_edit_content('AdditionalTarget', text='Доп. цель успешно создана', end=True)
async def target_reward(m: Message):
    text = m.text.lower()
    target_id = int(states.get(m.peer_id).split("*")[1])
    if text.startswith('реп'):
        try:
            fraction_id, reputation_bonus = map(int, text.split()[1:])
        except ValueError:
            raise FormatDataException('Неверно указаны параметры')
        fraction_id = await db.select([db.Fraction.id]).order_by(db.Fraction.id.asc()).offset(fraction_id - 1).limit(1).gino.scalar()
        if not fraction_id:
            raise FormatDataException('Неправильный номер фракции')
        data = json.dumps({
            'type': 'fraction_bonus',
            'fraction_id': fraction_id,
            'reputation_bonus': reputation_bonus
        })
        await db.AdditionalTarget.update.values(reward_info=data).where(db.AdditionalTarget.id == target_id).gino.status()
    elif text.startswith('вал'):
        try:
            _, bonus = text.split()
            bonus = int(bonus)
        except ValueError:
            raise FormatDataException('Неверно указаны параметры')
        data = json.dumps({
            'type': 'value_bonus',
            'bonus': bonus
        })
        await db.AdditionalTarget.update.values(reward_info=data).where(db.AdditionalTarget.id == target_id).gino.status()
    else:
        raise FormatDataException('Недоступный вариант награды')


@bot.on.private_message(StateRule(f"{Admin.SELECT_ACTION}_AdditionalTarget"), PayloadRule({"AdditionalTarget": "delete"}), AdminRule())
async def select_delete_quest(m: Message):
    targets = await db.select([db.AdditionalTarget.name]).order_by(db.AdditionalTarget.id.asc()).gino.all()
    if not targets:
        return "Дополнительные цели ещё не созданы"
    reply = "Выберите доп. цель для удаления:\n\n"
    for i, target in enumerate(targets):
        reply = f"{reply}{i + 1}. {target.name}\n"
    states.set(m.peer_id, Admin.TARGET_DELETE)
    await m.answer(reply, keyboard=Keyboard())


@bot.on.private_message(StateRule(Admin.TARGET_DELETE), NumericRule(), AdminRule())
async def delete_quest(m: Message, value: int):
    target_id = await db.select([db.AdditionalTarget.id]).order_by(db.AdditionalTarget.id.asc()).offset(value - 1).limit(1).gino.scalar()
    await db.AdditionalTarget.delete.where(db.AdditionalTarget.id == target_id).gino.status()
    states.set(m.peer_id, f"{Admin.SELECT_ACTION}_AdditionalTarget")
    await m.answer("Дополнительная цель успешно удалена", keyboard=keyboards.gen_type_change_content("AdditionalTarget"))
    await send_content_page(m, "AdditionalTarget", 1)
