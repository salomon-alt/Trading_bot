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
    from tinkoff_invest import Client
except ImportError:
    print("⚠️  Устанавливаем tinkoff-invest...")
    subprocess.check_call([sys.executable, '-m', 'pip', 'install', '--no-cache-dir', 'tinkoff-invest==1.0.5'])
    from tinkoff_invest import Client

load_dotenv()
TOKEN = os.getenv("TINKOFF_INVEST_API_TOKEN")

# Интервалы (строки, поддерживаемые пакетом)
INTERVAL_MAPPING = {
    "day": "day",
    "week": "week",
    "4h": "4hour",   # если не работает, попробуйте "4h"
    "1h": "1hour",
}

_client = None

def init_client(token: str):
    global _client
    if _client is None:
        _client = Client(token)
    return _client

def get_figi_by_ticker(ticker: str):
    global _client
    if _client is None:
        raise RuntimeError("Клиент не инициализирован")

    if ticker in FIGI_CACHE:
        return FIGI_CACHE[ticker]

    instruments = []
    # Получаем инструменты всех типов
    try:
        resp = _client.get_shares()
        instruments.extend(resp.instruments)
    except:
        pass
    try:
        resp = _client.get_currencies()
        instruments.extend(resp.instruments)
    except:
        pass
    try:
        resp = _client.get_etfs()
        instruments.extend(resp.instruments)
    except:
        pass
    try:
        resp = _client.get_bonds()
        instruments.extend(resp.instruments)
    except:
        pass

    for inst in instruments:
        if inst.ticker.upper() == ticker.upper():
            FIGI_CACHE[ticker] = inst.figi
            return inst.figi

    return None

def get_candles(figi: str, interval_key: str, days: int, ticker: str = None):
    global _client
    if _client is None:
        raise RuntimeError("Клиент не инициализирован")

    interval = INTERVAL_MAPPING.get(interval_key)
    if not interval:
        raise ValueError(f"Неподдерживаемый интервал: {interval_key}")

    now = datetime.utcnow()
    from_time = now - timedelta(days=days)

    response = _client.get_candles(
        figi=figi,
        from_=from_time.isoformat(),
        to=now.isoformat(),
        interval=interval
    )
    candles = response.candles

    if not candles:
        return pd.DataFrame()

    data = []
    for c in candles:
        open_price = c.open
        high_price = c.high
        low_price = c.low
        close_price = c.close

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
