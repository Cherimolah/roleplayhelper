"""
Оптимизированный модуль для работы с базой данных экспедитора
"""

class User:
    def __init__(self, id: int, name: str):
        self.id = id
        self.name = name

async def get_active_users(self) -> list[User]:
    """
    Получает список активных пользователей (имеющих не замороженных персонажей)
    
    Returns:
        list[User]: Список активных пользователей
    """
    try:
        async with self.pool.acquire() as conn:
            users = await conn.fetch(
                """
                SELECT DISTINCT u.id, u.name
                FROM users u
                JOIN expeditor_characters ec ON u.id = ec.user_id
                WHERE ec.is_frozen = FALSE
                ORDER BY u.name
                """
            )
            
            return [User(user['id'], user['name']) for user in users]
            
    except Exception as e:
        print(f"Error getting active users: {e}")
        return []

async def get_user_by_name(self, name: str) -> Optional[User]:
    """
    Получает пользователя по имени
    
    Args:
        name: Имя пользователя
        
    Returns:
        Optional[User]: Объект пользователя или None, если не найден
    """
    try:
        async with self.pool.acquire() as conn:
            user = await conn.fetchrow(
                """
                SELECT id, name
                FROM users
                WHERE name = $1
                """,
                name
            )
            
            if user:
                return User(user['id'], user['name'])
            return None
            
    except Exception as e:
        print(f"Error getting user by name: {e}")
        return None

async def transfer_item(self, sender_id: int, recipient_id: int, item_id: int) -> bool:
    """
    Передает предмет от одного персонажа другому
    
    Args:
        sender_id: ID персонажа-отправителя
        recipient_id: ID персонажа-получателя
        item_id: ID передаваемого предмета
        
    Returns:
        bool: True если передача успешна, False в противном случае
    """
    try:
        # Проверяем, что предмет принадлежит отправителю
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                # Проверяем принадлежность предмета
                item_owner = await conn.fetchval(
                    """
                    SELECT character_id 
                    FROM character_items 
                    WHERE character_id = $1 AND item_id = $2
                    """,
                    sender_id, item_id
                )
                
                if not item_owner:
                    return False
                
                # Удаляем предмет у отправителя
                await conn.execute(
                    """
                    DELETE FROM character_items 
                    WHERE character_id = $1 AND item_id = $2
                    """,
                    sender_id, item_id
                )
                
                # Добавляем предмет получателю
                await conn.execute(
                    """
                    INSERT INTO character_items (character_id, item_id)
                    VALUES ($1, $2)
                    """,
                    recipient_id, item_id
                )
                
                return True
                
    except Exception as e:
        print(f"Error transferring item: {e}")
        return False 