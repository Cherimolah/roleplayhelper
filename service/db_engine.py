"""
Класс для работы с базой данных
"""
import datetime
import enum
import os.path
from typing import List, Tuple

from gino import Gino
from sqlalchemy import Column, Integer, BigInteger, ForeignKey, Text, Boolean, TIMESTAMP, func, and_, Float, ARRAY, \
    JSON, Date, DateTime

from config import USER, PASSWORD, HOST, DATABASE, HALL_CHAT_ID


def now():
    """
    Функция для получения текущего времени с тайм-зоной
    """
    return datetime.datetime.now(tz=datetime.timezone(datetime.timedelta(hours=3)))

def date():
    return now().date()


class Attribute(enum.IntEnum):
    POWER = 1  # Сила
    SPEED = 2  # Скорость
    ENDURANCE = 3  # Выносливость
    DEXTERITY = 4  # Ловкость
    PERCEPTION = 5  # Восприятие
    REACTION = 6  # Реакция
    STRESS_RESISTANCE = 7  # Стрессоустойчивость


class GroupItem(enum.IntEnum):
    EQUIPMENT = 1  # Экипировка
    ARMAMENT = 2  # Вооружение
    SUPPLIES = 3  # Расходные материалы
    TOOLS = 4  # Инструменты


class TypeItem(enum.IntEnum):
    ONE_TIME = 1  # Одноразовый
    REUSABLE = 2  # Многоразовый
    CONSTANT = 3  # Постоянный


class StateType(enum.IntEnum):
    injuries = 1  # Травмы
    madness = 2  # Безумие


