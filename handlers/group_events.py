import asyncio

from vkbottle import GroupEventType
from vkbottle_types.events.bot_events import GroupJoin

from loader import bot, user_bot
import messages


@bot.on.raw_event(GroupEventType.GROUP_JOIN, GroupJoin)
async def group_join(event: GroupJoin):
    group_id = (await bot.api.groups.get_by_id()).groups[0].id
    if await bot.api.groups.is_member(group_id=group_id, user_id=event.object.user_id):
        return
    await user_bot.api.groups.approve_request(group_id=event.group_id, user_id=event.object.user_id)
    await asyncio.sleep(0.34)
    can_write = (await user_bot.api.users.get(user_ids=[event.object.user_id],
                                      fields=['can_write_private_message']))[0].can_write_private_message  # type: ignore
    await asyncio.sleep(0.34)
    if can_write:
        await user_bot.api.messages.send(peer_id=event.object.user_id, message=messages.accepted_to_group, random_id=0)
