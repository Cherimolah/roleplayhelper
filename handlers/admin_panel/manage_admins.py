"""
Модуль для управления администраторами и судьями системы.
Позволяет добавлять и удалять администраторов, назначать судей.
"""

from vkbottle.bot import Message
from vkbottle.dispatch.rules.base import PayloadRule, PayloadMapRule
from vkbottle import Keyboard, Text, KeyboardButtonColor

import messages
import service.keyboards as keyboards
from loader import bot
from service.custom_rules import AdminRule, StateRule
from service.middleware import states
from service.states import Admin
from service.db_engine import db
from service.utils import get_mention_from_message
from handlers.admin_panel.users_list import send_administrators


@bot.on.private_message(StateRule(Admin.SELECT_MANAGE_ADMINS), PayloadRule({"manage_admins": "add_admin"}))
@bot.on.private_message(StateRule(Admin.ENTER_OLD_ADMIN_ID), PayloadRule({"manage_admins": "add_admin"}))
@bot.on.private_message(StateRule(Admin.ENTER_NEW_ADMIN_ID), PayloadRule({"manage_admins": "add_admin"}))
async def enter_new_admin_id(m: Message):
    """Начало процесса добавления нового администратора"""
    states.set(m.from_id, Admin.ENTER_NEW_ADMIN_ID)
    keyboard = Keyboard().add(
        Text('Назад', {'manage_judge': 'back'}), KeyboardButtonColor.NEGATIVE
    )
    await m.answer(messages.enter_new_admin_id, keyboard=keyboard)


@bot.on.private_message(StateRule(Admin.ENTER_NEW_ADMIN_ID), AdminRule())
async def ask_new_admin(m: Message):
    """Запрос подтверждения для нового администратора"""
    user_id = await get_mention_from_message(m)
    user = await bot.api.users.get(user_id)
    if not user_id:
        await m.answer(messages.user_not_found)
        return
    keyboard = Keyboard().add(
        Text("Подтвердить", {"new_admin": user_id}), KeyboardButtonColor.POSITIVE
    ).row().add(
        Text("Отклонить", {"new_admin": "decline"}), KeyboardButtonColor.NEGATIVE
    )
    states.set(m.from_id, Admin.CONFIRM_NEW_ADMIN_ID)
    await m.answer(messages.confirm_new_admin.format(f"[id{user[0].id}|{user[0].first_name} {user[0].last_name}]"),
                        keyboard=keyboard)


@bot.on.private_message(StateRule(Admin.CONFIRM_NEW_ADMIN_ID), PayloadMapRule({"new_admin": int}), AdminRule())
async def add_new_admin(m: Message):
    """Добавление нового администратора"""
    user_id = m.payload['new_admin']
    await db.User.update.values(admin=1).where(db.User.user_id == int(user_id)).gino.status()
    states.set(m.from_id, Admin.SELECT_MANAGE_ADMINS)
    user = await bot.api.users.get(user_id)
    await m.answer(messages.new_admin.format(f"[id{user[0].id}|{user[0].first_name} {user[0].last_name}]"))
    await m.answer(messages.manage_admins, keyboard=keyboards.manage_admins)


@bot.on.private_message(StateRule(Admin.SELECT_MANAGE_ADMINS), PayloadRule({"manage_admins": "delete_admins"}))
async def delete_old_admin(m: Message):
    """Начало процесса удаления администратора"""
    states.set(m.from_id, Admin.ENTER_OLD_ADMIN_ID)
    keyboard = Keyboard().add(
        Text('Назад', {'manage_judge': 'back'}), KeyboardButtonColor.NEGATIVE
    )
    await m.answer(messages.enter_old_admin, keyboard=keyboard)


@bot.on.private_message(StateRule(Admin.ENTER_OLD_ADMIN_ID), AdminRule())
async def ask_old_admin(m: Message):
    """Запрос подтверждения для удаления администратора"""
    user_id = await get_mention_from_message(m)
    user = await bot.api.users.get(user_id)
    if not user_id:
        await m.answer(messages.user_not_found)
        return
    keyboard = Keyboard().add(
        Text("Подтвердить", {"old_admin": user_id}), KeyboardButtonColor.POSITIVE
    ).row().add(
        Text("Отклонить", {"old_admin": "decline"}), KeyboardButtonColor.NEGATIVE
    )
    states.set(m.from_id, Admin.CONFIRM_OLD_ADMIN_ID)
    await m.answer(messages.confirm_old_admin.format(f"[id{user[0].id}|{user[0].first_name} {user[0].last_name}]"),
                        keyboard=keyboard)


