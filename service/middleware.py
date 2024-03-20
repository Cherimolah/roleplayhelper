from abc import ABC

from vkbottle import BaseMiddleware, CtxStorage
from vkbottle.bot import Message

from service.db_engine import db

states = CtxStorage()


class Middleware(BaseMiddleware[Message], ABC):

    async def pre(self) -> None:
        state = await db.select([db.User.state]).where(db.User.user_id == self.event.from_id).gino.scalar()
        states.set(self.event.from_id, state or "")

    async def post(self) -> None:
        state = states.get(self.event.from_id)
        await db.User.update.values(state=state).where(db.User.user_id == self.event.from_id).gino.status()
        states.delete(self.event.from_id)


