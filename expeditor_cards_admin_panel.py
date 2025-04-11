"""
Модуль для управления картами экспедитора в админ панели
"""
from vkbottle.bot import Message, Bot
from vkbottle.bot import BotLabeler
from vkbottle import Keyboard, KeyboardButtonColor, Text
from typing import Optional, List

from expeditor.expeditor_database_optimized import Database
from expeditor.models import Character, Item, Effect

expeditor_admin_labeler = BotLabeler()

def get_expeditor_admin_keyboard() -> Keyboard:
    keyboard = Keyboard(one_time=True)
    keyboard.add(Text("Список карт"), color=KeyboardButtonColor.PRIMARY)
    keyboard.add(Text("Назад"), color=KeyboardButtonColor.SECONDARY)
    return keyboard

def get_character_edit_keyboard() -> Keyboard:
    keyboard = Keyboard(one_time=True)
    keyboard.add(Text("Изменить характеристики"), color=KeyboardButtonColor.PRIMARY)
    keyboard.add(Text("Изменить профессию"), color=KeyboardButtonColor.PRIMARY)
    keyboard.row()
    keyboard.add(Text("Изменить расу"), color=KeyboardButtonColor.PRIMARY)
    keyboard.add(Text("Управление предметами"), color=KeyboardButtonColor.PRIMARY)
    keyboard.row()
    keyboard.add(Text("Управление эффектами"), color=KeyboardButtonColor.PRIMARY)
    keyboard.add(Text("Изменить статус оплодотворения"), color=KeyboardButtonColor.PRIMARY)
    keyboard.row()
    keyboard.add(Text("Назад"), color=KeyboardButtonColor.SECONDARY)
    return keyboard

def get_characteristics_keyboard() -> Keyboard:
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
    keyboard.add(Text("Назад"), color=KeyboardButtonColor.SECONDARY)
    return keyboard

def get_race_keyboard() -> Keyboard:
    keyboard = Keyboard(one_time=True)
    keyboard.add(Text("Человек"), color=KeyboardButtonColor.PRIMARY)
    keyboard.add(Text("Ксенос"), color=KeyboardButtonColor.PRIMARY)
    keyboard.row()
    keyboard.add(Text("Мутант"), color=KeyboardButtonColor.PRIMARY)
    keyboard.add(Text("Робот"), color=KeyboardButtonColor.PRIMARY)
    keyboard.row()
    keyboard.add(Text("Назад"), color=KeyboardButtonColor.SECONDARY)
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
    keyboard.row()
    keyboard.add(Text("Назад"), color=KeyboardButtonColor.SECONDARY)
    return keyboard

def get_items_keyboard() -> Keyboard:
    keyboard = Keyboard(one_time=True)
    keyboard.add(Text("Добавить предмет"), color=KeyboardButtonColor.POSITIVE)
    keyboard.add(Text("Удалить предмет"), color=KeyboardButtonColor.NEGATIVE)
    keyboard.row()
    keyboard.add(Text("Назад"), color=KeyboardButtonColor.SECONDARY)
    return keyboard

def get_effects_keyboard() -> Keyboard:
    keyboard = Keyboard(one_time=True)
    keyboard.add(Text("Добавить эффект"), color=KeyboardButtonColor.POSITIVE)
    keyboard.add(Text("Удалить эффект"), color=KeyboardButtonColor.NEGATIVE)
    keyboard.row()
    keyboard.add(Text("Назад"), color=KeyboardButtonColor.SECONDARY)
    return keyboard

def get_deletion_requests_keyboard() -> Keyboard:
    keyboard = Keyboard(one_time=True)
    keyboard.add(Text("Одобрить"), color=KeyboardButtonColor.POSITIVE)
    keyboard.add(Text("Отклонить"), color=KeyboardButtonColor.NEGATIVE)
    keyboard.row()
    keyboard.add(Text("Назад"), color=KeyboardButtonColor.SECONDARY)
    return keyboard

