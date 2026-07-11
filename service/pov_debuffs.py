"""
Интеграция дебафов Карты Экспедитора с POV-режимом (см. модуль pov_mode_and_effects
в техническом задании).

Если у дебафа (db.StateDebuff.pov_effect) указан ключ эффекта из service.effects.EFFECTS,
выдача этого дебафа игроку принудительно включает ему POV-режим и активирует
соответствующий текстовый эффект на всё время действия дебафа (StateDebuff.time_use).
Если время действия не ограничено, эффект действует, пока дебаф не будет снят вручную.

POV-режим сам по себе при снятии дебафа НЕ выключается (у игрока могут быть другие
причины оставаться в POV) — снимается только сам текстовый эффект.
"""
from datetime import datetime, timedelta

from service.db_engine import db
from service.effects import EFFECTS
from service.chat_manager import force_pov_on

# Эффект дебафа (StateDebuff.pov_effect) -> поле db.FirstPersonMode, до которого эффект действует
POV_EFFECT_FIELDS = {
    'limited_visibility': 'limited_vision_until',
    'concussion': 'concussion_until',
    'blindness': 'blindness_until',
    'deafness': 'deafness_until',
}


async def _user_id_for_expeditor(expeditor_id: int):
    form_id = await db.select([db.Expeditor.form_id]).where(db.Expeditor.id == expeditor_id).gino.scalar()
    if not form_id:
        return None
    return await db.select([db.Form.user_id]).where(db.Form.id == form_id).gino.scalar()


async def apply_debuff_pov_effect(expeditor_id: int, debuff_id: int):
    """Включает (если нужно) POV игроку и активирует текстовый эффект выданного дебафа"""
    debuff = await db.select([db.StateDebuff.pov_effect, db.StateDebuff.time_use, db.StateDebuff.name]).where(
        db.StateDebuff.id == debuff_id).gino.first()
    if not debuff or not debuff.pov_effect or debuff.pov_effect not in POV_EFFECT_FIELDS:
        return
    user_id = await _user_id_for_expeditor(expeditor_id)
    if not user_id:
        return

    until = datetime.now() + timedelta(seconds=debuff.time_use) if debuff.time_use else datetime.max
    field = POV_EFFECT_FIELDS[debuff.pov_effect]

    mode = await db.FirstPersonMode.query.where(db.FirstPersonMode.user_id == user_id).gino.first()
    if not (mode and mode.is_active):
        await force_pov_on(user_id, reason=f'Дебаф «{debuff.name}»')
        mode = await db.FirstPersonMode.query.where(db.FirstPersonMode.user_id == user_id).gino.first()
    await mode.update(**{field: until}).apply()


async def clear_debuff_pov_effects(expeditor_id: int, debuff_ids: list[int]):
    """Снимает текстовые эффекты для списка дебафов (POV-режим при этом не выключается)"""
    debuff_ids = [x for x in debuff_ids if x]
    if not debuff_ids:
        return
    pov_effects = [x[0] for x in await db.select([db.StateDebuff.pov_effect]).where(
        db.StateDebuff.id.in_(debuff_ids) & db.StateDebuff.pov_effect.isnot(None)
    ).gino.all()]
    if not pov_effects:
        return
    user_id = await _user_id_for_expeditor(expeditor_id)
    if not user_id:
        return
    mode = await db.FirstPersonMode.query.where(db.FirstPersonMode.user_id == user_id).gino.first()
    if not mode:
        return
    values = {POV_EFFECT_FIELDS[e]: None for e in pov_effects if e in POV_EFFECT_FIELDS}
    if values:
        await mode.update(**values).apply()
