"""
Команды системы экспедитора
"""
from vkbottle.bot import Message, Bot
from vkbottle.bot import BotLabeler
from vkbottle import Keyboard, KeyboardButtonColor, Text
from typing import Optional

from .expeditor_database_optimized import Database
from .expeditor_mechanics import generate_characteristics, perform_check, calculate_available_actions
from .models import Character, ActionMode
from roleplayhelper.messages import (
    expeditor_race_human, expeditor_race_xenos, expeditor_race_mutant, expeditor_race_robot,
    expeditor_profession_maid, expeditor_profession_engineer, expeditor_profession_medical,
    expeditor_profession_lab, expeditor_profession_security, expeditor_profession_reception,
    expeditor_profession_sysadmin, expeditor_profession_doctor, expeditor_profession_lawyer,
    expeditor_profession_scientist, expeditor_profession_medic_head, expeditor_profession_maitre,
    expeditor_profession_security_head, expeditor_profession_engineer_head,
    expeditor_profession_research_head, expeditor_profession_station_head
)

expeditor_labeler = BotLabeler()

# Клавиатуры для создания персонажа
def get_race_keyboard() -> Keyboard:
    keyboard = Keyboard(one_time=True)
    keyboard.add(Text("Человек"), color=KeyboardButtonColor.PRIMARY)
    keyboard.add(Text("Ксенос"), color=KeyboardButtonColor.PRIMARY)
    keyboard.row()
    keyboard.add(Text("Мутант"), color=KeyboardButtonColor.PRIMARY)
    keyboard.add(Text("Робот"), color=KeyboardButtonColor.PRIMARY)
    return keyboard

def get_profession_keyboard() -> Keyboard:
    keyboard = Keyboard(one_time=True)
    keyboard.add(Text("Горничные"), color=KeyboardButtonColor.PRIMARY)
    keyboard.add(Text("Инженеры-техники"), color=KeyboardButtonColor.PRIMARY)
    keyboard.row()
    keyboard.add(Text("Медицинские сотрудники"), color=KeyboardButtonColor.PRIMARY)
    keyboard.add(Text("Лаборанты"), color=KeyboardButtonColor.PRIMARY)
    keyboard.row()
    keyboard.add(Text("Сотрудники службы безопасности"), color=KeyboardButtonColor.PRIMARY)
    keyboard.add(Text("Администраторы ресепшена"), color=KeyboardButtonColor.PRIMARY)
    keyboard.row()
    keyboard.add(Text("Системные администраторы"), color=KeyboardButtonColor.PRIMARY)
    keyboard.add(Text("Врачи"), color=KeyboardButtonColor.PRIMARY)
    keyboard.row()
    keyboard.add(Text("Юридический консультант/бухгалтер"), color=KeyboardButtonColor.PRIMARY)
    keyboard.add(Text("Учёный"), color=KeyboardButtonColor.PRIMARY)
    keyboard.row()
    keyboard.add(Text("Глава медицинского блока"), color=KeyboardButtonColor.PRIMARY)
    keyboard.add(Text("Метрдотель жилого блока"), color=KeyboardButtonColor.PRIMARY)
    keyboard.row()
    keyboard.add(Text("Начальник службы безопасности"), color=KeyboardButtonColor.PRIMARY)
    keyboard.add(Text("Главный инженер"), color=KeyboardButtonColor.PRIMARY)
    keyboard.row()
    keyboard.add(Text("Глава научно-исследовательского блока"), color=KeyboardButtonColor.PRIMARY)
    keyboard.add(Text("Управляющий станцией rg-98"), color=KeyboardButtonColor.PRIMARY)
    return keyboard

def get_action_keyboard(character: Character) -> Keyboard:
    keyboard = Keyboard(one_time=True)
    available_actions = calculate_available_actions(character)
    
    # Добавляем кнопки действий в зависимости от доступного количества
    for i in range(1, available_actions + 1):
        keyboard.add(Text(f"Действие {i}"), color=KeyboardButtonColor.PRIMARY)
        if i % 2 == 0:
            keyboard.row()
    
    return keyboard

