"""
Модуль для работы с экспедитором в публичном меню
"""
from vkbottle.bot import Message, Bot
from vkbottle.bot import BotLabeler
from vkbottle import Keyboard, KeyboardButtonColor, Text
from typing import Optional

from expeditor.expeditor_commands import (
    get_race_keyboard, get_profession_keyboard, get_action_keyboard,
    get_characteristic_keyboard, get_difficulty_keyboard, get_action_type_keyboard
)
from expeditor.expeditor_database_optimized import Database
from expeditor.expeditor_mechanics import generate_characteristics, perform_check, calculate_available_actions
from expeditor.models import Character

expeditor_labeler = BotLabeler()

def get_expeditor_keyboard() -> Keyboard:
    keyboard = Keyboard(one_time=True)
    keyboard.add(Text("Создать персонажа"), color=KeyboardButtonColor.POSITIVE)
    keyboard.add(Text("Мои персонажи"), color=KeyboardButtonColor.PRIMARY)
    keyboard.row()
    keyboard.add(Text("Назад"), color=KeyboardButtonColor.SECONDARY)
    return keyboard

def get_character_management_keyboard() -> Keyboard:
    keyboard = Keyboard(one_time=True)
    keyboard.add(Text("Удалить персонажа"), color=KeyboardButtonColor.NEGATIVE)
    keyboard.add(Text("Назад"), color=KeyboardButtonColor.SECONDARY)
    return keyboard

def get_inventory_keyboard() -> Keyboard:
    keyboard = Keyboard(one_time=True)
    keyboard.add(Text("Экипировка"), color=KeyboardButtonColor.PRIMARY)
    keyboard.add(Text("Вооружение"), color=KeyboardButtonColor.PRIMARY)
    keyboard.row()
    keyboard.add(Text("Расходные материалы"), color=KeyboardButtonColor.PRIMARY)
    keyboard.add(Text("Инструменты"), color=KeyboardButtonColor.PRIMARY)
    keyboard.row()
    keyboard.add(Text("Назад"), color=KeyboardButtonColor.SECONDARY)
    return keyboard

def get_item_transfer_keyboard() -> Keyboard:
    keyboard = Keyboard(one_time=True)
    keyboard.add(Text("Передать предмет"), color=KeyboardButtonColor.POSITIVE)
    keyboard.add(Text("Назад"), color=KeyboardButtonColor.SECONDARY)
    return keyboard

def get_confirmation_keyboard() -> Keyboard:
    keyboard = Keyboard(one_time=True)
    keyboard.add(Text("Подтвердить передачу"), color=KeyboardButtonColor.POSITIVE)
    keyboard.add(Text("Отменить передачу"), color=KeyboardButtonColor.NEGATIVE)
    return keyboard

@expeditor_labeler.message(text="Карта экспедитора")
async def expeditor_menu(m: Message):
    db = Database()
    character = await db.get_approved_expeditor_character(m.from_id)
    
    if character:
        # Формируем сообщение с картой экспедитора
        message = (
            f"📋 Карта Экспедитора\n\n"
            f"👤 Имя: {character.name}\n"
            f"👽 Раса: {character.race.capitalize()}\n"
            f"💼 Профессия: {character.profession.capitalize()}\n\n"
            f"📊 Характеристики:\n"
            f"💪 Сила: {character.base_strength}\n"
            f"⚡ Скорость: {character.base_speed}\n"
            f"🛡️ Выносливость: {character.base_endurance}\n"
            f"🎯 Ловкость: {character.base_dexterity}\n"
            f"👁️ Восприятие: {character.base_perception}\n"
            f"⚡ Реакция: {character.base_reaction}\n"
            f"🧠 Стрессоустойчивость: {character.base_stress_resistance}\n\n"
            f"🎒 Инвентарь:\n"
        )
        
        # Добавляем предметы
        if character.items:
            for item in character.items:
                message += f"• {item.name}\n"
        else:
            message += "Пусто\n"
            
        # Добавляем эффекты
        message += "\n🔮 Эффекты:\n"
        if character.effects:
            for effect in character.effects:
                message += f"• {effect.name}\n"
        else:
            message += "Нет эффектов\n"
            
        # Добавляем статус оплодотворения
        message += f"\n🤰 Статус оплодотворения: {'Оплодотворен' if character.is_fertilized else 'Не оплодотворен'}"
        
        # Создаем клавиатуру для действий
        keyboard = Keyboard(one_time=True)
        available_actions = calculate_available_actions(character)
        
        for i in range(1, available_actions + 1):
            keyboard.add(Text(f"Действие {i}"), color=KeyboardButtonColor.PRIMARY)
            if i % 2 == 0:
                keyboard.row()
        
        await m.answer(message, keyboard=keyboard)
    else:
        await m.answer(
            "Добро пожаловать в систему экспедитора!\n"
            "Выберите действие:",
            keyboard=get_expeditor_keyboard()
        )

