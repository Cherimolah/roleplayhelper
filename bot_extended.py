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
from vkbottle import VKAPIError, Keyboard
from vkbottle.dispatch.views.bot import RawBotEventView, BotHandlerBasement, ABCBotMessageView, BotMessageView
from vkbottle_types.events.bot_events import BaseGroupEvent
from vkbottle.tools.mini_types.bot.message_event import MessageEventMin
from vkbottle.tools.mini_types.bot import MessageMin
from vkbottle.tools.mini_types.bot import message_min
from vkbottle.dispatch.base import Router
from vkbottle.modules import logger
from vkbottle.exception_factory.error_handler.error_handler import ErrorHandler
from vkbottle.http.aiohttp import AiohttpClient

from sqlalchemy import and_
from aiohttp import ClientSession, ClientResponse, TCPConnector

from service.db_engine import db


class MessagesCategoryExtended(MessagesCategory):

    async def send(
            self,
            peer_ids=None,
            message=None,
            attachment=None,
            keyboard=None,
            disable_mentions=True,
            random_id=0,
            peer_id=None,
            user_id=None,
            domain=None,
            chat_id=None,
            user_ids=None,
            lat=None,
            long=None,
            reply_to=None,
            forward_messages=None,
            forward=None,
            sticker_id=None,
            group_id=None,
            template=None,
            payload=None,
            content_source=None,
            dont_parse_links=None,
            intent=None,
            subscribe_id=None,
            is_notification=False,
            **kwargs
    ) -> typing.Union[int, typing.List[MessagesSendUserIdsResponseItem]]:
        if user_id:
            if isinstance(user_id, list):
                peer_ids = user_id
            else:
                peer_ids = [user_id]
            del user_id
        if peer_id:
            if isinstance(peer_id, list):
                peer_ids = peer_id
            else:
                peer_ids = [peer_id]
            del peer_id
        if user_ids:
            if isinstance(user_ids, list):
                peer_ids = user_ids
            else:
                peer_ids = [user_ids]
            del user_ids
        if not isinstance(peer_ids, list):
            peer_ids = [peer_ids]
        if message is None:
            message = ""  # Set iterable
        if isinstance(random_id, str):  # Compatible
            message = random_id
            random_id = 0
        if is_notification:
            peer_ids = [x[0] for x in await db.select([db.User.user_id]).where(
                and_(db.User.user_id.in_(peer_ids), db.User.notification_enabled.is_(True))).gino.all()]
        if not peer_ids:
            return []
        count = int(len(message) // 4096)
        msgs = []
        # Если длина сообщения больше 4096 символов, отправляем вложения и клавиатуру последним сообщением
        for number, i in enumerate(range(0, len(message), 4096)):
            if number < count:
                params = {k: v for k, v in locals().items() if k not in ('self', 'message', 'attachment', 'keyboard')}
                msgs.append(await super().send(message=message[i:i + 4096], **params))
            else:
                params = {k: v for k, v in locals().items() if k not in ('self', 'message')}
                msgs.append(await super().send(message=message[i:i + 4096], **params))
        if not message:
            params = {k: v for k, v in locals().items() if k not in ('self',)}
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
        """Кастомная настройка обходит ошибку устаревшего сообщения"""
        try:
            if isinstance(keyboard, Keyboard):
                keyboard = keyboard.get_json()
            response = await super().edit(peer_id, message, lat, long, attachment, keep_forward_messages,
                                          keep_snippets, group_id, dont_parse_links, disable_mentions,
                                          message_id, conversation_message_id, template, keyboard, **kwargs)
            return response
        except VKAPIError:
            try:
                if message_id:
                    message_ids = [message_id]
                else:
                    message_ids = None
                if conversation_message_id:
                    cmids = [conversation_message_id]
                else:
                    cmids = None
                await self.delete(message_ids, delete_for_all=True, peer_id=peer_id, cmids=cmids)
            except:
                pass
            await self.send(
                peer_id=peer_id, message=message, lat=lat, attachment=attachment, group_id=group_id,
                dont_parse_links=dont_parse_links, disable_mentions=disable_mentions, template=template,
                keyboard=keyboard, **kwargs
            )


class UsersCategoryExtended(UsersCategory, ABC):

    async def get(
            self,
            user_ids: typing.Optional[typing.List[typing.Union[int, str]]] = None,
            fields: typing.Optional[typing.List[str]] = None,
            name_case: typing.Optional[
                typing.Literal["nom", "gen", "dat", "acc", "ins", "abl"]
            ] = None,
            **kwargs
    ) -> typing.List[UsersUserFull]:
        if isinstance(user_ids, list):
            responses = [await super(UsersCategoryExtended, self).get(user_ids=user_ids[i:i + 1000], fields=fields, name_case=name_case, **kwargs)
                         for i in range(0, len(user_ids), 1000)]
            return [y for x in responses for y in x]
        return await super(UsersCategoryExtended, self).get(user_ids=user_ids, fields=fields, name_case=name_case, **kwargs)


class APICategoriesExtended(APICategories, ABC):
    @property
    def messages(self) -> messages.MessagesCategory:
        return MessagesCategoryExtended(self.api_instance)

    @property
    def users(self) -> UsersCategory:
        return UsersCategoryExtended(self.api_instance)


class AioHTTPClientExtended(AiohttpClient, ABC):

    async def request_raw(
        self,
        url: str,
        method: str = "GET",
        data: Optional[dict] = None,
        **kwargs,
    ) -> "ClientResponse":
        if not self.session:
            connector = TCPConnector(ssl=False)
            self.session = ClientSession(
                json_serialize=self.json_processing_module.dumps,
                connector=connector,
                **self._session_params,
            )
        async with self.session.request(url=url, method=method, data=data, **kwargs) as response:
            await response.read()
            return response


class APIExtended(APICategoriesExtended, API):
    pass


class MessageEventMinExtended(MessageEventMin):

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
        """Кастомное редактирование сообщения с обработкой ошибки устаревшего сообщения"""
        if isinstance(keyboard, Keyboard):
            keyboard = keyboard.get_json()
        try:
            response = await super().edit_message(message, lat, long, attachment, keep_forward_messages, keep_snippets,
                                                  dont_parse_links, template, keyboard, **kwargs)
            return response
        except VKAPIError:
            await self.send_message(message=message, lat=lat, long=long, attachment=attachment,
                                    dont_parse_links=dont_parse_links, template=template, keyboard=keyboard)


class RawBotEventViewExtended(RawBotEventView, ABC):

    def get_event_model(
            self, handler_basement: "BotHandlerBasement", event: dict
    ) -> typing.Union[dict, "BaseGroupEvent"]:
        """Кастомная настройка вьюхи событий, чтобы работал дополненный MessageEvent"""
        if handler_basement.dataclass == MessageEventMin:
            return MessageEventMinExtended(**event)
        return super().get_event_model(handler_basement, event)


class ABCBotMessageViewExtended(ABCBotMessageView, ABC):
    @staticmethod
    async def get_message(
            event: dict, ctx_api: Union["API", "ABCAPI"], replace_mention: bool
    ) -> "MessageMin":
        """Кастомная вьюха, чтобы payload был формата JSON"""
        message = message_min(event, ctx_api, replace_mention)
        if isinstance(message.payload, str):
            message.payload = json.loads(message.payload)
        return message


class BotMessageViewExtended(ABCBotMessageViewExtended, BotMessageView):
    """Микс дополненных классов и обычных из vkbottle"""
    pass


class ErrorHandlerExtended(ErrorHandler):
    async def handle(self, error: Exception, *args, **kwargs):
        handler = self.lookup_handler(type(error)) or self.undefined_error_handler

        if not handler:
            if self.raise_exceptions:
                raise error
            logger.exception(error)
            return
        return await handler(error, *args, **kwargs)


class RouterExtended(Router):
    async def route(self, event: dict, ctx_api: "ABCAPI") -> None:
        logger.debug("Routing update {}", event)

        for view in self.views.values():
            try:
                if not await view.process_event(event):
                    continue
                await view.handle_event(event, ctx_api, self.state_dispenser)
            except Exception as e:
                await self.error_handler.handle(e, peer_id=event.get('object', {}).get('message', {}).get('peer_id'),
                                                message=event.get('object', {}).get('message', {}).get('text'))