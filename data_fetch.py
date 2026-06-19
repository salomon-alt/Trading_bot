import os
import pandas as pd
from datetime import datetime, timedelta
from dotenv import load_dotenv
from pandas import DataFrame
from figi_cache import FIGI_CACHE
import subprocess
import sys

# --- Устанавливаем пакет, если не установлен ---
try:
    from tinkoff_invest import ProductionSession as Client
except ImportError:
    print("⚠️  Устанавливаем tinkoff-invest...")
    subprocess.check_call([sys.executable, '-m', 'pip', 'install', '--no-cache-dir', 'tinkoff-invest==1.0.5'])
    from tinkoff_invest import ProductionSession as Client

load_dotenv()
TOKEN = os.getenv("TINKOFF_INVEST_API_TOKEN")

# Глобальный клиент
_client = None

def init_client(token: str):
    global _client
    if _client is None:
        _client = Client(token)
        # --- ОТЛАДКА: выводим все методы клиента ---
        print("=== Доступные методы клиента ===")
        methods = [m for m in dir(_client) if not m.startswith('_')]
        print(methods)
        # --- Пробуем получить инструменты разными способами ---
        print("=== Пробуем get_shares() ===")
        try:
            resp = _client.get_shares()
            print(f"Ответ: {resp}")
            if hasattr(resp, 'instruments'):
                print(f"Найдено акций: {len(resp.instruments)}")
            elif hasattr(resp, 'payload'):
                print(f"payload: {resp.payload}")
            else:
                print("Нет поля instruments или payload")
        except Exception as e:
            print(f"Ошибка: {e}")

        print("=== Пробуем get_currencies() ===")
        try:
            resp = _client.get_currencies()
            print(f"Ответ: {resp}")
            if hasattr(resp, 'instruments'):
                print(f"Найдено валют: {len(resp.instruments)}")
            elif hasattr(resp, 'payload'):
                print(f"payload: {resp.payload}")
        except Exception as e:
            print(f"Ошибка: {e}")

        print("=== Пробуем метод get_instruments() если есть ===")
        if hasattr(_client, 'get_instruments'):
            try:
                resp = _client.get_instruments()
                print(f"Ответ: {resp}")
            except Exception as e:
                print(f"Ошибка: {e}")
        else:
            print("Метод get_instruments отсутствует")
    return _client

# ... остальные функции (get_figi_by_ticker, get_candles) пока не нужны, 
# но мы их оставим заглушками для компиляции

def get_figi_by_ticker(ticker: str):
    # Временно возвращаем None, пока не отладим
    return None

def get_candles(figi: str, interval_key: str, days: int, ticker: str = None):
    return pd.DataFrame()
