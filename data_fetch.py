import os
import subprocess
import sys

# Устанавливаем пакет, если не установлен
try:
    from tinkoff_invest import ProductionSession as Client
except ImportError:
    print("⚠️  Устанавливаем tinkoff-invest...")
    subprocess.check_call([sys.executable, '-m', 'pip', 'install', '--no-cache-dir', 'tinkoff-invest==1.0.5'])
    from tinkoff_invest import ProductionSession as Client

from dotenv import load_dotenv
load_dotenv()

TOKEN = os.getenv("TINKOFF_INVEST_API_TOKEN")
print(f"TOKEN: {'УСТАНОВЛЕН' if TOKEN else 'НЕ УСТАНОВЛЕН'}")

_client = None

def init_client(token: str):
    global _client
    if _client is None:
        print("=== Инициализация клиента ===")
        _client = Client(token)
        print("=== Доступные методы клиента ===")
        methods = [m for m in dir(_client) if not m.startswith('_')]
        print(methods)
        
        print("=== Пробуем get_shares() ===")
        try:
            resp = _client.get_shares()
            print(f"Тип ответа: {type(resp)}")
            print(f"Атрибуты: {[a for a in dir(resp) if not a.startswith('_')]}")
            if hasattr(resp, 'instruments'):
                print(f"Найдено акций: {len(resp.instruments)}")
                if len(resp.instruments) > 0:
                    print(f"Первая акция: {resp.instruments[0].ticker} -> {resp.instruments[0].figi}")
            elif hasattr(resp, 'payload'):
                print(f"payload: {resp.payload}")
                if hasattr(resp.payload, 'instruments'):
                    print(f"В payload.instruments: {len(resp.payload.instruments)}")
        except Exception as e:
            print(f"Ошибка: {e}")
        
        print("=== Пробуем get_currencies() ===")
        try:
            resp = _client.get_currencies()
            if hasattr(resp, 'instruments'):
                print(f"Найдено валют: {len(resp.instruments)}")
        except Exception as e:
            print(f"Ошибка: {e}")
        
        print("=== Инициализация завершена ===")
    return _client

# Заглушки для остальных функций, чтобы main.py не падал
def get_figi_by_ticker(ticker: str):
    print(f"[DEBUG] Запрос FIGI для {ticker}")
    return None

def get_candles(figi: str, interval_key: str, days: int, ticker: str = None):
    print(f"[DEBUG] Запрос свечей для {figi}, интервал: {interval_key}")
    import pandas as pd
    return pd.DataFrame()
