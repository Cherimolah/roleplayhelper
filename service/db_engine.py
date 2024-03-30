import asyncio
import datetime

from gino import Gino
from sqlalchemy import Column, Integer, BigInteger, ForeignKey, Text, Boolean, TIMESTAMP, ARRAY

from config import USER, PASSWORD, HOST, DATABASE


class Database(Gino):

    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super().__new__(cls, *args, **kwargs)
        return cls._instance

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        class User(self.Model):
            __tablename__ = "users"

            user_id = Column(Integer, primary_key=True)
            admin = Column(Integer, default=0)
            state = Column(Text)
            creating_form = Column(Boolean, default=True)
            notification_enabled = Column(Boolean, default=True)

        self.User = User

        class Profession(self.Model):
            __tablename__ = "professions"

            id = Column(Integer, primary_key=True)
            name = Column(Text, unique=True)
            special = Column(Boolean, default=False)
            salary = Column(Integer, default=100)

        self.Profession = Profession

        class Status(self.Model):
            __tablename__ = 'statuses'

            id = Column(Integer, primary_key=True)
            name = Column(Text)

        self.Status = Status

        class Form(self.Model):
            __tablename__ = "forms"

            id = Column(BigInteger, primary_key=True)
            user_id = Column(Integer, ForeignKey("users.user_id", ondelete='CASCADE'))
            name = Column(Text)
            profession = Column(Integer, ForeignKey("professions.id", ondelete='SET NULL'))
            age = Column(BigInteger)
            height = Column(Integer)
            weight = Column(Integer)
            features = Column(Text)
            bio = Column(Text)
            character = Column(Text)
            motives = Column(Text)
            orientation = Column(Integer)
            fetishes = Column(Text)
            taboo = Column(Text)
            photo = Column(Text)
            cabin = Column(Integer)
            cabin_type = Column(Integer, ForeignKey("cabins.id", ondelete='SET NULL'))
            is_request = Column(Boolean, default=True)
            balance = Column(BigInteger, default=1000)
            freeze = Column(Boolean, default=False)
            last_payment = Column(TIMESTAMP, default=datetime.datetime.now)
            status = Column(Integer, ForeignKey("statuses.id", ondelete='SET NULL'), default=1)
            active_quest = Column(Integer, ForeignKey("quests.id", ondelete='SET NULL'))
            activated_daylic = Column(Integer, ForeignKey("daylics.id", ondelete='SET NULL'))
            deactivated_daylic = Column(TIMESTAMP, default=datetime.datetime.now)
            freeze_request = Column(Boolean, default=False)
            delete_request = Column(Boolean, default=False)

        self.Form = Form

        class Shop(self.Model):
            __tablename__ = "shop"

            id = Column(Integer, primary_key=True)
            name = Column(Text)
            photo = Column(Text)
            description = Column(Text)
            price = Column(BigInteger)
            service = Column(Boolean, default=False)

        self.Shop = Shop

        class Transactions(self.Model):
            __tablename__ = "transactions"

            id = Column(Integer, primary_key=True)
            from_user = Column(Integer, ForeignKey("forms.id", ondelete='CASCADE'))
            to_user = Column(Integer, ForeignKey("forms.id", ondelete='CASCADE'))
            amount = Column(BigInteger)

        self.Transactions = Transactions

        class SalaryRequests(self.Model):
            __tablename__ = "salary_requests"

            id = Column(Integer, primary_key=True)
            user_id = Column(Integer, ForeignKey("users.user_id", ondelete='CASCADE'))

        self.SalaryRequests = SalaryRequests

        class Cabins(self.Model):
            __tablename__ = "cabins"

            id = Column(Integer, primary_key=True)
            name = Column(Text)
            cost = Column(Integer)

        self.Cabins = Cabins

        class Mailings(self.Model):
            __tablename__ = "mailings"

            id = Column(Integer, primary_key=True)
            message_id = Column(Integer)
            send_at = Column(TIMESTAMP)

        self.Mailings = Mailings

        class Donate(self.Model):
            __tablename__ = "donates"

            id = Column(Integer, primary_key=True)
            form_id = Column(Integer, ForeignKey("forms.id", ondelete='CASCADE'))
            amount = Column(Integer)

        self.Donate = Donate

        class Quest(self.Model):
            __tablename__ = "quests"

            id = Column(Integer, primary_key=True)
            name = Column(Text)
            description = Column(Text)
            reward = Column(Integer)
            start_at = Column(TIMESTAMP, default=datetime.datetime.now)
            closed_at = Column(TIMESTAMP)
            execution_time = Column(Integer)

        self.Quest = Quest

        class ReadyQuest(self.Model):
            __tablename__ = "ready_quests"

            id = Column(Integer, primary_key=True)
            quest_id = Column(Integer, ForeignKey("quests.id", ondelete='SET NULL'))
            form_id = Column(Integer, ForeignKey("forms.id", ondelete='CASCADE'))

        self.ReadyQuest = ReadyQuest

        class Daylic(self.Model):
            __tablename__ = "daylics"

            id = Column(Integer, primary_key=True)
            name = Column(Text)
            description = Column(Text)
            reward = Column(Integer)
            cooldown = Column(Integer)
            profession_id = Column(Integer, ForeignKey("professions.id", ondelete='SET NULL'))

        self.Daylic = Daylic

        class CompletedDaylic(self.Model):
            __tablename__ = "completed_daylics"

            id = Column(Integer, primary_key=True)
            form_id = Column(Integer, ForeignKey("forms.id"))
            daylic_id = Column(Integer, ForeignKey("daylics.id", ondelete='SET NULL'))

        self.CompletedDaylic = CompletedDaylic

    async def connect(self):
        await self.set_bind(f"postgresql://{USER}:{PASSWORD}@{HOST}/{DATABASE}")
        await self.gino.create_all()


db = Database()
asyncio.get_event_loop().run_until_complete(db.connect())
