expeditor/models.py

from dataclasses import dataclass
from typing import List, Dict, Optional
from enum import Enum

class ItemType(Enum):
    EQUIPMENT = "Экипировка"
    WEAPON = "Вооружение"
    CONSUMABLE = "Расходный материал"
    TOOL = "Инструмент"

class ItemUsageType(Enum):
    PERMANENT = "Постоянный"
    SINGLE_USE = "Одноразовый"
    MULTI_USE = "Многоразовый"

@dataclass
class Item:
    id: int
    name: str
    description: str
    item_type: ItemType
    usage_type: ItemUsageType
    properties: Dict[str, int]  # Характеристики и их модификаторы
    image_url: Optional[str] = None
    uses_remaining: Optional[int] = None
    price: Optional[int] = None
    available_in_shop: bool = False
    required_faction: Optional[str] = None
    required_reputation: Optional[int] = None

@dataclass
class Effect:
    id: int
    name: str
    description: str
    duration: int
    modifiers: Dict[str, int]

@dataclass
class Character:
    id: int
    user_id: int
    name: str
    race: str
    profession: str
    base_strength: int
    base_speed: int
    base_endurance: int
    base_dexterity: int
    base_perception: int
    base_reaction: int
    base_stress_resistance: int
    is_fertilized: bool = False
    inventory: List[Item] = None
    effects: List[Effect] = None

@dataclass
class ActionMode:
    active: bool
    judge_id: Optional[int]
    participants: List[int]  # Список ID участников
    initiative_order: List[Dict[int, int]]  # {user_id: initiative}

@dataclass
class Consequence:
    type: str  # Тип последствия (например, "Получение Травмы", "Повышение Либидо")
    details: Dict  # Детали (например, {"characteristic": "speed", "penalty": 10})