import os
import pandas as pd
from datetime import datetime, timedelta
from dotenv import load_dotenv
from pandas import DataFrame
from figi_cache import FIGI_CACHE

# ---------- БЛОК АВТОУСТАНОВКИ SDK (перед импортом tinkoff) ----------
import importlib.util
import subprocess
import sys

# Проверяем, доступен ли модуль tinkoff.invest
if importlib.util.find_spec("tinkoff.invest") is None:
    print("⚠️  Tinkoff SDK не найден, устанавливаем...")
    # Устанавливаем с флагом --no-deps, чтобы избежать конфликта с зависимостью tinkoff
    subprocess.check_call([
        sys.executable, '-m', 'pip', 'install',
        '--no-cache-dir', '--no-deps',
        'tinkoff-investments'
    ])
    print("✅ SDK установлен.")

# Теперь импортируем классы из SDK
from tinkoff.invest import Client, CandleInterval
# ----------------------------------------------------------------------

load_dotenv()

TOKEN = os.getenv("TINKOFF_INVEST_API_TOKEN")

INTERVAL_MAPPING = {
    "day": CandleInterval.CANDLE_INTERVAL_DAY,
    "week": CandleInterval.CANDLE_INTERVAL_WEEK,
}

# Глобальный клиент (инициализируется один раз)
_client = None

def init_client(token: str):
    """Инициализирует клиент Tinkoff один раз при запуске."""
    global _client
    if _client is None:
        _client = Client(token).__enter__()
    return _client


def get_figi_by_ticker(ticker: str):
    """Возвращает FIGI для тикера, используя кэш и единый клиент."""
    global _client
    if _client is None:
        raise RuntimeError("Клиент Tinkoff не инициализирован. Вызовите init_client() сначала.")

    if ticker in FIGI_CACHE:
        return FIGI_CACHE[ticker]

    services = [
        _client.instruments.shares,
        _client.instruments.currencies,
        _client.instruments.etfs,
        _client.instruments.bonds,
    ]

    for service in services:
        try:
            instruments = service().instruments
            for instrument in instruments:
                if instrument.ticker.upper() == ticker.upper():
                    FIGI_CACHE[ticker] = instrument.figi
                    return instrument.figi
        except Exception:
            continue

    return None


def get_candles(figi: str, interval_key: str, days: int):
    """Загружает свечи для заданного FIGI и интервала."""
    global _client
    if _client is None:
        raise RuntimeError("Клиент Tinkoff не инициализирован. Вызовите init_client() сначала.")

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
