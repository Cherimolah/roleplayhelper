import inspect

from vkbottle.bot import Message, MessageEvent
from vkbottle.dispatch.rules.base import PayloadRule, PayloadMapRule
from vkbottle import GroupEventType, Keyboard

import messages
import service.keyboards as keyboards
from loader import bot
from service.custom_rules import AdminRule, StateRule, SelectContent, NumericRule, EditContent
from service.middleware import states
from service.states import Admin
from service.utils import page_content, send_edit_item, fields_content, Field, RelatedTable
from service.db_engine import db


@bot.on.private_message(StateRule(Admin.MENU), PayloadRule({"admin_menu": "edit_content"}), AdminRule())
@bot.on.private_message(AdminRule(), text='/content')
@bot.on.private_message(PayloadRule({"Cabins": "back"}), AdminRule())
@bot.on.private_message(PayloadRule({"Profession": "back"}), AdminRule())
@bot.on.private_message(PayloadRule({"Shop": "back"}), AdminRule())
@bot.on.private_message(PayloadRule({"Status": "back"}), AdminRule())
@bot.on.private_message(PayloadRule({"Quest": "back"}), AdminRule())
@bot.on.private_message(PayloadRule({"Daylic": "back"}), AdminRule())
@bot.on.private_message(PayloadRule({"Decor": "back"}), AdminRule())
@bot.on.private_message(PayloadRule({"Fraction": "back"}), AdminRule())
@bot.on.private_message(PayloadRule({"AdditionalTarget": "back"}), AdminRule())
@bot.on.private_message(PayloadRule({"DaughterQuest": "back"}), AdminRule())
@bot.on.private_message(PayloadRule({"DaughterTarget": "back"}), AdminRule())
@bot.on.private_message(PayloadRule({"Item": "back"}), AdminRule())
@bot.on.private_message(PayloadRule({"StateDebuff": "back"}), AdminRule())
async def select_edit_content(m: Message):
    states.set(m.from_id, Admin.SELECT_EDIT_CONTENT)
    await m.answer(messages.content, keyboard=keyboards.manage_content)


@bot.on.private_message(StateRule(Admin.SELECT_EDIT_CONTENT), PayloadMapRule({"edit_content": str}), AdminRule())
@bot.on.private_message(PayloadMapRule({"edit_content": str}), AdminRule())
async def select_action_with_cabins(m: Message):
    await db.User.update.values(editing_content=False).where(db.User.user_id == m.from_id).gino.status()
    table_name = m.payload['edit_content']
    states.set(m.from_id, f"{Admin.SELECT_ACTION}_{table_name}")
    reply, keyboard = await page_content(table_name, page=1)
    await m.answer(messages.select_action, keyboard=keyboards.gen_type_change_content(table_name))
    await m.answer(reply, keyboard=keyboard)


@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent, PayloadMapRule({"content_page": int, "content": str}), AdminRule())
async def show_page_content(m: MessageEvent):
    page = m.payload['content_page']
    content = m.payload['content']
    reply, keyboard = await page_content(content, page)
    await m.edit_message(message=reply, keyboard=keyboard)


@bot.on.private_message(SelectContent(), NumericRule(), AdminRule())
async def select_cabin(m: Message, value: int, content_type: str, table):
    item = await db.select([*table]).order_by(table.id.asc()).offset(value-1).limit(1).gino.first()
    if not item:
        return "Не найдено контента"
    reply = ""
    attachment = None
    for i, data in enumerate(fields_content[content_type]['fields']):
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
    keyboard = keyboards.manage_item(content_type, item.id)
    await m.answer(reply, keyboard=keyboard, attachment=attachment)


@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent, SelectContent(),
                  PayloadMapRule({"item_type": str, "item_id": int, "action": "delete"}))
async def delete_cabin_message_event(m: MessageEvent, content_type: str, table):
    item_id = m.payload["item_id"]
    item_name = await db.select([table.name]).where(table.id == item_id).gino.scalar()
    if table.__tablename__ == 'fractions':
        user_ids = [x[0] for x in
                    await db.select([db.Form.user_id]).where(db.Form.fraction_id == item_id).gino.all()]
        await db.Form.update.values(fraction_id=1).where(db.Form.user_id.in_(user_ids)).gino.status()
    if table.__tablename__ == 'additional_target':
        data = await db.select([db.Quest.id, db.Quest.target_ids]).where(
            db.Quest.target_ids.op('@>')([item_id])).gino.all()
        for quest_id, target_ids in data:
            target_ids.remove(item_id)
            await db.Quest.update.values(target_ids=target_ids).where(db.Quest.id == quest_id).gino.status()
        data = await db.select([db.QuestToForm.id, db.QuestToForm.active_targets]).where(
            db.QuestToForm.active_targets.op('@>')([item_id])).gino.all()
        for id_, target_ids in data:
            target_ids.remove(item_id)
            await db.QuestToForm.update.values(active_targets=target_ids).where(db.QuestToForm.id == id_).gino.status()
    if table.__tablename__ == 'quests':
        await db.QuestToForm.delete.where(db.QuestToForm.quest_id == item_id).gino.status()
        await db.QuestHistory.delete.where(db.QuestHistory.quest_id == item_id).gino.status()
    if table.__tablename__ == 'daughter_targets':
        data = await db.select([db.DaughterQuest.id, db.DaughterQuest.target_ids]).where(
            db.DaughterQuest.target_ids.op('@>')([item_id])).gino.all()
        for quest_id, target_ids in data:
            target_ids.remove(item_id)
            await db.DaughterQuest.update.values(target_ids=target_ids).where(
                db.DaughterQuest.id == quest_id).gino.status()
    await table.delete.where(table.id == item_id).gino.status()
    await m.edit_message(f"{fields_content[content_type]['name']} {item_name} успешно удалён")


@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent, SelectContent(),
                  PayloadMapRule({"item_type": str, "item_id": int, "action": "edit"}))
async def edit_cabin_message_event(m: MessageEvent, content_type: str, table):
    item = await db.select([*table]).where(table.id == m.payload['item_id']).gino.first()
    reply = ""
    attachment = None
    for i, data in enumerate(fields_content[content_type]['fields']):
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
    await send_edit_item(m.user_id, m.payload["item_id"], content_type)


@bot.on.private_message(EditContent(), NumericRule(), AdminRule())
async def select_field_to_edit(m: Message, value: int, content_type: str):
    if value > len(fields_content[content_type]['fields']):
        return "Слишком большое число"
    item_id = int(states.get(m.from_id).split("*")[1])
    states.set(m.from_id, f"{fields_content[content_type]['fields'][value - 1].state}*{item_id}")
    await m.answer(f"Введите новое значение для поля {fields_content[content_type]['fields'][value - 1].name}:",
                   keyboard=Keyboard())
    if fields_content[content_type]['fields'][value - 1].info_func:
        if len(inspect.signature(fields_content[content_type]['fields'][value - 1].info_func).parameters) == 0:
            text, keyboard = await fields_content[content_type]['fields'][value - 1].info_func()
        else:
            text, keyboard = await fields_content[content_type]['fields'][value - 1].info_func(item_id)
        await m.answer(text, keyboard=keyboard)
