from vkbottle.bot import MessageEvent, Message
from vkbottle import GroupEventType
from vkbottle.dispatch.rules.base import PayloadMapRule
from vkbottle_types.objects import MessagesForward, UsersUserFull

from loader import bot
from service.db_engine import db
from service.custom_rules import AdminRule, ExpeditorRequestAvailable
from service.serializers import fields_content, RelatedTable, Field
from service.utils import send_edit_item


@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent, PayloadMapRule({'request_expeditor_id': int, 'action': 'confirm'}), AdminRule(), ExpeditorRequestAvailable())
async def confirm_expeditor(m: MessageEvent | Message, user: UsersUserFull, name: str, form_id: int, expeditor_id: int):
    await db.Expeditor.update.values(is_confirmed=True).where(db.Expeditor.id == expeditor_id).gino.status()
    data = await db.select([db.ExpeditorRequest.admin_id, db.ExpeditorRequest.message_id]).where(db.ExpeditorRequest.expeditor_id == expeditor_id).gino.all()
    if isinstance(m, MessageEvent):
        admin = (await bot.api.users.get(m.user_id))[0]
    else:
        admin = (await bot.api.users.get(m.from_id))[0]
    for admin_id, message_id in data:
        await bot.api.messages.send(message=f'✅ Карта экспедитора игрока [id{user.id}|{name} / {user.first_name} {user.last_name}] принята администратором '
                                            f'[id{admin_id}|{admin.first_name} {admin.last_name}]',
                                    forward=MessagesForward(
                                        peer_id=admin_id,
                                        conversation_message_ids=[message_id],
                                        is_reply=True
                                    ).json(),
                                    peer_id=admin_id)
    if isinstance(m, MessageEvent):
        await m.show_snackbar('Карта экспедитора успешно принята')
    await db.ExpeditorRequest.delete.where(db.ExpeditorRequest.expeditor_id == expeditor_id).gino.status()
    status = await db.select([db.Form.status]).where(db.Form.id == form_id).gino.scalar()
    if status == 2:
        fraction_id = await db.select([db.Form.fraction_id]).where(db.Form.id == form_id).gino.scalar()
        await db.change_reputation(user.id, fraction_id, 30)
        fraction_ids = {x[0] for x in await db.select([db.Fraction.id]).gino.all()}
        fraction_ids = fraction_ids - {fraction_id}
        for fraction_id in fraction_ids:
            await db.change_reputation(user.id, fraction_id, 10)
    else:
        fraction_ids = {x[0] for x in await db.select([db.Fraction.id]).gino.all()}
        for fraction_id in fraction_ids:
            await db.change_reputation(user.id, fraction_id, 10)
    await bot.api.messages.send(message='Поздравляем! Ваша карта экспедитора была принята!\n'
                                        'За заполнение Карты вы также получили бонусную репутацию во всех фракциях!',
                                peer_id=user.id,
                                is_notification=True)


@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent, PayloadMapRule({'request_expeditor_id': int, 'action': 'decline'}), AdminRule(), ExpeditorRequestAvailable())
async def decline_expeditor_request(m: MessageEvent, user: UsersUserFull, name: str, form_id: int, expeditor_id: int):
    data = await db.select([db.ExpeditorRequest.admin_id, db.ExpeditorRequest.message_id]).where(
        db.ExpeditorRequest.expeditor_id == expeditor_id).gino.all()
    await db.Expeditor.delete.where(db.Expeditor.id == expeditor_id).gino.status()
    admin = (await bot.api.users.get(m.user_id))[0]
    for admin_id, message_id in data:
        try:
            await bot.api.messages.send(
                message=f'❌ Карта экспедитора игрока [id{user.id}|{name} / {user.first_name} {user.last_name}] отклонена администратором '
                        f'[id{admin_id}|{admin.first_name} {admin.last_name}]',
                forward=MessagesForward(
                    peer_id=admin_id,
                    conversation_message_ids=[message_id],
                    is_reply=True
                ).json(),
                peer_id=admin_id)
        except:
            await bot.api.messages.send(
                message=f'❌ Карта экспедитора игрока [id{user.id}|{name} / {user.first_name} {user.last_name}] отклонена администратором '
                        f'[id{admin_id}|{admin.first_name} {admin.last_name}]',
                peer_id=admin_id)
    await m.show_snackbar('Карта экспедитора отклонена')
    await db.ExpeditorRequest.delete.where(db.ExpeditorRequest.expeditor_id == expeditor_id).gino.status()
    await bot.api.messages.send(message='К сожалению, ваша карта экспедитора была отклонена\n'
                                        'Свяжитесь с администрацией для выяснения причины',
                                peer_id=user.id,
                                is_notification=True)


@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent, PayloadMapRule({'request_expeditor_id': int, 'action': 'edit'}), AdminRule(), ExpeditorRequestAvailable())
async def edit_expeditor(m: MessageEvent):
    request_expeditor_id = m.payload['request_expeditor_id']
    expeditor_id = await db.select([db.ExpeditorRequest.expeditor_id]).where(db.ExpeditorRequest.id == request_expeditor_id).gino.scalar()
    item = await db.select([*db.Expeditor]).where(db.Expeditor.id == expeditor_id).gino.first()
    reply = ''
    attachment = None
    for i, data in enumerate(fields_content['Expeditor']['fields']):
        if isinstance(data, RelatedTable):
            if not data.serialize_func:
                reply += f"{i + 1}. {data.name}: {item[i + 1]}\n"
            else:
                reply += f"{i + 1}. {data.name}: {await data.serialize_func(item.id)}\n"
        elif isinstance(data, Field):
            if data.name == "Фото":
                attachment = item[i + 1]
            if not data.serialize_func:
                reply += f"{i + 1}. {data.name}: {item[i + 1]}\n"
            else:
                reply += f"{i + 1}. {data.name}: {await data.serialize_func(item[i + 1])}\n"
    await m.edit_message(reply, attachment=attachment)
    await send_edit_item(m.user_id, expeditor_id, 'Expeditor')