@expeditor_labeler.message(text="Создать персонажа")
async def create_character(m: Message):
    db = Database()
    character_count = await db.get_character_count(m.from_id)
    
    if character_count >= 1:
        await m.answer(
            "У вас уже есть персонаж. Вы можете создать нового только после удаления существующего.",
            keyboard=get_expeditor_keyboard()
        )
        return
    
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

@expeditor_labeler.message(text="Мои персонажи")
async def show_characters(m: Message):
    db = Database()
    characters = await db.get_user_characters(m.from_id)
    
    if not characters:
        await m.answer("У вас пока нет персонажей!")
        return
    
    keyboard = Keyboard(one_time=True)
    for character in characters:
        keyboard.add(Text(f"Выбрать {character.name}"), color=KeyboardButtonColor.PRIMARY)
        keyboard.row()
    
    keyboard.add(Text("Управление персонажем"), color=KeyboardButtonColor.SECONDARY)
    keyboard.add(Text("Назад"), color=KeyboardButtonColor.SECONDARY)
    
    await m.answer(
        "Ваши персонажи:\n" + 
        "\n".join([f"{char.name} ({char.race}, {char.profession})" for char in characters]),
        keyboard=keyboard
    )

@expeditor_labeler.message(text="Управление персонажем")
async def manage_character(m: Message):
    await m.answer(
        "Выберите действие:",
        keyboard=get_character_management_keyboard()
    )

@expeditor_labeler.message(text="Удалить персонажа")
async def delete_character(m: Message):
    db = Database()
    character = await db.get_expeditor_character(m.from_id)
    
    if not character:
        await m.answer("У вас нет активного персонажа!")
        return
    
    m.payload = {"action": "delete_character", "character_id": character.id}
    
    keyboard = Keyboard(one_time=True)
    keyboard.add(Text("Сохранить копию"), color=KeyboardButtonColor.POSITIVE)
    keyboard.add(Text("Удалить без копии"), color=KeyboardButtonColor.NEGATIVE)
    keyboard.row()
    keyboard.add(Text("Отмена"), color=KeyboardButtonColor.SECONDARY)
    
    await m.answer(
        "Вы уверены, что хотите удалить персонажа?\n"
        "Вы можете сохранить копию всех данных перед удалением.\n"
        "После удаления персонажа вы сможете создать нового.",
        keyboard=keyboard
    )

@expeditor_labeler.message(text=["Сохранить копию", "Удалить без копии"])
async def confirm_deletion(m: Message):
    keep_copy = m.text == "Сохранить копию"
    character_id = m.payload.get("character_id")
    
    m.payload = {
        "action": "delete_character",
        "character_id": character_id,
        "keep_copy": keep_copy
    }
    
    await m.answer(
        "Пожалуйста, укажите причину удаления персонажа.\n"
        "Ваш запрос будет рассмотрен администраторами."
    )

@expeditor_labeler.message()
async def handle_deletion_reason(m: Message):
    if m.payload.get("action") != "delete_character":
        return
    
    character_id = m.payload.get("character_id")
    keep_copy = m.payload.get("keep_copy", False)
    reason = m.text
    
    db = Database()
    success = await db.create_deletion_request(m.from_id, character_id, reason, keep_copy)
    
    if success:
        await m.answer(
            "Ваш запрос на удаление персонажа отправлен администраторам.\n"
            "Вы получите уведомление, когда запрос будет рассмотрен.",
            keyboard=get_expeditor_keyboard()
        )
    else:
        await m.answer(
            "Произошла ошибка при отправке запроса. Пожалуйста, попробуйте позже.",
            keyboard=get_expeditor_keyboard()
        )

