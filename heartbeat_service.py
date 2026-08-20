import asyncio
from loguru import logger
import os
import sys
import time

# Логи
os.makedirs("logs", exist_ok=True)
logger.remove()
logger.add(sys.stderr, level="INFO", colorize=True,
           format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
                  "<level>{level: <8}</level> | "
                  "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
                  "<level>{message}</level>")
logger.add("logs/heartbeat.log", rotation="5 MB", retention=5, compression="zip", level="INFO")

async def heartbeat():
    while True:
        logger.info("💓 Heartbeat: бот активен")
        await asyncio.sleep(60)

if __name__ == "__main__":
    try:
        logger.info("🚀 Heartbeat-сервис запущен")
        asyncio.run(heartbeat())
    except (KeyboardInterrupt, SystemExit):
        logger.info("⛔️ Heartbeat-сервис остановлен вручную")
