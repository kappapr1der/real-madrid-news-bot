from datetime import datetime
import pytz

TZ = pytz.timezone("Europe/Berlin")

def digest_label(now: datetime | None = None) -> str:
    """
    Возвращает одну из меток:
      - Утренние сливки дня   (05:00–11:00)
      - Дневные сливки дня    (11:00–17:00)
      - Вечерние сливки дня   (17:00–23:59)
      - Ночные сливки         (00:00–05:00)
    """
    dt = now.astimezone(TZ) if now else datetime.now(TZ)
    h = dt.hour
    if 5 <= h < 11:
        return "Утренние сливки дня"
    if 11 <= h < 17:
        return "Дневные сливки дня"
    if 17 <= h <= 23:
        return "Вечерние сливки дня"
    return "Ночные сливки"
