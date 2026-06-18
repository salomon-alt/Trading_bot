import os
from dotenv import load_dotenv

load_dotenv()

TINKOFF_TOKEN    = os.getenv("TINKOFF_INVEST_API_TOKEN")
TELEGRAM_TOKEN   = os.getenv("TG_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TG_CHAT_ID")

if not all([TINKOFF_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID]):
    raise RuntimeError("В .env должны быть TINKOFF_INVEST_API_TOKEN, TG_BOT_TOKEN и TG_CHAT_ID")