def get_characteristic_keyboard() -> Keyboard:
    keyboard = Keyboard(one_time=True)
    keyboard.add(Text("Сила"), color=KeyboardButtonColor.PRIMARY)
    keyboard.add(Text("Скорость"), color=KeyboardButtonColor.PRIMARY)
    keyboard.row()
    keyboard.add(Text("Выносливость"), color=KeyboardButtonColor.PRIMARY)
    keyboard.add(Text("Ловкость"), color=KeyboardButtonColor.PRIMARY)
    keyboard.row()
    keyboard.add(Text("Восприятие"), color=KeyboardButtonColor.PRIMARY)
    keyboard.add(Text("Реакция"), color=KeyboardButtonColor.PRIMARY)
    keyboard.row()
    keyboard.add(Text("Стрессоустойчивость"), color=KeyboardButtonColor.PRIMARY)
    keyboard.add(Text("Отмена"), color=KeyboardButtonColor.NEGATIVE)
    return keyboard

def get_difficulty_keyboard() -> Keyboard:
    keyboard = Keyboard(one_time=True)
    keyboard.add(Text("Легкая"), color=KeyboardButtonColor.POSITIVE)
    keyboard.add(Text("Нормальная"), color=KeyboardButtonColor.PRIMARY)
    keyboard.row()
    keyboard.add(Text("Сложная"), color=KeyboardButtonColor.SECONDARY)
    keyboard.add(Text("Очень сложная"), color=KeyboardButtonColor.NEGATIVE)
    keyboard.row()
    keyboard.add(Text("Невозможная"), color=KeyboardButtonColor.NEGATIVE)
    keyboard.add(Text("Отмена"), color=KeyboardButtonColor.NEGATIVE)
    return keyboard

def get_action_type_keyboard() -> Keyboard:
    keyboard = Keyboard(one_time=True)
    keyboard.add(Text("Проверка характеристики"), color=KeyboardButtonColor.PRIMARY)
    keyboard.add(Text("Использовать предмет"), color=KeyboardButtonColor.PRIMARY)
    keyboard.row()
    keyboard.add(Text("Взаимодействие"), color=KeyboardButtonColor.PRIMARY)
    keyboard.add(Text("Отмена"), color=KeyboardButtonColor.NEGATIVE)
    return keyboard

def get_admin_keyboard() -> Keyboard:
    keyboard = Keyboard(one_time=True)
    keyboard.add(Text("Включить экшен режим"), color=KeyboardButtonColor.POSITIVE)
    keyboard.add(Text("Выключить экшен режим"), color=KeyboardButtonColor.NEGATIVE)
    keyboard.row()
    keyboard.add(Text("Добавить расу"), color=KeyboardButtonColor.PRIMARY)
    keyboard.add(Text("Добавить профессию"), color=KeyboardButtonColor.PRIMARY)
    keyboard.row()
    keyboard.add(Text("Просмотреть логи"), color=KeyboardButtonColor.PRIMARY)
    keyboard.add(Text("Назад"), color=KeyboardButtonColor.SECONDARY)
    return keyboard

@expeditor_labeler.message(text="Начать экспедитора")
async def start_expeditor(m: Message):
    keyboard = Keyboard(one_time=True)
    keyboard.add(Text("Создать персонажа"), color=KeyboardButtonColor.POSITIVE)
    keyboard.add(Text("Мои персонажи"), color=KeyboardButtonColor.PRIMARY)
    keyboard.row()
    
    db = Database()
    if await db.is_admin(m.from_id):
        keyboard.add(Text("Админ панель"), color=KeyboardButtonColor.SECONDARY)
    
    await m.answer(
        "Добро пожаловать в систему экспедитора!\n"
        "Выберите действие:",
        keyboard=keyboard
    )

@expeditor_labeler.message(text="Админ панель")
async def admin_panel(m: Message):
    db = Database()
    if not await db.is_admin(m.from_id):
        await m.answer("У вас нет доступа к админ панели!")
        return
    
    await m.answer(
        "Админ панель экспедитора:\n"
        "Выберите действие:",
        keyboard=get_admin_keyboard()
    )

@expeditor_labeler.message(text="Создать персонажа")
async def create_character(m: Message):
    await m.answer(
        "Выберите расу персонажа:\n\n"
        f"{expeditor_race_human}\n\n"
        f"{expeditor_race_xenos}\n\n"
        f"{expeditor_race_mutant}\n\n"
        f"{expeditor_race_robot}",
        keyboard=get_race_keyboard()
    )

