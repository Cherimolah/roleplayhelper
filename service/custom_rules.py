"""
Модуль с кастомными правилами для хедлеров
"""
import re
from typing import Union, Optional

from vkbottle.dispatch.rules import ABCRule
from vkbottle.bot import Message, MessageEvent
from vkbottle_types.objects import MessagesMessageActionStatus

from loader import states, bot
from service.db_engine import db
import messages
from service.states import Menu, Admin, Judge
import service.keyboards as keyboards
from service.utils import get_mention_from_message, get_current_form_id, fields_content, get_current_turn
from config import ADMINS
from service.states import StateValue


class StateRule(ABCRule[Message]):
    """
    Класс проверки состояния игрока. Возвращает True если игрок находится в правильном состоянии (см. использование в README)
    """

    def __init__(self, state: str | StateValue):
        self.state = str(state)

    async def check(self, event: Union[Message, MessageEvent]):
        if isinstance(event, Message):
            user_state = states.get(event.from_id)
            if not user_state:
                user_state = await db.select([db.User.state]).where(db.User.user_id == event.from_id).gino.scalar()
        elif isinstance(event, MessageEvent):
            user_state = states.get(event.user_id)
            if not user_state:
                user_state = await db.select([db.User.state]).where(db.User.user_id == event.user_id).gino.scalar()
        else:
            return False
        if not user_state and not self.state:
            return True
        if not user_state:
            return False
        state = user_state.split("*")[0]  # В state хранится некоторая полезная информация, отделяется от названия стейта символом *
        return self.state == state


class NumericRule(ABCRule[Message]):
    """
    Класс для проверки того, что в сообщении введено целое число в нужном диапазоне
    по умолчанию от 1 до бесконечности.
    Используется где необходимо установить числовые данные / выбрать позицию из списка
    """

    def __init__(self, min_number: Optional[int] = 1, max_number: Optional[int] = None):
        self.min_number = min_number
        if max_number is None:
            self.max_number = float('inf')
        else:
            self.max_number = max_number

    async def check(self, event: Message):
        try:
            int(event.text)
        except ValueError:
            await event.answer('Не удаётся преобразовать в целое число')
            return False
        if self.min_number <= int(event.text) <= self.max_number:
            return {"value": int(event.text)}
        await event.answer(f"Необходимо ввести целое число от {self.min_number} до "
                           f"{self.max_number if self.max_number != float('inf') else 'бесконечности'}")


class LimitSymbols(ABCRule[Message]):
    """
    Класс проверяющий длину сообщения на превышение лимита.
    Используется для того, чтобы ограничить количество символов в некоторых полях в анкете
    """

    def __init__(self, max_limit: int = 4095, min_limit: int = 1):
        self.max_limit = max_limit
        self.min_limit = min_limit

    async def check(self, event: Message):
        if not self.min_limit <= len(event.text) <= self.max_limit:
            await event.answer(f"На это поле установлен лимит в {self.min_limit} - {self.max_limit} символов")
            return False
        return True


class AdminRule(ABCRule):
    """
    Класс проверяющий, на то, что пользователь отправивший сообщений был администратором / владельцем
    Используется там, где функции бота доступны только администраторам
    """

    async def check(self, event: MessageEvent):
        admins = [x[0] for x in await db.select([db.User.user_id]).where(db.User.admin > 0).gino.all()]
        admins = list(set(admins).union(ADMINS))
        if isinstance(event, MessageEvent):
            return event.user_id in admins
        if isinstance(event, Message):
            return event.from_id in admins


class ValidateAccount(ABCRule[Message]):
    """
    Класс проверяющий, что пользователь не является банкротом и его анкета не заморожена
    Используется, для того чтобы нельзя было будучи банкротом совершать сделки
    """

    async def check(self, m: Message):
        if isinstance(m, Message):
            balance, freeze = (await db.select([db.Form.balance, db.Form.freeze])
                               .where(db.Form.user_id == m.from_id).gino.first())
        else:
            balance, freeze = (await db.select([db.Form.balance, db.Form.freeze])
                               .where(db.Form.user_id == m.user_id).gino.first())
        if balance < 0:
            states.set(m.from_id, Menu.BANK_MENU)
            await m.answer(messages.banckrot, keyboard=keyboards.bank)
            return False
        if freeze:
            states.set(m.from_id, Menu.BANK_MENU)
            await m.answer(messages.freeze, keyboard=keyboards.bank)
            return False
        return True


class CommandWithAnyArgs(ABCRule):
    """
    Класс который, получает все аргументы из /команды
    Используется для команд /апи /скл
    """

    def __init__(self, command: str):
        prefixes = ["/", "!", ""]
        self.patterns = [f"{x}{command}" for x in prefixes]

    async def check(self, event: Message):
        for pattern in self.patterns:
            if event.text.lower().startswith(pattern):
                return {"params": event.text[len(pattern)+1:]}
        return False


