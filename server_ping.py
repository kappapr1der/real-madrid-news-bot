#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Простой HTTP эндпоинт для UptimeRobot
Проверяет, что бот жив (возвращает 200 OK).
"""

from flask import Flask

app = Flask(__name__)

@app.route("/ping")
def ping():
    return "☕ Coffee Bot alive", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