@expeditor_labeler.message(text=["Человек", "Ксенос", "Мутант", "Робот"])
async def select_profession(m: Message):
    race = m.text.lower()
    # Сохраняем выбранную расу в payload
    m.payload = {"race": race}
    
    await m.answer(
        "Выберите профессию персонажа:\n\n"
        f"{expeditor_profession_maid}\n\n"
        f"{expeditor_profession_engineer}\n\n"
        f"{expeditor_profession_medical}\n\n"
        f"{expeditor_profession_lab}\n\n"
        f"{expeditor_profession_security}\n\n"
        f"{expeditor_profession_reception}\n\n"
        f"{expeditor_profession_sysadmin}\n\n"
        f"{expeditor_profession_doctor}\n\n"
        f"{expeditor_profession_lawyer}\n\n"
        f"{expeditor_profession_scientist}\n\n"
        f"{expeditor_profession_medic_head}\n\n"
        f"{expeditor_profession_maitre}\n\n"
        f"{expeditor_profession_security_head}\n\n"
        f"{expeditor_profession_engineer_head}\n\n"
        f"{expeditor_profession_research_head}\n\n"
        f"{expeditor_profession_station_head}",
        keyboard=get_profession_keyboard()
    )

@expeditor_labeler.message(text=[
    "Горничные", "Инженеры-техники", "Медицинские сотрудники", "Лаборанты",
    "Сотрудники службы безопасности", "Администраторы ресепшена", "Системные администраторы",
    "Врачи", "Юридический консультант/бухгалтер", "Учёный", "Глава медицинского блока",
    "Метрдотель жилого блока", "Начальник службы безопасности", "Главный инженер",
    "Глава научно-исследовательского блока", "Управляющий станцией rg-98"
])
async def finalize_character(m: Message):
    profession = m.text.lower()
    race = m.payload.get("race", "человек")  # Получаем расу из payload
    
    # Генерируем характеристики
    characteristics = generate_characteristics(race, profession)
    
    # Создаем персонажа
    db = Database()
    character = Character(
        user_id=m.from_id,
        name="Новый персонаж",  # Можно добавить запрос имени
        race=race,
        profession=profession,
        **characteristics
    )
    
    # Сохраняем персонажа
    await db.save_expeditor_character(character)
    
    # Показываем результат
    await m.answer(
        f"Персонаж создан!\n\n"
        f"Раса: {race.capitalize()}\n"
        f"Профессия: {profession.capitalize()}\n\n"
        f"Характеристики:\n"
        f"Сила: {characteristics['base_strength']}\n"
        f"Скорость: {characteristics['base_speed']}\n"
        f"Выносливость: {characteristics['base_endurance']}\n"
        f"Ловкость: {characteristics['base_dexterity']}\n"
        f"Восприятие: {characteristics['base_perception']}\n"
        f"Реакция: {characteristics['base_reaction']}\n"
        f"Стрессоустойчивость: {characteristics['base_stress_resistance']}",
        keyboard=get_action_keyboard(character)
    )

@expeditor_labeler.message(text=lambda text: text.startswith("Действие "))
async def perform_action(m: Message):
    action_number = int(m.text.split()[1])
    db = Database()
    
    # Получаем персонажа
    character = await db.get_expeditor_character(m.from_id)
    if not character:
        await m.answer("У вас нет активного персонажа!")
        return
    
    # Проверяем доступность действия
    available_actions = calculate_available_actions(character)
    if action_number > available_actions:
        await m.answer(f"У вас доступно только {available_actions} действий!")
        return
    
    # Сохраняем номер действия в payload
    m.payload = {"action_number": action_number}
    
    await m.answer(
        f"Выберите тип действия {action_number}:",
        keyboard=get_action_type_keyboard()
    )

@expeditor_labeler.message(text="Проверка характеристики")
async def check_characteristic(m: Message):
    action_number = m.payload.get("action_number", 1)
    await m.answer(
        f"Выберите характеристику для проверки действия {action_number}:",
        keyboard=get_characteristic_keyboard()
    )