@expeditor_admin_labeler.message(text="Редактирование Карт Экспедитора")
async def expeditor_cards_menu(m: Message):
    db = Database()
    if not await db.is_admin(m.from_id):
        await m.answer("У вас нет доступа к этой функции!")
        return
    
    await m.answer(
        "Управление картами экспедитора:\n"
        "Выберите действие:",
        keyboard=get_expeditor_admin_keyboard()
    )

@expeditor_admin_labeler.message(text="Список карт")
async def show_cards(m: Message):
    db = Database()
    characters = await db.get_all_characters()
    
    if not characters:
        await m.answer("Нет созданных карт!")
        return
    
    keyboard = Keyboard(one_time=True)
    for character in characters:
        keyboard.add(Text(f"Редактировать {character.name}"), color=KeyboardButtonColor.PRIMARY)
        keyboard.row()
    
    keyboard.add(Text("Назад"), color=KeyboardButtonColor.SECONDARY)
    
    await m.answer(
        "Список карт экспедитора:\n" + 
        "\n".join([f"{char.name} ({char.race}, {char.profession})" for char in characters]),
        keyboard=keyboard
    )

@expeditor_admin_labeler.message(text=lambda text: text.startswith("Редактировать "))
async def edit_character(m: Message):
    character_name = m.text.replace("Редактировать ", "")
    db = Database()
    
    character = await db.get_character_by_name(character_name)
    if not character:
        await m.answer("Персонаж не найден!")
        return
    
    m.payload = {"character_id": character.id}
    
    await m.answer(
        f"Редактирование персонажа {character.name}:\n"
        f"Раса: {character.race}\n"
        f"Профессия: {character.profession}\n"
        f"Характеристики:\n"
        f"Сила: {character.base_strength}\n"
        f"Скорость: {character.base_speed}\n"
        f"Выносливость: {character.base_endurance}\n"
        f"Ловкость: {character.base_dexterity}\n"
        f"Восприятие: {character.base_perception}\n"
        f"Реакция: {character.base_reaction}\n"
        f"Стрессоустойчивость: {character.base_stress_resistance}",
        keyboard=get_character_edit_keyboard()
    )

@expeditor_admin_labeler.message(text="Изменить характеристики")
async def edit_characteristics(m: Message):
    character_id = m.payload.get("character_id")
    if not character_id:
        await m.answer("Ошибка: не выбран персонаж!")
        return
    
    await m.answer(
        "Выберите характеристику для изменения:",
        keyboard=get_characteristics_keyboard()
    )

@expeditor_admin_labeler.message(text=[
    "Сила", "Скорость", "Выносливость", "Ловкость",
    "Восприятие", "Реакция", "Стрессоустойчивость"
])
async def set_characteristic_value(m: Message):
    characteristic = m.text.lower()
    character_id = m.payload.get("character_id")
    
    m.payload = {
        "character_id": character_id,
        "characteristic": characteristic
    }
    
    await m.answer(
        f"Введите новое значение для {characteristic} (1-10):",
        keyboard=Keyboard(one_time=True)
    )

@expeditor_admin_labeler.message(text=lambda text: text.isdigit() and 1 <= int(text) <= 10)
async def update_characteristic(m: Message):
    value = int(m.text)
    character_id = m.payload.get("character_id")
    characteristic = m.payload.get("characteristic")
    
    db = Database()
    await db.update_characteristic(character_id, characteristic, value)
    
    await m.answer(
        f"Характеристика {characteristic} обновлена до {value}",
        keyboard=get_character_edit_keyboard()
    )

@expeditor_admin_labeler.message(text="Изменить профессию")
async def edit_profession(m: Message):
    await m.answer(
        "Выберите новую профессию:",
        keyboard=get_profession_keyboard()
    )

@expeditor_admin_labeler.message(text="Изменить расу")
async def edit_race(m: Message):
    await m.answer(
        "Выберите новую расу:",
        keyboard=get_race_keyboard()
    )

