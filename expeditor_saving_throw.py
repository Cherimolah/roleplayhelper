"""
Модуль для механики соревновательного спас-броска
"""
from dataclasses import dataclass
from typing import List, Optional, Dict, Union
from enum import Enum
import random

class Difficulty(Enum):
    VERY_EASY = 1.2  # +20%
    NORMAL = 1.0     # без изменений
    HARD = 0.8       # -20%
    VERY_HARD = 0.6  # -40%

class SavingThrowType(Enum):
    VS_CHARACTER = "Против персонажа"
    VS_THREAT = "Против угрозы"

@dataclass
class Participant:
    name: str
    characteristic: str
    value: int
    bonuses: Dict[str, int]  # {item_type: bonus}
    penalties: Dict[str, int]  # {effect_type: penalty}
    judge_bonus: int = 0
    judge_penalty: int = 0

@dataclass
class Threat:
    name: str
    characteristic: str
    value: int
    judge_bonus: int = 0
    judge_penalty: int = 0

@dataclass
class SavingThrowResult:
    participant_name: str
    target_percentage: float
    roll: int
    final_result: float
    success_level: str  # "Критический успех", "Успех", "Провал", "Критический провал"

class SavingThrow:
    def __init__(self, participants: List[Union[Participant, Threat]], difficulty: Difficulty, 
                 saving_throw_type: SavingThrowType, judge_bonus: int = 0, judge_penalty: int = 0):
        self.participants = participants
        self.difficulty = difficulty
        self.saving_throw_type = saving_throw_type
        self.judge_bonus = judge_bonus
        self.judge_penalty = judge_penalty
        self.results: List[SavingThrowResult] = []

    def calculate_target_percentage(self, participant: Union[Participant, Threat]) -> float:
        # Базовое значение характеристики
        base_value = participant.value

        # Суммируем бонусы от предметов
        item_bonus = sum(participant.bonuses.values()) if isinstance(participant, Participant) else 0

        # Суммируем штрафы от эффектов
        effect_penalty = sum(participant.penalties.values()) if isinstance(participant, Participant) else 0

        # Применяем бонусы и штрафы судьи
        total = (base_value + item_bonus + participant.judge_bonus - 
                effect_penalty - participant.judge_penalty)

        # Применяем сложность
        return total * self.difficulty.value

    def perform_roll(self) -> None:
        self.results = []
        for participant in self.participants:
            target_percentage = self.calculate_target_percentage(participant)
            roll = random.randint(1, 100)
            final_result = target_percentage - roll

            # Определяем уровень успеха
            if roll >= 95:
                success_level = "Критический провал"
            elif final_result <= 0:
                success_level = "Провал"
            elif final_result >= target_percentage * 0.8:
                success_level = "Критический успех"
            else:
                success_level = "Успех"

            self.results.append(SavingThrowResult(
                participant_name=participant.name,
                target_percentage=target_percentage,
                roll=roll,
                final_result=final_result,
                success_level=success_level
            ))

    def get_winner(self) -> Optional[str]:
        if not self.results:
            return None

        # Сортируем результаты по final_result в убывающем порядке
        sorted_results = sorted(self.results, key=lambda x: x.final_result, reverse=True)

        # Проверяем на ничью (разница <= 5)
        if len(sorted_results) > 1 and (sorted_results[0].final_result - sorted_results[1].final_result) <= 5:
            return None  # Ничья

        return sorted_results[0].participant_name

    def get_success_level(self, participant_name: str) -> Optional[str]:
        for result in self.results:
            if result.participant_name == participant_name:
                return result.success_level
        return None

    def get_participant_result(self, participant_name: str) -> Optional[SavingThrowResult]:
        for result in self.results:
            if result.participant_name == participant_name:
                return result
        return None

    def format_results(self) -> str:
        result_text = "Результаты спас-броска:\n\n"
        
        for result in self.results:
            result_text += (
                f"{result.participant_name}:\n"
                f"Целевое значение: {result.target_percentage:.1f}\n"
                f"Бросок: {result.roll}\n"
                f"Результат: {result.final_result:.1f}\n"
                f"Уровень успеха: {result.success_level}\n\n"
            )

        winner = self.get_winner()
        if winner:
            result_text += f"Победитель: {winner}\n"
        else:
            result_text += "Ничья!\n"

        return result_text 