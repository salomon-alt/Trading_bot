import os
import subprocess
import sys
import pandas as pd
from datetime import datetime, timedelta
from dotenv import load_dotenv
from figi_cache import FIGI_CACHE

# -------------------------------------------------------------------
# 1. Установка пакета, если он не найден
# -------------------------------------------------------------------
try:
    from tinkoff_invest import ProductionSession as Client
except ImportError:
    print("⚠️  Устанавливаем tinkoff-invest...")
    subprocess.check_call([sys.executable, '-m', 'pip', 'install', '--no-cache-dir', 'tinkoff-invest==1.0.5'])
    from tinkoff_invest import ProductionSession as Client

# -------------------------------------------------------------------
# 2. Загрузка переменных окружения
# -------------------------------------------------------------------
load_dotenv()
TOKEN = os.getenv("TINKOFF_INVEST_API_TOKEN")
print(f"[DEBUG] TOKEN: {'✅ УСТАНОВЛЕН' if TOKEN else '❌ НЕ УСТАНОВЛЕН'}")

# -------------------------------------------------------------------
# 3. Глобальный клиент
# -------------------------------------------------------------------
_client = None

def init_client(token: str):
    global _client
    if _client is None:
        print("[DEBUG] === Инициализация клиента ===")
        _client = Client(token)
        print("[DEBUG] === Доступные методы клиента ===")
        methods = [m for m in dir(_client) if not m.startswith('_')]
        print(methods)

        # ---- Проверяем получение инструментов ----
        print("[DEBUG] === Пробуем get_shares() ===")
        try:
            resp = _client.get_shares()
            print(f"[DEBUG] Тип ответа: {type(resp)}")
            attrs = [a for a in dir(resp) if not a.startswith('_')]
            print(f"[DEBUG] Атрибуты ответа: {attrs}")
            if hasattr(resp, 'instruments'):
                instruments = resp.instruments
                print(f"[DEBUG] Найдено акций: {len(instruments)}")
                if len(instruments) > 0:
                    print(f"[DEBUG] Пример: {instruments[0].ticker} -> {instruments[0].figi}")
            elif hasattr(resp, 'payload'):
                print(f"[DEBUG] payload: {resp.payload}")
                if hasattr(resp.payload, 'instruments'):
                    print(f"[DEBUG] В payload.instruments: {len(resp.payload.instruments)}")
            else:
                print("[DEBUG] Нет ни instruments, ни payload")
        except Exception as e:
            print(f"[DEBUG] Ошибка get_shares: {e}")

        print("[DEBUG] === Пробуем get_currencies() ===")
        try:
            resp = _client.get_currencies()
            if hasattr(resp, 'instruments'):
                print(f"[DEBUG] Найдено валют: {len(resp.instruments)}")
            else:
                print(f"[DEBUG] Ответ: {resp}")
        except Exception as e:
            print(f"[DEBUG] Ошибка get_currencies: {e}")

        print("[DEBUG] === Пробуем get_etfs() ===")
        try:
            resp = _client.get_etfs()
            if hasattr(resp, 'instruments'):
                print(f"[DEBUG] Найдено ETF: {len(resp.instruments)}")
        except Exception as e:
            print(f"[DEBUG] Ошибка get_etfs: {e}")

        print("[DEBUG] === Пробуем get_bonds() ===")
        try:
            resp = _client.get_bonds()
            if hasattr(resp, 'instruments'):
                print(f"[DEBUG] Найдено облигаций: {len(resp.instruments)}")
        except Exception as e:
            print(f"[DEBUG] Ошибка get_bonds: {e}")

        print("[DEBUG] === Инициализация завершена ===")
    return _client

# -------------------------------------------------------------------
# 4. Заглушки для остальных функций (чтобы main.py не падал)
#    Они будут перезаписаны, когда мы напишем правильную логику.
# -------------------------------------------------------------------
def get_figi_by_ticker(ticker: str):
    print(f"[DEBUG] Запрос FIGI для {ticker}")
    # Пока возвращаем None, чтобы бот не падал, но выводил отладочную информацию
    # В будущем здесь будет реальный поиск по полученным инструментам
    return None

def get_candles(figi: str, interval_key: str, days: int, ticker: str = None):
    print(f"[DEBUG] Запрос свечей для {figi}, интервал: {interval_key}, дней: {days}")
    return pd.DataFrame()

# -------------------------------------------------------------------
# 5. Экспортируемые переменные (для main.py)
# -------------------------------------------------------------------
# TOKEN уже объявлен выше
