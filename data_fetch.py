import os
import subprocess
import sys
import logging
import pandas as pd
from datetime import datetime, timedelta
from dotenv import load_dotenv
from figi_cache import FIGI_CACHE

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")

# -------------------------------------------------------------------
# 1. Установка пакета, если он не найден
# -------------------------------------------------------------------
try:
    from tinkoff_invest import ProductionSession as Client
except ImportError:
    logging.warning("⚠️ Устанавливаем tinkoff-invest...")
    subprocess.check_call([sys.executable, '-m', 'pip', 'install', '--no-cache-dir', 'tinkoff-invest==1.0.5'])
    from tinkoff_invest import ProductionSession as Client

# -------------------------------------------------------------------
# 2. Загрузка переменных окружения
# -------------------------------------------------------------------
load_dotenv()
TOKEN = os.getenv("TINKOFF_INVEST_API_TOKEN")
logging.info(f"TOKEN: {'✅ УСТАНОВЛЕН' if TOKEN else '❌ НЕ УСТАНОВЛЕН'}")

# -------------------------------------------------------------------
# 3. Глобальный клиент
# -------------------------------------------------------------------
_client = None

def init_client(token: str):
    global _client
    if _client is None:
        logging.info("=== Инициализация клиента ===")
        _client = Client(token)
        logging.info("=== Доступные методы клиента ===")
        methods = [m for m in dir(_client) if not m.startswith('_')]
        logging.info(methods)

        # ---- Проверяем получение инструментов ----
        logging.info("=== Пробуем get_shares() ===")
        try:
            resp = _client.get_shares()
            logging.info(f"Тип ответа: {type(resp)}")
            attrs = [a for a in dir(resp) if not a.startswith('_')]
            logging.info(f"Атрибуты ответа: {attrs}")
            if hasattr(resp, 'instruments'):
                instruments = resp.instruments
                logging.info(f"Найдено акций: {len(instruments)}")
                if len(instruments) > 0:
                    logging.info(f"Пример: {instruments[0].ticker} -> {instruments[0].figi}")
            elif hasattr(resp, 'payload'):
                logging.info(f"payload: {resp.payload}")
                if hasattr(resp.payload, 'instruments'):
                    logging.info(f"В payload.instruments: {len(resp.payload.instruments)}")
            else:
                logging.info("Нет ни instruments, ни payload")
        except Exception as e:
            logging.error(f"Ошибка get_shares: {e}")

        logging.info("=== Пробуем get_currencies() ===")
        try:
            resp = _client.get_currencies()
            if hasattr(resp, 'instruments'):
                logging.info(f"Найдено валют: {len(resp.instruments)}")
            else:
                logging.info(f"Ответ: {resp}")
        except Exception as e:
            logging.error(f"Ошибка get_currencies: {e}")

        logging.info("=== Пробуем get_etfs() ===")
        try:
            resp = _client.get_etfs()
            if hasattr(resp, 'instruments'):
                logging.info(f"Найдено ETF: {len(resp.instruments)}")
        except Exception as e:
            logging.error(f"Ошибка get_etfs: {e}")

        logging.info("=== Пробуем get_bonds() ===")
        try:
            resp = _client.get_bonds()
            if hasattr(resp, 'instruments'):
                logging.info(f"Найдено облигаций: {len(resp.instruments)}")
        except Exception as e:
            logging.error(f"Ошибка get_bonds: {e}")

        logging.info("=== Инициализация завершена ===")
    return _client

# -------------------------------------------------------------------
# 4. Заглушки для остальных функций
# -------------------------------------------------------------------
def get_figi_by_ticker(ticker: str):
    logging.info(f"Запрос FIGI для {ticker}")
    return None

def get_candles(figi: str, interval_key: str, days: int, ticker: str = None):
    logging.info(f"Запрос свечей для {figi}, интервал: {interval_key}, дней: {days}")
    return pd.DataFrame()
