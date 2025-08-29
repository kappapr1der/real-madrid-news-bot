from datetime import datetime
from zoneinfo import ZoneInfo

# Настрой пороги как тебе надо:
# утро 05–11, день 11–17, вечер 17–23, ночь остальное
def get_daypart(now: datetime | None = None, tz: str = "Europe/Berlin") -> str:
    dt = (now or datetime.now(ZoneInfo(tz))).astimezone(ZoneInfo(tz))
    h = dt.hour
    if 5 <= h < 11: return "Утренний"
    if 11 <= h < 17: return "Дневной"
    if 17 <= h < 23: return "Вечерний"
    return "Ночной"