@expeditor_labeler.message(text=lambda text: text.startswith("Выбрать "))
async def select_character(m: Message):
    character_name = m.text.replace("Выбрать ", "")
    db = Database()
    
    character = await db.get_expeditor_character_by_name(m.from_id, character_name)
    if not character:
        await m.answer("Персонаж не найден!")
        return
    
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
async def back_to_form(m: Message):
    keyboard = Keyboard(one_time=True)
    keyboard.add(Text("Форма"), color=KeyboardButtonColor.PRIMARY)
    keyboard.add(Text("Назад"), color=KeyboardButtonColor.SECONDARY)
    
    await m.answer(
        "Возврат к форме:",
        keyboard=keyboard
    )

@expeditor_labeler.message(text="Инвентарь")
async def show_inventory(m: Message):
    db = Database()
    character = await db.get_expeditor_character(m.from_id)
    
    if not character:
        await m.answer("У вас нет активного персонажа!")
        return
    
    items = await db.get_character_items(character.id)
    
    if not items:
        await m.answer(
            "Ваш инвентарь пуст.",
            keyboard=get_inventory_keyboard()
        )
        return
    
    # Группируем предметы по типам
    equipment = [i for i in items if i.item_type == ItemType.EQUIPMENT]
    weapons = [i for i in items if i.item_type == ItemType.WEAPON]
    consumables = [i for i in items if i.item_type == ItemType.CONSUMABLE]
    tools = [i for i in items if i.item_type == ItemType.TOOL]
    
    message = "Ваш инвентарь:\n\n"
    
    if equipment:
        message += "Экипировка:\n"
        for item in equipment:
            message += f"- {item.name}\n"
        message += "\n"
    
    if weapons:
        message += "Вооружение:\n"
        for item in weapons:
            message += f"- {item.name}\n"
        message += "\n"
    
    if consumables:
        message += "Расходные материалы:\n"
        for item in consumables:
            message += f"- {item.name}"
            if item.usage_type == ItemUsageType.MULTI_USE:
                message += f" (Осталось использований: {item.uses_remaining})"
            message += "\n"
        message += "\n"
    
    if tools:
        message += "Инструменты:\n"
        for item in tools:
            message += f"- {item.name}\n"
    
    await m.answer(message, keyboard=get_inventory_keyboard())

@expeditor_labeler.message(text=[
    "Экипировка", "Вооружение", "Расходные материалы", "Инструменты"
])
async def show_item_group(m: Message):
    item_type = {
        "Экипировка": ItemType.EQUIPMENT,
        "Вооружение": ItemType.WEAPON,
        "Расходные материалы": ItemType.CONSUMABLE,
        "Инструменты": ItemType.TOOL
    }[m.text]
    
    db = Database()
    character = await db.get_expeditor_character(m.from_id)
    
    if not character:
        await m.answer("У вас нет активного персонажа!")
        return
    
    items = await db.get_character_items(character.id)
    group_items = [i for i in items if i.item_type == item_type]
    
    if not group_items:
        await m.answer(
            f"У вас нет предметов типа {m.text}.",
            keyboard=get_inventory_keyboard()
        )
        return
    
    keyboard = Keyboard(one_time=True)
    for item in group_items:
        keyboard.add(Text(f"Просмотреть {item.name}"), color=KeyboardButtonColor.PRIMARY)
        keyboard.row()
    
    keyboard.add(Text("Назад"), color=KeyboardButtonColor.SECONDARY)
    
    await m.answer(
        f"Предметы типа {m.text}:",
        keyboard=keyboard
    )

