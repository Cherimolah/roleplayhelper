from vkbottle.bot import Message, MessageEvent
from vkbottle.dispatch.rules.base import PayloadRule, PayloadMapRule
from vkbottle import Keyboard, Callback, KeyboardButtonColor, GroupEventType
from sqlalchemy import and_, func

from loader import bot
from service.custom_rules import StateRule
from service.states import Menu
from service.db_engine import db, now
from service.utils import get_current_form_id, create_mention, get_admin_ids
from service.serializers import serialize_target_reward
from config import DATETIME_FORMAT


async def page_mandatory_quest(e: Message | MessageEvent, page: int) -> tuple[str, Keyboard | None]:
    if isinstance(e, Message):
        form_id = await get_current_form_id(e.from_id)
    else:
        form_id = await get_current_form_id(e.user_id)
    quest: db.MandatoryQuest = await db.select([*db.MandatoryQuest]).where(
        and_(db.MandatoryQuest.form_ids.op('@>')([form_id]), db.MandatoryQuest.completed.is_(False),
             db.MandatoryQuest.expired_at > now())
    ).order_by(db.MandatoryQuest.id.asc()).offset(page - 1).limit(1).gino.first()
    count = await db.select([func.count(db.MandatoryQuest.id)]).where(
        and_(db.MandatoryQuest.form_ids.op('@>')([form_id]), db.MandatoryQuest.completed.is_(False),
             db.MandatoryQuest.expired_at > now())
    ).gino.scalar()
    if not quest:
        return '✅ На данный момент все обязательные квесты выполнены', None
    from_user_id = await db.select([db.Form.user_id]).where(db.Form.id == quest.from_form_id).gino.scalar()
    reply = (f'Квест «{quest.name}» от игрока {await create_mention(from_user_id)}\n'
             f'Описание: {quest.description}\n'
             f'Дата завершения: {quest.expired_at.strftime(DATETIME_FORMAT)}\n'
             f'Награда: {await serialize_target_reward(quest.reward)}\n'
             f'Штраф за невыполнение: {await serialize_target_reward(quest.reward)}')
    has_active_request = await db.select([db.MandatoryQuestRequest.id]).where(
        and_(db.MandatoryQuestRequest.quest_id == quest.id, db.MandatoryQuestRequest.checked.is_(False))
    ).gino.first()
    keyboard = None
    if not has_active_request:
        keyboard = Keyboard(inline=True).add(
            Callback('Отправить на проверку', {'mandatory_quest_check': quest.id}), KeyboardButtonColor.POSITIVE
        )
    if page > 1:
        if not keyboard:
            keyboard = Keyboard(inline=True).add(
                Callback('<-', {'mandatory_quest_page': page - 1}), KeyboardButtonColor.PRIMARY
            )
        else:
            keyboard.row().add(
                Callback('<-', {'mandatory_quest_page': page - 1}), KeyboardButtonColor.PRIMARY
            )
    if count > 1 and page < count:
        if not keyboard:
            keyboard = Keyboard(inline=True).add(
                Callback('->', {'mandatory_quest_page': page + 1}), KeyboardButtonColor.PRIMARY
            )
        else:
            keyboard.row().add(
                Callback('->', {'mandatory_quest_page': page + 1}), KeyboardButtonColor.PRIMARY
            )
    return reply, keyboard


@bot.on.private_message(PayloadRule({'menu': 'required_quests'}), StateRule(Menu.MAIN))
async def show_mandatory_quests(m: Message):
    reply, keyboard = await page_mandatory_quest(m, 1)
    await m.answer(reply, keyboard=keyboard)


@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent, PayloadMapRule({'mandatory_quest_page': int}))
async def show_mandatory_quest_page(e: MessageEvent):
    page = e.payload['mandatory_quest_page']
    reply, keyboard = await page_mandatory_quest(e, page)
    await e.edit_message(reply, keyboard=keyboard)


@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent, PayloadMapRule({'mandatory_quest_check': int}))
async def send_check_request_mandatory_quest(e: MessageEvent):
    quest_id = e.payload['mandatory_quest_check']
    has_active_request = await db.select([db.MandatoryQuestRequest.id]).where(
        and_(db.MandatoryQuestRequest.quest_id == quest_id, db.MandatoryQuestRequest.checked.is_(False))
    ).gino.first()
    if has_active_request:
        await e.show_snackbar('❌ По данному квесту уже есть активный запрос на проверку администрации')
        return
    quest = await db.MandatoryQuest.get(quest_id)
    request = await db.MandatoryQuestRequest.create(quest_id=quest_id)
    await e.edit_message(f'✅ Квест «{quest.name}» отправлен на проверку администрации')
    admins = await get_admin_ids()
    keyboard = Keyboard(inline=True).add(
        Callback('Принять', {'mandatory_quest_request': request.id, 'action': 'accept'}), KeyboardButtonColor.POSITIVE
    ).row().add(
        Callback('Отклонить', {'mandatory_quest_request': request.id, 'action': 'reject'}), KeyboardButtonColor.NEGATIVE
    )
    for admin in admins:
        await bot.api.messages.send(peer_id=admin, message=f'Пользователь {await create_mention(e.user_id)} '
                                                           f'отправил отчет о выполнении обязательного квеста «{quest.name}»\n'
                                                           f'Описание: {quest.description}',
                                    keyboard=keyboard)
