import re
import random
from typing import Optional

def limited_visibility(text: str, min_level: float = 0.3, max_level: float = 0.8) -> str:
    """
    Ограниченная видимость с рандомным уровнем замазывания для каждого сообщения
    """
    # Генерируем случайный уровень для этого сообщения
    level = random.uniform(min_level, max_level)
    
    lines = text.split('\n')
    processed_lines = []
    
    for line in lines:
        stripped_line = line.strip()
        # Это прямая речь - не трогаем
        if re.match(r'^\s*[-]{1,}\s*', stripped_line):
            processed_lines.append(line)
        else:
            words = line.split()
            blurred_words = []
            for word in words:
                if random.random() < level:
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

def disorientation(text: str, remove_sender: bool = True) -> str:
    """
    Дезориентация: 
    1. Удаляет информацию об отправителе (если remove_sender=True)
    2. Перемешивает строки текста
    3. Добавляет случайные помехи
    """
    # Разбиваем текст на строки
    lines = text.split('\n')
    
    # Удаляем строки с упоминанием отправителя
    if remove_sender:
        lines = [line for line in lines if not any(
            marker in line.lower() for marker in ['от ', 'от:', '@', 'отправитель']
        )]
    
    # Перемешиваем строки (кроме прямой речи)
    speech_lines = []
    other_lines = []
    
    for line in lines:
        if re.match(r'^\s*[-]{1,}\s*', line.strip()):
            speech_lines.append(line)
        else:
            other_lines.append(line)
    
    # Перемешиваем не-речь
    random.shuffle(other_lines)
    
    # Собираем обратно, сохраняя относительный порядок речи
    result_lines = []
    for line in lines:
        if re.match(r'^\s*[-]{1,}\s*', line.strip()):
            # Оставляем речь на месте
            result_lines.append(line)
        elif other_lines:
            # Берем следующую перемешанную строку
            result_lines.append(other_lines.pop(0))
    
    # Добавляем помехи
    disturbances = [
        "??",
        "...",
        "Что?..",
        "Неразборчиво.",
        "Шум на частоте.",
        "Связь прерывается.",
    ]
    
    if random.random() < 0.3:  # 30% шанс добавить помеху
        disturbance = random.choice(disturbances)
        insert_pos = random.randint(0, len(result_lines))
        result_lines.insert(insert_pos, disturbance)
    
    return '\n'.join(result_lines)

async def apply_text_effects(text: str, user_id: int, db, is_action_mode: bool = False) -> Dict:
    """
    Применяет все активные эффекты к тексту
    Возвращает словарь с обработанным текстом и флагами эффектов
    """
    result = {
        'text': text,
        'effects': [],
        'remove_sender': False,
        'disoriented': False
    }
    
    # Получаем информацию о режиме пользователя
    mode = await db.FirstPersonMode.query.where(
        db.FirstPersonMode.user_id == user_id
    ).gino.first()
    
    if not mode or not mode.is_active:
        return result
    
    # Применяем эффекты в порядке важности
    if mode.blindness_until and mode.blindness_until > datetime.now():
        result['text'] = blindness(result['text'])
        result['effects'].append('blindness')
    
    if hasattr(mode, 'disorientation_until') and mode.disorientation_until and mode.disorientation_until > datetime.now():
        result['text'] = disorientation(result['text'], remove_sender=True)
        result['effects'].append('disorientation')
        result['remove_sender'] = True
        result['disoriented'] = True
    
    if mode.concussion_until and mode.concussion_until > datetime.now():
        result['text'] = concussion(result['text'])
        result['effects'].append('concussion')
    
    if mode.deafness_until and mode.deafness_until > datetime.now():
        result['text'] = deafness(result['text'])
        result['effects'].append('deafness')
    
    if mode.limited_vision_until and mode.limited_vision_until > datetime.now():
        # Используем рандомизированный уровень
        result['text'] = limited_visibility(result['text'], min_level=0.2, max_level=0.9)
        result['effects'].append('limited_vision')
    
    return result
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
