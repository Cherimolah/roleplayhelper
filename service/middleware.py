import asyncio
import datetime
from abc import ABC

from vkbottle import BaseMiddleware, Keyboard
from vkbottle.bot import Message

from service.db_engine import db
from service.utils import check_last_activity
from loader import states


class MaintainenceMiddleware(BaseMiddleware[Message], ABC):

    async def pre(self) -> None:
        if self.event.peer_id > 2_000_000_000:
            return
        is_break = await db.select([db.Metadata.maintainence_break]).gino.scalar()
        if is_break:
            admin = await db.select([db.User.admin]).where(db.User.user_id == self.event.from_id).gino.scalar()
            if admin <= 0:
                await self.event.answer("⚠ Бот находится на техническом обслуживании. Повторите поытку позже")
                self.stop()


class StateMiddleware(BaseMiddleware[Message], ABC):

    async def pre(self) -> None:
        if self.event.peer_id > 2000000000:
            return
        state = await db.select([db.User.state]).where(db.User.user_id == self.event.from_id).gino.scalar()
        if not state and self.event.text.lower() != 'начать':
            await self.event.answer('Я забыл где ты находишься. Давай начнем сначала. Напиши «Начать»',
                                    keyboard=Keyboard())
            await self.stop()
        states.set(self.event.from_id, state or "")

    async def post(self) -> None:
        state = states.get(self.event.from_id)
        await db.User.update.values(state=state).where(db.User.user_id == self.event.from_id).gino.status()
        states.delete(self.event.from_id)


class FormMiddleware(BaseMiddleware[Message], ABC):

    async def pre(self):
        if self.event.peer_id > 2_000_000_000:
            return
        user = await db.select([db.User.user_id]).where(db.User.user_id == self.event.from_id).gino.scalar()
        form = await db.select([db.Form.id]).where(db.Form.user_id == self.event.from_id).gino.scalar()
        if user and not form and self.event.text.lower() not in ("начать", "заполнить заново"):
            await self.event.answer("Я вас знаю, но у вас нет анкеты! Напишите «Начать», чтобы заполнить её и "
                                    "продолжить пользоваться")
            self.stop()


class ActivityUsersMiddleware(BaseMiddleware[Message], ABC):

    async def pre(self) -> None:
        if self.event.peer_id > 2_000_000_000:
            return
        freeze = await db.select([db.Form.freeze]).where(db.Form.user_id == self.event.from_id).gino.scalar()
        if freeze:
            await db.Form.update.values(freeze=False).where(db.Form.user_id == self.event.from_id).gino.status()
            await self.event.answer("🎉 С вовзвращением! Ваша анкета разморожена")

    async def post(self):
        if self.event.peer_id > 2_000_000_000:
            return
        await db.User.update.values(last_activity=datetime.datetime.now()).where(db.User.user_id == self.event.from_id).gino.status()
        asyncio.get_event_loop().create_task(check_last_activity(self.event.from_id))