class UserSpecified(ABCRule[Message]):

    """
    Класс, который возвращает айди формы и пользователя, который указан в сообщении
    Используется, где нужно указывать пользователя
    """

    def __init__(self, state: str = None):
        self.state = state

    async def check(self, m: Message):
        user_id = await get_mention_from_message(m)
        if not user_id:
            await m.answer("Пользователь не указан")
            return
        name = await db.select([db.Form.name]).where(db.Form.user_id == user_id).gino.scalar()
        if not name:
            await m.answer(messages.not_form_id)
            return False
        form_id = await get_current_form_id(user_id)
        return {"form": (form_id, user_id)}


class ManyUsersSpecified(ABCRule[Message]):

    """
    Класс для того, чтобы получить из сообщения указания на нескольких пользователей
    """

    async def check(self, event: Message):
        state = states.get(event.from_id)
        if len(state.split("*")) > 1:
            form_ids = list(map(int, state.split("*")[1:]))
            user_ids = [x[0] for x in await db.select([db.Form.user_id]).where(db.Form.id.in_(form_ids)).gino.all()]
            return {"forms": list(zip(form_ids, user_ids))}
        user_ids = await get_mention_from_message(event, True)
        if not user_ids:
            await event.answer("Пользователей не найдено")
            return
        forms = []
        for user_id in user_ids:
            form_id = await get_current_form_id(user_id)
            forms.append(tuple([form_id, user_id]))
        return {"forms": forms}


content_types = list(fields_content.keys())


class EditContent(ABCRule[Message]):

    """
    Класс для того, чтобы вытащить тип контента и таблицу, где контент будет редактироваться если стейт Admin.EDIT_CONTENT
    Используется при выборе объекта, который хотим отредактирвоать
    """

    async def check(self, m: Message):
        if isinstance(m, Message):
            state = (await db.select([db.User.state]).where(db.User.user_id == m.from_id).gino.scalar()).split("*")[0]
        elif isinstance(m, MessageEvent):
            state = (await db.select([db.User.state]).where(db.User.user_id == m.user_id).gino.scalar()).split("*")[0]
        else:
            return False
        for content in content_types:
            if state == f"{Admin.EDIT_CONTENT}_{content}":
                return {"content_type": content, "table": getattr(db, content)}
        return False


class SelectContent(ABCRule[Message]):
    """
    Класс для того, чтобы вытащить тип контента и таблицу, где контент будет редактироваться если стейт Admin.SELECT_ACTION
    Используется при выборе действия после выбора объекта редактирования
    """

    async def check(self, m: Message):
        if isinstance(m, Message):
            state = (await db.select([db.User.state]).where(db.User.user_id == m.from_id).gino.scalar()).split("*")[0]
        elif isinstance(m, MessageEvent):
            state = (await db.select([db.User.state]).where(db.User.user_id == m.user_id).gino.scalar()).split("*")[0]
        else:
            return False
        for content in content_types:
            if state == f"{Admin.SELECT_ACTION}_{content}":
                return {"content_type": content, "table": getattr(db, content)}
        return False


class ChatAction(ABCRule[Message]):

    """
    Класс, проверяющий, что сообщение в чате и в нем введена команда [команда]
    Используется для простейших команд в тексте в квадратных скобках (без аргументов)
    """

    def __init__(self, command: str):
        self.command = command

    async def check(self, m: Message):
        if m.chat_id > 0 and f"[{self.command}]" in m.text.lower():
            return True
        return False


class DaughterRule(ABCRule[Message]):
    """
    Проверка на то, что пользователь является дочерью
    Используется для проверки доступа к функциям для дочерей
    """
    async def check(self, event: Message):
        status = await db.select([db.Form.status]).where(db.Form.user_id == event.from_id).gino.scalar()
        return status == 2


class ExpeditorRequestAvailable(ABCRule[MessageEvent]):
    """
    Проверка на то, что запрос на создание карты экспедитора еще актуален
    """
    async def check(self, m: MessageEvent):
        if not m.payload.get('request_expeditor_id'):
            return False
        expeditor_id = await db.select([db.ExpeditorRequest.expeditor_id]).where(
            db.ExpeditorRequest.id == m.payload['request_expeditor_id']).gino.scalar()
        if not expeditor_id:
            await m.show_snackbar(
                f'Запрос на Карту экспедитора устарел')
            return False
        form_id = await db.select([db.Expeditor.form_id]).where(db.Expeditor.id == expeditor_id).gino.scalar()
        user_id, name = await db.select([db.Form.user_id, db.Form.name]).where(db.Form.id == form_id).gino.first()
        user = (await bot.api.users.get(user_id))[0]
        return {'user': user, 'name': name, 'form_id': form_id, 'expeditor_id': expeditor_id}


class JudgeRule(ABCRule):
    """
    Проверка на то, что пользователь является судьей
    """
    async def check(self, event: Message | MessageEvent):
        if isinstance(event, Message):
            is_judge = await db.select([db.User.judge]).where(db.User.user_id == event.from_id).gino.scalar()
        else:
            is_judge = await db.select([db.User.judge]).where(db.User.user_id == event.user_id).gino.scalar()
        return is_judge


