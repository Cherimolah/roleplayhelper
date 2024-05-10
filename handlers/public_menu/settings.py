import asyncio
import sys
import subprocess

from vkbottle.bot import Message
from vkbottle.dispatch.rules.base import PayloadRule
from vkbottle import Keyboard, Text, KeyboardButtonColor, Callback

from loader import bot
from service.keyboards import get_settings_menu, main_menu, timing_keyboard
from service.db_engine import db
from service.custom_rules import StateRule, AdminRule
from service.states import Menu, Admin
from service.middleware import states
from service.utils import parse_cooldown, parse_period, check_last_activity
from config import SYSTEMD_NAME


@bot.on.private_message(PayloadRule({"menu": "settings"}), StateRule(Menu.MAIN))
@bot.on.private_message(PayloadRule({"freeze": "back"}), StateRule(Menu.FREEZE_REQUEST))
@bot.on.private_message(PayloadRule({"delete": "back"}), StateRule(Menu.DELETE_FORM_REQUEST))
@bot.on.private_message(PayloadRule({"timing": "back"}), StateRule(Admin.TIMING_SETTINGS))
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
    has_req = await db.select([db.Form.freeze_request]).where(db.Form.user_id == m.from_id).gino.scalar()
    if has_req:
        await m.answer("У вас уже есть отправленный запрос на заморозку/разморозку анкеты")
        return
    states.set(m.from_id, Menu.FREEZE_REQUEST)
    freeze = await db.select([db.Form.freeze]).where(db.Form.user_id == m.from_id).gino.scalar()
    kb = Keyboard().add(
        Text(f"Подтвердить", {"freeze": "send_request"} if not freeze else {"unfreeze": "send_request"}), KeyboardButtonColor.POSITIVE
    ).row().add(
        Text("Назад", {"freeze": "back"}), KeyboardButtonColor.NEGATIVE
    )
    await m.answer('Вы действительно готовы "разморозить" свою анкету, чтобы вернуться к активной деятельности на станции?' if freeze else 'Вы действительно хотите оформить запрос для отправки вашей анкеты "на мороз"?',
                   keyboard=kb)


@bot.on.private_message(PayloadRule({"freeze": "send_request"}), StateRule(Menu.FREEZE_REQUEST))
async def ask_reason_freeze(m: Message):
    states.set(m.from_id, Menu.FREEZE_REASON)
    await m.answer("Кратко опишите причину \"Заморозки\" и примерное время вашего отсутствия", keyboard=Keyboard())


@bot.on.private_message(PayloadRule({"unfreeze": "send_request"}), StateRule(Menu.FREEZE_REQUEST))
@bot.on.private_message(StateRule(Menu.FREEZE_REASON))
async def freeze_request_send_accepted(m: Message):
    admins = [x[0] for x in await db.select([db.User.user_id]).where(db.User.admin > 0).gino.all()]
    name, freeze = await db.select([db.Form.name, db.Form.freeze]).where(db.Form.user_id == m.from_id).gino.first()
    kb = Keyboard(inline=True).add(
        Callback(f"{'Разморозить' if freeze else 'Заморозить'}", {"freeze": "accept", "user_id": m.from_id}), KeyboardButtonColor.POSITIVE
    ).add(
        Callback("Отклонить", {"freeze": "decline", "user_id": m.from_id}), KeyboardButtonColor.NEGATIVE
    )
    await db.Form.update.values(freeze_request=True).where(db.Form.user_id == m.from_id).gino.status()
    if not freeze:
        reply = f"Игрок [id{m.from_id}|{name}] хочет заморозить свою анкету по причине:\n{m.text}"
    else:
        reply = f"Игрок [id{m.from_id}|{name}] хочет разморозить свою анкету"
    await bot.api.messages.send(admins,
                                reply,
                                keyboard=kb)
    await m.answer(f"Запрос на {'разморозку' if freeze else 'заморозку'} страницы отправлен")
    states.set(m.from_id, Menu.MAIN)
    await m.answer("Главное меню", keyboard=await main_menu(m.from_id))