@expeditor_labeler.message(text=lambda text: text.startswith("Просмотреть "))
async def show_item_details(m: Message):
    item_name = m.text.replace("Просмотреть ", "")
    db = Database()
    character = await db.get_expeditor_character(m.from_id)
    
    if not character:
        await m.answer("У вас нет активного персонажа!")
        return
    
    items = await db.get_character_items(character.id)
    item = next((i for i in items if i.name == item_name), None)
    
    if not item:
        await m.answer("Предмет не найден!")
        return
    
    message = (
        f"Название: {item.name}\n"
        f"Описание: {item.description}\n"
        f"Тип: {item.item_type.value}\n"
        f"Использование: {item.usage_type.value}\n"
    )
    
    if item.properties:
        message += "\nСвойства:\n"
        for prop, value in item.properties.items():
            message += f"- {prop}: {value:+d}\n"
    
    if item.usage_type == ItemUsageType.MULTI_USE:
        message += f"\nОсталось использований: {item.uses_remaining}"
    
    keyboard = Keyboard(one_time=True)
    if item.usage_type != ItemUsageType.PERMANENT:
        keyboard.add(Text(f"Использовать {item.name}"), color=KeyboardButtonColor.POSITIVE)
        keyboard.row()
    keyboard.add(Text("Назад"), color=KeyboardButtonColor.SECONDARY)
    
    await m.answer(message, keyboard=keyboard)

@expeditor_labeler.message(text=lambda text: text.startswith("Использовать "))
async def use_item(m: Message):
    item_name = m.text.replace("Использовать ", "")
    db = Database()
    character = await db.get_expeditor_character(m.from_id)
    
    if not character:
        await m.answer("У вас нет активного персонажа!")
        return
    
    items = await db.get_character_items(character.id)
    item = next((i for i in items if i.name == item_name), None)
    
    if not item:
        await m.answer("Предмет не найден!")
        return
    
    if item.usage_type == ItemUsageType.PERMANENT:
        await m.answer("Этот предмет нельзя использовать!")
        return
    
    if item.usage_type == ItemUsageType.MULTI_USE and item.uses_remaining <= 0:
        await m.answer("У предмета закончились использования!")
        return
    
    # Применяем эффекты предмета
    for prop, value in item.properties.items():
        # Здесь должна быть логика применения эффектов
        pass
    
    if item.usage_type == ItemUsageType.SINGLE_USE:
        await db.remove_item_from_character(character.id, item.id)
    elif item.usage_type == ItemUsageType.MULTI_USE:
        await db.update_item_uses(character.id, item.id, item.uses_remaining - 1)
    
    await m.answer(
        f"Предмет {item.name} использован!",
        keyboard=get_inventory_keyboard()
    )

@expeditor_labeler.message(text="Передать предмет")
async def initiate_item_transfer(m: Message):
    db = Database()
    character = await db.get_expeditor_character(m.from_id)
    
    if not character:
        await m.answer("У вас нет активного персонажа!")
        return
    
    items = await db.get_character_items(character.id)
    
    if not items:
        await m.answer("У вас нет предметов для передачи!")
        return
    
    keyboard = Keyboard(one_time=True)
    for item in items:
        keyboard.add(Text(f"Передать {item.name}"), color=KeyboardButtonColor.PRIMARY)
        keyboard.row()
    
    keyboard.add(Text("Назад"), color=KeyboardButtonColor.SECONDARY)
    
    m.payload = {"action": "transfer_item", "step": "select_item"}
    
    await m.answer(
        "Выберите предмет для передачи:",
        keyboard=keyboard
    )

@expeditor_labeler.message(text=lambda text: text.startswith("Передать "))
async def select_recipient(m: Message):
    if m.payload.get("action") != "transfer_item" or m.payload.get("step") != "select_item":
        return
    
    item_name = m.text.replace("Передать ", "")
    db = Database()
    
    character = await db.get_expeditor_character(m.from_id)
    if not character:
        await m.answer("У вас нет активного персонажа!")
        return
    
    items = await db.get_character_items(character.id)
    item = next((i for i in items if i.name == item_name), None)
    
    if not item:
        await m.answer("Предмет не найден!")
        return
    
    # Получаем список активных пользователей
    active_users = await db.get_active_users()
    if not active_users:
        await m.answer("Нет активных пользователей для передачи!")
        return
    
    keyboard = Keyboard(one_time=True)
    for user in active_users:
        if user.id != m.from_id:  # Исключаем текущего пользователя
            keyboard.add(Text(f"Передать {item_name} {user.name}"), color=KeyboardButtonColor.PRIMARY)
            keyboard.row()
    
    keyboard.add(Text("Назад"), color=KeyboardButtonColor.SECONDARY)
    
    m.payload = {
        "action": "transfer_item",
        "step": "select_recipient",
        "item_id": item.id,
        "item_name": item_name
    }
    
    await m.answer(
        "Выберите получателя:",
        keyboard=keyboard
    )

