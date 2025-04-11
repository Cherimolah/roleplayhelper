import psycopg2
from psycopg2.extras import RealDictCursor
from config import DB_HOST, DB_PORT, DB_USER, DB_NAME, DB_PASS
import json
from typing import Optional, Dict, List

class Database:
    def __init__(self):
        self.conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            database=DB_NAME,
            password=DB_PASS
        )
        self.cursor = self.conn.cursor(cursor_factory=RealDictCursor)
        self.create_tables()

    def create_tables(self):
        # Основная таблица персонажей
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS expeditor_characters (
                id SERIAL PRIMARY KEY,
                user_id INTEGER UNIQUE,
                name TEXT NOT NULL,
                age INTEGER,
                gender TEXT,
                race TEXT,
                profession TEXT
            )
        """)

        # Таблица характеристик
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS expeditor_characteristics (
                character_id INTEGER PRIMARY KEY REFERENCES expeditor_characters(id) ON DELETE CASCADE,
                strength INTEGER,
                speed INTEGER,
                endurance INTEGER,
                dexterity INTEGER,
                perception INTEGER,
                reaction INTEGER,
                stress_resistance INTEGER
            )
        """)

        # Таблица психического состояния
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS expeditor_mental_state (
                character_id INTEGER PRIMARY KEY REFERENCES expeditor_characters(id) ON DELETE CASCADE,
                madness JSONB,
                submission INTEGER,
                libido INTEGER,
                impregnation TEXT
            )
        """)

        # Таблица травм
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS expeditor_injuries (
                character_id INTEGER PRIMARY KEY REFERENCES expeditor_characters(id) ON DELETE CASCADE,
                injuries JSONB
            )
        """)

        # Таблица экипировки
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS expeditor_equipment (
                character_id INTEGER PRIMARY KEY REFERENCES expeditor_characters(id) ON DELETE CASCADE,
                equipment JSONB
            )
        """)

        # Таблица оружия
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS expeditor_weapons (
                character_id INTEGER PRIMARY KEY REFERENCES expeditor_characters(id) ON DELETE CASCADE,
                weapons JSONB
            )
        """)

        # Таблица расходников
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS expeditor_consumables (
                character_id INTEGER PRIMARY KEY REFERENCES expeditor_characters(id) ON DELETE CASCADE,
                consumables JSONB
            )
        """)

        # Таблица инструментов
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS expeditor_tools (
                character_id INTEGER PRIMARY KEY REFERENCES expeditor_characters(id) ON DELETE CASCADE,
                tools JSONB
            )
        """)

        # Таблица предметов (общая)
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS expeditor_items (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                properties JSONB,
                item_group TEXT,
                item_type TEXT,
                uses INTEGER
            )
        """)

        # Таблица состояния "Экшен режима"
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS expeditor_action_mode (
                id SERIAL PRIMARY KEY,
                active BOOLEAN DEFAULT FALSE,
                judge_id INTEGER,
                participants JSONB,
                initiative_order JSONB
            )
        """)

        # Таблица логов проверок
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS expeditor_check_logs (
                id SERIAL PRIMARY KEY,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                user_id INTEGER,
                action TEXT,
                result TEXT,
                consequences TEXT
            )
        """)

        # Таблица администраторов
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS expeditor_admins (
                user_id INTEGER PRIMARY KEY
            )
        """)

        # Таблица рас
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS expeditor_races (
                name TEXT PRIMARY KEY,
                modifiers JSONB
            )
        """)

        # Таблица профессий
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS expeditor_professions (
                name TEXT PRIMARY KEY,
                modifiers JSONB
            )
        """)

        self.conn.commit()
        self.initialize_races_and_professions()

    def initialize_races_and_professions(self):
        # Начальные расы
        initial_races = {
            "Человек": {
                "strength": 0,
                "speed": 0,
                "endurance": 0,
                "dexterity": 0,
                "perception": 0,
                "reaction": 0,
                "stress_resistance": 0
            },
            "Ксенос": {
                "strength": -5,
                "speed": 0,
                "endurance": 0,
                "dexterity": 0,
                "perception": 10,
                "reaction": 5,
                "stress_resistance": 0
            },
            "Мутант": {
                "strength": 10,
                "speed": 0,
                "endurance": 10,
                "dexterity": 0,
                "perception": 0,
                "reaction": 0,
                "stress_resistance": -10
            },
            "Робот": {
                "strength": 15,
                "speed": 0,
                "endurance": 15,
                "dexterity": 0,
                "perception": -10,
                "reaction": 0,
                "stress_resistance": -20
            }
        }

        # Начальные профессии
        initial_professions = {
            "Горничные": {"endurance": 10, "perception": 10, "stress_resistance": 5},
            "Инженеры-техники": {"strength": 10, "perception": 10, "reaction": 5},
            "Медицинские сотрудники": {"dexterity": 10, "perception": 10, "stress_resistance": 5},
            "Лаборанты": {"perception": 10, "dexterity": 10, "stress_resistance": 5},
            "Сотрудники Службы Безопасности": {"strength": 10, "speed": 10, "reaction": 5},
            "Администраторы ресепшена": {"perception": 10, "stress_resistance": 10, "reaction": 5},
            "Системные администраторы": {"perception": 10, "reaction": 10, "stress_resistance": 5},
            "Врачи": {"dexterity": 10, "perception": 10, "stress_resistance": 5},
            "Юридический консультант/бухгалтер": {"perception": 10, "stress_resistance": 10, "reaction": 5},
            "Учёный": {"perception": 10, "dexterity": 10, "stress_resistance": 5},
            "Глава Медицинского Блока": {"perception": 15, "stress_resistance": 15, "reaction": 10},
            "Метрдотель Жилого Блока": {"perception": 15, "stress_resistance": 15, "reaction": 10},
            "Начальник Службы Безопасности": {"strength": 15, "reaction": 15, "stress_resistance": 10},
            "Главный инженер": {"strength": 15, "perception": 15, "reaction": 10},
            "Глава Научно-исследовательского Блока": {"perception": 15, "stress_resistance": 15, "dexterity": 10},
            "Управляющий Станцией RG-98": {"perception": 20, "stress_resistance": 20, "reaction": 15}
        }

        for race, modifiers in initial_races.items():
            self.cursor.execute("""
                INSERT INTO expeditor_races (name, modifiers)
                VALUES (%s, %s)
                ON CONFLICT (name) DO NOTHING
            """, (race, json.dumps(modifiers)))

        for profession, modifiers in initial_professions.items():
            self.cursor.execute("""
                INSERT INTO expeditor_professions (name, modifiers)
                VALUES (%s, %s)
                ON CONFLICT (name) DO NOTHING
            """, (profession, json.dumps(modifiers)))

        self.conn.commit()

    def apply_race_modifiers(self, character):
        """Применяет модификаторы расы к характеристикам персонажа"""
        self.cursor.execute("SELECT modifiers FROM expeditor_races WHERE name = %s", (character.race,))
        race_modifiers = self.cursor.fetchone()
        
        if not race_modifiers:
            return character
            
        modifiers = race_modifiers['modifiers']
        
        # Применяем модификаторы к базовым характеристикам
        character.strength += modifiers.get('strength', 0)
        character.speed += modifiers.get('speed', 0)
        character.endurance += modifiers.get('endurance', 0)
        character.dexterity += modifiers.get('dexterity', 0)
        character.perception += modifiers.get('perception', 0)
        character.reaction += modifiers.get('reaction', 0)
        character.stress_resistance += modifiers.get('stress_resistance', 0)
        
        return character

    def save_expeditor_character(self, character):
        # Применяем модификаторы расы перед сохранением
        character = self.apply_race_modifiers(character)
        
        # Сохранение основной информации персонажа
        self.cursor.execute("""
            INSERT INTO expeditor_characters (user_id, name, age, gender, race, profession)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (user_id) DO UPDATE
            SET name = %s, age = %s, gender = %s, race = %s, profession = %s
            RETURNING id
        """, (
            character.id, character.name, character.age, character.gender, character.race, character.profession,
            character.name, character.age, character.gender, character.race, character.profession
        ))
        character_id = self.cursor.fetchone()['id']

        # Сохранение характеристик
        self.cursor.execute("""
            INSERT INTO expeditor_characteristics (character_id, strength, speed, endurance, dexterity, perception, reaction, stress_resistance)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (character_id) DO UPDATE
            SET strength = %s, speed = %s, endurance = %s, dexterity = %s, perception = %s, reaction = %s, stress_resistance = %s
        """, (
            character_id, character.strength, character.speed, character.endurance, character.dexterity,
            character.perception, character.reaction, character.stress_resistance,
            character.strength, character.speed, character.endurance, character.dexterity,
            character.perception, character.reaction, character.stress_resistance
        ))

        # Сохранение психического состояния
        self.cursor.execute("""
            INSERT INTO expeditor_mental_state (character_id, madness, submission, libido, impregnation)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (character_id) DO UPDATE
            SET madness = %s, submission = %s, libido = %s, impregnation = %s
        """, (
            character_id, json.dumps(character.madness), character.submission, character.libido, character.impregnation,
            json.dumps(character.madness), character.submission, character.libido, character.impregnation
        ))

        # Сохранение травм
        self.cursor.execute("""
            INSERT INTO expeditor_injuries (character_id, injuries)
            VALUES (%s, %s)
            ON CONFLICT (character_id) DO UPDATE
            SET injuries = %s
        """, (character_id, json.dumps(character.injuries), json.dumps(character.injuries)))

        # Сохранение экипировки и предметов
        self.cursor.execute("""
            INSERT INTO expeditor_equipment (character_id, equipment)
            VALUES (%s, %s)
            ON CONFLICT (character_id) DO UPDATE
            SET equipment = %s
        """, (character_id, json.dumps([vars(item) for item in character.equipment]), json.dumps([vars(item) for item in character.equipment])))

        self.cursor.execute("""
            INSERT INTO expeditor_weapons (character_id, weapons)
            VALUES (%s, %s)
            ON CONFLICT (character_id) DO UPDATE
            SET weapons = %s
        """, (character_id, json.dumps([vars(item) for item in character.weapons]), json.dumps([vars(item) for item in character.weapons])))

        self.cursor.execute("""
            INSERT INTO expeditor_consumables (character_id, consumables)
            VALUES (%s, %s)
            ON CONFLICT (character_id) DO UPDATE
            SET consumables = %s
        """, (character_id, json.dumps([vars(item) for item in character.consumables]), json.dumps([vars(item) for item in character.consumables])))

        self.cursor.execute("""
            INSERT INTO expeditor_tools (character_id, tools)
            VALUES (%s, %s)
            ON CONFLICT (character_id) DO UPDATE
            SET tools = %s
        """, (character_id, json.dumps([vars(item) for item in character.tools]), json.dumps([vars(item) for item in character.tools])))

        self.conn.commit()

    def get_expeditor_character(self, user_id):
        # Получение основной информации персонажа
        self.cursor.execute("SELECT * FROM expeditor_characters WHERE user_id = %s", (user_id,))
        character_data = self.cursor.fetchone()
        if not character_data:
            return None

        character_id = character_data['id']

        # Получение характеристик
        self.cursor.execute("SELECT * FROM expeditor_characteristics WHERE character_id = %s", (character_id,))
        characteristics = self.cursor.fetchone()

        # Получение психического состояния
        self.cursor.execute("SELECT * FROM expeditor_mental_state WHERE character_id = %s", (character_id,))
        mental_state = self.cursor.fetchone()

        # Получение травм
        self.cursor.execute("SELECT * FROM expeditor_injuries WHERE character_id = %s", (character_id,))
        injuries = self.cursor.fetchone()

        # Получение экипировки и предметов
        self.cursor.execute("SELECT * FROM expeditor_equipment WHERE character_id = %s", (character_id,))
        equipment = self.cursor.fetchone()

        self.cursor.execute("SELECT * FROM expeditor_weapons WHERE character_id = %s", (character_id,))
        weapons = self.cursor.fetchone()

        self.cursor.execute("SELECT * FROM expeditor_consumables WHERE character_id = %s", (character_id,))
        consumables = self.cursor.fetchone()

        self.cursor.execute("SELECT * FROM expeditor_tools WHERE character_id = %s", (character_id,))
        tools = self.cursor.fetchone()

        # Создание объекта персонажа
        character = expeditor.models.Character(
            id=character_data['user_id'],
            name=character_data['name'],
            age=character_data['age'],
            gender=character_data['gender'],
            race=character_data['race'],
            profession=character_data['profession'],
            strength=characteristics['strength'],
            speed=characteristics['speed'],
            endurance=characteristics['endurance'],
            dexterity=characteristics['dexterity'],
            perception=characteristics['perception'],
            reaction=characteristics['reaction'],
            stress_resistance=characteristics['stress_resistance'],
            madness=mental_state['madness'],
            injuries=injuries['injuries'],
            submission=mental_state['submission'],
            libido=mental_state['libido'],
            impregnation=mental_state['impregnation'],
            equipment=[expeditor.models.Item(**item) for item in equipment['equipment']],
            weapons=[expeditor.models.Item(**item) for item in weapons['weapons']],
            consumables=[expeditor.models.Item(**item) for item in consumables['consumables']],
            tools=[expeditor.models.Item(**item) for item in tools['tools']]
        )

        return character

    def get_base_characteristics(self, character):
        """Возвращает базовые характеристики персонажа без учета модификаторов расы"""
        self.cursor.execute("SELECT modifiers FROM expeditor_races WHERE name = %s", (character.race,))
        race_modifiers = self.cursor.fetchone()
        
        if not race_modifiers:
            return {
                'strength': character.strength,
                'speed': character.speed,
                'endurance': character.endurance,
                'dexterity': character.dexterity,
                'perception': character.perception,
                'reaction': character.reaction,
                'stress_resistance': character.stress_resistance
            }
            
        modifiers = race_modifiers['modifiers']
        
        return {
            'strength': character.strength - modifiers.get('strength', 0),
            'speed': character.speed - modifiers.get('speed', 0),
            'endurance': character.endurance - modifiers.get('endurance', 0),
            'dexterity': character.dexterity - modifiers.get('dexterity', 0),
            'perception': character.perception - modifiers.get('perception', 0),
            'reaction': character.reaction - modifiers.get('reaction', 0),
            'stress_resistance': character.stress_resistance - modifiers.get('stress_resistance', 0)
        }

    def close(self):
        self.cursor.close()
        self.conn.close()

    async def get_approved_expeditor_character(self, user_id: int) -> Optional[Character]:
        """Получить одобренную карту экспедитора пользователя"""
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("""
                    SELECT * FROM expeditor_characters 
                    WHERE user_id = %s AND is_approved = TRUE
                    ORDER BY created_at DESC LIMIT 1
                """, (user_id,))
                result = await cur.fetchone()
                
                if result:
                    return Character(
                        id=result['id'],
                        user_id=result['user_id'],
                        name=result['name'],
                        race=result['race'],
                        profession=result['profession'],
                        base_strength=result['base_strength'],
                        base_speed=result['base_speed'],
                        base_endurance=result['base_endurance'],
                        base_dexterity=result['base_dexterity'],
                        base_perception=result['base_perception'],
                        base_reaction=result['base_reaction'],
                        base_stress_resistance=result['base_stress_resistance'],
                        is_fertilized=result['is_fertilized'],
                        is_approved=result['is_approved']
                    )
                return None

    async def get_character_count(self, user_id: int) -> int:
        """Получить количество персонажей пользователя"""
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("""
                    SELECT COUNT(*) FROM expeditor_characters 
                    WHERE user_id = %s
                """, (user_id,))
                result = await cur.fetchone()
                return result['count'] if result else 0

    async def create_deletion_request(self, user_id: int, character_id: int, reason: str, keep_copy: bool) -> bool:
        """Создать запрос на удаление персонажа"""
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                try:
                    await cur.execute("""
                        INSERT INTO expeditor_deletion_requests 
                        (user_id, character_id, reason, keep_copy, status) 
                        VALUES (%s, %s, %s, %s, 'pending')
                    """, (user_id, character_id, reason, keep_copy))
                    await conn.commit()
                    return True
                except Exception as e:
                    print(f"Error creating deletion request: {e}")
                    return False

    async def get_deletion_requests(self) -> list:
        """Получить все запросы на удаление"""
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("""
                    SELECT dr.*, c.name as character_name, c.race, c.profession
                    FROM expeditor_deletion_requests dr
                    JOIN expeditor_characters c ON dr.character_id = c.id
                    WHERE dr.status = 'pending'
                """)
                return await cur.fetchall()

    async def process_deletion_request(self, request_id: int, approve: bool) -> bool:
        """Обработать запрос на удаление"""
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                try:
                    # Получаем информацию о запросе
                    await cur.execute("""
                        SELECT * FROM expeditor_deletion_requests 
                        WHERE id = %s AND status = 'pending'
                    """, (request_id,))
                    request = await cur.fetchone()
                    
                    if not request:
                        return False
                    
                    if approve:
                        # Если нужно сохранить копию
                        if request['keep_copy']:
                            await cur.execute("""
                                INSERT INTO expeditor_character_archive 
                                SELECT *, CURRENT_TIMESTAMP as archived_at 
                                FROM expeditor_characters 
                                WHERE id = %s
                            """, (request['character_id'],))
                        
                        # Удаляем персонажа
                        await cur.execute("""
                            DELETE FROM expeditor_characters 
                            WHERE id = %s
                        """, (request['character_id'],))
                    
                    # Обновляем статус запроса
                    await cur.execute("""
                        UPDATE expeditor_deletion_requests 
                        SET status = %s, processed_at = CURRENT_TIMESTAMP 
                        WHERE id = %s
                    """, ('approved' if approve else 'rejected', request_id))
                    
                    await conn.commit()
                    return True
                except Exception as e:
                    print(f"Error processing deletion request: {e}")
                    return False

    async def create_item(self, name: str, description: str, item_type: str, usage_type: str,
                         properties: Dict[str, int], image_url: Optional[str] = None,
                         uses_remaining: Optional[int] = None, price: Optional[int] = None,
                         available_in_shop: bool = False, required_faction: Optional[str] = None,
                         required_reputation: Optional[int] = None) -> int:
        """Создание нового предмета"""
        query = """
            INSERT INTO expeditor_items (
                name, description, item_type, usage_type, properties, image_url,
                uses_remaining, price, available_in_shop, required_faction, required_reputation
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
            RETURNING id
        """
        return await self.pool.fetchval(
            query,
            name, description, item_type, usage_type, properties, image_url,
            uses_remaining, price, available_in_shop, required_faction, required_reputation
        )

    async def get_item(self, item_id: int) -> Optional[Item]:
        """Получение предмета по ID"""
        query = "SELECT * FROM expeditor_items WHERE id = $1"
        row = await self.pool.fetchrow(query, item_id)
        if row:
            return Item(**row)
        return None

    async def get_shop_items(self, user_id: int) -> List[Item]:
        """Получение предметов, доступных в магазине для пользователя"""
        query = """
            SELECT i.* FROM expeditor_items i
            LEFT JOIN user_factions uf ON i.required_faction = uf.faction_name
            WHERE i.available_in_shop = true
            AND (i.required_faction IS NULL OR 
                (uf.user_id = $1 AND uf.reputation >= i.required_reputation))
        """
        rows = await self.pool.fetch(query, user_id)
        return [Item(**row) for row in rows]

    async def add_item_to_character(self, character_id: int, item_id: int) -> bool:
        """Добавление предмета персонажу"""
        query = """
            INSERT INTO character_items (character_id, item_id)
            VALUES ($1, $2)
        """
        try:
            await self.pool.execute(query, character_id, item_id)
            return True
        except:
            return False

    async def remove_item_from_character(self, character_id: int, item_id: int) -> bool:
        """Удаление предмета у персонажа"""
        query = """
            DELETE FROM character_items
            WHERE character_id = $1 AND item_id = $2
        """
        try:
            await self.pool.execute(query, character_id, item_id)
            return True
        except:
            return False

    async def get_character_items(self, character_id: int) -> List[Item]:
        """Получение предметов персонажа"""
        query = """
            SELECT i.* FROM expeditor_items i
            JOIN character_items ci ON i.id = ci.item_id
            WHERE ci.character_id = $1
        """
        rows = await self.pool.fetch(query, character_id)
        return [Item(**row) for row in rows]

    async def update_item_uses(self, character_id: int, item_id: int, new_uses: int) -> bool:
        """Обновление количества использований предмета"""
        query = """
            UPDATE character_items
            SET uses_remaining = $3
            WHERE character_id = $1 AND item_id = $2
        """
        try:
            await self.pool.execute(query, character_id, item_id, new_uses)
            return True
        except:
            return False

    async def get_all_items(self) -> List[Item]:
        """Получение всех предметов"""
        query = "SELECT * FROM expeditor_items"
        rows = await self.pool.fetch(query)
        return [Item(**row) for row in rows]

    async def delete_item(self, item_id: int) -> bool:
        """Удаление предмета"""
        query = "DELETE FROM expeditor_items WHERE id = $1"
        try:
            await self.pool.execute(query, item_id)
            return True
        except:
            return False 