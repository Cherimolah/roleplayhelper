"""
Модуль улучшающий взаимодействие с апи VK и VKBottle.
Здесь создаются миксины с классами VKBottle
Заменяет обычные методы классов VKBottle а кастомные, так что можно просто использовать их как обычно
Также добавляет некоторые полезные фичи: словарь в message.payload и логи исключений
"""

import json
import typing
from typing import Optional, Union
from abc import ABC

from vkbottle_types.methods.messages import MessagesCategory
from vkbottle_types.methods.users import UsersCategory
from vkbottle_types.categories import APICategories
from vkbottle_types.methods import messages
from vkbottle.api.api import API, ABCAPI
from vkbottle_types.responses.messages import MessagesSendUserIdsResponseItem
from vkbottle_types.responses.users import UsersUserFull
from vkbottle import VKAPIError, Keyboard, Router
from vkbottle.dispatch.views.bot import RawBotEventView, BotHandlerBasement, ABCBotMessageView, BotMessageView
from vkbottle.tools.mini_types.bot.message_event import MessageEventMin
from vkbottle.tools.mini_types.bot import MessageMin
from vkbottle.http.aiohttp import AiohttpClient
from vkbottle_types.codegen.objects import BaseUserGroupFields
from vkbottle_types.objects import MessagesGetConversationById, MessagesGetConversationByIdExtended
from vkbottle_types.events.bot_events import MessageNew, BaseGroupEvent

from aiohttp import ClientSession, ClientResponse, TCPConnector
from loguru import logger

from service.db_engine import db


