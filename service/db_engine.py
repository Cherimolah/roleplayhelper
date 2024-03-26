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
            activated_form = Column(Integer, default=0)
            creating_form = Column(Boolean, default=True)

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
            user_id = Column(Integer, ForeignKey("users.user_id"))
            name = Column(Text)
            profession = Column(Integer, ForeignKey("professions.id"))
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
            cabin_type = Column(Integer, ForeignKey("cabins.id"))
            is_request = Column(Boolean, default=True)
            number = Column(Integer, default=1)
            is_edit = Column(Boolean, default=False)
            balance = Column(BigInteger, default=1000)
            freeze = Column(Boolean, default=False)
            last_payment = Column(TIMESTAMP, default=datetime.datetime.now)
            status = Column(Integer, ForeignKey("statuses.id"), default=1)
            active_quest = Column(Integer, ForeignKey("quests.id"))
            activated_daylic = Column(Integer, ForeignKey("daylics.id"))
            deactivated_daylic = Column(TIMESTAMP, default=datetime.datetime.now)
            medals = Column(Integer, default=0)
            activated_flight = Column(Integer, ForeignKey("flights.id"))

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
            from_user = Column(Integer, ForeignKey("forms.id"))
            to_user = Column(Integer, ForeignKey("forms.id"))
            amount = Column(BigInteger)

        self.Transactions = Transactions

        class SalaryRequests(self.Model):
            __tablename__ = "salary_requests"

            id = Column(Integer, primary_key=True)
            user_id = Column(Integer, ForeignKey("users.user_id"))

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
            form_id = Column(Integer, ForeignKey("forms.id"))
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
            quest_id = Column(Integer, ForeignKey("quests.id"))
            form_id = Column(Integer, ForeignKey("forms.id"))

        self.ReadyQuest = ReadyQuest

        class Daylic(self.Model):
            __tablename__ = "daylics"

            id = Column(Integer, primary_key=True)
            name = Column(Text)
            description = Column(Text)
            reward = Column(Integer)
            cooldown = Column(Integer)
            profession_id = Column(Integer, ForeignKey("professions.id"))

        self.Daylic = Daylic

        class CompletedDaylic(self.Model):
            __tablename__ = "completed_daylics"

            id = Column(Integer, primary_key=True)
            form_id = Column(Integer, ForeignKey("forms.id"))
            daylic_id = Column(Integer, ForeignKey("daylics.id"))

        self.CompletedDaylic = CompletedDaylic

        class Flight(self.Model):
            __tablename__ = "flights"

            id = Column(Integer, primary_key=True)
            organizer = Column(Integer, ForeignKey("forms.id"))
            started_at = Column(TIMESTAMP)

        self.Flight = Flight

        class Event(self.Model):
            __tablename__ = "events"

            id = Column(Integer, primary_key=True)
            title = Column(Text)
            description = Column(Text)
            mask = Column(Text)

        self.Event = Event

        class PerfectEvent(self.Model):
            __tablename__ = "perfect_events"

            id = Column(Integer, primary_key=True)
            flight_id = Column(Integer, ForeignKey("flights.id"))
            event_id = Column(Integer, ForeignKey("events.id"))
            objects = Column(ARRAY(Integer))
            subjects = Column(ARRAY(Integer))

        self.PerfectEvent = PerfectEvent

    async def connect(self):
        await self.set_bind(f"postgresql://{USER}:{PASSWORD}@{HOST}/{DATABASE}")
        await self.gino.create_all()


db = Database()
asyncio.get_event_loop().run_until_complete(db.connect())
