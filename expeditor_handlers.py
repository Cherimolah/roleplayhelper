//"expeditor/handlers.py"

from vkbottle.bot import Bot, Message
from vkbottle import Keyboard, KeyboardButtonColor, Text
from .models import Character, Item, Effect, ActionMode, Consequence
from .mechanics import generate_characteristics, perform_check, calculate_initiative, calculate_movement_distance, apply_consequence
import random
import json

class ExpEditorHandlers:
    def __init__(self, bot: Bot, db):
        self.bot = bot
        self.db = db
        self.pending_checks = {}  # {user_id: {action, characteristic, difficulty, bonus, penalty, consequences, cancellable}}
        self.pending_action_mode = {}  # {judge_id: {participants}}
        self.pending_character_creation = {}  # {user_id: {step, data}}
        self.pending_consequence = {}  # {user_id: {step, data}}

    def register_handlers(self):
        @self.bot.on.message(text="/expeditor_start")
        async def start_handler(message: Message):
            await self.start(message)

        @self.bot.on.message(text="/expeditor_create_character")
        async def create_character_handler(message: Message):
            await self.create_character(message)

        @self.bot.on.message(text="/expeditor_action_mode_on")
        async def action_mode_on_handler(message: Message):
            await self.action_mode_on(message)

        @self.bot.on.message(text="/expeditor_action_mode_off")
        async def action_mode_off_handler(message: Message):
            await self.action_mode_off(message)

        @self.bot.on.message(text="/expeditor_add_admin <user_id>")
        async def add_admin_handler(message: Message, user_id: str):
            await self.add_admin(message, int(user_id))

        @self.bot.on.message(text="/expeditor_add_race")
        async def add_race_handler(message: Message):
            await self.add_race(message)

        @self.bot.on.message(text="/expeditor_add_profession")
        async def add_profession_handler(message: Message):
            await self.add_profession(message)

        @self.bot.on.message(text="/expeditor_view_logs")
        async def view_logs_handler(message: Message):
            await self.view_logs(message)

        @self.bot.on.message(regexp=r"\[.*?\]")
        async def action_handler(message: Message):
            await self.handle_action(message)

        @self.bot.on.message(text=["Сила", "Скорость", "Выносливость", "Ловкость", "Восприятие", "Реакция", "Стрессоустойчивость"])
        async def judge_response_handler(message: Message):
            if any(check["characteristic"] is None for check in self.pending_checks.values()):
                await self.handle_judge_response(message)
            elif any("characteristic" in data for data in self.pending_character_creation.values()):
                await self.handle_character_creation_points(message)
            elif any("characteristic" in data for data in self.pending_consequence.values()):
                await self.handle_consequence_characteristic(message)

        @self.bot.on.message(text=["Легкая", "Нормальная", "Сложная", "Очень сложная"])
        async def difficulty_handler(message: Message):
            await self.handle_difficulty(message)

        @self.bot.on.message(text=["Отсутствует", "Низкий", "Обычный", "Высокий"])
        async def penalty_bonus_handler(message: Message):
            if message.from_id in [self.db.get_expeditor_action_mode().judge_id]:
                if any(check["penalty"] is None and check["difficulty"] for check in self.pending_checks.values()):
                    await self.handle_penalty(message)
                elif any(check["bonus"] is None and check["penalty"] is not None for check in self.pending_checks.values()):
                    await self.handle_bonus(message)

        @self.bot.on.message(text=["Да", "Нет"])
        async def cancellable_handler(message: Message):
            if any(check["cancellable"] is None and check["bonus"] is not None for check in self.pending_checks.values()):
                await self.handle_cancellable(message)
            elif message.from_id in self.pending_action_mode:
                await self.handle_action_mode_participants(message)

        @self.bot.on.message(text=["Выполнить проверку", "Отменить проверку"])
        async def player_response_handler(message: Message):
            await self.handle_player_response(message)

        @self.bot.on.message(text=["Получение Травмы", "Лечение Травмы", "Получение Психоза", "Лечение Психоза", "Повышение Либидо", "Понижение Либидо", "Повышение Подчинения", "Понижение Подчинения", "Оплодотворение", "Снятие Оплодотворения"])
        async def consequence_type_handler(message: Message):
            await self.handle_consequence_type(message)

    async def start(self, message: Message):
        await message.answer("Привет! Это модуль Карты Экспедитора. Используй команды:\n"
                             "/expeditor_create_character - создать персонажа\n"
                             "/expeditor_action_mode_on - включить Экшен режим\n"
                             "/expeditor_action_mode_off - выключить Экшен режим\n"
                             "/expeditor_add_admin <user_id> - добавить администратора\n"
                             "/expeditor_add_race - добавить новую расу\n"
                             "/expeditor_add_profession - добавить новую профессию\n"
                             "/expeditor_view_logs - просмотреть логи проверок\n"
                             "[Действие] - выполнить действие в Экшен режиме")

    async def add_admin(self, message: Message, user_id: int):
        if not self.db.is_admin(message.from_id):
            await message.answer("Только администратор может добавлять новых администраторов!")
            return

        self.db.add_admin(user_id)
        await message.answer(f"Пользователь {user_id} добавлен в администраторы.")

    async def create_character(self, message: Message):
        if not self.db.is_admin(message.from_id):
            await message.answer("Только администратор может создавать персонажей!")
            return

        user_id = message.from_id
        races = self.db.get_races()
        keyboard = Keyboard(one_time=True)
        for race in races.keys():
            keyboard.add(Text(race), color=KeyboardButtonColor.PRIMARY)
        await message.answer("Выберите расу персонажа:", keyboard=keyboard.get_json())
        self.pending_character_creation[user_id] = {"step": "race", "data": {}}

    async def handle_character_creation(self, message: Message):
        user_id = message.from_id
        if user_id not in self.pending_character_creation:
            return

        step = self.pending_character_creation[user_id]["step"]
        data = self.pending_character_creation[user_id]["data"]

        if step == "race":
            races = self.db.get_races()
            if message.text not in races:
                await message.answer("Неверная раса! Попробуйте снова.")
                return
            data["race"] = message.text
            professions = self.db.get_professions()
            keyboard = Keyboard(one_time=True)
            for profession in professions.keys():
                keyboard.add(Text(profession), color=KeyboardButtonColor.PRIMARY)
            await message.answer("Выберите профессию персонажа:", keyboard=keyboard.get_json())
            self.pending_character_creation[user_id]["step"] = "profession"

        elif step == "profession":
            professions = self.db.get_professions()
            if message.text not in professions:
                await message.answer("Неверная профессия! Попробуйте снова.")
                return
            data["profession"] = message.text
            data["name"] = "Доктор Томео Андо"  # Для примера
            data["age"] = 29
            data["gender"] = "Мужской"
            keyboard = Keyboard(one_time=True)
            for char in ["Сила", "Скорость", "Выносливость", "Ловкость", "Восприятие", "Реакция", "Стрессоустойчивость"]:
                keyboard.add(Text(char), color=KeyboardButtonColor.PRIMARY)
            await message.answer("Выберите характеристику для +20 очков:", keyboard=keyboard.get_json())
            self.pending_character_creation[user_id]["step"] = "points_20"
            self.pending_character_creation[user_id]["data"]["additional_points"] = {}

        elif step == "points_20":
            data["additional_points"]["characteristic"] = message.text.lower()
            await message.answer("Введите количество очков для распределения (например, 20):")
            self.pending_character_creation[user_id]["step"] = "points_20_value"

        elif step == "points_20_value":
            try:
                points = int(message.text)
                data["additional_points"][data["additional_points"]["characteristic"]] = points
                keyboard = Keyboard(one_time=True)
                for char in ["Сила", "Скорость", "Выносливость", "Ловкость", "Восприятие", "Реакция", "Стрессоустойчивость"]:
                    keyboard.add(Text(char), color=KeyboardButtonColor.PRIMARY)
                await message.answer("Выберите характеристику для +10 очков:", keyboard=keyboard.get_json())
                self.pending_character_creation[user_id]["step"] = "points_10"
            except ValueError:
                await message.answer("Введите корректное число!")

        elif step == "points_10":
            data["additional_points"]["characteristic_10"] = message.text.lower()
            await message.answer("Введите количество очков для распределения (например, 10):")
            self.pending_character_creation[user_id]["step"] = "points_10_value"

        elif step == "points_10_value":
            try:
                points = int(message.text)
                data["additional_points"][data["additional_points"]["characteristic_10"]] = points
                characteristics = generate_characteristics(self.db, data["race"], data["profession"], data["additional_points"])
                character = Character(
                    id=user_id,
                    name=data["name"],
                    age=data["age"],
                    gender=data["gender"],
                    race=data["race"],
                    profession=data["profession"],
                    strength=characteristics["strength"],
                    speed=characteristics["speed"],
                    endurance=characteristics["endurance"],
                    dexterity=characteristics["dexterity"],
                    perception=characteristics["perception"],
                    reaction=characteristics["reaction"],
                    stress_resistance=characteristics["stress_resistance"],
                    madness=[{"name": "Легкая тревожность", "effect": {"characteristic": "stress_resistance", "penalty": 5}}],
                    injuries=[{"name": "Растяжение лодыжки", "effect": {"characteristic": "speed", "penalty": 10}}],
                    submission=0,
                    libido=0,
                    impregnation=None,
                    equipment=[
                        Item("Костюм", "Костюм медика", {"perception": 10}, "Экипировка", "Постоянный", 0),
                        Item("Перчатка Шодан", "Улучшает восприятие", {"perception": 20}, "Экипировка", "Постоянный", 0),
                        Item("Перчатка КПД-Мед", "Улучшает восприятие", {"perception": 15}, "Экипировка", "Постоянный", 0),
                        Item("Очки Лумус", "Улучшают восприятие", {"perception": 10}, "Экипировка", "Постоянный", 0)
                    ],
                    weapons=[Item("Плазменный пистолет", "Оружие", {"speed": -5}, "Вооружение", "Постоянный", 0)],
                    consumables=[],
                    tools=[Item("Кейс с инструментами", "Медицинский кейс", {"perception": 10}, "Инструменты", "Постоянный", 0)]
                )
                self.db.save_expeditor_character(character)
                await message.answer(f"Персонаж создан:\n"
                                     f"Имя: {character.name}\n"
                                     f"Сила: {character.strength}\n"
                                     f"Скорость: {character.speed}\n"
                                     f"Выносливость: {character.endurance}\n"
                                     f"Ловкость: {character.dexterity}\n"
                                     f"Восприятие: {character.perception}\n"
                                     f"Реакция: {character.reaction}\n"
                                     f"Стрессоустойчивость: {character.stress_resistance}")
                del self.pending_character_creation[user_id]
            except ValueError:
                await message.answer("Введите корректное число!")

    async def handle_character_creation_points(self, message: Message):
        await self.handle_character_creation(message)

    async def action_mode_on(self, message: Message):
        if not self.db.is_admin(message.from_id):
            await message.answer("Только администратор может включать Экшен режим!")
            return

        action_mode = self.db.get_expeditor_action_mode()
        if action_mode.active:
            await message.answer("Экшен режим уже включен!")
            return

        self.pending_action_mode[message.from_id] = {"participants": []}
        await message.answer("Введите ID первого участника (или 'Готово' для завершения):")

    async def handle_action_mode_participants(self, message: Message):
        judge_id = message.from_id
        if judge_id not in self.pending_action_mode:
            return

        if message.text == "Готово":
            action_mode = self.db.get_expeditor_action_mode()
            action_mode.active = True
            action_mode.judge_id = judge_id
            action_mode.participants = self.pending_action_mode[judge_id]["participants"]
            action_mode.initiative_order = []

            for user_id in action_mode.participants:
                character = self.db.get_expeditor_character(user_id)
                if character:
                    initiative = calculate_initiative(character)
                    action_mode.initiative_order.append({user_id: initiative})

            action_mode.initiative_order.sort(key=lambda x: list(x.values())[0], reverse=True)
            self.db.save_expeditor_action_mode(action_mode)
            await message.answer("Экшен режим включен!\n"
                                 f"Судья: {action_mode.judge_id}\n"
                                 f"Участники: {action_mode.participants}\n"
                                 f"Очередь: {[list(item.keys())[0] for item in action_mode.initiative_order]}")
            del self.pending_action_mode[judge_id]
        else:
            try:
                user_id = int(message.text)
                self.pending_action_mode[judge_id]["participants"].append(user_id)
                await message.answer("Участник добавлен. Введите ID следующего участника (или 'Готово' для завершения):")
            except ValueError:
                await message.answer("Введите корректный ID участника или 'Готово' для завершения.")

    async def action_mode_off(self, message: Message):
        if not self.db.is_admin(message.from_id):
            await message.answer("Только администратор может выключать Экшен режим!")
            return

        action_mode = self.db.get_expeditor_action_mode()
        if not action_mode.active:
            await message.answer("Экшен режим уже выключен!")
            return

        action_mode.active = False
        action_mode.judge_id = None
        action_mode.participants = []
        action_mode.initiative_order = []
        self.db.save_expeditor_action_mode(action_mode)
        await message.answer("Экшен режим выключен!")

    async def add_race(self, message: Message):
        if not self.db.is_admin(message.from_id):
            await message.answer("Только администратор может добавлять расы!")
            return

        await message.answer("Введите название новой расы:")
        self.pending_character_creation[message.from_id] = {"step": "add_race_name", "data": {}}

    async def add_profession(self, message: Message):
        if not self.db.is_admin(message.from_id):
            await message.answer("Только администратор может добавлять профессии!")
            return

        await message.answer("Введите название новой профессии:")
        self.pending_character_creation[message.from_id] = {"step": "add_profession_name", "data": {}}

    async def handle_add_race_profession(self, message: Message):
        user_id = message.from_id
        if user_id not in self.pending_character_creation:
            return

        step = self.pending_character_creation[user_id]["step"]
        data = self.pending_character_creation[user_id]["data"]

        if step == "add_race_name":
            data["name"] = message.text
            keyboard = Keyboard(one_time=True)
            for char in ["Сила", "Скорость", "Выносливость", "Ловкость", "Восприятие", "Реакция", "Стрессоустойчивость"]:
                keyboard.add(Text(char), color=KeyboardButtonColor.PRIMARY)
            await message.answer("Выберите характеристику для модификатора:", keyboard=keyboard.get_json())
            self.pending_character_creation[user_id]["step"] = "add_race_modifier_char"
            data["modifiers"] = {}

        elif step == "add_race_modifier_char":
            data["current_char"] = message.text.lower()
            await message.answer(f"Введите модификатор для {message.text} (например, 10 или -5):")
            self.pending_character_creation[user_id]["step"] = "add_race_modifier_value"

        elif step == "add_race_modifier_value":
            try:
                value = int(message.text)
                data["modifiers"][data["current_char"]] = value
                keyboard = Keyboard(one_time=True)
                keyboard.add(Text("Да"), color=KeyboardButtonColor.POSITIVE)
                keyboard.add(Text("Нет"), color=KeyboardButtonColor.NEGATIVE)
                await message.answer("Добавить еще модификатор?", keyboard=keyboard.get_json())
                self.pending_character_creation[user_id]["step"] = "add_race_more"
            except ValueError:
                await message.answer("Введите корректное число!")

        elif step == "add_race_more":
            if message.text == "Да":
                keyboard = Keyboard(one_time=True)
                for char in ["Сила", "Скорость", "Выносливость", "Ловкость", "Восприятие", "Реакция", "Стрессоустойчивость"]:
                    keyboard.add(Text(char), color=KeyboardButtonColor.PRIMARY)
                await message.answer("Выберите характеристику для модификатора:", keyboard=keyboard.get_json())
                self.pending_character_creation[user_id]["step"] = "add_race_modifier_char"
            else:
                self.db.add_race(data["name"], data["modifiers"])
                await message.answer(f"Раса {data['name']} добавлена!")
                del self.pending_character_creation[user_id]

        elif step == "add_profession_name":
            data["name"] = message.text
            keyboard = Keyboard(one_time=True)
            for char in ["Сила", "Скорость", "Выносливость", "Ловкость", "Восприятие", "Реакция", "Стрессоустойчивость"]:
                keyboard.add(Text(char), color=KeyboardButtonColor.PRIMARY)
            await message.answer("Выберите характеристику для модификатора:", keyboard=keyboard.get_json())
            self.pending_character_creation[user_id]["step"] = "add_profession_modifier_char"
            data["modifiers"] = {}

        elif step == "add_profession_modifier_char":
            data["current_char"] = message.text.lower()
            await message.answer(f"Введите модификатор для {message.text} (например, 10 или -5):")
            self.pending_character_creation[user_id]["step"] = "add_profession_modifier_value"

        elif step == "add_profession_modifier_value":
            try:
                value = int(message.text)
                data["modifiers"][data["current_char"]] = value
                keyboard = Keyboard(one_time=True)
                keyboard.add(Text("Да"), color=KeyboardButtonColor.POSITIVE)
                keyboard.add(Text("Нет"), color=KeyboardButtonColor.NEGATIVE)
                await message.answer("Добавить еще модификатор?", keyboard=keyboard.get_json())
                self.pending_character_creation[user_id]["step"] = "add_profession_more"
            except ValueError:
                await message.answer("Введите корректное число!")

        elif step == "add_profession_more":
            if message.text == "Да":
                keyboard = Keyboard(one_time=True)
                for char in ["Сила", "Скорость", "Выносливость", "Ловкость", "Восприятие", "Реакция", "Стрессоустойчивость"]:
                    keyboard.add(Text(char), color=KeyboardButtonColor.PRIMARY)
                await message.answer("Выберите характеристику для модификатора:", keyboard=keyboard.get_json())
                self.pending_character_creation[user_id]["step"] = "add_profession_modifier_char"
            else:
                self.db.add_profession(data["name"], data["modifiers"])
                await message.answer(f"Профессия {data['name']} добавлена!")
                del self.pending_character_creation[user_id]

    async def view_logs(self, message: Message):
        if not self.db.is_admin(message.from_id):
            await message.answer("Только администратор может просматривать логи!")
            return

        logs = self.db.get_check_logs()
        if not logs:
            await message.answer("Логи проверок отсутствуют.")
            return

        response = "Логи проверок:\n"
        for log in logs[:10]:  # Ограничим 10 записями
            response += f"[{log['timestamp']}] Пользователь {log['user_id']}: {log['action']} - {log['result']}, Последствия: {log['consequences']}\n"
        await message.answer(response)

    async def handle_action(self, message: Message):
        action_mode = self.db.get_expeditor_action_mode()
        if not action_mode.active:
            await message.answer("Экшен режим не активен! Включите его командой /expeditor_action_mode_on")
            return

        current_user = list(action_mode.initiative_order[0].keys())[0]
        if message.from_id != current_user:
            await message.answer("Сейчас не ваш ход!")
            return

        action_text = message.text.strip("[]")
        if not action_text:
            await message.answer("Укажите действие в формате [Действие]")
            return

        character = self.db.get_expeditor_character(message.from_id)
        if not character:
            await message.answer("Персонаж не найден! Создайте его командой /expeditor_create_character")
            return

        movement_distance = calculate_movement_distance(character)
        await message.answer(f"Вы можете переместиться на {movement_distance} метров перед или после действия.")

        keyboard = Keyboard(one_time=True)
        for char in ["Сила", "Скорость", "Выносливость", "Ловкость", "Восприятие", "Реакция", "Стрессоустойчивость"]:
            keyboard.add(Text(char), color=KeyboardButtonColor.PRIMARY)
        keyboard.row()
        keyboard.add(Text("Отмена"), color=KeyboardButtonColor.NEGATIVE)
        await self.bot.api.messages.send(
            user_id=action_mode.judge_id,
            message=f"Игрок {message.from_id} выполняет действие: [{action_text}]\nВыберите характеристику для проверки:",
            keyboard=keyboard.get_json(),
            random_id=random.randint(1, 1000000)
        )

        self.pending_checks[message.from_id] = {
            "action": action_text,
            "characteristic": None,
            "difficulty": None,
            "bonus": None,
            "penalty": None,
            "consequences": {"success": [], "failure": []},
            "cancellable": None
        }

    async def handle_judge_response(self, message: Message):
        user_id = next((uid for uid, check in self.pending_checks.items() if check["characteristic"] is None), None)
        if not user_id or message.from_id != self.db.get_expeditor_action_mode().judge_id:
            return

        if message.text == "Отмена":
            del self.pending_checks[user_id]
            await message.answer("Проверка отменена.")
            return

        self.pending_checks[user_id]["characteristic"] = message.text

        keyboard = Keyboard(one_time=True)
        for difficulty in ["Легкая", "Нормальная", "Сложная", "Очень сложная"]:
            keyboard.add(Text(difficulty), color=KeyboardButtonColor.PRIMARY)
        keyboard.row()
        keyboard.add(Text("Отмена"), color=KeyboardButtonColor.NEGATIVE)
        await message.answer("Выберите сложность проверки:", keyboard=keyboard.get_json())

    async def handle_difficulty(self, message: Message):
        user_id = next((uid for uid, check in self.pending_checks.items() if check["difficulty"] is None and check["characteristic"]), None)
        if not user_id or message.from_id != self.db.get_expeditor_action_mode().judge_id:
            return

        if message.text == "Отмена":
            del self.pending_checks[user_id]
            await message.answer("Проверка отменена.")
            return

        self.pending_checks[user_id]["difficulty"] = message.text

        keyboard = Keyboard(one_time=True)
        for penalty in ["Отсутствует", "Низкий", "Обычный", "Высокий"]:
            keyboard.add(Text(penalty), color=KeyboardButtonColor.PRIMARY)
        keyboard.row()
        keyboard.add(Text("Отмена"), color=KeyboardButtonColor.NEGATIVE)
        await message.answer("Выберите штраф:", keyboard=keyboard.get_json())

    async def handle_penalty(self, message: Message):
        user_id = next((uid for uid, check in self.pending_checks.items() if check["penalty"] is None and check["difficulty"]), None)
        if not user_id or message.from_id != self.db.get_expeditor_action_mode().judge_id:
            return

        if message.text == "Отмена":
            del self.pending_checks[user_id]
            await message.answer("Проверка отменена.")
            return

        penalty_values = {"Отсутствует": 0, "Низкий": 20, "Обычный": 40, "Высокий": 60}
        self.pending_checks[user_id]["penalty"] = penalty_values[message.text]

        keyboard = Keyboard(one_time=True)
        for bonus in ["Отсутствует", "Низкий", "Обычный", "Высокий"]:
            keyboard.add(Text(bonus), color=KeyboardButtonColor.PRIMARY)
        keyboard.row()
        keyboard.add(Text("Отмена"), color=KeyboardButtonColor.NEGATIVE)
        await message.answer("Выберите бонус:", keyboard=keyboard.get_json())

    async def handle_bonus(self, message: Message):
        user_id = next((uid for uid, check in self.pending_checks.items() if check["bonus"] is None and check["penalty"] is not None), None)
        if not user_id or message.from_id != self.db.get_expeditor_action_mode().judge_id:
            return

        if message.text == "Отмена":
            del self.pending_checks[user_id]
            await message.answer("Проверка отменена.")
            return

        bonus_values = {"Отсутствует": 0, "Низкий": 20, "Обычный": 40, "Высокий": 60}
        self.pending_checks[user_id]["bonus"] = bonus_values[message.text]

        keyboard = Keyboard(one_time=True)
        for consequence_type in ["Получение Травмы", "Лечение Травмы", "Получение Психоза", "Лечение Психоза", "Повышение Либидо", "Понижение Либидо", "Повышение Подчинения", "Понижение Подчинения", "Оплодотворение", "Снятие Оплодотворения"]:
            keyboard.add(Text(consequence_type), color=KeyboardButtonColor.PRIMARY)
        keyboard.row()
        keyboard.add(Text("Готово"), color=KeyboardButtonColor.POSITIVE)
        await message.answer("Выберите тип последствия для успеха:", keyboard=keyboard.get_json())
        self.pending_consequence[user_id] = {"step": "type_success", "data": {"success": [], "failure": []}}

    async def handle_consequence_type(self, message: Message):
        user_id = next((uid for uid in self.pending_consequence.keys()), None)
        if not user_id or message.from_id != self.db.get_expeditor_action_mode().judge_id:
            return

        step = self.pending_consequence[user_id]["step"]
        data = self.pending_consequence[user_id]["data"]

        if message.text == "Готово":
            if step == "type_success":
                self.pending_consequence[user_id]["step"] = "type_failure"
                keyboard = Keyboard(one_time=True)
                for consequence_type in ["Получение Травмы", "Лечение Травмы", "Получение Психоза", "Лечение Психоза", "Повышение Либидо", "Понижение Либидо", "Повышение Подчинения", "Понижение Подчинения", "Оплодотворение", "Снятие Оплодотворения"]:
                    keyboard.add(Text(consequence_type), color=KeyboardButtonColor.PRIMARY)
                keyboard.row()
                keyboard.add(Text("Готово"), color=KeyboardButtonColor.POSITIVE)
                await message.answer("Выберите тип последствия для провала:", keyboard=keyboard.get_json())
            else:
                self.pending_checks[user_id]["consequences"] = data
                keyboard = Keyboard(one_time=True)
                keyboard.add(Text("Да"), color=KeyboardButtonColor.POSITIVE)
                keyboard.add(Text("Нет"), color=KeyboardButtonColor.NEGATIVE)
                await message.answer("Разрешить отмену проверки?", keyboard=keyboard.get_json())
                del self.pending_consequence[user_id]
            return

        consequence = {"type": message.text, "details": {}}
        if message.text in ["Получение Травмы", "Лечение Травмы", "Получение Психоза", "Лечение Психоза"]:
            await message.answer("Введите название (например, 'Растяжение лодыжки'):")
            self.pending_consequence[user_id]["step"] = f"{step}_name"
            self.pending_consequence[user_id]["data"]["current"] = consequence
        elif message.text in ["Повышение Либидо", "Понижение Либидо", "Повышение Подчинения", "Понижение Подчинения"]:
            await message.answer("Введите значение (например, 10):")
            self.pending_consequence[user_id]["step"] = f"{step}_value"
            self.pending_consequence[user_id]["data"]["current"] = consequence
        elif message.text == "Оплодотворение":
            await message.answer("Введите, кем оплодотворен:")
            self.pending_consequence[user_id]["step"] = f"{step}_by"
            self.pending_consequence[user_id]["data"]["current"] = consequence
        elif message.text == "Снятие Оплодотворения":
            if step == "type_success":
                data["success"].append(consequence)
            else:
                data["failure"].append(consequence)
            await message.answer("Последствие добавлено. Добавить еще?", keyboard=keyboard.get_json())

    async def handle_consequence_characteristic(self, message: Message):
        user_id = next((uid for uid in self.pending_consequence.keys()), None)
        if not user_id or message.from_id != self.db.get_expeditor_action_mode().judge_id:
            return

        step = self.pending_consequence[user_id]["step"]
        data = self.pending_consequence[user_id]["data"]
        consequence = data["current"]

        if step.endswith("_name"):
            consequence["details"]["name"] = message.text
            if consequence["type"] in ["Получение Травмы", "Получение Психоза"]:
                keyboard = Keyboard(one_time=True)
                for char in ["Сила", "Скорость", "Выносливость", "Ловкость", "Восприятие", "Реакция", "Стрессоустойчивость"]:
                    keyboard.add(Text(char), color=KeyboardButtonColor.PRIMARY)
                await message.answer("Выберите характеристику для штрафа:", keyboard=keyboard.get_json())
                self.pending_consequence[user_id]["step"] = step.replace("_name", "_char")
            else:
                if step.startswith("type_success"):
                    data["success"].append(consequence)
                else:
                    data["failure"].append(consequence)
                keyboard = Keyboard(one_time=True)
                for consequence_type in ["Получение Травмы", "Лечение Травмы", "Получение Психоза", "Лечение Психоза", "Повышение Либидо", "Понижение Либидо", "Повышение Подчинения", "Понижение Подчинения", "Оплодотворение", "Снятие Оплодотворения"]:
                    keyboard.add(Text(consequence_type), color=KeyboardButtonColor.PRIMARY)
                keyboard.row()
                keyboard.add(Text("Готово"), color=KeyboardButtonColor.POSITIVE)
                await message.answer("Добавить еще последствие?", keyboard=keyboard.get_json())

        elif step.endswith("_char"):
            consequence["details"]["characteristic"] = message.text.lower()
            await message.answer("Введите величину штрафа (например, 10):")
            self.pending_consequence[user_id]["step"] = step.replace("_char", "_penalty")

        elif step.endswith("_penalty"):
            try:
                penalty = int(message.text)
                consequence["details"]["penalty"] = penalty
                if step.startswith("type_success"):
                    data["success"].append(consequence)
                else:
                    data["failure"].append(consequence)
                keyboard = Keyboard(one_time=True)
                for consequence_type in ["Получение Травмы", "Лечение Травмы", "Получение Психоза", "Лечение Психоза", "Повышение Либидо", "Понижение Либидо", "Повышение Подчинения", "Понижение Подчинения", "Оплодотворение", "Снятие Оплодотворения"]:
                    keyboard.add(Text(consequence_type), color=KeyboardButtonColor.PRIMARY)
                keyboard.row()
                keyboard.add(Text("Готово"), color=KeyboardButtonColor.POSITIVE)
                await message.answer("Добавить еще последствие?", keyboard=keyboard.get_json())
            except ValueError:
                await message.answer("Введите корректное число!")

        elif step.endswith("_value"):
            try:
                value = int(message.text)
                consequence["details"]["value"] = value
                if step.startswith("type_success"):
                    data["success"].append(consequence)
                else:
                    data["failure"].append(consequence)
                keyboard = Keyboard(one_time=True)
                for consequence_type in ["Получение Травмы", "Лечение Травмы", "Получение Психоза", "Лечение Психоза", "Повышение Либидо", "Понижение Либидо", "Повышение Подчинения", "Понижение Подчинения", "Оплодотворение", "Снятие Оплодотворения"]:
                    keyboard.add(Text(consequence_type), color=KeyboardButtonColor.PRIMARY)
                keyboard.row()
                keyboard.add(Text("Готово"), color=KeyboardButtonColor.POSITIVE)
                await message.answer("Добавить еще последствие?", keyboard=keyboard.get_json())
            except ValueError:
                await message.answer("Введите корректное число!")

        elif step.endswith("_by"):
            consequence["details"]["by"] = message.text
            if step.startswith("type_success"):
                data["success"].append(consequence)
            else:
                data["failure"].append(consequence)
            keyboard = Keyboard(one_time=True)
            for consequence_type in ["Получение Травмы", "Лечение Травмы", "Получение Психоза", "Лечение Психоза", "Повышение Либидо", "Понижение Либидо", "Повышение Подчинения", "Понижение Подчинения", "Оплодотворение", "Снятие Оплодотворения"]:
                keyboard.add(Text(consequence_type), color=KeyboardButtonColor.PRIMARY)
            keyboard.row()
            keyboard.add(Text("Готово"), color=KeyboardButtonColor.POSITIVE)
            await message.answer("Добавить еще последствие?", keyboard=keyboard.get_json())

    async def handle_cancellable(self, message: Message):
        user_id = next((uid for uid, check in self.pending_checks.items() if check["cancellable"] is None and check["bonus"] is not None), None)
        if not user_id or message.from_id != self.db.get_expeditor_action_mode().judge_id:
            return

        self.pending_checks[user_id]["cancellable"] = message.text == "Да"

        check = self.pending_checks[user_id]
        keyboard = Keyboard(one_time=True)
        keyboard.add(Text("Выполнить проверку"), color=KeyboardButtonColor.POSITIVE)
        if check["cancellable"]:
            keyboard.add(Text("Отменить проверку"), color=KeyboardButtonColor.NEGATIVE)

        await self.bot.api.messages.send(
            user_id=user_id,
            message=f"Название проверки: [{check['action']}]\n"
                    f"Проверка характеристики: {check['characteristic']}\n"
                    f"Сложность: {check['difficulty']}\n"
                    f"Штраф: {check['penalty']}\n"
                    f"Бонус: {check['bonus']}",
            keyboard=keyboard.get_json(),
            random_id=random.randint(1, 1000000)
        )

    async def handle_player_response(self, message: Message):
        if message.from_id not in self.pending_checks:
            return

        check = self.pending_checks[message.from_id]
        if message.text == "Отменить проверку" and check["cancellable"]:
            del self.pending_checks[message.from_id]
            await message.answer("Проверка отменена.")
            return

        if message.text != "Выполнить проверку":
            return

        character = self.db.get_expeditor_character(message.from_id)
        success, result = perform_check(
            character,
            check["characteristic"],
            check["difficulty"],
            check["bonus"],
            check["penalty"]
        )

        consequences = check["consequences"]["success" if success else "failure"]
        consequence_texts = []
        for consequence in consequences:
            apply_consequence(character, Consequence(type=consequence["type"], details=consequence["details"]))
            consequence_texts.append(f"{consequence['type']}: {json.dumps(consequence['details'])}")

        self.db.save_expeditor_character(character)
        self.db.log_expeditor_check(message.from_id, check["action"], result, ", ".join(consequence_texts))
        await message.answer(f"{character.name} {result.lower()} прошел проверку.\n"
                             f"Последствия: {', '.join(consequence_texts) if consequence_texts else 'Нет'}{f', дополнительный эффект ({result.lower()})' if 'Критический' in result else ''}")

        action_mode = self.db.get_expeditor_action_mode()
        action_mode.initiative_order.append(action_mode.initiative_order.pop(0))
        self.db.save_expeditor_action_mode(action_mode)
        next_user = list(action_mode.initiative_order[0].keys())[0]
        await self.bot.api.messages.send(
            user_id=next_user,
            message="Ваш ход! Укажите действие в формате [Действие]",
            random_id=random.randint(1, 1000000)
        )

        del self.pending_checks[message.from_id]