class Database(Gino):
    """
    Класс-одинчока базы данных
    В методе __init__ прописаны таблицы
    """
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super().__new__(cls, *args, **kwargs)
        return cls._instance

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        class User(self.Model):
            """
            Таблица пользователей
            """
            __tablename__ = "users"

            user_id = Column(Integer, primary_key=True)  # Айди из вк
            admin = Column(Integer, default=0)  # Уровень админки
            judge = Column(Boolean, default=False)  # Является ли судьей
            state = Column(Text)  # Текущее состояние (FSM)
            creating_form = Column(Boolean, default=True)  # Создает ли сейчас анкету
            editing_form = Column(Boolean, default=False)  # Редактирует ли сейчас анкету
            notification_enabled = Column(Boolean, default=True)  # Отключены/включены уведомления
            editing_content = Column(Boolean, default=False)  # Редактирует ли контент (в админ/судья панели)
            last_activity = Column(TIMESTAMP, default=datetime.datetime.now)  # Последняя активность пользователя
            creating_expeditor = Column(Boolean, default=False)  # Создает ли сейчас карту экспедитора
            judge_panel = Column(Boolean, default=False)  # Включена ли панель судьи вместо админ панели
            check_action_id = Column(Integer, ForeignKey('actions.id', ondelete='SET NULL'))  # Текущая проверка действия в экшен режиме (если есть)

        self.User = User

        class Profession(self.Model):
            """
            Таблица с профессиями
            """
            __tablename__ = "professions"

            id = Column(Integer, primary_key=True)
            name = Column(Text, unique=True)  # Название
            special = Column(Boolean, default=False)  # Является ли специальной (специальные не показываются при регистрации)
            salary = Column(Integer, default=100)  # Зарплата

        self.Profession = Profession

        class Status(self.Model):
            """
            Статусы (резидент и дочери, можно дополнять)
            """
            __tablename__ = 'statuses'

            id = Column(Integer, primary_key=True)
            name = Column(Text)

        self.Status = Status

        class Form(self.Model):
            """
            Анкеты пользователей (их персонажей)
            Основная информация анкет заполняется при регистрации в handlers/questions.py
            !Крайне рекомендуем использовать по одной принятой анкете на одного пользователя, т.к. иначе невозможно будет использоть бота
            Один человек может управлять одним персонажем
            Один пользователь может иметь 2 анкеты, если одна существующая, вторая отредактированная и отправлена на проверку,
            но управляет все равно одним персонажем
            """
            __tablename__ = "forms"

            id = Column(BigInteger, primary_key=True)
            user_id = Column(Integer, ForeignKey("users.user_id", ondelete='CASCADE'))  # Айди пользователя в ВК
            name = Column(Text)  # Имя персонажа
            profession = Column(Integer, ForeignKey("professions.id", ondelete='SET NULL'))  # Айди профессии
            age = Column(BigInteger)  # Возраст персонажа
            height = Column(Integer)  # Рост персонажа
            weight = Column(Integer)  # Вес персонажа
            features = Column(Text)  # Физиологические особенности персонажа
            bio = Column(Text)  # Биография персонажа
            character = Column(Text)  # Характер персонажа
            motives = Column(Text)  # Мотивы нахождения на станции
            orientation = Column(Integer)  # Айди ориентации персонажа (0 - гетеро, 1 - би, 2 - гомо)
            fetishes = Column(Text)  # Фетиши персоанжа
            taboo = Column(Text)  # Табу персонажа
            photo = Column(Text)  # Фотография персонажа (attachment строка формата "photo-{group_id}_{photo_id}_{access_key}")
            cabin = Column(Integer)  # Номер каюты персонажа
            cabin_type = Column(Integer, ForeignKey("cabins.id", ondelete='SET NULL'))  # Айди типа каюты персонажа
            is_request = Column(Boolean, default=True)  # Является ли анкета отправленная на проверку (после проверки становится False)
            balance = Column(BigInteger, default=1000)  # Баланс пользователя
            freeze = Column(Boolean, default=False)  # Является ли анкета заморожена (для замороженных анкет не снимается плата за аренду)
            last_payment = Column(TIMESTAMP, default=datetime.datetime.now)  # Последнее дата-время снятия арендной платы
            status = Column(Integer, ForeignKey("statuses.id", ondelete='SET NULL'), default=1)  # Айди статуса (резидент/дочь)
            activated_daylic = Column(Integer, ForeignKey("daylics.id", ondelete='SET NULL'))  # Активный дейлик
            daylic_completed = Column(Boolean, default=False)  # Выполнил ли пользователь дейлик
            freeze_request = Column(Boolean, default=False)  # Отправил ли пользователь запрос на заморозку анкеты
            delete_request = Column(Boolean, default=False)  # Отправил ли пользователь запрос на удаление анкеты
            created_at = Column(TIMESTAMP, default=datetime.datetime.now)  # Дата-время создания анкеты
            fraction_id = Column(Integer, ForeignKey("fractions.id", ondelete='SET NULL'))  # Айди фракции, в которой состоит пользователь
            libido_bonus = Column(Integer, default=0)  # Бонус к уровню либидо (указывается на основе ответов для дочерей при регистрации, используется в ежедневном обновлении уровня либидо)
            subordination_bonus = Column(Integer, default=0)  # Бонус к уровню подчинения (см. примечание в строке выше)
            subordination_level = Column(Integer, default=0)  # Текущий базовый уровень подчинения (без бафов)
            libido_level = Column(Integer, default=0)  # Текущий базовый уровень либидо (без бафов)
            board_comment_id = Column(Integer)

        self.Form = Form

        class Shop(self.Model):
            """
            Таблица с товарами и услугами в магазине
            """
            __tablename__ = "shop"

            id = Column(Integer, primary_key=True)
            name = Column(Text)  # Название
            photo = Column(Text)  # Фото (attachment строка формата "photo-{group_id}_{photo_id}_{access_key}")
            description = Column(Text)  # Описание предмета
            price = Column(BigInteger)  # Цена предмета
            service = Column(Boolean, default=False)  # True - услуга, False - товар

        self.Shop = Shop

        class Transactions(self.Model):
            """
            Таблица со сделками
            """
            __tablename__ = "transactions"

            id = Column(Integer, primary_key=True)
            from_user = Column(Integer, ForeignKey("forms.id", ondelete='CASCADE'))  # От кого
            to_user = Column(Integer, ForeignKey("forms.id", ondelete='CASCADE'))  # Кому
            amount = Column(BigInteger)  # Сумма

        self.Transactions = Transactions

        class SalaryRequests(self.Model):
            """
            Таблица с текущими запросами зарплаты
            """
            __tablename__ = "salary_requests"

            id = Column(Integer, primary_key=True)
            user_id = Column(Integer, ForeignKey("users.user_id", ondelete='CASCADE'))  # Пользователь запросивший зарплату

        self.SalaryRequests = SalaryRequests

        class Cabins(self.Model):
            """
            Таблица с типами кают
            """
            __tablename__ = "cabins"

            id = Column(Integer, primary_key=True)
            name = Column(Text)  # Название
            cost = Column(Integer)  # Арендная плата
            decor_slots = Column(Integer)  # Количество слотов для обычного декора
            functional_slots = Column(Integer)  # Количество слотов для функционального декора

        self.Cabins = Cabins

        class Mailings(self.Model):
            """
            Таблица с рассылками
            """
            __tablename__ = "mailings"

            id = Column(Integer, primary_key=True)
            message_id = Column(Integer)  # Айди сообщение, которое будет переслано пользователям
            send_at = Column(TIMESTAMP)  # Время в которое нужно его отправить

        self.Mailings = Mailings

        class Donate(self.Model):
            """
            Таблица с пожертвованиями (в храм) игровой валюты
            """
            __tablename__ = "donates"

            id = Column(Integer, primary_key=True)
            form_id = Column(Integer, ForeignKey("forms.id", ondelete='CASCADE'))  # Кто пожертоввал
            amount = Column(Integer)  # Сумма пожертвования

        self.Donate = Donate

        class Quest(self.Model):
            """
            Таблица с обычными квестами
            """
            __tablename__ = "quests"

            id = Column(Integer, primary_key=True)
            name = Column(Text)  # Название
            description = Column(Text)  # Описание
            start_at = Column(TIMESTAMP, server_default=func.now())  # Дата начала
            closed_at = Column(TIMESTAMP)  # Дата окончания
            execution_time = Column(Integer)  # Время на выполнение
            allowed_fraction = Column(Integer, ForeignKey('fractions.id', ondelete='SET NULL'))  # Доступ для определенных фракций (если не указано - доступно всем)
            allowed_profession = Column(Integer, ForeignKey('professions.id', ondelete='SET NULL'))  # Доступ для профессий (если не указано - доступно всем)
            allowed_forms = Column(ARRAY(Integer), default=[])  # Доступ для определенных анкет (если не указано доступно всем)
            target_ids = Column(ARRAY(Integer), default=[])  # Айди дополнительных целей
            reward = Column(JSON)  # Объект награды (см. README)
            penalty = Column(JSON)  # Объект штрафа (см. README)

        self.Quest = Quest

        class AdditionalTarget(self.Model):
            """
            Таблица с дополнительными целями для обычных квестов
            """
            __tablename__ = 'additional_target'

            id = Column(Integer, primary_key=True)
            name = Column(Text)  # Название
            description = Column(Text)  # Описание
            fraction_reputation = Column(Integer, ForeignKey('fractions.id', ondelete='SET NULL'))  # Фракция, в которой необходимо иметь определенный уровень репутации (если не указана - доступна всем)
            reputation = Column(Integer)  # Необходимый уровень репутации
            fraction = Column(Integer, ForeignKey("fractions.id", ondelete='SET NULL'))  # Фракция, участникам которой доступен квест (если не указано - доступно всем)
            profession = Column(Integer, ForeignKey('professions.id', ondelete='SET NULL'))  # Профессия для каких участников доступна цель
            daughter_params = Column(ARRAY(Integer))  # Необходимые параметры дочери (либидо и подчинение)
            forms = Column(ARRAY(Integer), default=[])  # Пользователи, которым доступна доп. уель
            reward_info = Column(JSON)  # Награда за доп. цель
            for_all_users = Column(Boolean, default=False)  # Доступна всем пользователям или нет

        self.AdditionalTarget = AdditionalTarget

        class ReadyQuest(self.Model):
            """
            Таблица с запросами выполненных квестов
            """
            __tablename__ = "ready_quests"

            id = Column(Integer, primary_key=True)
            quest_id = Column(Integer, ForeignKey("quests.id", ondelete='SET NULL'))  # Айди квеста
            form_id = Column(Integer, ForeignKey("forms.id", ondelete='CASCADE'))  # Айди анкеты
            is_claimed = Column(Boolean, default=False)  # Получена ли уже награда
            is_checked = Column(Boolean, default=False)  # Проверено ли администратором

        self.ReadyQuest = ReadyQuest

        class QuestToForm(self.Model):
            """
            Таблица для связывания анкет с взятым на выполнение квестом
            """
            __tablename__ = "quests_to_forms"

            id = Column(Integer, primary_key=True)
            quest_id = Column(Integer, ForeignKey("quests.id", ondelete='CASCADE'))  # Айди квеста
            form_id = Column(Integer, ForeignKey("forms.id", ondelete='CASCADE'))  # Кто взял квест
            quest_start = Column(TIMESTAMP, default=datetime.datetime.now)  # Дата начала выполнения квеста
            active_targets = Column(ARRAY(Integer), default=[])  # Доступные доп цели для выполнения
            is_paused = Column(Boolean, default=False)  # Находится ли квест на паузе (используется чтобы не тратилось время на выполнение, когда квест отправлен на проверку)
            remained_time = Column(Integer)  # Оставшееся время на выполнение квеста (указывается при установки на паузу)
            timer_id = Column(Integer, default=0)  # Айди таймера отсчёта обратного времени

        self.QuestToForm = QuestToForm

        class ReadyTarget(self.Model):
            """
            Таблица с запросами выполненных доп. целей
            """
            __tablename__ = "ready_targets"

            id = Column(Integer, primary_key=True)
            target_id = Column(Integer, ForeignKey("additional_target.id", ondelete='CASCADE'))  # Айди доп. цели
            form_id = Column(Integer, ForeignKey("forms.id", ondelete='CASCADE'))  # Айди анкеты пользователя
            is_claimed = Column(Boolean, default=False)  # Получена ли награда
            is_checked = Column(Boolean, default=False)  # Проверен ли запрос администратором

        self.ReadyTarget = ReadyTarget

        class Daylic(self.Model):
            """
            Таблица с дейликами
            """
            __tablename__ = "daylics"

            id = Column(Integer, primary_key=True)
            name = Column(Text)  # Название
            description = Column(Text)  # Описание
            reward = Column(Integer)  # Награда
            profession_id = Column(Integer, ForeignKey("professions.id", ondelete='SET NULL'))  # Айди профессии
            # Эти столбцы legacy были еще до изоберетения reward
            fraction_id = Column(Integer, ForeignKey("fractions.id", ondelete='SET NULL'))  # Айди фракции, к которой применится бонус к репутации
            reputation = Column(Integer, default=0)  # Бонус к репутации
            chill = Column(Boolean)  # Флаг того, что дейлик будет являться типом "Выходной дейлик"

        self.Daylic = Daylic

        class CompletedDaylic(self.Model):
            """
            Таблица с выполненными дейликами
            """
            __tablename__ = "completed_daylics"

            id = Column(Integer, primary_key=True)
            form_id = Column(Integer, ForeignKey("forms.id", ondelete='CASCADE'))  # АЙди анкеты кто выполнил
            daylic_id = Column(Integer, ForeignKey("daylics.id", ondelete='CASCADE'))  # Айди дейлика
            is_claimed = Column(Boolean, default=False)  # Получена ли награда
            is_checked = Column(Boolean, default=False)  # Проверен ли запрос администратором
            created_at = Column(DateTime(timezone=True), default=now)  # Время создания запроса

        self.CompletedDaylic = CompletedDaylic

        class Metadata(self.Model):
            """
            Таблица с некоторйо сервисной информацией
            """
            __tablename__ = "metadata"

            maintainence_break = Column(Boolean, default=False)  # Включен ли режим технического обслуживания
            time_to_freeze = Column(Integer, default=604800)  # Таймаут заморозки анкеты (1 неделя неакитивности в боте по умолчанию)
            time_to_delete = Column(Integer, default=2592000)  # Таймайт удаления анкеты (1 месяц неактивности в боте по умолчанию)
            last_daylic_date = Column(TIMESTAMP(timezone=True), default=now)  # Последняя расылка дейлика (необходимо т.к. отправляем раз в 3 дня)

        self.Metadata = Metadata

        class Decor(self.Model):
            """
            Таблица с декором для каюты
            """
            __tablename__ = "decors"

            id = Column(Integer, primary_key=True)
            name = Column(Text)  # Название
            price = Column(Integer)  # Цена
            is_func = Column(Boolean)  # Функциональный ли декор
            photo = Column(Text)  # Фото (attachment строка)
            description = Column(Text)  # Описание

        self.Decor = Decor

        class UserDecor(self.Model):
            """
            Таблица с декором, который установил пользователь
            """
            __tablename__ = "user_decors"

            id = Column(Integer, primary_key=True)
            user_id = Column(Integer, ForeignKey("users.user_id", ondelete='CASCADE'))  # Айди пользователя
            decor_id = Column(Integer, ForeignKey("decors.id", ondelete='CASCADE'))  # Айди декора

        self.UserDecor = UserDecor

        class Fraction(self.Model):
            """
            Таблица с фракциями
            """
            __tablename__ = "fractions"

            id = Column(Integer, primary_key=True)
            name = Column(Text)  # Имя
            description = Column(Text)  # Описание
            leader_id = Column(Integer, ForeignKey("users.user_id", ondelete='SET NULL'))  # Айди лидера фракции
            photo = Column(Text)  # Фото
            libido_koef = Column(Float, default=1)  # Коэффициент фракции для бонуса к либидо
            subordination_koef = Column(Float, default=1)  # Коэффициент фракции для бонуса к подчинению

        self.Fraction = Fraction

        class UserToFraction(self.Model):
            """
            Таблица с пользователями и их фракцией
            """
            __tablename__ = 'users_to_fractions'

            id = Column(Integer, primary_key=True)
            user_id = Column(Integer, ForeignKey("users.user_id", ondelete='CASCADE'))  # Айди пользователя
            fraction_id = Column(Integer, ForeignKey("fractions.id", ondelete='CASCADE'))  # Айди фракции
            reputation = Column(Integer, default=0)  # Уровень репутации в этой фракции

        self.UserToFraction = UserToFraction

        class DaylicHistory(self.Model):
            """
            Таблица с историей выполненных дейликов
            Выполненные дейлики сохраняются, пока не будут выполнены все из пула, потом заново
            """
            __tablename__ = 'daylic_history'

            id = Column(Integer, primary_key=True)
            form_id = Column(Integer, ForeignKey("forms.id", ondelete='CASCADE'))  # Айди анкеты, кто выполнил дейлик
            daylic_id = Column(Integer, ForeignKey('daylics.id', ondelete='CASCADE'))  # Айди дейлика

        self.DaylicHistory = DaylicHistory

        class QuestHistory(self.Model):
            """
            Таблица пользователей и какие квесты они выполнили
            """
            __tablename__ = 'quest_history'

            id = Column(Integer, primary_key=True)
            form_id = Column(Integer, ForeignKey("forms.id", ondelete='CASCADE'))  # Айди анкеты, кто выполнил квест
            quest_id = Column(Integer, ForeignKey('quests.id', ondelete='CASCADE'))  # Айди квеста

        self.QuestHistory = QuestHistory

        class DaughterQuest(self.Model):
            """
            Таблица с квестами для дочерей
            """
            __tablename__ = 'daughter_quests'

            id = Column(Integer, primary_key=True)
            name = Column(Text)  # Название
            description = Column(Text)  # Описание
            to_form_id = Column(Integer, ForeignKey('forms.id', ondelete='SET NULL'))  # Для кого предназначен квест
            reward = Column(JSON)  # Награда за квест
            penalty = Column(JSON)  # Штраф за невыполнение квеста
            target_ids = Column(ARRAY(Integer))  # Массив с дополнительными целями для квестов дочерей

        self.DaughterQuest = DaughterQuest

        class DaughterTarget(self.Model):
            """
            Таблица с дополнительными целями для дочерей
            """
            __tablename__ = 'daughter_targets'

            id = Column(Integer, primary_key=True)
            name = Column(Text)  # Название
            description = Column(Text)  # Описание
            reward = Column(JSON)  # Награда
            params = Column(ARRAY(Integer), default=[])  # Правило параметров (см. README)
            penalty = Column(JSON)  # Штраф

        self.DaughterTarget = DaughterTarget

        class DaughterTargetRequest(self.Model):
            """
            Таблица с запросами на выполненные доп. цели для дочерей
            """
            __tablename__ = 'daughter_target_request'

            id = Column(Integer, primary_key=True)
            target_id = Column(Integer, ForeignKey('daughter_targets.id', ondelete='CASCADE'))  # Айди доп. цели
            form_id = Column(Integer, ForeignKey('forms.id', ondelete='CASCADE'))  # Айди анкеты
            confirmed = Column(Boolean, default=False)  # Подтвержден ли запрос администрацией
            created_at = Column(Date, default=date)  # Дата создания

        self.DaughterTargetRequest = DaughterTargetRequest

        class DaughterQuestRequest(self.Model):
            """
            Таблица запросов на выполненные квесты дочерей
            """
            __tablename__ = 'daughter_quest_request'

            id = Column(Integer, primary_key=True)
            quest_id = Column(Integer, ForeignKey('daughter_quests.id', ondelete='CASCADE'))  # Айди квеста
            form_id = Column(Integer, ForeignKey('forms.id', ondelete='CASCADE'))  # Айди анкеты
            confirmed = Column(Boolean, default=False)  # Подтвержден ли запрос администрацией
            created_at = Column(Date, default=date)  # Дата создания

        self.DaughterQuestRequest = DaughterQuestRequest

        class Attribute(self.Model):
            """
            Таблица с характеристиками экспедитора
            """
            __tablename__ = 'attributes'

            id = Column(Integer, primary_key=True)
            name = Column(Text)  # Название (сила, ловкость и т.д.)

        self.Attribute = Attribute

        class ProfessionBonus(self.Model):
            """
            Таблица с бонусами к характеристикам карты экспедитора от профессии
            """
            __tablename__ = 'profession_bonus'

            id = Column(Integer, primary_key=True)
            attribute_id = Column(Integer, ForeignKey('attributes.id', ondelete='CASCADE'))  # Айди характеристики
            profession_id = Column(Integer, ForeignKey('professions.id', ondelete='CASCADE'))  # Айди профессии
            bonus = Column(Integer, default=0)  # Айди бонуса

        self.ProfessionBonus = ProfessionBonus

        class ItemGroup(self.Model):
            """
            Таблица с группами предметов
            """
            __tablename__ = 'item_groups'

            id = Column(Integer, primary_key=True)
            name = Column(Text)  # Название "Экипировка", "Вооружение", "Расходные материалы", "Инструменты"

        self.ItemGroup = ItemGroup

        class ItemType(self.Model):
            """
            Таблица с названиями типов предметов
            """
            __tablename__ = 'item_types'

            id = Column(Integer, primary_key=True)
            name = Column(Text)  # Название (одноразовый, многоразовый, постоянный)

        self.ItemType = ItemType

        class Item(self.Model):
            """
            Таблица с предметами карты экспедитора
            """
            __tablename__ = 'items'

            id = Column(Integer, primary_key=True)
            name = Column(Text)  # Название
            description = Column(Text)  # Описание
            group_id = Column(Integer, ForeignKey('item_groups.id', ondelete='SET NULL'))  # Айди группы
            type_id = Column(Integer, ForeignKey('item_types.id', ondelete='SET NULL'))  # Айди типа
            count_use = Column(Integer, default=1)  # Количество возможных использований
            available_for_sale = Column(Boolean, default=True)  # Доступен ли в продаже
            price = Column(Integer, default=0)  # Цена в магазине (если доступен в продаже)
            fraction_id = Column(Integer, ForeignKey('fractions.id', ondelete='SET NULL'))  # В какой фракции необходимо иметь определенную репутацию (либо доступно всем)
            reputation = Column(Integer, default=0)  # Необходимый уровень репутации для приобретения (во фракции сверху)
            photo = Column(Text) # Фото предмета (attachment строка)
            bonus = Column(JSON, default=[])  # Бонус предмета (см. README)
            action_time = Column(Integer, default=0)  # Количество циклов в экшен-режиме, которые действует предмет
            time_use = Column(Integer, default=0)  # Время действия предмета (в секундах)

            # Индекс для быстрого поиска по названию
            _name_idx = self.Index('idx_gin_name', name, postgresql_using='gin', postgresql_ops={'name': 'gin_trgm_ops'})

        self.Item = Item

        class DebuffType(self.Model):
            """
            Таблица с типами дебафаов карты экспедитора
            """
            __tablename__ = 'debuff_types'

            id = Column(Integer, primary_key=True)
            name = Column(Text)  # Название (травмы / безумие)

        self.DebuffType = DebuffType

        class StateDebuff(self.Model):
            """
            Таблица с дебафами карты экспедитора
            """
            __tablename__ = 'state_debuffs'

            id = Column(Integer, primary_key=True)
            name = Column(Text)  # Название
            type_id = Column(Integer, ForeignKey('debuff_types.id', ondelete='SET NULL'))  # Айди типа
            attribute_id = Column(Integer, ForeignKey('attributes.id', ondelete='SET NULL'))  # Айди харктеристики
            penalty = Column(Integer, default=0)  # Налагаемый дебаф (минус к характеристике)
            action_time = Column(Integer, default=0)  # Количество циклов, которое действует дебаф в эушен-режиме
            time_use = Column(Integer, default=0)  # Время действия дебафа (в секундах)

        self.StateDebuff = StateDebuff

        class Race(self.Model):
            """
            Таблица с расами
            """
            __tablename__ = 'races'

            id = Column(Integer, primary_key=True)
            name = Column(Text)  # Название (человек, робот и т.д.)

        self.Race = Race

        class RaceBonus(self.Model):
            """
            Таблица с бонусами рас к характеристикам экспедитора
            """
            __tablename__ = 'race_bonus'

            id = Column(Integer, primary_key=True)
            attribute_id = Column(Integer, ForeignKey('attributes.id', ondelete='CASCADE'))  # Айди характеристики
            race_id = Column(Integer, ForeignKey('races.id', ondelete='CASCADE'))  # Айди расы
            bonus = Column(Integer, default=0)  # Добавляемый бонус

        self.RaceBonus = RaceBonus

        class Expeditor(self.Model):
            """
            Таблица с экспедиторами
            """
            __tablename__ = 'expeditors'

            id = Column(Integer, primary_key=True)
            name = Column(Text)  # Имя экспедитора (берется имя персонажа из анкеты)
            sex = Column(Integer)  # Пол экспедитора (1 - мужской, 2 - женский, 3 - другой)
            race_id = Column(Integer, ForeignKey('races.id', ondelete='SET NULL'))  # АЙди расы
            pregnant = Column(Text)  # Оплодотворение (просто текст, по ходу игры устанавливается значение от кого кем и т.д.)
            count_actions = Column(Integer, default=5)  # Количество действий доступных в экшен-режиме
            action_number = Column(Integer, default=1)  # Текущий номер действия
            is_confirmed = Column(Boolean, default=False)  # Подтверждена ли карта администратором
            form_id = Column(Integer, ForeignKey('forms.id', ondelete='CASCADE'))  # Айди анкеты, кому принадлежит карта

        self.Expeditor = Expeditor

        class ExpeditorToAttributes(self.Model):
            """
            Таблица с экспедиторами и их характеристиками
            """
            __tablename__ = 'expeditor_attributes'

            id = Column(Integer, primary_key=True)
            expeditor_id = Column(Integer, ForeignKey('expeditors.id', ondelete='CASCADE'))  # Айди экспедитора
            attribute_id = Column(Integer, ForeignKey('attributes.id', ondelete='CASCADE'))  # Айди характеристики
            value = Column(Integer)  # Значение

        self.ExpeditorToAttributes = ExpeditorToAttributes

        class ExpeditorToItems(self.Model):
            """
            Таблица с инвентарем предметов экспедитора
            """
            __tablename__ = 'expeditor_items'

            id = Column(Integer, primary_key=True)
            expeditor_id = Column(Integer, ForeignKey('expeditors.id', ondelete='CASCADE'))  # Айди экспедитора
            item_id = Column(Integer, ForeignKey('items.id', ondelete='CASCADE'))  # Айди предмета
            count_use = Column(Integer, default=0)  # Количество использований (сколько уже раз был использован предмет)

        self.ExpeditorToItems = ExpeditorToItems

        class ExpeditorToDebuffs(self.Model):
            """
            Таблица активными дебафами экспедитора
            """
            __tablename__ = 'expeditor_debuffs'

            id = Column(Integer, primary_key=True)
            expeditor_id = Column(Integer, ForeignKey('expeditors.id', ondelete='CASCADE'))  # Айди экпедитора
            debuff_id = Column(Integer, ForeignKey('state_debuffs.id', ondelete='CASCADE'))  # Айди дебафа
            created_at = Column(DateTime(timezone=True), default=now)  # Дата начала действия

        self.ExpeditorToDebuffs = ExpeditorToDebuffs

        class ExpeditorRequest(self.Model):
            """
            Таблица с запросами на создание карты экспедитора
            """
            __tablename__ = 'expeditor_requests'

            id = Column(Integer, primary_key=True)
            expeditor_id = Column(Integer, ForeignKey('expeditors.id', ondelete='CASCADE'))  # Айди карты экспедитора
            admin_id = Column(Integer, ForeignKey('users.user_id', ondelete='CASCADE'))  # Айди админа, кому был отправлен запрос
            message_id = Column(Integer)  # Айди сообщения в беседе с админом

        self.ExpeditorRequest = ExpeditorRequest

        class ActiveItemToExpeditor(self.Model):
            """
            Таблица активных предметов экспедитора
            """
            __tablename__ = 'active_item_to_expeditors'

            id = Column(Integer, primary_key=True)
            expeditor_id = Column(Integer, ForeignKey('expeditors.id', ondelete='CASCADE'))  # Айди экспедитора
            row_item_id = Column(Integer, ForeignKey('expeditor_items.id', ondelete='CASCADE'))  # Айди предмета из !инвентаря! (не просто айди предмета)
            created_at = Column(DateTime(timezone=True), default=now)  # Дата активации предмета
            remained_use = Column(Integer, default=0)  # Количество оставшихся циклов действия предмета в экшен-режиме

        self.ActiveItemToExpeditor = ActiveItemToExpeditor

        class ActionMode(self.Model):
            """
            Таблица с экшен-режимами
            """
            __tablename__ = 'action_mode'

            id = Column(Integer, primary_key=True)
            chat_id = Column(Integer)  # Айди чата
            judge_id = Column(Integer, ForeignKey('users.user_id', ondelete='CASCADE'))  # Айди текущего судьи
            started = Column(Boolean, default=False)  # Статус начался/еще нет
            number_step = Column(Integer, default=0)  # Номер участника, у кого очередь писать пост (0 - судья)
            finished = Column(Boolean, default=False)  # Закончился ли экшен-режим
            time_to_post = Column(Integer, default=0)  # Время ожидания на написание поста (0 - без времени)
            number_check = Column(Integer, default=0)  # Номер действия в проверке поста
            check_status = Column(Boolean, default=False)  # Идет ли сейчас проверка поста
            first_cycle = Column(Boolean, default=True)  # Является ли цикл первым (при первом цикле не надо убавлять использование предметов)

        self.ActionMode = ActionMode

        class UsersToActionMode(self.Model):
            """
            Таблица с пользователями, участвующими в экшен-режиме
            """
            __tablename__ = 'users_to_action_mode'

            id = Column(Integer, primary_key=True)
            action_mode_id = Column(Integer, ForeignKey('action_mode.id', ondelete='CASCADE'))  # Айди экшен-режима
            user_id = Column(Integer, ForeignKey('users.user_id', ondelete='CASCADE'))  # Айди пользователя
            initiative = Column(Integer, default=0)  # Текущий уровень инициативы
            participate = Column(Boolean, default=False)  # Будет добавлен в следующем цикле
            exited = Column(Boolean, default=False)  # Будет удален в следующем цикле

        self.UsersToActionMode = UsersToActionMode

        class ActionModeRequest(self.Model):
            """
            Таблица с запрсоами на создание экшен-режимов
            """
            __tablename__ = 'action_mode_requests'

            id = Column(Integer, primary_key=True)
            chat_id = Column(Integer)  # Айди чата
            judge_id = Column(Integer, ForeignKey('users.user_id', ondelete='CASCADE'))  # Айди судьи
            message_id = Column(Integer)  # Айди сообщения в чате судьи
            from_id = Column(Integer)  # Кто запросил экшен-режим

        self.ActionModeRequest = ActionModeRequest

        class Post(self.Model):
            """
            Таблица с постами игрков в экшен-режиме
            """
            __tablename__ = 'posts'

            id = Column(Integer, primary_key=True)
            user_id = Column(Integer, ForeignKey('users.user_id', ondelete='CASCADE'))  # Айди пользователя
            action_mode_id = Column(Integer, ForeignKey('action_mode.id', ondelete='CASCADE'))  # Айди экшен-режима
            created_at = Column(DateTime(timezone=True), default=now)  # Дата создания
            difficult = Column(Integer, default=0)  # Уровень сложности (0 - легкая и т.д.)
            decline_check = Column(Boolean, default=False)  # Есть ли возможность отказаться от проверки
            started_check = Column(Boolean, default=False)  # Начат ли пост проверяться судьей

        self.Post = Post

        class Action(self.Model):
            """
            Таблица с действиями игроков из постов в экшен-режиме
            """
            __tablename__ = 'actions'

            id = Column(Integer, primary_key=True)
            data = Column(JSON)  # Действие игрока см. README
            bonus = Column(Integer, default=0)  # Бонус/штраф судьи
            post_id = Column(Integer, ForeignKey('posts.id', ondelete='CASCADE'))  # Айди поста
            attribute_id = Column(Integer, ForeignKey('attributes.id', ondelete='CASCADE'))  # Айди характеристики по которому будет происходить проверка

        self.Action = Action

        class Consequence(self.Model):
            """
            Таблица с последствиями
            """
            __tablename__ = 'consequences'

            id = Column(Integer, primary_key=True)
            data = Column(JSON, default={})  # Данные о последствиях (см. README)
            type = Column(Integer)  # Номер последствия (критический провал, провал, успех, критический успех см. в service/keyboards.py)
            action_id = Column(Integer, ForeignKey('actions.id', ondelete='CASCADE'))  # Айди действия

        self.Consequence = Consequence

        class Chat(self.Model):
            """
            Таблица с зарегистрирвоанными чатами
            """
            __tablename__ = 'chats'

            chat_id = Column(Integer, unique=True)  # Айди чата для бота группы
            is_private = Column(Boolean, default=False)  # Является ли он приватным
            visible_messages = Column(Integer, default=1000)  # Сколько сообщений видно при приглашении / ссылке
            cabin_user_id = Column(Integer, ForeignKey('users.user_id', ondelete='SET NULL'))  # Номер каюты (если это чат каюты)
            user_chat_id = Column(Integer)  # Айди чата для юзер-бота

        self.Chat = Chat

        class UserToChat(self.Model):
            """
            Таблица с пользователями и их местоположением в чатах
            """
            __tablename__ = 'users_chats'

            id = Column(Integer, primary_key=True)
            user_id = Column(Integer, ForeignKey('users.user_id', ondelete='CASCADE'))  # Айди пользователя
            chat_id = Column(Integer, ForeignKey('chats.chat_id', ondelete='CASCADE'))  # Айди чата

        self.UserToChat = UserToChat

        class ChatToProfessions(self.Model):
            """
            Таблица с профессиями, которые имеют доступ к чатам
            """
            __tablename__ = 'chats_to_professions'

            id = Column(Integer, primary_key=True)
            chat_id = Column(Integer, ForeignKey('chats.chat_id', ondelete='CASCADE'))  # Айди чата
            profession_id = Column(Integer, ForeignKey('professions.id', ondelete='CASCADE'))  # Айди прфоесии

        self.ChatToProfessions = ChatToProfessions

        class ChatRequest(self.Model):
            """
            Таблица с запросами на проход в чат
            """
            __tablename__ = 'chat_requests'

            id = Column(Integer, primary_key=True)
            chat_id = Column(Integer, ForeignKey('chats.chat_id', ondelete='CASCADE'))  # Айди чата куда игрок хочет перейти
            user_id = Column(Integer, ForeignKey('users.user_id', ondelete='CASCADE'))  # Айди пользователя кто хочет зайти в чат
            admin_id = Column(Integer, ForeignKey('users.user_id', ondelete='CASCADE'))  # Айди пользователя, который имеет доступ к чату
            message_id = Column(Integer)  # Айди сообщения

        self.ChatRequest = ChatRequest

        class AttributePenalties(self.Model):
            """
            Таблица со штрафами по карте экспедитора

            Это нужно, чтобы отменить их после выполнения всех доп. целей дочери
            """
            __tablename__ = 'attribute_penalties'

            id = Column(Integer, primary_key=True)
            expeditor_id = Column(Integer, ForeignKey('expeditors.id', ondelete='CASCADE'))  # Айди экспедитора
            attribute_id = Column(Integer, ForeignKey('attributes.id', ondelete='CASCADE'), nullable=False)  # Айди аттрибута
            value = Column(Integer, nullable=False)  # Размер штрафа

        self.AttributePenalties = AttributePenalties

    async def connect(self):
        """
        Устанавливает подлючение к базе данных, создает таблицы и загружает первую необходимую информацию
        """
        await self.set_bind(f"postgresql://{USER}:{PASSWORD}@{HOST}/{DATABASE}")
        await self.status(self.text('CREATE EXTENSION IF NOT EXISTS fuzzystrmatch;'))
        await self.status(self.text('CREATE EXTENSION IF NOT EXISTS pg_trgm;'))
        await self.status(self.text(f'ALTER DATABASE {DATABASE} SET pg_trgm.similarity_threshold = 0.1;'))
        await self.gino.create_all()
        await self.first_load()

    async def first_load(self):
        """
        Загрузка первичных данных
        """
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
            for name in (
            'Сила', "Скорость", "Выносливость", "Ловкость", "Восприятие", "Реакция", "Стрессоустойчивость"):
                await self.Attribute.create(name=name)
        item_groups = await self.select([func.count(db.ItemGroup.id)]).gino.scalar()
        if item_groups == 0:
            for name in ("Экипировка", "Вооружение", "Расходные материалы", "Инструменты"):
                await self.ItemGroup.create(name=name)
        item_types = await self.select([func.count(db.ItemType.id)]).gino.scalar()
        if item_types == 0:
            for name in ('Одноразовый', 'Многоразовый', 'Постоянный'):
                await self.ItemType.create(name=name)
        state_types = await self.select([func.count(db.DebuffType.id)]).gino.scalar()
        if state_types == 0:
            for name in ('Травмы', 'Безумие'):
                await self.DebuffType.create(name=name)

        races = await self.select([func.count(self.Race.id)]).gino.scalar()
        if races == 0:
            await self.Race.create(name='Человек')

        chats = await db.select([func.count(db.Chat.chat_id)]).gino.scalar()
        if chats == 0 and HALL_CHAT_ID:
            await db.Chat.create(chat_id=HALL_CHAT_ID)

        if not os.path.exists('data'):
            os.mkdir('data')
            os.mkdir('data/decors')
            os.mkdir('data/shop')

    async def change_reputation(self, user_id: int, fraction_id: int, delta: int):
        """
        Метод для изменения репутации / принятия бонуса/штрафа к репутации во фракции
        """
        id = await self.select([self.UserToFraction.id]).where(
            and_(self.UserToFraction.user_id == user_id, self.UserToFraction.fraction_id == fraction_id)).gino.scalar()
        if id:
            reputation = await self.select([self.UserToFraction.reputation]).where(
                and_(self.UserToFraction.user_id == user_id,
                     self.UserToFraction.fraction_id == fraction_id)).gino.scalar()
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
        """
        Метод для получения списка репутации во всех фракциях у игрока
        """
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

class FirstPersonMode(self.Model):
    __tablename__ = 'first_person_mode'
    
    user_id = Column(Integer, ForeignKey('users.vk_id', ondelete='CASCADE'), primary_key=True)
    is_active = Column(Boolean, default=False)
    blackout_mode = Column(Boolean, default=False)  # Принудительный режим
    blackout_reason = Column(Text, nullable=True)   # Причина блэкаута
    deafness_until = Column(DateTime, nullable=True)
    blindness_until = Column(DateTime, nullable=True)
    concussion_until = Column(DateTime, nullable=True)
    limited_vision_until = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

self.FirstPersonMode = FirstPersonMode

class UserChatHistory(self.Model):
    """История чатов пользователя для восстановления"""
    __tablename__ = 'user_chat_history'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.vk_id', ondelete='CASCADE'))
    chat_id = Column(Integer, ForeignKey('chats.id', ondelete='CASCADE'))
    joined_at = Column(DateTime, default=datetime.now)
    left_at = Column(DateTime, nullable=True)
    is_restored = Column(Boolean, default=False)

self.UserChatHistory = UserChatHistory

db = Database()