@expeditor_admin_labeler.message(text="Управление предметами")
async def manage_items(m: Message):
    await m.answer(
        "Управление предметами персонажа:",
        keyboard=get_items_keyboard()
    )

@expeditor_admin_labeler.message(text="Управление эффектами")
async def manage_effects(m: Message):
    await m.answer(
        "Управление эффектами персонажа:",
        keyboard=get_effects_keyboard()
    )

@expeditor_admin_labeler.message(text="Изменить статус оплодотворения")
async def toggle_fertilization(m: Message):
    character_id = m.payload.get("character_id")
    if not character_id:
        await m.answer("Ошибка: не выбран персонаж!")
        return
    
    db = Database()
    character = await db.get_character_by_id(character_id)
    new_status = not character.is_fertilized
    
    await db.update_fertilization_status(character_id, new_status)
    
    await m.answer(
        f"Статус оплодотворения изменен на {'оплодотворен' if new_status else 'не оплодотворен'}",
        keyboard=get_character_edit_keyboard()
    )

@expeditor_admin_labeler.message(text="Назад")
async def back_to_admin(m: Message):
    keyboard = Keyboard(one_time=True)
    keyboard.add(Text("Админ панель"), color=KeyboardButtonColor.PRIMARY)
    
    await m.answer(
        "Возврат в админ панель:",
        keyboard=keyboard
    )

@expeditor_admin_labeler.message(text="Запросы на удаление")
async def show_deletion_requests(m: Message):
    db = Database()
    requests = await db.get_deletion_requests()
    
    if not requests:
        await m.answer("Нет активных запросов на удаление.")
        return
    
    keyboard = Keyboard(one_time=True)
    for request in requests:
        keyboard.add(Text(f"Запрос #{request['id']}"), color=KeyboardButtonColor.PRIMARY)
        keyboard.row()
    
    keyboard.add(Text("Назад"), color=KeyboardButtonColor.SECONDARY)
    
    await m.answer(
        "Список запросов на удаление:\n" + 
        "\n".join([f"#{req['id']} - {req['character_name']} ({req['user_id']})" for req in requests]),
        keyboard=keyboard
    )

@expeditor_admin_labeler.message(text=lambda text: text.startswith("Запрос #"))
async def show_deletion_request(m: Message):
    request_id = int(m.text.split("#")[1])
    db = Database()
    requests = await db.get_deletion_requests()
    request = next((r for r in requests if r['id'] == request_id), None)
    
    if not request:
        await m.answer("Запрос не найден.")
        return
    
    m.payload = {"action": "process_deletion", "request_id": request_id}
    
    await m.answer(
        f"Запрос на удаление персонажа:\n\n"
        f"ID запроса: #{request['id']}\n"
        f"Пользователь: {request['user_id']}\n"
        f"Персонаж: {request['character_name']}\n"
        f"Причина: {request['reason']}\n"
        f"Сохранить копию: {'Да' if request['keep_copy'] else 'Нет'}\n\n"
        f"Выберите действие:",
        keyboard=get_deletion_requests_keyboard()
    )

@expeditor_admin_labeler.message(text=["Одобрить", "Отклонить"])
async def process_deletion_request(m: Message):
    if m.payload.get("action") != "process_deletion":
        return
    
    request_id = m.payload.get("request_id")
    approve = m.text == "Одобрить"
    
    db = Database()
    success = await db.process_deletion_request(request_id, approve)
    
    if success:
        status = "одобрен" if approve else "отклонен"
        await m.answer(
            f"Запрос на удаление #{request_id} {status}.",
            keyboard=get_expeditor_admin_keyboard()
        )
    else:
        await m.answer(
            "Произошла ошибка при обработке запроса. Пожалуйста, попробуйте позже.",
            keyboard=get_expeditor_admin_keyboard()
        ) 