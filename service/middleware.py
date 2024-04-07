from abc import ABC

from vkbottle import BaseMiddleware, CtxStorage
from vkbottle.bot import Message

from service.db_engine import db

states = CtxStorage()


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
        state = await db.select([db.User.state]).where(db.User.user_id == self.event.from_id).gino.scalar()
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
        if user and not form:
            await self.event.answer("Я вас знаю, но у вас нет анкеты! Напишите начать, чтобы заполнить её и "
                                    "продолжить пользоваться")
            self.stop()