class UserFree(ABCRule):
    """
    Проверка на то, что пользователь не создает анкеты / контента / карты экспедитора / не включена панель судьи
    """
    async def check(self, event: Message | MessageEvent):
        if isinstance(event, Message):
            user_id = event.from_id
        else:
            user_id = event.user_id
        user = await db.User.get(user_id)
        action_mode = await db.select([db.UsersToActionMode.id]).where(db.UsersToActionMode.user_id == user_id).gino.scalar()
        if action_mode:
            if isinstance(event, Message):
                await event.answer('Необходимо выйти из экшен-режима')
                return
            else:
                await event.show_snackbar('Необходимо выйти из экшен-режима')
        judge_mode = await db.select([db.ActionMode.id]).where(db.ActionMode.judge_id == user_id).gino.scalar()
        if judge_mode:
            if isinstance(event, Message):
                await event.answer('Необходимо освободится от обязанности судьи')
                return
            else:
                await event.show_snackbar('Необходимо освободится от обязанности судьи')
            return False
        if user.creating_form or user.editing_form or user.editing_content or user.creating_expeditor or user.judge_panel:
            if isinstance(event, Message):
                await event.answer('Сначала необходимо выйти в главное меню')
                return
            else:
                await event.show_snackbar('Сначала необходимо выйти в главное меню')
            return False
        return True


class JudgeFree(ABCRule):
    """
    Проверка на то, что судья не судит какой-то экшен режим
    """
    async def check(self, event: Message | MessageEvent):
        if isinstance(event, Message):
            user_id = event.from_id
        else:
            user_id = event.user_id
        form_id = await get_current_form_id(user_id)
        chat_id = await db.select([db.ActionMode.chat_id]).where(db.ActionMode.judge_id == form_id).gino.scalar()
        if chat_id:
            chat_name = (await bot.api.messages.get_conversations_by_id(peer_ids=[2000000000 + chat_id])).items[0].chat_settings.title
            if isinstance(event, Message):
                await event.answer(f'Вы уже руководите Экшен-режимом в чате «{chat_name}»')
                return
            else:
                await event.show_snackbar(f'Вы уже руководите Экшен-режимом в чате «{chat_name}»')
            return False
        return True


class ActionModeTurn(ABCRule):
    """
    Класс, который возвращает номер очереди участника в экшен режиме
    Используется для проверки того, что соблюдается очередность постов участников в экшен-режиме
    """
    async def check(self, event: Message):
        if event.peer_id < 2000000000:
            return False
        action_mode = await db.select([db.ActionMode.id]).where(db.ActionMode.chat_id == event.chat_id).gino.scalar()
        if not action_mode:
            return False
        turn = await get_current_turn(action_mode)
        if turn == event.from_id:
            return {'action_mode_id': action_mode}
        else:
            return False


class JudgePostTurn(ABCRule):
    """
    Класс для проверки того, что сейчас очередь судьи писать пост в экшен-режиме
    """
    async def check(self, event: Message):
        if event.peer_id < 2000000000 or not event.text:
            return False
        action_mode = await db.select([db.ActionMode.id]).where(db.ActionMode.chat_id == event.chat_id).gino.scalar()
        if not action_mode:
            return False
        number_step = await db.select([db.ActionMode.number_step]).where(db.ActionMode.id == action_mode).gino.scalar()
        if number_step == 0:
            judge_id = await db.select([db.ActionMode.judge_id]).where(db.ActionMode.id == action_mode).gino.scalar()
            if judge_id == event.from_id:
                return {'action_mode_id': action_mode}
        return False


invites = [
    MessagesMessageActionStatus.CHAT_INVITE_USER_BY_MESSAGE_REQUEST,
    MessagesMessageActionStatus.CHAT_INVITE_USER_BY_LINK,
    MessagesMessageActionStatus.CHAT_INVITE_USER
]


class ChatInviteMember(ABCRule):
    """
    Класс для проверки того, что кто-то вступил в чат
    Используется
    """
    async def check(self, event: Message):
        m = event
        if event.peer_id > 2000000000 and event.action and event.action.type in invites:
            if m.action.type == MessagesMessageActionStatus.CHAT_INVITE_USER:
                member_id = m.action.member_id
            elif m.action.type == MessagesMessageActionStatus.CHAT_INVITE_USER_BY_LINK:
                member_id = m.from_id
            else:
                return False
            return {'member_id': member_id}
        return False


class FromUserRule(ABCRule):

    """
    Класс для проверки от кого пришло сообщение
    Сейчас используется для принятия сообщений юзерботом от имени группы
    """

    def __init__(self, from_id: int):
        self.from_id = from_id
    async def check(self, event: Message):
        return event.from_id == self.from_id


class RegexRule(ABCRule):
    """
    Класс фильтр по регулярному выражению. В отличие от VKBottle он использует re.search() вместо re.match()
    """
    def __init__(self, regexp):
        self.regexp = regexp

    async def check(self, event: Message):
        match = re.search(self.regexp, event.text)
        if match is not None:
            return {'match': match.groups()}
        return False
