import asyncio
import random

from vkbottle import GroupEventType, API
from vkbottle_types.events.bot_events import GroupJoin

from loader import bot, users
import messages


@bot.on.raw_event(GroupEventType.GROUP_JOIN, GroupJoin)
async def group_join(event: GroupJoin):
    user: API = random.choice(users)
    group_id = (await bot.api.groups.get_by_id())[0].id
    if await bot.api.groups.is_member(group_id, event.object.user_id):
        return
    await user.groups.approve_request(event.group_id, event.object.user_id)
    await asyncio.sleep(0.34)
    can_write = (await user.users.get([event.object.user_id],
                                      fields=["can_write_private_message"]))[0].can_write_private_message
    await asyncio.sleep(0.34)
    if can_write:
        await user.messages.send(user_id=event.object.user_id, random_id=0,
                                 message=messages.accepted_to_group)
