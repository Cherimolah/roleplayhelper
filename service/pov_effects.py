"""
Модуль текстовых эффектов для режима «От первого лица» (POV).

Эффекты применяются к пересылаемым через юзербота сообщениям в зависимости
от наложенных на игрока дебаффов:
  - limited_visibility  — «Ограниченная видимость»
  - concussion          — «Контузия»
  - blindness           — «Слепота»
  - deafness            — «Глухота»
  - stealth             — «Режим скрытности» (не фильтрует текст, а перехватывает)
"""

import re
import random

# Регулярка для прямой речи: строки, начинающиеся с "- " или "— "
_SPEECH_RE = re.compile(r'^\s*[-—]\s*(.*)$', re.MULTILINE)

# Минимальное количество символов (без пробелов) для пересылки сообщения в POV-режиме
POV_MIN_CHARS = 300

# Команды бота в квадратных скобках
_COMMAND_RE = re.compile(r'^\[.+\]$')


def _is_only_commands(text: str) -> bool:
    """
    Возвращает True, если текст состоит только из команд бота вида [команда],
    и не содержит никаких других слов.
    """
    words = text.split()
    return all(_COMMAND_RE.match(w) for w in words) if words else True


def _has_repeated_words(text: str, threshold: float = 0.7) -> bool:
    """
    Возвращает True, если в тексте доля повторяющихся слов превышает порог.
    Используется для защиты от спама.
    """
    words = re.findall(r'\w+', text.lower())
    if not words:
        return False
    unique = set(words)
    return len(unique) / len(words) < (1 - threshold)


def is_valid_pov_message(text: str) -> bool:
    """
    Проверяет, подходит ли сообщение для пересылки в POV-режиме.

    Правила:
    1. Не менее 300 символов без пробелов.
    2. Не состоит только из команд бота.
    3. Не состоит из одних и тех же повторяющихся слов.
    """
    text_no_spaces = text.replace(' ', '').replace('\n', '')
    if len(text_no_spaces) < POV_MIN_CHARS:
        return False
    if _is_only_commands(text):
        return False
    if _has_repeated_words(text):
        return False
    return True


# ─── Текстовые эффекты ────────────────────────────────────────────────────────

def apply_limited_visibility(text: str, level: float = 0.5) -> str:
    """
    «Ограниченная видимость»: случайные куски текста замазываются символом *,
    кроме прямой речи (строки, начинающиеся с «- » или «— »).

    level: от 0.0 (ничего не замазано) до 1.0 (всё, кроме речи).
    """
    lines = text.split('\n')
    result = []
    for line in lines:
        stripped = line.strip()
        # Прямую речь не трогаем
        if re.match(r'^\s*[-—]\s*', stripped):
            result.append(line)
        else:
            words = line.split()
            blurred = []
            for word in words:
                if random.random() < level:
                    chunk = random.randint(1, max(1, len(word)))
                    start = random.randint(0, max(0, len(word) - chunk))
                    blurred.append(word[:start] + '*' * chunk + word[start + chunk:])
                else:
                    blurred.append(word)
            result.append(' '.join(blurred))
    return '\n'.join(result)


def apply_concussion(text: str) -> str:
    """
    «Контузия»: полностью рандомизируем (перемешиваем) буквы в каждом слове,
    включая первую и последнюю.
    """
    words = text.split()
    randomized = []
    for word in words:
        if len(word) > 1:
            chars = list(word)
            random.shuffle(chars)
            randomized.append(''.join(chars))
        else:
            randomized.append(word)
    return ' '.join(randomized)


def apply_blindness(text: str) -> str:
    """
    «Слепота»: оставляем только прямую речь (строки начинающиеся с «- » / «— »).
    Если речи нет — «Вы ничего не видите.»
    """
    quotes = re.findall(r'^\s*[-—]\s*(.*)$', text, re.MULTILINE)
    if quotes:
        return '\n'.join(f'— {q}' for q in quotes)
    return 'Вы ничего не видите.'


def apply_deafness(text: str) -> str:
    """
    «Глухота»: прямая речь замазывается символами *, нарратив остаётся.
    """
    def blur_match(m: re.Match) -> str:
        leader = m.group(0).replace(m.group(1), '')  # «— » или «- »
        content = m.group(1)
        return leader + '*' * len(content)

    return re.sub(r'^\s*[-—]\s*(.*)$', blur_match, text, flags=re.MULTILINE).strip()


def apply_effect(text: str, effect_name: str, **kwargs) -> str:
    """
    Применяет указанный эффект к тексту.

    effect_name: 'limited_visibility' | 'concussion' | 'blindness' | 'deafness'
    """
    effects = {
        'limited_visibility': apply_limited_visibility,
        'concussion': apply_concussion,
        'blindness': apply_blindness,
        'deafness': apply_deafness,
    }
    fn = effects.get(effect_name)
    if fn is None:
        return text
    return fn(text, **kwargs) if effect_name == 'limited_visibility' else fn(text)