@bot.on.private_message(StateRule(Admin.CONFIRM_OLD_ADMIN_ID), PayloadMapRule({"old_admin": int}), AdminRule())
async def delete_old_admin_(m: Message):
    """Удаление администратора"""
    user_id = m.payload['old_admin']
    await db.User.update.values(admin=0).where(db.User.user_id == int(user_id)).gino.status()
    states.set(m.from_id, Admin.SELECT_MANAGE_ADMINS)
    user = await bot.api.users.get(user_id)
    await m.answer(messages.deleted_admin.format(f"[id{user[0].id}|{user[0].first_name} {user[0].last_name}]"))
    await send_administrators(m)


@bot.on.private_message(StateRule(Admin.SELECT_MANAGE_ADMINS), PayloadRule({"manage_admins": "add_judge"}), AdminRule())
async def select_judge_to_add(m: Message):
    """Начало процесса добавления судьи"""
    states.set(m.from_id, Admin.ADD_JUDGE)
    keyboard = Keyboard().add(
        Text('Назад', {'manage_judge': 'back'}), KeyboardButtonColor.NEGATIVE
    )
    await m.answer('Отправьте ссылку/ссобщения/упоминание на пользователя, которого хотите назначить судьёй',
                   keyboard=keyboard)


@bot.on.private_message(StateRule(Admin.ADD_JUDGE), AdminRule())
async def ask_new_admin(m: Message):
    """Запрос подтверждения для нового судьи"""
    user_id = await get_mention_from_message(m)
    user = (await bot.api.users.get(user_id))[0]
    if not user_id:
        await m.answer(messages.user_not_found)
        return
    keyboard = Keyboard().add(
        Text("Подтвердить", {"new_judge": user_id}), KeyboardButtonColor.POSITIVE
    ).row().add(
        Text("Отклонить", {"new_judge": "decline"}), KeyboardButtonColor.NEGATIVE
    )
    states.set(m.from_id, Admin.ENTER_NEW_JUDGE)
    name = await db.select([db.Form.name]).where(db.User.user_id == user_id).gino.scalar()
    await m.answer(f'Подтвердить выдачу прав судьи пользователю [id{user_id}|{name} / {user.first_name} {user.last_name}]',keyboard=keyboard)


@bot.on.private_message(StateRule(Admin.ENTER_NEW_JUDGE), PayloadMapRule({"new_judge": int}), AdminRule())
async def create_new_judge(m: Message):
    """Добавление нового судьи"""
    user_id = m.payload['new_judge']
    await db.User.update.values(judge=True).where(db.User.user_id == user_id).gino.status()
    name = await db.select([db.Form.name]).where(db.User.user_id == user_id).gino.scalar()
    user = (await bot.api.users.get(user_id))[0]
    await m.answer(f'Вы выдали права судьи пользователю [id{user_id}|{name} / {user.first_name} {user.last_name}]')
    await send_administrators(m)


@bot.on.private_message(StateRule(Admin.SELECT_MANAGE_ADMINS), PayloadRule({'manage_admins': 'delete_judge'}))
async def delete_old_admin(m: Message):
    """Начало процесса удаления судьи"""
    states.set(m.from_id, Admin.DELETE_JUDGE)
    keyboard = Keyboard().add(
        Text('Назад', {'manage_judge': 'back'}), KeyboardButtonColor.NEGATIVE
    )
    await m.answer('Отправьте ссылку/пересланное сообщение/упоминание на человека, с которого хотите снять роль судьи',
                   keyboard=keyboard)


@bot.on.private_message(StateRule(Admin.DELETE_JUDGE), AdminRule())
async def ask_old_admin(m: Message):
    """Запрос подтверждения для удаления судьи"""
    user_id = await get_mention_from_message(m)
    user = (await bot.api.users.get(user_id))[0]
    if not user_id:
        await m.answer(messages.user_not_found)
        return
    keyboard = Keyboard().add(
        Text("Подтвердить", {"old_judge": user_id}), KeyboardButtonColor.POSITIVE
    ).row().add(
        Text("Отклонить", {"old_judge": "decline"}), KeyboardButtonColor.NEGATIVE
    )
    name = await db.select([db.Form.name]).where(db.Form.user_id == user_id).gino.scalar()
    states.set(m.from_id, Admin.ENTER_OLD_JUDGE)
    await m.answer(
        f'Подтвердить снятие прав судьи с пользователя [id{user_id}|{name} / {user.first_name} {user.last_name}]',
        keyboard=keyboard)


@bot.on.private_message(StateRule(Admin.ENTER_OLD_JUDGE), PayloadMapRule({"old_judge": int}), AdminRule())
async def delete_old_admin_(m: Message):
    """Удаление судьи"""
    user_id = m.payload['old_judge']
    await db.User.update.values(judge=False).where(db.User.user_id == user_id).gino.status()
    name = await db.select([db.Form.name]).where(db.User.user_id == user_id).gino.scalar()
    user = (await bot.api.users.get(user_id))[0]
    await m.answer(f'Вы сняли права судьи с пользователя [id{user_id}|{name} / {user.first_name} {user.last_name}]')
    await send_administrators(m)
