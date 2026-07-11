"""
Утилитарные функции модификации текста для дебаффов POV-режима.

Каждый эффект — чистая функция text -> str. Новые эффекты добавляются сюда же
по той же сигнатуре и регистрируются в EFFECTS, чтобы их можно было применять
по строковому ключу (см. service/db_engine.StateDebuff.pov_effect).
"""
import re
import random

DIALOG_LINE_RE = re.compile(r'^\s*[-—]\s*')
DIALOG_CONTENT_RE = re.compile(r'^\s*[-—]\s*(.*)$')


def is_dialog_line(line: str) -> bool:
    """Прямая речь: строка с новой строки, начинающаяся с дефиса/тире."""
    return bool(DIALOG_LINE_RE.match(line.strip()))


def limited_visibility(text: str, level: float = 0.5) -> str:
    """Ограниченная видимость: замазывает случайные части слов, не трогая прямую речь."""
    lines = text.split('\n')
    processed_lines = []
    for line in lines:
        stripped_line = line.strip()
        if re.match(r'^\s*[-—]\s*', stripped_line):
            processed_lines.append(line)
        else:
            words = line.split()
            blurred_words = []
            for word in words:
                if random.random() < level:
                    chunk_size = random.randint(1, len(word))
                    start = random.randint(0, len(word) - chunk_size)
                    blurred = word[:start] + '*' * chunk_size + word[start + chunk_size:]
                else:
                    blurred = word
                blurred_words.append(blurred)
            processed_lines.append(' '.join(blurred_words))
    return '\n'.join(processed_lines)


def concussion(text: str) -> str:
    """Контузия: полностью перемешивает буквы внутри каждого слова."""
    words = text.split()
    randomized_words = []
    for word in words:
        if len(word) > 1:
            chars = list(word)
            random.shuffle(chars)
            randomized_words.append(''.join(chars))
        else:
            randomized_words.append(word)
    return ' '.join(randomized_words)


def blindness(text: str) -> str:
    """Слепота: остаётся только прямая речь с новой строки и дефиса/тире."""
    quotes = re.findall(r'^\s*[-—]\s*(.*)$', text, re.MULTILINE)
    return '\n'.join(quotes) if quotes else "Вы ничего не видите."


def deafness(text: str) -> str:
    """Глухота: замазывает звёздочками всю прямую речь, сохраняя структуру строк."""
    def replace_match(match):
        content = match.group(1)
        return match.group(0).replace(content, '*' * len(content))
    return re.sub(r'^\s*[-—]\s*(.*)$', replace_match, text, flags=re.MULTILINE).strip()


# Реестр эффектов по строковому ключу — используется, чтобы дебафы карты
# экспедитора (StateDebuff.pov_effect) могли ссылаться на эффект по имени,
# не зная о его реализации. Добавление нового эффекта = новая функция выше +
# запись здесь.
EFFECTS = {
    'limited_visibility': limited_visibility,
    'concussion': concussion,
    'blindness': blindness,
    'deafness': deafness,
}


def apply_effect(name: str, text: str, **kwargs) -> str:
    """Применяет эффект по имени из EFFECTS. Если имя неизвестно — возвращает текст без изменений."""
    effect = EFFECTS.get(name)
    if not effect:
        return text
    return effect(text, **kwargs)
