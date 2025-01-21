import asyncio
import random

from vkbottle import GroupEventType, API
from vkbottle_types.events.bot_events import GroupJoin
from vkbottle_types.objects import UsersFields

from loader import bot, users
import messages


@bot.on.raw_event(GroupEventType.GROUP_JOIN, GroupJoin)
async def group_join(event: GroupJoin):
    user: API = random.choice(users)
    group_id = (await bot.api.groups.get_by_id()).groups[0].id
    if await bot.api.groups.is_member(group_id, event.object.user_id):
        return
    await user.groups.approve_request(group_id=event.group_id, user_id=event.object.user_id)
    await asyncio.sleep(0.34)
    can_write = (await user.users.get(user_ids=[event.object.user_id],
                                      fields=[UsersFields.CAN_WRITE_PRIVATE_MESSAGE]))[0].can_write_private_message
    await asyncio.sleep(0.34)
    if can_write:
        await user.messages.send(user_id=event.object.user_id, random_id=0,
                                 message=messages.accepted_to_group)
