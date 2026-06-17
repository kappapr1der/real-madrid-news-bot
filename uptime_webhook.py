#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os

import requests
from dotenv import load_dotenv
from flask import Flask, request

load_dotenv()

app = Flask(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TARGET_CHAT_ID")


@app.route("/uptime", methods=["POST"])
def uptime_webhook():
    if not TELEGRAM_TOKEN or not CHAT_ID:
        return "Telegram credentials are not configured", 503

    try:
        data = request.json or request.form
        message = f"🔔 UptimeRobot уведомление:\n{data}"
        telegram_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(
            telegram_url,
            json={
                "chat_id": CHAT_ID,
                "text": message,
            },
            timeout=10,
        )
        return "OK", 200
    except Exception as e:
        return str(e), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=9000)
