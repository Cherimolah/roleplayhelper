from abc import ABC
from typing import Union

from vkbottle.dispatch.rules import ABCRule
from vkbottle.bot import Message, MessageEvent
from sqlalchemy import and_, func

from service.middleware import states
from service.db_engine import db
from loader import bot
import messages
from service.states import Menu
import service.keyboards as keyboards
from service.utils import get_mention_from_message, select_form, get_current_form_id


class StateRule(ABCRule[Message], ABC):

    def __init__(self, state: str, starts: bool = False):
        self.state = state
        self.starts = starts

    async def check(self, event: Union[Message, MessageEvent]):
        if isinstance(event, Message):
            user_state = states.get(event.from_id)
        elif isinstance(event, MessageEvent):
            user_state = states.get(event.user_id)
        else:
            return False
        if not user_state and not self.state:
            return True
        if not self.starts:
            return user_state == self.state
        return user_state.startswith(self.state)


class NumericRule(ABCRule[Message], ABC):

    async def check(self, event: Message):
        if event.text.isdigit():
            return {"value": int(event.text)}
        await event.answer("Необходимо ввести число")


class LimitSymbols(ABCRule[Message], ABC):

    def __init__(self, limit: int):
        self.limit = limit

    async def check(self, event: Message):
        if len(event.text) > self.limit:
            await event.answer(f"На это поле установлен лимит в {self.limit} символов")
            return False
        return True


class AdminRule(ABCRule, ABC):

    async def check(self, event: MessageEvent):
        admins = [x[0] for x in await db.select([db.User.user_id]).where(db.User.admin > 0).gino.all()]
        if isinstance(event, MessageEvent):
            return event.user_id in admins
        if isinstance(event, Message):
            return event.from_id in admins


class ValidateAccount(ABCRule[Message], ABC):

    async def check(self, m: Message):
        if isinstance(m, Message):
            balance, freeze = (await db.select([db.Form.balance, db.Form.freeze])
                               .select_from(db.Form.join(db.User,
                                                         and_(db.Form.user_id == db.User.user_id,
                                                              db.Form.number == db.User.activated_form)))
                               .where(db.Form.user_id == m.from_id).gino.first())
        else:
            balance, freeze = (await db.select([db.Form.balance, db.Form.freeze])
                               .select_from(db.Form.join(db.User,
                                                         and_(db.Form.user_id == db.User.user_id,
                                                              db.Form.number == db.User.activated_form)))
                               .where(db.Form.user_id == m.user_id).gino.first())
        if balance < 0:
            states.set(m.from_id, Menu.BANK_MENU)
            await bot.write_msg(m.peer_id, messages.banckrot, keyboard=keyboards.bank)
            return False
        if freeze:
            states.set(m.from_id, Menu.BANK_MENU)
            await bot.write_msg(m.peer_id, messages.freeze, keyboard=keyboards.bank)
            return False
        return True


class CommandWithAnyArgs(ABCRule, ABC):

    def __init__(self, command: str):
        prefixes = ["/", "!", ""]
        self.patterns = [f"{x}{command}" for x in prefixes]

    async def check(self, event: Message):
        for pattern in self.patterns:
            if event.text.lower().startswith(pattern):
                return {"params": event.text[len(pattern)+1:]}
        return False


class UserSpecified(ABCRule[Message], ABC):

    def __init__(self, state: str = None):
        self.state = state

    async def check(self, m: Message):
        state = states.get(m.from_id)
        if len(state.split("*")) == 2:
            form_id = int(state.split("*")[1])
            user_id = await db.select([db.Form.user_id]).where(db.Form.id == form_id).gino.scalar()
            return {"form": (form_id, user_id)}
        if len(state.split("*")) > 2:
            return False
        user_ids = await get_mention_from_message(m, True)
        if len(user_ids) > 1:
            return True
        user_id = user_ids[0]
        if not user_id:
            await bot.write_msg(m.peer_id, "Пользователь не указан")
            return
        names = [x[0] for x in await db.select([db.Form.name]).where(db.Form.user_id == user_id).gino.all()]
        if len(names) == 0:
            await bot.write_msg(m.peer_id, messages.not_form_id)
            return False
        if len(names) > 1:
            await select_form(self.state, user_id, m)
            return False
        form_id = await get_current_form_id(user_id)
        return {"form": (form_id, user_id)}


class ManyUsersSpecified(ABCRule[Message], ABC):

    async def check(self, event: Message):
        state = states.get(event.from_id)
        if len(state.split("*")) > 1:
            form_ids = list(map(int, state.split("*")[1:]))
            user_ids = [x[0] for x in await db.select([db.Form.user_id]).where(db.Form.id.in_(form_ids)).gino.all()]
            return {"forms": list(zip(form_ids, user_ids))}
        user_ids = await get_mention_from_message(event, True)
        if not user_ids:
            await bot.write_msg(event.peer_id, "Пользователей не найдено")
            return
        forms = []
        for user_id in user_ids:
            form_id = await get_current_form_id(user_id)
            forms.append(tuple([form_id, user_id]))
        return {"forms": forms}

