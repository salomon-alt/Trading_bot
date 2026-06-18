from telegram import Bot
import logging
from utils import TG_BOT_TOKEN, TG_CHAT_ID

# Предварительно инициализируем логгер, чтобы увидеть ошибки отправки
logging.getLogger().setLevel(logging.INFO)

bot = Bot(token=TG_BOT_TOKEN)

def send_signal_to_telegram(message: str):
    try:
        bot.send_message(chat_id=int(TG_CHAT_ID), text=message)
    except Exception as e:
        logging.error(f"Telegram send error: {e}")