class MessagesCategoryExtended(MessagesCategory):
    """
    Класс кастомных методов для работы с апи группы messages
    """

    async def send(
            self,
            user_id=None,
            random_id=0,
            peer_id=None,
            peer_ids=None,
            domain=None,
            chat_id=None,
            user_ids=None,
            message=None,
            lat=None,
            long=None,
            attachment=None,
            reply_to=None,
            forward_messages=None,
            forward=None,
            sticker_id=None,
            group_id=None,
            keyboard=None,
            template=None,
            payload=None,
            content_source=None,
            dont_parse_links=None,
            disable_mentions=True,
            intent=None,
            subscribe_id=None,
            is_notification=None,
            **kwargs
    ) -> typing.Union[int, typing.List[MessagesSendUserIdsResponseItem]]:
        """
        Метод для отправки сообщений. Разбивает сообщения по 4096 символов. Добавляет фотографии и клавиатуру
        к последнему сообщению. Также устанавливает random_id = 0, и использует передачу peer_ids чтобы возвращать
        объекты сообщений

        Добавляется кастомный параметр is_notification, который отправляет сообщение только, если у пользователя включены уведомления от бота
        Используется для сервисных оповещений от бота
        """
        if user_id:
            peer_ids = [user_id]
            del user_id
        if peer_id:
            peer_ids = [peer_id]
            del peer_id
        if is_notification:
            for p in peer_ids:
                enabled = await db.select([db.User.notification_enabled]).where(db.User.user_id == p).gino.scalar()
                if not enabled:
                    peer_ids.remove(p)
            if not peer_ids:
                return
        if message is None:
            message = ""  # Set iterable
        if isinstance(random_id, str):  # Compatible
            message = random_id
            random_id = 0
        count = int(len(message) // 4096)
        msgs = []
        if len(message) == 0:
            params = {k: v for k, v in locals().items() if k not in ('self', 'message')}
            msgs.append(await super().send(**params))
            return msgs
        for number, i in enumerate(range(0, len(message), 4096)):
            if number < count:
                params = {k: v for k, v in locals().items() if k not in ('self', 'message', 'attachment', 'keyboard')}
                msgs.append(await super().send(message=message[i:i + 4096], **params))
            else:
                params = {k: v for k, v in locals().items() if k not in ('self', 'message', 'msgs', 'params')}
                params['message'] = message[i:i + 4096]
                msgs.append(await super().send(**params))
        msgs = [y for x in msgs for y in x]
        return msgs

    async def remove_chat_user(
            self,
            chat_id: int,
            user_id: typing.Optional[int] = None,
            member_id: typing.Optional[int] = None,
            **kwargs
    ) -> int:
        """
        Удаляет пользователя из чата, отключает вызов исключения
        """
        try:
            return await super().remove_chat_user(chat_id, user_id, member_id, **kwargs)
        except VKAPIError:
            pass

    async def edit(
            self,
            peer_id: int,
            message: typing.Optional[str] = None,
            lat: typing.Optional[float] = None,
            long: typing.Optional[float] = None,
            attachment: typing.Optional[str] = None,
            keep_forward_messages: typing.Optional[bool] = None,
            keep_snippets: typing.Optional[bool] = True,
            group_id: typing.Optional[int] = None,
            dont_parse_links: typing.Optional[bool] = None,
            disable_mentions: typing.Optional[bool] = True,
            message_id: typing.Optional[int] = None,
            conversation_message_id: typing.Optional[int] = None,
            template: typing.Optional[str] = None,
            keyboard: typing.Optional[str] = None,
            **kwargs
    ) -> bool:
        """
        Метод пытается отредактировать сообщение, если вызывается исключение (сообщение старое / вк решил, что мы много
        редактируем), то отправляет новое сообщение
        """
        try:
            response = await super().edit(peer_id=peer_id, message=message, lat=lat, long=long,
                                          attachment=attachment, keep_forward_messages=keep_forward_messages,
                                          keep_snippets=keep_snippets, group_id=group_id,
                                          dont_parse_links=dont_parse_links,
                                          disable_mentions=disable_mentions,
                                          message_id=message_id, conversation_message_id=conversation_message_id,
                                          template=template, keyboard=keyboard, **kwargs)
            return response
        except VKAPIError:
            await self.delete(peer_id=peer_id, cmids=conversation_message_id, delete_for_all=True)
            await self.send(
                peer_id=peer_id, message=message, lat=lat, attachment=attachment, group_id=group_id,
                dont_parse_links=dont_parse_links, disable_mentions=disable_mentions, template=template,
                keyboard=keyboard, **kwargs
            )

    async def delete(
            self,
            message_ids: typing.Optional[typing.List[int]] = None,
            spam: typing.Optional[bool] = None,
            group_id: typing.Optional[int] = None,
            delete_for_all: typing.Optional[bool] = None,
            peer_id: typing.Optional[int] = None,
            cmids: typing.Optional[typing.List[int]] = None,
            **kwargs
    ) -> typing.Dict[str, int]:
        """
        Удаляет сообщение, отключает вызов исключения
        """
        try:
            return await super().delete(message_ids=message_ids, spam=spam, group_id=group_id,
                                        delete_for_all=delete_for_all, peer_id=peer_id, cmids=cmids, **kwargs)
        except:
            pass

    async def get_conversations_by_id(
        self,
        peer_ids: typing.List[int],
        extended: typing.Optional[bool] = None,
        fields: typing.Optional[typing.List[BaseUserGroupFields]] = None,
        group_id: typing.Optional[int] = None,
        **kwargs: typing.Any,
    ) -> typing.Union["MessagesGetConversationById", "MessagesGetConversationByIdExtended"]:
        """
        Возвращает список бесед бота, обходит лимит в количество бесед за один запрос
        """
        responses = [await super(MessagesCategoryExtended, self).get_conversations_by_id(
            peer_ids=peer_ids[i:i+100],
            extended=extended,
            fields=fields,
            group_id=group_id,
            **kwargs
        ) for i in range(0, len(peer_ids), 100)]
        items = []
        for response in responses:
            items.extend(response.items)
        response = responses[0].model_copy(update={'items': items})
        return response


class UsersCategoryExtended(UsersCategory, ABC):
    """
    Класс для кастомных методов апи группы users
    """

    async def get(
            self,
            user_ids: typing.Optional[typing.List[typing.Union[int, str]]] = None,
            fields: typing.Optional[typing.List[str]] = None,
            name_case: typing.Optional[
                typing.Literal["nom", "gen", "dat", "acc", "ins", "abl"]
            ] = None,
            **kwargs
    ) -> typing.List[UsersUserFull]:
        """
        Возвращает информацию о пользователе, обходит лимит по количеству пользователей за один запрос
        """
        if isinstance(user_ids, list):
            responses = [await super(UsersCategoryExtended, self).get(user_ids=user_ids[i:i + 1000], fields=fields,
                                                                      name_case=name_case, **kwargs)
                         for i in range(0, len(user_ids), 1000)]
            return [y for x in responses for y in x]
        return await super(UsersCategoryExtended, self).get(user_ids=user_ids, fields=fields, name_case=name_case,
                                                            **kwargs)


class APICategoriesExtended(APICategories, ABC):
    """
    Миксин, чтобы подгрузить кастомные классы категорий
    """
    @property
    def messages(self) -> messages.MessagesCategory:
        return MessagesCategoryExtended(self.api_instance)

    @property
    def users(self) -> UsersCategory:
        return UsersCategoryExtended(self.api_instance)


class APIExtended(APICategoriesExtended, API):
    """
    Миксин для подгрузки кастомных классов категорий в класс API. Может показаться, что он пустой, но так надо.
    """
    pass


class MessageEventMinExtended(MessageEventMin):
    """
    Класс для кастомных методов у объекта MessageEvent
    """

    async def edit_message(
            self,
            message: Optional[str] = None,
            lat: Optional[float] = None,
            long: Optional[float] = None,
            attachment: Optional[str] = None,
            keep_forward_messages: Optional[bool] = None,
            keep_snippets: Optional[bool] = None,
            dont_parse_links: Optional[bool] = None,
            template: Optional[str] = None,
            keyboard: Optional[str] = None,
            **kwargs,
    ) -> int:
        """
        Метод редактирует сообщение, если устарело отправляет новое
        """
        if isinstance(keyboard, Keyboard):
            keyboard = keyboard.get_json()
        try:
            response = await super().edit_message(message=message, lat=lat, long=long, attachment=attachment,
                                                  keep_forward_messages=keep_forward_messages, keep_snippets=keep_snippets,
                                                  dont_parse_links=dont_parse_links, template=template,
                                                  keyboard=keyboard, **kwargs)
            return response
        except VKAPIError:
            await self.send_message(message=message, lat=lat, long=long, attachment=attachment,
                                    dont_parse_links=dont_parse_links, template=template, keyboard=keyboard)


class RawBotEventViewExtended(RawBotEventView, ABC):
    """
    Кастомный view для сырых ивентов. Нужно, чтобы создавался объект MessageEventExtended с кастомным методам
    редактирования (см. выше)
    """

    def get_event_model(
            self, handler_basement: "BotHandlerBasement", event: dict
    ) -> typing.Union[dict, "BaseGroupEvent"]:
        if handler_basement.dataclass == MessageEventMin:
            return MessageEventMinExtended(**event)  # Здесь собственно и создается кастомный объект сырых ивентов
        return super().get_event_model(handler_basement, event)


class MessageMinExtended(MessageMin, ABC):
    async def answer(
            self,
            message: str = None,
            attachment: Optional[str] = None,
            random_id: Optional[int] = 0,
            lat: Optional[float] = None,
            long: Optional[float] = None,
            reply_to: Optional[int] = None,
            forward_messages: Optional[list[int]] = None,
            forward: Optional[str] = None,
            sticker_id: Optional[int] = None,
            keyboard: Optional[str] = None,
            template: Optional[str] = None,
            payload: Optional[str] = None,
            content_source: Optional[str] = None,
            dont_parse_links: Optional[bool] = None,
            disable_mentions: Optional[bool] = None,
            intent: Optional[str] = None,
            subscribe_id: Optional[int] = None,
            **kwargs
    ) -> "MessagesSendUserIdsResponseItem":
        """
        Этот метод нужен, чтобы VKBottle сам не резал сообщения, т.к. он их нарезает неправильно
        """

        data = self.ctx_api.messages.get_set_params(locals())
        deprecated_params = ("peer_id", "user_id", "domain", "chat_id", "user_ids")
        deprecated = [k for k in data if k in deprecated_params]
        if deprecated:
            logger.warning(
                "Params like peer_id or user_id is deprecated in Message.answer()."
                "Use API.messages.send() instead"
            )
            for k in deprecated:
                data.pop(k, None)

        if message is None:
            message = ""
        elif not isinstance(message, str):
            message = str(message)

        response = (await self.ctx_api.messages.send(peer_ids=[self.peer_id], **data))[0]  # type: ignore
        return response


def message_min(event: dict, ctx_api: "ABCAPI", replace_mention: bool = True) -> "MessageMin":
    """
    Функция создает MessageMin, она нужна в ABCBotMessageViewExtended (кастомный MessageView).
    Код скопирован из VKBottle
    """
    update = MessageNew(**event)

    if update.object.message is None:
        msg = "Please set longpoll to latest version"
        raise RuntimeError(msg)

    return MessageMinExtended(
        **update.object.message.dict(),
        client_info=update.object.client_info,
        group_id=update.group_id,
        replace_mention=replace_mention,
        unprepared_ctx_api=ctx_api,
    )


class ABCBotMessageViewExtended(ABCBotMessageView, ABC):
    """
    Кастомный MessageView, нужен, чтобы изменить объект MessageMin
    """
    @staticmethod
    async def get_message(
            event: dict, ctx_api: Union["API", "ABCAPI"], replace_mention: bool
    ) -> "MessageMin":
        """
        Заменяет payload со строки на словарь для удобства использования
        """
        message = message_min(event, ctx_api, replace_mention)  # Создаем обычный MessageMin
        if isinstance(message.payload, str):
            message.payload = json.loads(message.payload)  # Изменяем payload со строки на словарь
        return message


class BotMessageViewExtended(ABCBotMessageViewExtended, BotMessageView):
    """
    Миксин для загрузки кастомного MessageView, он пустой это нормально
    """
    pass


class AioHTTPClientExtended(AiohttpClient, ABC):
    """
    Расширение класса AiohttpClient. Так как по каким-то причинам aiohttp не хочет принимать TLS сертификат vk.ru
    здесь отключается его проверка
    """

    async def request_raw(
            self,
            url: str,
            method: str = "GET",
            data: Optional[dict] = None,
            **kwargs,
    ) -> "ClientResponse":
        """
        Метод делает HTTPS запрос по ссылке с отключенной проверкой TLS сертфиката
        """
        connector = TCPConnector(ssl=False)
        if not self.session:
            self.session = ClientSession(
                json_serialize=self.json_processing_module.dumps,
                connector=connector,
                **self._session_params,
            )
        async with self.session.request(url=url, method=method, data=data, **kwargs) as response:
            await response.read()
            return response


class RouterExtended(Router):
    """
    Расширение для класса Router, нужен чтобы вызывать метод обработки исключений с кастомными аргументами
    """
    async def route(self, event: dict, ctx_api: "ABCAPI") -> None:
        """
        Метод прокидывающий приходящий ивент по хендлерам.
        Если в ходе обработки проиходит ошибка вызывается обработчик ошибок (см. main.exception)
        """
        logger.debug("Routing update {}", event)

        for view in self.views.values():
            try:
                if not await view.process_event(event):
                    continue
                await view.handle_event(event, ctx_api, self.state_dispenser)
            except Exception as e:
                await self.error_handler.handle(e, peer_id=event.get('object', {}).get('message', {}).get('peer_id'),
                                                message=event.get('object', {}).get('message', {}).get('text'))
