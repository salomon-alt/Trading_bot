import os
import requests
import time

from dotenv import load_dotenv

load_dotenv()

TG_TOKEN = os.getenv("TG_BOT_TOKEN")
CHAT_ID = os.getenv("TG_CHAT_ID")


def send_signal(message):

    url = (
        f"https://api.telegram.org/"
        f"bot{TG_TOKEN}/sendMessage"
    )

    payload = {
        "chat_id": CHAT_ID,
        "text": message
    }

    for attempt in range(3):

        try:

            response = requests.post(
                url,
                data=payload,
                timeout=10
            )

            if response.status_code == 200:
                return True

        except Exception:
            pass

        time.sleep(5)

    return False