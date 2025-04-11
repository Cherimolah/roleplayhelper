"""
Механики системы экспедитора
"""
import random
import math
from typing import Dict, List, Optional, Union
from .models import Character, Item, Effect, ActionMode, Consequence

def generate_characteristics(race: str, profession: str) -> Dict[str, int]:
    """
    Генерирует характеристики персонажа на основе расы и профессии
    
    Args:
        race: Раса персонажа
        profession: Профессия персонажа
        
    Returns:
        Dict[str, int]: Словарь с характеристиками персонажа
    """
    # Базовые характеристики
    base_characteristics = {
        "base_strength": 50,
        "base_speed": 50,
        "base_endurance": 50,
        "base_dexterity": 50,
        "base_perception": 50,
        "base_reaction": 50,
        "base_stress_resistance": 50
    }
    
    # Модификаторы расы
    race_modifiers = {
        "человек": {
            "strength": 0,
            "speed": 0,
            "endurance": 0,
            "dexterity": 0,
            "perception": 0,
            "reaction": 0,
            "stress_resistance": 0
        },
        "ксенос": {
            "strength": -5,
            "speed": 0,
            "endurance": 0,
            "dexterity": 0,
            "perception": 10,
            "reaction": 5,
            "stress_resistance": 0
        },
        "мутант": {
            "strength": 10,
            "speed": 0,
            "endurance": 10,
            "dexterity": 0,
            "perception": 0,
            "reaction": 0,
            "stress_resistance": -10
        },
        "робот": {
            "strength": 15,
            "speed": 0,
            "endurance": 15,
            "dexterity": 0,
            "perception": -10,
            "reaction": 0,
            "stress_resistance": -20
        }
    }
    
    # Модификаторы профессии
    profession_modifiers = {
        "горничные": {
            "strength": 0,
            "speed": 0,
            "endurance": 10,
            "dexterity": 0,
            "perception": 10,
            "reaction": 0,
            "stress_resistance": 5
        },
        "инженеры-техники": {
            "strength": 10,
            "speed": 0,
            "endurance": 0,
            "dexterity": 0,
            "perception": 10,
            "reaction": 5,
            "stress_resistance": 0
        },
        "медицинские сотрудники": {
            "strength": 0,
            "speed": 0,
            "endurance": 0,
            "dexterity": 10,
            "perception": 10,
            "reaction": 0,
            "stress_resistance": 5
        },
        "лаборанты": {
            "strength": 0,
            "speed": 0,
            "endurance": 0,
            "dexterity": 10,
            "perception": 15,
            "reaction": 0,
            "stress_resistance": 0
        },
        "сотрудники службы безопасности": {
            "strength": 10,
            "speed": 5,
            "endurance": 10,
            "dexterity": 5,
            "perception": 5,
            "reaction": 10,
            "stress_resistance": 10
        },
        "администраторы ресепшена": {
            "strength": 0,
            "speed": 0,
            "endurance": 0,
            "dexterity": 5,
            "perception": 10,
            "reaction": 5,
            "stress_resistance": 5
        },
        "системные администраторы": {
            "strength": 0,
            "speed": 0,
            "endurance": 0,
            "dexterity": 10,
            "perception": 15,
            "reaction": 5,
            "stress_resistance": 0
        },
        "врачи": {
            "strength": 0,
            "speed": 0,
            "endurance": 0,
            "dexterity": 15,
            "perception": 15,
            "reaction": 0,
            "stress_resistance": 5
        },
        "юридический консультант/бухгалтер": {
            "strength": 0,
            "speed": 0,
            "endurance": 0,
            "dexterity": 5,
            "perception": 10,
            "reaction": 5,
            "stress_resistance": 5
        },
        "учёный": {
            "strength": 0,
            "speed": 0,
            "endurance": 0,
            "dexterity": 5,
            "perception": 15,
            "reaction": 0,
            "stress_resistance": 0
        },
        "глава медицинского блока": {
            "strength": 0,
            "speed": 0,
            "endurance": 0,
            "dexterity": 15,
            "perception": 15,
            "reaction": 5,
            "stress_resistance": 10
        },
        "метрдотель жилого блока": {
            "strength": 0,
            "speed": 0,
            "endurance": 5,
            "dexterity": 10,
            "perception": 10,
            "reaction": 5,
            "stress_resistance": 10
        },
        "начальник службы безопасности": {
            "strength": 10,
            "speed": 5,
            "endurance": 10,
            "dexterity": 10,
            "perception": 10,
            "reaction": 10,
            "stress_resistance": 15
        },
        "главный инженер": {
            "strength": 10,
            "speed": 0,
            "endurance": 5,
            "dexterity": 10,
            "perception": 15,
            "reaction": 10,
            "stress_resistance": 5
        },
        "глава научно-исследовательского блока": {
            "strength": 0,
            "speed": 0,
            "endurance": 0,
            "dexterity": 10,
            "perception": 15,
            "reaction": 5,
            "stress_resistance": 5
        },
        "управляющий станцией rg-98": {
            "strength": 5,
            "speed": 5,
            "endurance": 5,
            "dexterity": 10,
            "perception": 15,
            "reaction": 10,
            "stress_resistance": 15
        }
    }
    
    # Применяем модификаторы
    final_characteristics = base_characteristics.copy()
    race_mod = race_modifiers.get(race.lower(), {})
    prof_mod = profession_modifiers.get(profession.lower(), {})
    
    for char in final_characteristics:
        base_char = char.replace("base_", "")
        final_characteristics[char] += race_mod.get(base_char, 0) + prof_mod.get(base_char, 0)
    
    return final_characteristics

