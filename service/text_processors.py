import re
import random
from typing import Optional

def limited_visibility(text: str, level: float = 0.5) -> str:
    """
    Ограниченная видимость: замазываем случайные куски текста (*), кроме прямой речи
    level: степень замазывания (0.0 - ничего, 1.0 - всё замазано, кроме речи)
    """
    lines = text.split('\n')
    processed_lines = []
    
    for line in lines:
        stripped_line = line.strip()
        # Это прямая речь (начинается с - или ---) - не трогаем
        if re.match(r'^\s*[-]{1,}\s*', stripped_line):
            processed_lines.append(line)
        else:  # Нарратив: замазываем случайные куски
            words = line.split()
            blurred_words = []
            for word in words:
                if random.random() < level:  # С вероятностью level замазываем слово
                    chunk_size = random.randint(1, len(word))
                    start = random.randint(0, len(word) - chunk_size)
                    blurred = word[:start] + '*' * chunk_size + word[start + chunk_size:]
                    blurred_words.append(blurred)
                else:
                    blurred_words.append(word)
            processed_lines.append(' '.join(blurred_words))
    
    return '\n'.join(processed_lines)

def concussion(text: str) -> str:
    """Контузия: перемешивает буквы в словах"""
    words = text.split()
    randomized_words = []
    
    for word in words:
        if len(word) > 1:
            chars = list(word)
            random.shuffle(chars)
            randomized_word = ''.join(chars)
            randomized_words.append(randomized_word)
        else:
            randomized_words.append(word)
    
    return ' '.join(randomized_words)

def blindness(text: str) -> str:
    """Слепота: оставляет только прямую речь"""
    quotes = re.findall(r'^\s*[-]{1,}\s*(.*)$', text, re.MULTILINE)
    if quotes:
        return '\n'.join(quotes)
    return "Вы ничего не видите."

def deafness(text: str) -> str:
    """Глухота: замазывает прямую речь"""
    def replace_match(match):
        content = match.group(1)
        blurred = '*' * len(content)
        return match.group(0).replace(content, blurred)
    
    cleaned_text = re.sub(r'^\s*[-]{1,}\s*(.*)$', replace_match, text, flags=re.MULTILINE)
    return cleaned_text.strip()

def apply_text_effects(text: str, user_id: int, db) -> str:
    """Применяет все активные эффекты к тексту"""
    # Получаем информацию о режиме пользователя
    mode = await db.FirstPersonMode.query.where(
        db.FirstPersonMode.user_id == user_id
    ).gino.first()
    
    if not mode or not mode.is_active:
        return text
    
    # Применяем эффекты в порядке важности
    if mode.blindness_until and mode.blindness_until > datetime.now():
        text = blindness(text)
    
    if mode.concussion_until and mode.concussion_until > datetime.now():
        text = concussion(text)
    
    if mode.deafness_until and mode.deafness_until > datetime.now():
        text = deafness(text)
    
    if mode.limited_vision_until and mode.limited_vision_until > datetime.now():
        text = limited_visibility(text)
    
    return text

def check_message_length(text: str, min_chars: int = 300) -> bool:
    """
    Проверяет длину сообщения для режима от первого лица
    Убирает команды бота, повторяющиеся слова и пробелы
    """
    # Убираем команды бота (начинаются с /)
    lines = text.split('\n')
    filtered_lines = []
    for line in lines:
        if not line.strip().startswith('/'):
            filtered_lines.append(line)
    text = '\n'.join(filtered_lines)
    
    # Убираем пробелы
    text_no_spaces = ''.join(text.split())
    
    # Убираем повторяющиеся слова
    words = text.split()
    unique_words = []
    seen_words = set()
    for word in words:
        if word.lower() not in seen_words:
            seen_words.add(word.lower())
            unique_words.append(word)
    
    unique_text = ' '.join(unique_words)
    unique_text_no_spaces = ''.join(unique_text.split())
    
    # Проверяем длину
    return len(unique_text_no_spaces) >= min_chars
