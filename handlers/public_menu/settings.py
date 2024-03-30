from vkbottle.bot import Message
from vkbottle.dispatch.rules.base import PayloadRule
from vkbottle import Keyboard, Text, KeyboardButtonColor, Callback

from loader import bot
from service.keyboards import get_settings_menu
from service.db_engine import db
from service.custom_rules import StateRule
from service.states import Menu
from service.middleware import states


@bot.on.private_message(PayloadRule({"menu": "settings"}), StateRule(Menu.MAIN))
@bot.on.private_message(PayloadRule({"freeze": "back"}), StateRule(Menu.FREEZE_REQUEST))
@bot.on.private_message(PayloadRule({"delete": "back"}), StateRule(Menu.DELETE_FORM_REQUEST))
async def settings(m: Message):
    states.set(m.from_id, Menu.SETTING)
    await m.answer("Меню настроек", keyboard=await get_settings_menu(m.from_id))


@bot.on.private_message(PayloadRule({"settings": "notifications"}), StateRule(Menu.SETTING))
async def change_notifications(m: Message):
    is_enabled = await db.select([db.User.notification_enabled]).where(db.User.user_id == m.from_id).gino.scalar()
    await db.User.update.values(notification_enabled=not is_enabled).where(db.User.user_id == m.from_id).gino.status()
    if is_enabled:
        await m.answer("Вы больше не будете получать рассылки и уведомления о "
                       "дейликах, квестах, выплатах и т.д. от бота", keyboard=await get_settings_menu(m.from_id))
    else:
        await m.answer("Уведомления включены")
        await settings(m)


@bot.on.private_message(PayloadRule({"settings": "freeze_request"}), StateRule(Menu.SETTING))
async def send_freeze_request(m: Message):
    states.set(m.from_id, Menu.FREEZE_REQUEST)
    freeze = await db.select([db.Form.name, db.Form.freeze]).where(db.Form.user_id == m.from_id).gino.scalar()
    kb = Keyboard().add(
        Text(f"{'Разморозить' if freeze else 'Заморозить'} анкету", {"freeze": "send_request"}), KeyboardButtonColor.POSITIVE
    ).row().add(
        Text("Отмена", {"freeze": "back"}), KeyboardButtonColor.NEGATIVE
    )
    await m.answer("Вы действительно хотите отправить запрос на замораживание вашей анкеты?",
                   keyboard=kb)


@bot.on.private_message(PayloadRule({"freeze": "send_request"}), StateRule(Menu.FREEZE_REQUEST))
async def freeze_request_send_accepted(m: Message):
    has_req = await db.select([db.Form.freeze_request]).where(db.Form.user_id == m.from_id).gino.scalar()
    if has_req:
        await m.answer("У вас уже есть отправленный запрос на заморозку анкеты")
        return
    admins = [x[0] for x in await db.select([db.User.user_id]).where(db.User.admin > 0).gino.all()]
    name, freeze = await db.select([db.Form.name, db.Form.freeze]).where(db.Form.user_id == m.from_id).gino.first()
    kb = Keyboard(inline=True).add(
        Callback(f"{'Разморозить' if freeze else 'Заморозить'}", {"freeze": "accept", "user_id": m.from_id}), KeyboardButtonColor.POSITIVE
    ).add(
        Callback("Отклонить", {"freeze": "decline", "user_id": m.from_id}), KeyboardButtonColor.NEGATIVE
    )
    await db.Form.update.values(freeze_request=True).where(db.Form.user_id == m.from_id).gino.status()
    await bot.api.messages.send(admins,
                                f"Игрок [id{m.from_id}|{name}] хочет {'разморозить' if freeze else 'заморозить'} свою анкету",
                                keyboard=kb)
    await m.answer(f"Запрос на {'разморозку' if freeze else 'заморозку'} страницы отправлен")
    await settings(m)


@bot.on.private_message(PayloadRule({"settings": "delete_request"}), StateRule(Menu.SETTING))
async def ask_delete(m: Message):
    states.set(m.from_id, Menu.DELETE_FORM_REQUEST)
    kb = Keyboard().add(
        Text("Удалить анкету", {"delete": "send_request"}), KeyboardButtonColor.POSITIVE
    ).row().add(
        Text("Отмена", {"delete": "back"}), KeyboardButtonColor.NEGATIVE
    )
    await m.answer("Вы действительно хотите отправить запрос на удаление вашей анкеты?",
                   keyboard=kb)


@bot.on.private_message(PayloadRule({"delete": "send_request"}), StateRule(Menu.DELETE_FORM_REQUEST))
async def send_delete_request(m: Message):
    has_req = await db.select([db.Form.delete_request]).where(db.Form.user_id == m.from_id).gino.scalar()
    if has_req:
        await m.answer("У вас уже есть отправленный запрос на удаление анкеты")
        return
    admins = [x[0] for x in await db.select([db.User.user_id]).where(db.User.admin > 0).gino.all()]
    name, form_id = await db.select([db.Form.name, db.Form.id]).where(db.Form.user_id == m.from_id).gino.first()
    kb = Keyboard(inline=True).add(
        Callback("Удалить", {"delete": "accept", "user_id": m.from_id}), KeyboardButtonColor.POSITIVE
    ).add(
        Callback("Отклонить", {"delete": "decline", "user_id": m.from_id}), KeyboardButtonColor.NEGATIVE
    )
    await db.Form.update.values(delete_request=True).where(db.Form.id == form_id).gino.status()
    await bot.api.messages.send(admins,
                                f"Игрок [id{m.from_id}|{name}] хочет удалить свою анкету",
                                keyboard=kb)
    await m.answer("Запрос на удаление страницы отправлен")
    await settings(m)
