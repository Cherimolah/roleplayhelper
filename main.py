"""
Основной файл запуска
"""
import asyncio
from datetime import datetime, timedelta, timezone
import traceback

from loguru import logger

from loader import bot, user_bot
import handlers  # Important
from service.db_engine import db
from service.utils import send_mailing, take_off_payments, quest_over, send_daylics, check_last_activity, timer_daughter_levels, calculate_time, wait_users_post, wait_take_off_item, wait_disable_debuff
from config import ADMINS, BOARD_FORMS_TOPIC_ID, ARCHIVE_FORMS_TOPIC_ID, GROUP_ID
from service.middleware import MaintainenceMiddleware, StateMiddleware, FormMiddleware, ActivityUsersMiddleware, StateMiddlewareME, ActionModeMiddleware
from service.keyboards import action_mode_panel

bot.labeler.message_view.register_middleware(MaintainenceMiddleware)
bot.labeler.message_view.register_middleware(FormMiddleware)
bot.labeler.message_view.register_middleware(StateMiddleware)
bot.labeler.message_view.register_middleware(ActivityUsersMiddleware)
bot.labeler.message_view.register_middleware(ActionModeMiddleware)
bot.labeler.raw_event_view.register_middleware(StateMiddlewareME)


async def on_startup():
    """
    Выполняется при запуске.
    В бэклог кладутся задачи отправки рассылок, снятия платы за аренду и
    окончания квеста
    :return: None
    """
    await db.connect()
    mailings = await db.Mailings.query.gino.all()
    for mail in mailings:
        if not mail.send_at or mail.send_at < datetime.now():
            continue
        delta = mail.send_at - datetime.now()
        asyncio.get_event_loop().create_task(send_mailing(delta.total_seconds(), mail.message_id, mail.id))
    form_ids = [x[0] for x in await db.select([db.Form.id]).gino.all()]
    for form_id in form_ids:
        asyncio.get_event_loop().create_task(take_off_payments(form_id))
    quests = await db.select([db.QuestToForm.form_id, db.QuestToForm.quest_id, db.QuestToForm.quest_start]).gino.all()
    for form_id, quest_id, start_at in quests:
        quest = await db.Quest.get(quest_id)
        cooldown = calculate_time(quest, start_at)
        if cooldown:
            asyncio.get_event_loop().create_task(quest_over(cooldown, form_id, quest_id))
    admins = [x[0] for x in await db.select([db.User.user_id]).where(db.User.admin > 0).gino.all()]
    if admins:
        await bot.api.messages.send(peer_ids=admins, message="🎉 Бот запущен!", is_notification=True)

    user_ids = [x[0] for x in await db.select([db.User.user_id]).gino.all()]
    for user_id in user_ids:
        asyncio.get_event_loop().create_task(check_last_activity(user_id))

    post_ids = [x[0] for x in await db.select([db.Post.id]).gino.all()]
    for post_id in post_ids:
        asyncio.get_event_loop().create_task(wait_users_post(post_id))

    item_ids = [x[0] for x in await db.select([db.ActiveItemToExpeditor.id]).gino.all()]
    for item_id in item_ids:
        asyncio.get_event_loop().create_task(wait_take_off_item(item_id))

    debuff_ids = [x[0] for x in await db.select([db.ExpeditorToDebuffs.id]).gino.all()]
    for debuff_id in debuff_ids:
        asyncio.get_event_loop().create_task(wait_disable_debuff(debuff_id))

    # Закрываем топики
    await user_bot.api.request('board.closeTopic', {'group_id': abs(GROUP_ID), 'topic_id': BOARD_FORMS_TOPIC_ID})
    await asyncio.sleep(0.33)
    await user_bot.api.request('board.closeTopic', {'group_id': abs(GROUP_ID), 'topic_id': ARCHIVE_FORMS_TOPIC_ID})

    await bot.api.messages.send(peer_id=486697492, message='Панель судьи', keyboard=action_mode_panel)

    asyncio.get_event_loop().create_task(polling())


def number_error():
    i = 1
    while True:
        yield i
        i += 1


err_num = number_error()


async def polling():
    """
    Функция поллинга для юзер бота
    """
    _polling = user_bot.polling
    logger.info("Starting {} for {!r}", type(_polling).__name__, _polling.api)

    async for event in _polling.listen():
        logger.debug("New event was received: {!r}", event)
        for update in event.get("updates", []):
            asyncio.get_event_loop().create_task(user_bot.router.route(update, _polling.api))


@bot.error_handler.register_error_handler(Exception)
async def exception(e: Exception, peer_id: int = None, message: int = None):
    """
    Информирует о произошедших ошибках
    :param e:
    :return:
    """
    print((datetime.now(timezone(timedelta(hours=5)))).strftime("%d.%m.%Y %H:%M:%S"))
    num = next(err_num)
    print(f"[ERROR] №{num}: {e}")
    print(traceback.format_exc(), "\n")
    await bot.api.messages.send(peer_ids=ADMINS, message=f"⚠ [Ошибка] №{num}\nPeer id: {peer_id}\nMessage: {message}\n\n"
                                                          f"\n{traceback.format_exc()}", random_id=0)


if __name__ == '__main__':
    bot.loop_wrapper.add_task(on_startup())
    bot.loop_wrapper.add_task(send_daylics())
    bot.loop_wrapper.add_task(timer_daughter_levels())
    bot.run_forever()
