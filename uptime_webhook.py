#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from flask import Flask, request
import requests

app = Flask(__name__)

TELEGRAM_TOKEN = "***REMOVED***"
CHAT_ID = "@slivochniyfootball"  # или ID чата

TELEGRAM_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

@app.route("/uptime", methods=["POST"])
def uptime_webhook():
    try:
        data = request.json or request.form
        message = f"🔔 UptimeRobot уведомление:\\n{data}"
        requests.post(TELEGRAM_URL, json={
            "chat_id": CHAT_ID,
            "text": message
        })
        return "OK", 200
    except Exception as e:
        return str(e), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=9000)
