import os
import subprocess
import sys
import pandas as pd
from datetime import datetime, timedelta
from dotenv import load_dotenv
from pandas import DataFrame
from figi_cache import FIGI_CACHE

# -------------------------------------------------------------------
# 1. Установка официального SDK (если не установлен)
# -------------------------------------------------------------------
try:
    from tinkoff.invest import Client, CandleInterval
except ImportError:
    print("⚠️  Устанавливаем официальный SDK из GitHub-архива (без зависимостей)...")
    subprocess.check_call([
        sys.executable, '-m', 'pip', 'install',
        '--no-cache-dir', '--no-deps',
        'https://github.com/Tinkoff/invest-python/archive/refs/heads/master.zip'
    ])
    from tinkoff.invest import Client, CandleInterval

# -------------------------------------------------------------------
# 2. Загрузка переменных окружения
# -------------------------------------------------------------------
load_dotenv()
TOKEN = os.getenv("TINKOFF_INVEST_API_TOKEN")
if not TOKEN:
    raise RuntimeError("TINKOFF_INVEST_API_TOKEN не задан в .env")

# -------------------------------------------------------------------
# 3. Маппинг интервалов
# -------------------------------------------------------------------
INTERVAL_MAPPING = {
    "day": CandleInterval.CANDLE_INTERVAL_DAY,
    "week": CandleInterval.CANDLE_INTERVAL_WEEK,
    "4h": CandleInterval.CANDLE_INTERVAL_4_HOUR,
    "1h": CandleInterval.CANDLE_INTERVAL_HOUR,
}

# -------------------------------------------------------------------
# 4. Глобальный клиент
# -------------------------------------------------------------------
_client = None

def init_client(token: str):
    global _client
    if _client is None:
        _client = Client(token)
    return _client

# -------------------------------------------------------------------
# 5. Получение FIGI по тикеру
# -------------------------------------------------------------------
def get_figi_by_ticker(ticker: str):
    global _client
    if _client is None:
        raise RuntimeError("Клиент не инициализирован. Вызовите init_client()")

    if ticker in FIGI_CACHE:
        return FIGI_CACHE[ticker]

    instruments = []
    # Правильные вызовы: client.instruments.shares() и т.д.
    try:
        resp = _client.instruments.shares()
        instruments.extend(resp.instruments)
    except Exception as e:
        print(f"[DEBUG] Ошибка shares: {e}")

    try:
        resp = _client.instruments.currencies()
        instruments.extend(resp.instruments)
    except Exception as e:
        print(f"[DEBUG] Ошибка currencies: {e}")

    try:
        resp = _client.instruments.etfs()
        instruments.extend(resp.instruments)
    except Exception as e:
        print(f"[DEBUG] Ошибка etfs: {e}")

    try:
        resp = _client.instruments.bonds()
        instruments.extend(resp.instruments)
    except Exception as e:
        print(f"[DEBUG] Ошибка bonds: {e}")

    for inst in instruments:
        if inst.ticker.upper() == ticker.upper():
            FIGI_CACHE[ticker] = inst.figi
            return inst.figi

    return None

# -------------------------------------------------------------------
# 6. Получение свечей
# -------------------------------------------------------------------
def get_candles(figi: str, interval_key: str, days: int, ticker: str = None):
    global _client
    if _client is None:
        raise RuntimeError("Клиент не инициализирован")

    interval = INTERVAL_MAPPING.get(interval_key)
    if not interval:
        raise ValueError(f"Неподдерживаемый интервал: {interval_key}")

    now = datetime.utcnow()
    from_time = now - timedelta(days=days)

    candles = _client.market_data.get_candles(
        figi=figi,
        from_=from_time,
        to=now,
        interval=interval,
    ).candles

    if not candles:
        return pd.DataFrame()

    data = []
    for c in candles:
        open_price = c.open.units + c.open.nano / 1e9
        high_price = c.high.units + c.high.nano / 1e9
        low_price = c.low.units + c.low.nano / 1e9
        close_price = c.close.units + c.close.nano / 1e9

        if min(open_price, high_price, low_price, close_price) <= 0:
            continue

        data.append({
            "time": c.time,
            "open": open_price,
            "high": high_price,
            "low": low_price,
            "close": close_price,
            "volume": c.volume
        })

    df = pd.DataFrame(data)
    if df.empty:
        return df

    df = df.sort_values("time").reset_index(drop=True)
    return df
