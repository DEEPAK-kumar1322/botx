"""
Sound Test Stream: Sends 10 test alert messages (every 30 seconds) to Telegram and WhatsApp
so the user can adjust their phone volume, ringtones, and notification channels in real-time.
"""

import os
import time
import requests
from dotenv import load_dotenv

load_dotenv()

from src.notifications.whatsapp_alerts import WhatsAppAlertSender

token = os.getenv("TELEGRAM_BOT_TOKEN")
chat_id = os.getenv("TELEGRAM_CHAT_ID")
whatsapp = WhatsAppAlertSender()

print(f"Starting Sound Test Stream: 10 messages with 30s interval...")

for i in range(1, 11):
    msg = (
        f"🔊🔔 *[SOUND TEST #{i} OF 10]* 🔔🔊\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"⏰ *Time:* {time.strftime('%H:%M:%S')}\n"
        f"📢 *Test Note:* Phone volume ya notification sound adjust karo bhai!\n"
        f"⚡ *Progress:* Message {i} / 10\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🎵 Check karo ab sound aayi kya?"
    )

    # 1. Telegram
    if token and chat_id:
        try:
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            res = requests.post(url, json={
                "chat_id": chat_id,
                "text": msg,
                "parse_mode": "Markdown",
                "disable_notification": False
            }, timeout=8)
            print(f"[{time.strftime('%H:%M:%S')}] Telegram #{i} sent: {res.status_code}")
        except Exception as e:
            print(f"Telegram error: {e}")

    # 2. WhatsApp
    try:
        sent, _ = whatsapp.send_raw_message(msg)
        print(f"[{time.strftime('%H:%M:%S')}] WhatsApp #{i} sent: {sent}")
    except Exception as e:
        print(f"WhatsApp error: {e}")

    if i < 10:
        time.sleep(30)

print("Sound Test Stream completed (All 10 messages sent).")