@bot.on.private_message(PayloadRule({"settings": "delete_request"}), StateRule(Menu.SETTING))
async def ask_delete(m: Message):
    states.set(m.from_id, Menu.DELETE_FORM_REQUEST)
    kb = Keyboard().add(
        Text("Подтвердить", {"delete": "send_request"}), KeyboardButtonColor.POSITIVE
    ).row().add(
        Text("Назад", {"delete": "back"}), KeyboardButtonColor.NEGATIVE
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


@bot.on.private_message(PayloadRule({"settings": "maintainence"}), StateRule(Menu.SETTING), AdminRule())
async def change_maintainence(m: Message):
    m_break = await db.select([db.Metadata.maintainence_break]).gino.scalar()
    await db.Metadata.update.values(maintainence_break=not m_break).gino.status()
    if not m_break:
        await m.answer("⚠ Режим технического обслуживания включён. Бот доступен только для администраторов",
                       keyboard=await get_settings_menu(m.from_id))
    else:
        await m.answer("Режим технического обслуживания выключен. Бот доступен для всех",
                       keyboard=await get_settings_menu(m.from_id))


@bot.on.private_message(PayloadRule({"settings": "restart"}), StateRule(Menu.SETTING), AdminRule())
async def restart(m: Message):
    if not sys.platform.startswith("linux"):
        return "Перезапуск возможен только в среде Linux"
    await m.answer("Бот будет обновлён до последней версии и перезапущен")
    subprocess.run(["systemctl", "restart", SYSTEMD_NAME])


@bot.on.private_message(PayloadRule({"settings": "timing"}), StateRule(Menu.SETTING), AdminRule())
async def timing(m: Message):
    metadata = await db.select([*db.Metadata]).gino.first()
    states.set(m.from_id, Admin.TIMING_SETTINGS)
    await m.answer(f"Текущие настройки таймера:\n\n"
                   f"Заморозка анкеты после {parse_cooldown(metadata.time_to_freeze)} неактивности игрока\n"
                   f"Удаление анкеты после {parse_cooldown(metadata.time_to_delete)} неактивности игрока",
                   keyboard=timing_keyboard)


@bot.on.private_message(PayloadRule({"timing": "freeze"}), StateRule(Admin.TIMING_SETTINGS), AdminRule())
async def freeze_timing(m: Message):
    states.set(m.from_id, Admin.FREEZE_TIMING)
    await m.answer("Введите время неактивности после которого анкета будет автоматически заморожена\n"
                   "В формате 1 год 2 месяца 3 дня 4 часа 5 минут 6 секунд", keyboard=Keyboard())


@bot.on.private_message(StateRule(Admin.FREEZE_TIMING), AdminRule())
async def set_freeze_timing(m: Message):
    period = parse_period(m.text)
    if not period:
        return "Неверный период"
    user_ids = [x[0] for x in await db.select([db.User.user_id]).gino.all()]
    for user_id in user_ids:
        asyncio.get_event_loop().create_task(check_last_activity(user_id))
    await db.Metadata.update.values(time_to_freeze=period).gino.status()
    await m.answer(f"Анкеты будут замораживаться после {parse_cooldown(period)} неактивности игроков")
    return await timing(m)


@bot.on.private_message(PayloadRule({"timing": "delete"}), StateRule(Admin.TIMING_SETTINGS), AdminRule())
async def delete_timing(m: Message):
    states.set(m.from_id, Admin.DELETE_TIMING)
    await m.answer("Введите время неактивности после которого анкета будет автоматически УДАЛЕНА\n"
                   "В формате 1 год 2 месяца 3 дня 4 часа 5 минут 6 секунд", keyboard=Keyboard())


@bot.on.private_message(StateRule(Admin.DELETE_TIMING), AdminRule())
async def set_delete_timing(m: Message):
    period = parse_period(m.text)
    if not period:
        return "Неверный период"
    time_to_freeze = await db.select([db.Metadata.time_to_freeze]).gino.scalar()
    if time_to_freeze >= period:
        return "Время для удаления должно быть больше времени на заморозку"
    await db.Metadata.update.values(time_to_delete=period).gino.status()
    user_ids = [x[0] for x in await db.select([db.User.user_id]).gino.all()]
    for user_id in user_ids:
        asyncio.get_event_loop().create_task(check_last_activity(user_id))
    await m.answer(f"Анкеты будут удаляться после {parse_cooldown(period)} неактивности игроков")
    return await timing(m)