@expeditor_labeler.message(text=[
    "Сила", "Скорость", "Выносливость", "Ловкость",
    "Восприятие", "Реакция", "Стрессоустойчивость"
])
async def select_difficulty(m: Message):
    characteristic = m.text.lower()
    action_number = m.payload.get("action_number", 1)
    m.payload = {"characteristic": characteristic, "action_number": action_number}
    
    await m.answer(
        f"Выберите сложность проверки {characteristic} для действия {action_number}:",
        keyboard=get_difficulty_keyboard()
    )

@expeditor_labeler.message(text=[
    "Легкая", "Нормальная", "Сложная", "Очень сложная", "Невозможная"
])
async def perform_characteristic_check(m: Message):
    difficulty = m.text
    characteristic = m.payload.get("characteristic", "")
    action_number = m.payload.get("action_number", 1)
    
    db = Database()
    character = await db.get_expeditor_character(m.from_id)
    if not character:
        await m.answer("У вас нет активного персонажа!")
        return
    
    # Выполняем проверку
    success, result = perform_check(
        character=character,
        characteristic=characteristic,
        difficulty=difficulty,
        action_number=action_number
    )
    
    # Создаем клавиатуру для возврата к действиям
    keyboard = Keyboard(one_time=True)
    keyboard.add(Text("Вернуться к действиям"), color=KeyboardButtonColor.PRIMARY)
    
    await m.answer(
        f"Проверка {characteristic} ({difficulty}):\n"
        f"Результат: {'Успех' if success else 'Провал'}\n"
        f"Детали: {result}",
        keyboard=keyboard
    )

@expeditor_labeler.message(text="Вернуться к действиям")
async def return_to_actions(m: Message):
    db = Database()
    character = await db.get_expeditor_character(m.from_id)
    if not character:
        await m.answer("У вас нет активного персонажа!")
        return
    
    await m.answer(
        f"У вас доступно {calculate_available_actions(character)} действий.\n"
        "Выберите действие:",
        keyboard=get_action_keyboard(character)
    )

@expeditor_labeler.message(text="Мои персонажи")
async def show_characters(m: Message):
    db = Database()
    characters = await db.get_user_characters(m.from_id)
    
    if not characters:
        await m.answer("У вас пока нет персонажей!")
        return
    
    # Создаем клавиатуру с персонажами
    keyboard = Keyboard(one_time=True)
    for character in characters:
        keyboard.add(Text(f"Выбрать {character.name}"), color=KeyboardButtonColor.PRIMARY)
        keyboard.row()
    
    await m.answer(
        "Ваши персонажи:\n" + 
        "\n".join([f"{char.name} ({char.race}, {char.profession})" for char in characters]),
        keyboard=keyboard
    )

@expeditor_labeler.message(text=lambda text: text.startswith("Выбрать "))
async def select_character(m: Message):
    character_name = m.text.replace("Выбрать ", "")
    db = Database()
    
    # Получаем персонажа
    character = await db.get_expeditor_character_by_name(m.from_id, character_name)
    if not character:
        await m.answer("Персонаж не найден!")
        return
    
    # Создаем клавиатуру с действиями
    keyboard = Keyboard(one_time=True)
    available_actions = calculate_available_actions(character)
    
    for i in range(1, available_actions + 1):
        keyboard.add(Text(f"Действие {i}"), color=KeyboardButtonColor.PRIMARY)
        if i % 2 == 0:
            keyboard.row()
    
    await m.answer(
        f"Выбран персонаж {character.name}:\n"
        f"Раса: {character.race}\n"
        f"Профессия: {character.profession}\n"
        f"Доступно действий: {available_actions}",
        keyboard=keyboard
    )

@expeditor_labeler.message(text="Назад")
async def back_to_main(m: Message):
    keyboard = Keyboard(one_time=True)
    keyboard.add(Text("Создать персонажа"), color=KeyboardButtonColor.POSITIVE)
    keyboard.add(Text("Мои персонажи"), color=KeyboardButtonColor.PRIMARY)
    keyboard.row()
    
    db = Database()
    if await db.is_admin(m.from_id):
        keyboard.add(Text("Админ панель"), color=KeyboardButtonColor.SECONDARY)
    
    await m.answer(
        "Главное меню экспедитора:\n"
        "Выберите действие:",
        keyboard=keyboard
    ) 