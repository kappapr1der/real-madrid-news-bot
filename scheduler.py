from __future__ import annotations

from typing import Awaitable, Callable, Optional
from dataclasses import dataclass
from datetime import datetime
import pytz

from loguru import logger
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

# Тип коллбэка дайджеста: async def digest(): ...
DigestCoro = Callable[[], Awaitable[None]]

@dataclass
class ScheduleConfig:
    tz_name: str = "Europe/Moscow"
    morning: str = "0 9 * * *"   # 09:00
    day:     str = "0 15 * * *"  # 15:00
    evening: str = "0 21 * * *"  # 21:00
    test_on_start: bool = False  # если True — сделать тестовый дайджест при старте

def _cron(cron_expr: str, tz_name: str) -> CronTrigger:
    """
    Создаёт CronTrigger из crontab-строки с нужным таймзон.
    """
    return CronTrigger.from_crontab(cron_expr, timezone=pytz.timezone(tz_name))

def _log_jobs(scheduler: AsyncIOScheduler, tz_name: str) -> None:
    """
    Логируем все задания, чтобы в статусе было видно расписание.
    """
    tz = pytz.timezone(tz_name)
    lines = []
    for job in scheduler.get_jobs():
        next_run = job.next_run_time.astimezone(tz).strftime("%Y-%m-%d %H:%M:%S %Z") if job.next_run_time else "—"
        lines.append(f"• {job.id}: next={next_run}, trigger={job.trigger}")
    if lines:
        logger.info("📅 Планировщик активен. Ближайшие запуски:\n" + "\n".join(lines))
    else:
        logger.warning("⚠️ Планировщик активен, но заданий нет")

def setup_scheduler(bot, digest_coro: DigestCoro, config: Optional[ScheduleConfig] = None) -> AsyncIOScheduler:
    """
    Регистрирует три джоба (утро/день/вечер) по московскому времени
    и (опционально) запускает тестовый дайджест при старте.

    Пример использования:
        scheduler = setup_scheduler(bot, publish_digest)
    """
    if config is None:
        config = ScheduleConfig()

    # Обёртка чтобы передать только корутину дайджеста
    async def _run_digest(tag: str):
        try:
            logger.info(f"📰 Старт дайджеста: {tag}")
            await digest_coro()
            logger.success(f"✅ Дайджест отправлен: {tag}")
        except Exception as e:
            logger.exception(f"❌ Ошибка дайджеста ({tag}): {e}")

    scheduler = AsyncIOScheduler(timezone=pytz.timezone(config.tz_name))

    # Утро
    scheduler.add_job(
        lambda: bot.loop.create_task(_run_digest("morning")),
        _cron(config.morning, config.tz_name),
        id="digest_morning",
        replace_existing=True,
        coalesce=True,
        misfire_grace_time=600,  # 10 минут
        max_instances=1
    )

    # День
    scheduler.add_job(
        lambda: bot.loop.create_task(_run_digest("day")),
        _cron(config.day, config.tz_name),
        id="digest_day",
        replace_existing=True,
        coalesce=True,
        misfire_grace_time=600,
        max_instances=1
    )

    # Вечер
    scheduler.add_job(
        lambda: bot.loop.create_task(_run_digest("evening")),
        _cron(config.evening, config.tz_name),
        id="digest_evening",
        replace_existing=True,
        coalesce=True,
        misfire_grace_time=600,
        max_instances=1
    )

    scheduler.start()
    logger.info(f"🗓️ Планировщик запущен (TZ={config.tz_name})")
    _log_jobs(scheduler, config.tz_name)

    # По желанию — тестовый запуск сразу после старта сервиса
    if config.test_on_start:
        logger.info("🧪 Тестовый дайджест при старте включён")
        bot.loop.create_task(_run_digest("startup-test"))

    return scheduler
