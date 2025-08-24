#!/bin/bash
# 🚀 Запуск дайджестов «Кофе со сливками»

# Загружаем окружение
source .env

# Лог директория
mkdir -p logs

# Утренний дайджест
python3 digest.py утренний >> logs/digest.log 2>&1

# Дневной дайджест
python3 digest.py дневной >> logs/digest.log 2>&1

# Вечерний дайджест
python3 digest.py вечерний >> logs/digest.log 2>&1