@expeditor_labeler.message(text=lambda text: text.startswith("Передать ") and " " in text)
async def confirm_transfer(m: Message):
    if m.payload.get("action") != "transfer_item" or m.payload.get("step") != "select_recipient":
        return
    
    parts = m.text.split(" ")
    item_name = parts[1]
    recipient_name = " ".join(parts[2:])
    
    db = Database()
    
    # Получаем информацию о получателе
    recipient = await db.get_user_by_name(recipient_name)
    if not recipient:
        await m.answer("Получатель не найден!")
        return
    
    recipient_character = await db.get_expeditor_character(recipient.id)
    if not recipient_character:
        await m.answer("У получателя нет активного персонажа!")
        return
    
    # Проверяем, есть ли предмет у отправителя
    sender_character = await db.get_expeditor_character(m.from_id)
    if not sender_character:
        await m.answer("У вас нет активного персонажа!")
        return
    
    item_id = m.payload.get("item_id")
    
    # Проверяем, есть ли предмет в инвентаре отправителя
    sender_items = await db.get_character_items(sender_character.id)
    if not any(item.id == item_id for item in sender_items):
        await m.answer("У вас нет этого предмета!")
        return
    
    m.payload = {
        "action": "transfer_item",
        "step": "confirm",
        "item_id": item_id,
        "item_name": item_name,
        "recipient_id": recipient.id,
        "recipient_name": recipient_name,
        "sender_name": sender_character.name,
        "recipient_character_name": recipient_character.name
    }
    
    await m.answer(
        f"Вы собираетесь передать предмет {item_name} персонажу {recipient_character.name}.\n"
        f"Подтвердите передачу:",
        keyboard=get_confirmation_keyboard()
    )

@expeditor_labeler.message(text="Подтвердить передачу")
async def process_item_transfer(m: Message):
    if m.payload.get("action") != "transfer_item" or m.payload.get("step") != "confirm":
        return
    
    db = Database()
    
    item_id = m.payload.get("item_id")
    item_name = m.payload.get("item_name")
    recipient_id = m.payload.get("recipient_id")
    recipient_name = m.payload.get("recipient_name")
    sender_name = m.payload.get("sender_name")
    recipient_character_name = m.payload.get("recipient_character_name")
    
    # Проверяем, есть ли предмет у отправителя
    sender_character = await db.get_expeditor_character(m.from_id)
    if not sender_character:
        await m.answer("У вас нет активного персонажа!")
        return
    
    # Проверяем, есть ли предмет в инвентаре отправителя
    sender_items = await db.get_character_items(sender_character.id)
    if not any(item.id == item_id for item in sender_items):
        await m.answer("У вас нет этого предмета!")
        return
    
    # Передаем предмет
    success = await db.transfer_item(sender_character.id, recipient_id, item_id)
    
    if success:
        # Уведомляем отправителя
        await m.answer(
            f"Вы передали предмет {item_name} персонажу {recipient_character_name}!",
            keyboard=get_inventory_keyboard()
        )
        
        # Уведомляем получателя
        try:
            await m.ctx_api.messages.send(
                user_id=recipient_id,
                message=f"Персонаж {sender_name} передал вам предмет {item_name}!",
                random_id=0
            )
        except Exception as e:
            print(f"Error sending notification to recipient: {e}")
    else:
        await m.answer(
            "Произошла ошибка при передаче предмета!",
            keyboard=get_inventory_keyboard()
        )

@expeditor_labeler.message(text="Отменить передачу")
async def cancel_transfer(m: Message):
    if m.payload.get("action") != "transfer_item" or m.payload.get("step") != "confirm":
        return
    
    await m.answer(
        "Передача предмета отменена.",
        keyboard=get_inventory_keyboard()
    ) 