import datetime
import enum
from typing import List, Tuple

from gino import Gino
from sqlalchemy import Column, Integer, BigInteger, ForeignKey, Text, Boolean, TIMESTAMP, func, and_, Float, ARRAY, JSON, Date

from config import USER, PASSWORD, HOST, DATABASE


class Attribute(enum.IntEnum):
    POWER = 1  # Сила
    SPEED = 2  # Скорость
    ENDURANCE = 3  # Выносливость
    DEXTERITY = 4  # Ловкость
    PERCEPTION = 5  # Восприятие
    REACTION = 6  # Реакция
    STRESS_RESISTANCE = 7  # Стрессоустойчивость


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
            editing_form = Column(Boolean, default=False)
            notification_enabled = Column(Boolean, default=True)
            editing_content = Column(Boolean, default=False)
            last_activity = Column(TIMESTAMP, default=datetime.datetime.now)

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
            activated_daylic = Column(Integer, ForeignKey("daylics.id", ondelete='SET NULL'))
            deactivated_daylic = Column(TIMESTAMP, default=datetime.datetime.now)
            freeze_request = Column(Boolean, default=False)
            delete_request = Column(Boolean, default=False)
            created_at = Column(TIMESTAMP, default=datetime.datetime.now)
            fraction_id = Column(Integer, ForeignKey("fractions.id", ondelete='SET NULL'))
            daughter_bonus = Column(Integer, default=0)
            subordination_level = Column(Integer, default=0)
            libido_level = Column(Integer, default=0)

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
            decor_slots = Column(Integer)
            functional_slots = Column(Integer)

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
            start_at = Column(TIMESTAMP, server_default=func.now())
            closed_at = Column(TIMESTAMP)
            execution_time = Column(Integer)
            allowed_fraction = Column(Integer, ForeignKey('fractions.id', ondelete='SET NULL'))
            allowed_profession = Column(Integer, ForeignKey('professions.id', ondelete='SET NULL'))
            allowed_forms = Column(ARRAY(Integer), default=[])
            target_ids = Column(ARRAY(Integer), default=[])
            reward = Column(JSON)
            penalty = Column(JSON)

        self.Quest = Quest

        class AdditionalTarget(self.Model):
            __tablename__ = 'additional_target'

            id = Column(Integer, primary_key=True)
            name = Column(Text)
            description = Column(Text)
            fraction_reputation = Column(Integer, ForeignKey('fractions.id', ondelete='SET NULL'))
            reputation = Column(Integer)
            fraction = Column(Integer, ForeignKey("fractions.id", ondelete='SET NULL'))
            profession = Column(Integer, ForeignKey('professions.id', ondelete='SET NULL'))
            daughter_params = Column(ARRAY(Integer))
            forms = Column(ARRAY(Integer), default=[])
            reward_info = Column(JSON)
            for_all_users = Column(Boolean, default=False)

        self.AdditionalTarget = AdditionalTarget

        class ReadyQuest(self.Model):
            __tablename__ = "ready_quests"

            id = Column(Integer, primary_key=True)
            quest_id = Column(Integer, ForeignKey("quests.id", ondelete='SET NULL'))
            form_id = Column(Integer, ForeignKey("forms.id", ondelete='CASCADE'))
            is_claimed = Column(Boolean, default=False)
            is_checked = Column(Boolean, default=False)

        self.ReadyQuest = ReadyQuest

        class QuestToForm(self.Model):
            __tablename__ = "quests_to_forms"

            id = Column(Integer, primary_key=True)
            quest_id = Column(Integer, ForeignKey("quests.id", ondelete='CASCADE'))
            form_id = Column(Integer, ForeignKey("forms.id", ondelete='CASCADE'))
            quest_start = Column(TIMESTAMP, default=datetime.datetime.now)
            active_targets = Column(ARRAY(Integer), default=[])
            is_paused = Column(Boolean, default=False)
            remained_time = Column(Integer)
            timer_id = Column(Integer, default=0)

        self.QuestToForm = QuestToForm

        class ReadyTarget(self.Model):
            __tablename__ = "ready_targets"

            id = Column(Integer, primary_key=True)
            target_id = Column(Integer, ForeignKey("additional_target.id", ondelete='CASCADE'))
            form_id = Column(Integer, ForeignKey("forms.id", ondelete='CASCADE'))
            is_claimed = Column(Boolean, default=False)
            is_checked = Column(Boolean, default=False)

        self.ReadyTarget = ReadyTarget

        class Daylic(self.Model):
            __tablename__ = "daylics"

            id = Column(Integer, primary_key=True)
            name = Column(Text)
            description = Column(Text)
            reward = Column(Integer)
            cooldown = Column(Integer)
            profession_id = Column(Integer, ForeignKey("professions.id", ondelete='SET NULL'))
            fraction_id = Column(Integer, ForeignKey("fractions.id", ondelete='SET NULL'))
            reputation = Column(Integer, default=0)

        self.Daylic = Daylic

        class CompletedDaylic(self.Model):
            __tablename__ = "completed_daylics"

            id = Column(Integer, primary_key=True)
            form_id = Column(Integer, ForeignKey("forms.id"))
            daylic_id = Column(Integer, ForeignKey("daylics.id", ondelete='SET NULL'))
            is_claimed = Column(Boolean, default=False)
            is_checked = Column(Boolean, default=False)

        self.CompletedDaylic = CompletedDaylic

        class Metadata(self.Model):
            __tablename__ = "metadata"

            maintainence_break = Column(Boolean, default=False)
            time_to_freeze = Column(Integer, default=604800)  # 1 week
            time_to_delete = Column(Integer, default=2592000)  # 30 days
            last_daylic_date = Column(TIMESTAMP(timezone=False), default=datetime.datetime.now)

        self.Metadata = Metadata

        class Decor(self.Model):
            __tablename__ = "decors"

            id = Column(Integer, primary_key=True)
            name = Column(Text)
            price = Column(Integer)
            is_func = Column(Boolean)
            photo = Column(Text)
            description = Column(Text)

        self.Decor = Decor

        # TODO: Тут я дурачек зачем-то фракции, декор привзяал к user_id, а не к form_id. Переделывать не хочется. Пока и так рабоатет

        class UserDecor(self.Model):
            __tablename__ = "user_decors"

            id = Column(Integer, primary_key=True)
            user_id = Column(Integer, ForeignKey("users.user_id", ondelete='CASCADE'))
            decor_id = Column(Integer, ForeignKey("decors.id", ondelete='CASCADE'))

        self.UserDecor = UserDecor

        class Fraction(self.Model):
            __tablename__ = "fractions"

            id = Column(Integer, primary_key=True)
            name = Column(Text)
            description = Column(Text)
            leader_id = Column(Integer, ForeignKey("users.user_id", ondelete='SET NULL'))
            photo = Column(Text)
            daughter_multiplier = Column(Float, default=0)

        self.Fraction = Fraction

        class UserToFraction(self.Model):
            __tablename__ = 'users_to_fractions'

            id = Column(Integer, primary_key=True)
            user_id = Column(Integer, ForeignKey("users.user_id", ondelete='CASCADE'))
            fraction_id = Column(Integer, ForeignKey("fractions.id", ondelete='CASCADE'))
            reputation = Column(Integer, default=0)

        self.UserToFraction = UserToFraction

        class DaylicHistory(self.Model):
            __tablename__ = 'daylic_history'

            id = Column(Integer, primary_key=True)
            form_id = Column(Integer, ForeignKey("forms.id", ondelete='CASCADE'))
            daylic_id = Column(Integer, ForeignKey('daylics.id', ondelete='CASCADE'))

        self.DaylicHistory = DaylicHistory

        class QuestHistory(self.Model):
            __tablename__ = 'quest_history'

            id = Column(Integer, primary_key=True)
            form_id = Column(Integer, ForeignKey("forms.id", ondelete='CASCADE'))
            quest_id = Column(Integer, ForeignKey('quests.id', ondelete='CASCADE'))

        self.QuestHistory = QuestHistory

        class DaughterQuest(self.Model):
            __tablename__ = 'daughter_quests'

            id = Column(Integer, primary_key=True)
            name = Column(Text)
            description = Column(Text)
            to_form_id = Column(Integer, ForeignKey('forms.id', ondelete='SET NULL'))
            reward = Column(JSON)
            penalty = Column(JSON)
            target_ids = Column(ARRAY(Integer))

        self.DaughterQuest = DaughterQuest

        class DaughterTarget(self.Model):
            __tablename__ = 'daughter_targets'

            id = Column(Integer, primary_key=True)
            name = Column(Text)
            description = Column(Text)
            reward = Column(JSON)
            params = Column(ARRAY(Integer), default=[])

        self.DaughterTarget = DaughterTarget

        class DaughterTargetRequest(self.Model):
            __tablename__ = 'daughter_target_request'

            id = Column(Integer, primary_key=True)
            target_id = Column(Integer, ForeignKey('daughter_targets.id', ondelete='CASCADE'))
            form_id = Column(Integer, ForeignKey('forms.id', ondelete='CASCADE'))
            confirmed = Column(Boolean, default=False)
            created_at = Column(Date, default=datetime.date.today)

        self.DaughterTargetRequest = DaughterTargetRequest

        class DaughterQuestRequest(self.Model):
            __tablename__ = 'daughter_quest_request'

            id = Column(Integer, primary_key=True)
            quest_id = Column(Integer, ForeignKey('daughter_quests.id', ondelete='CASCADE'))
            form_id = Column(Integer, ForeignKey('forms.id', ondelete='CASCADE'))
            confirmed = Column(Boolean, default=False)
            created_at = Column(Date, default=datetime.date.today)

        self.DaughterQuestRequest = DaughterQuestRequest

        class Attribute(self.Model):
            __tablename__ = 'attributes'

            id = Column(Integer, primary_key=True)
            name = Column(Text)

        self.Attribute = Attribute

        class ProfessionBonus(self.Model):
            __tablename__ = 'profession_bonus'

            id = Column(Integer, primary_key=True)
            attribute_id = Column(Integer, ForeignKey('attributes.id', ondelete='CASCADE'))
            profession_id = Column(Integer, ForeignKey('professions.id', ondelete='CASCADE'))
            bonus = Column(Integer, default=0)

        self.ProfessionBonus = ProfessionBonus

    async def connect(self):
        await self.set_bind(f"postgresql://{USER}:{PASSWORD}@{HOST}/{DATABASE}")
        await self.gino.create_all()
        await self.first_load()

    async def first_load(self):
        """Загрузка первичных данных"""
        professions = await self.select([func.count(db.Profession.id)]).gino.scalar()
        if professions == 0:
            await self.Profession.create(name="Тестовая профессия", special=False)
        statuses = await self.select([func.count(db.Status.id)]).gino.scalar()
        if statuses == 0:
            await self.Status.create(name="Резидент")
            await self.Status.create(name="Дочь❤")
        cabins = await self.select([func.count(db.Cabins.id)]).gino.scalar()
        if cabins == 0:
            await self.Cabins.create(name="Тестовая каюта", cost=250, decor_slots=10, functional_slots=5)
        metadata = await self.select([self.func.count()]).select_from(self.Metadata).gino.scalar()
        if metadata == 0:
            await self.Metadata.create()
        await db.Form.update.values(created_at=datetime.datetime.now()).where(db.Form.created_at.is_(None)).gino.all()
        fractions = await self.select([func.count(db.Fraction.id)]).gino.scalar()
        if fractions == 0:
            await self.Fraction.create(name="Без фракции", description="Это базовая фракция, чтобы пройти регистрацию")
        shop = await self.select([func.count(db.Shop.id)]).gino.scalar()
        if shop == 0:
            await self.Shop.create(name='Коктейль в баре', price=10, service=False)
            await self.Shop.create(name='Премиальный коктейль в баре', price=50, service=False)
            await self.Shop.create(name='Бутылка дорогого алкоголя', price=100, service=False)
        attributes = await self.select([func.count(db.Attribute.id)]).gino.scalar()
        if attributes == 0:
            for name in ('Сила', "Скорость", "Выносливость", "Ловкость", "Восприятие", "Реакция", "Стрессоустойчивость"):
                await self.Attribute.create(name=name)

    async def change_reputation(self, user_id: int, fraction_id: int, delta: int):
        id = await self.select([self.UserToFraction.id]).where(
            and_(self.UserToFraction.user_id == user_id, self.UserToFraction.fraction_id == fraction_id)).gino.scalar()
        if id:
            reputation = await self.select([self.UserToFraction.reputation]).where(
                and_(self.UserToFraction.user_id == user_id, self.UserToFraction.fraction_id == fraction_id)).gino.scalar()
        else:
            reputation = 0
            id = (await self.UserToFraction.create(user_id=user_id, fraction_id=fraction_id)).id
        owner = await self.select([self.Fraction.leader_id]).where(self.Fraction.id == fraction_id).gino.scalar()
        if owner == user_id:
            max_r = 100
        else:
            max_r = 99
        reputation += delta
        if reputation < -100:
            reputation = -100
        elif reputation > max_r:
            reputation = max_r
        await self.UserToFraction.update.values(reputation=reputation).where(self.UserToFraction.id == id).gino.status()

    async def get_reputations(self, user_id: int) -> List[Tuple[int, int]]:
        fraction_joined = await self.select([self.Form.fraction_id]).where(self.Form.user_id == user_id).gino.scalar()
        reputation = (await self.select([self.UserToFraction.reputation])
                      .where(and_(self.UserToFraction.user_id == user_id,
                                  self.UserToFraction.fraction_id == fraction_joined))
                      .gino.scalar())
        rows = [(fraction_joined, reputation)]
        rows.extend(await self.select([self.UserToFraction.fraction_id, self.UserToFraction.reputation])
                    .where(
            and_(self.UserToFraction.user_id == user_id, self.UserToFraction.fraction_id != fraction_joined))
                    .order_by(self.UserToFraction.reputation.desc()).gino.all())
        return rows


db = Database()