def calculate_available_actions(character: Character) -> int:
    """
    Рассчитывает количество доступных действий за ход
    
    Args:
        character: Объект персонажа
        
    Returns:
        int: Количество доступных действий (максимум 5)
    """
    return min(5, 1 + (character.speed // 50))

def perform_check(character: Character, characteristic: str, difficulty: str, 
                 bonus: Optional[str] = None, penalty: Optional[str] = None,
                 action_number: int = 1) -> tuple[bool, str]:
    """
    Выполняет проверку характеристики персонажа
    
    Args:
        character: Объект персонажа
        characteristic: Название характеристики
        difficulty: Сложность проверки
        bonus: Бонус к проверке
        penalty: Штраф к проверке
        action_number: Номер действия в текущем ходу (начиная с 1)
        
    Returns:
        tuple[bool, str]: Результат проверки и описание результата
    """
    # Получаем значение характеристики
    char_value = getattr(character, characteristic, 0)
    
    # Определяем сложность
    difficulty_modifiers = {
        "Легкая": 1.2,  # +20%
        "Нормальная": 1.0,  # 0%
        "Сложная": 0.8,  # -20%
        "Очень сложная": 0.6,  # -40%
        "Невозможная": 0.4  # -60%
    }
    
    # Определяем бонусы и штрафы
    bonus_modifiers = {
        "Отсутствует": 0,
        "Низкий": 5,
        "Обычный": 10,
        "Высокий": 20,
        "Очень высокий": 40
    }
    
    penalty_modifiers = {
        "Отсутствует": 0,
        "Низкий": -5,
        "Обычный": -10,
        "Высокий": -20,
        "Очень высокий": -40
    }
    
    # Применяем модификаторы
    final_value = char_value
    final_value += bonus_modifiers.get(bonus, 0)
    final_value += penalty_modifiers.get(penalty, 0)
    
    # Применяем базовую сложность
    final_value = int(final_value * difficulty_modifiers.get(difficulty, 1.0))
    
    # Получаем количество доступных действий
    available_actions = calculate_available_actions(character)
    
    # Учитываем номер действия
    if action_number > 1:
        if available_actions == 5:  # Если доступно 5 действий
            if action_number == 4:  # Четвертое действие всегда "Сложное"
                final_value = int(final_value * difficulty_modifiers["Сложная"])
            elif action_number == 5:  # Пятое действие всегда "Очень сложное"
                final_value = int(final_value * difficulty_modifiers["Очень сложная"])
            else:
                # Для второго и третьего действия увеличиваем сложность на один уровень
                difficulty_levels = ["Нормальная", "Сложная", "Очень сложная", "Невозможная"]
                current_difficulty_index = difficulty_levels.index(difficulty) if difficulty in difficulty_levels else 1
                new_difficulty_index = min(current_difficulty_index + (action_number - 1), len(difficulty_levels) - 1)
                new_difficulty = difficulty_levels[new_difficulty_index]
                final_value = int(final_value * difficulty_modifiers.get(new_difficulty, 1.0))
        else:  # Если доступно меньше 5 действий
            if action_number > available_actions:
                # Если действие превышает доступный лимит, начинаем со "Сложной" и увеличиваем дальше
                difficulty_levels = ["Сложная", "Очень сложная", "Невозможная"]
                # Увеличиваем сложность на количество превышений лимита минус 1 (так как начинаем со "Сложной")
                new_difficulty_index = min(action_number - available_actions - 1, len(difficulty_levels) - 1)
                new_difficulty = difficulty_levels[new_difficulty_index]
                final_value = int(final_value * difficulty_modifiers.get(new_difficulty, 1.0))
            else:
                # Для действий в пределах лимита применяем обычную прогрессию сложности
                difficulty_levels = ["Нормальная", "Сложная", "Очень сложная", "Невозможная"]
                current_difficulty_index = difficulty_levels.index(difficulty) if difficulty in difficulty_levels else 1
                new_difficulty_index = min(current_difficulty_index + (action_number - 1), len(difficulty_levels) - 1)
                new_difficulty = difficulty_levels[new_difficulty_index]
                final_value = int(final_value * difficulty_modifiers.get(new_difficulty, 1.0))
    
    # Выполняем проверку
    roll = random.randint(1, 100)

    # Определяем результат
    if roll <= final_value:
        if roll <= final_value * 0.2:  # Критический успех
        return True, "Критический успех"
        return True, "Успех"
    else:
        if roll >= 95:  # Критический провал
            return False, "Критический провал"
        return False, "Провал"

def calculate_initiative(character: Character) -> int:
    """
    Рассчитывает инициативу персонажа
    
    Args:
        character: Объект персонажа
        
    Returns:
        int: Значение инициативы
    """
    return (character.speed + character.reaction) // 2

def apply_consequence(character: Character, consequence: Consequence) -> None:
    """
    Применяет последствие к персонажу
    
    Args:
        character: Объект персонажа
        consequence: Объект последствия
    """
    if consequence.type == "Получение Травмы":
        character.injuries.append(consequence)
    elif consequence.type == "Лечение Травмы":
        character.injuries = [i for i in character.injuries if i.name != consequence.name]
    elif consequence.type == "Получение Психоза":
        character.madness.append(consequence)
    elif consequence.type == "Лечение Психоза":
        character.madness = [m for m in character.madness if m.name != consequence.name]
    elif consequence.type == "Повышение Либидо":
        character.libido += consequence.value
    elif consequence.type == "Понижение Либидо":
        character.libido -= consequence.value
    elif consequence.type == "Повышение Подчинения":
        character.submission += consequence.value
    elif consequence.type == "Понижение Подчинения":
        character.submission -= consequence.value
    elif consequence.type == "Оплодотворение":
        character.impregnation = consequence
    elif consequence.type == "Снятие Оплодотворения":
        character.impregnation = None