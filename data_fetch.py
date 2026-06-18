import os
import pandas as pd
from datetime import datetime, timedelta
from dotenv import load_dotenv
from pandas import DataFrame
from tinkoff.invest import Client, CandleInterval

load_dotenv()
TOKEN = os.getenv("TINKOFF_INVEST_API_TOKEN")

INTERVAL_MAPPING = {
    "day": CandleInterval.CANDLE_INTERVAL_DAY,
    "week": CandleInterval.CANDLE_INTERVAL_WEEK,
    "4h": CandleInterval.CANDLE_INTERVAL_4_HOUR,
    "1h": CandleInterval.CANDLE_INTERVAL_HOUR,
}

# Кэш: {ticker: {'figi': figi, 'type': 'share'|'currency'|'etf'|'bond'}}
_INSTRUMENTS_CACHE = {}
_INSTRUMENTS_LOADED = False


def _load_all_instruments():
    global _INSTRUMENTS_CACHE, _INSTRUMENTS_LOADED
    if _INSTRUMENTS_LOADED:
        return

    with Client(TOKEN) as client:
        # Акции
        try:
            shares = client.instruments.shares().instruments
            for inst in shares:
                _INSTRUMENTS_CACHE[inst.ticker.upper()] = {'figi': inst.figi, 'type': 'share'}
        except Exception:
            pass

        # Валюты
        try:
            currencies = client.instruments.currencies().instruments
            for inst in currencies:
                _INSTRUMENTS_CACHE[inst.ticker.upper()] = {'figi': inst.figi, 'type': 'currency'}
        except Exception:
            pass

        # ETF
        try:
            etfs = client.instruments.etfs().instruments
            for inst in etfs:
                _INSTRUMENTS_CACHE[inst.ticker.upper()] = {'figi': inst.figi, 'type': 'etf'}
        except Exception:
            pass

        # Облигации
        try:
            bonds = client.instruments.bonds().instruments
            for inst in bonds:
                _INSTRUMENTS_CACHE[inst.ticker.upper()] = {'figi': inst.figi, 'type': 'bond'}
        except Exception:
            pass

    _INSTRUMENTS_LOADED = True


def init_client(token: str) -> None:
    pass


def get_figi_by_ticker(ticker: str):
    ticker = ticker.upper()
    if not _INSTRUMENTS_LOADED:
        _load_all_instruments()
    info = _INSTRUMENTS_CACHE.get(ticker)
    return info['figi'] if info else None


def get_instrument_type(ticker: str) -> str:
    """Возвращает тип инструмента: 'share', 'currency', 'etf', 'bond' или None."""
    ticker = ticker.upper()
    if not _INSTRUMENTS_LOADED:
        _load_all_instruments()
    info = _INSTRUMENTS_CACHE.get(ticker)
    return info['type'] if info else None


def get_candles(figi: str, interval_key: str, days: int, ticker: str = None) -> DataFrame:
    interval = INTERVAL_MAPPING.get(interval_key)
    if not interval:
        raise ValueError(f"Неподдерживаемый интервал: {interval_key}")

    now = datetime.utcnow()
    from_time = now - timedelta(days=days)

    with Client(TOKEN) as client:
        candles = client.market_data.get_candles(
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

    # Если это облигация – цена в процентах от номинала (1000 ₽) → умножаем на 10
    if ticker and get_instrument_type(ticker) == 'bond':
        df['open'] = df['open'] * 10
        df['high'] = df['high'] * 10
        df['low'] = df['low'] * 10
        df['close'] = df['close'] * 10

    return df
