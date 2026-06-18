# data_fetch.py

import os
from datetime import datetime, timedelta
import pandas as pd
from dotenv import load_dotenv
from tinkoff_invest import ProductionSession

# 1. Подхватываем токен из .env
load_dotenv()
TOKEN = os.getenv("TINKOFF_INVEST_API_TOKEN")
if not TOKEN:
    raise RuntimeError(
        "TINKOFF_INVEST_API_TOKEN не найден в .env. "
        "Проверьте, что .env содержит строку:\n"
        "TINKOFF_INVEST_API_TOKEN=ваш_токен_от_Tinkoff"
    )

# 2. Строковые ключи для интервалов
INTERVALS = {
    "day":  "day",
    "week": "week",
}

def get_figi_by_ticker(ticker: str) -> str:
    """
    Возвращает FIGI по тикеру (акция или валюта).
    Бросает ValueError, если тикер не найден.
    """
    # Теперь TOKEN гарантированно непустой
    session = ProductionSession(TOKEN)
    try:
        instr_service = session._get_instruments(False, None)
        for s in instr_service.shares().instruments:
            if s.ticker == ticker:
                return s.figi
        for c in instr_service.currencies().instruments:
            if c.ticker == ticker:
                return c.figi
        raise ValueError(f"FIGI не найден для тикера {ticker}")
    finally:
        del session

def get_candles(figi: str, interval_key: str, days: int = 100) -> pd.DataFrame:
    """
    Возвращает DataFrame c последними `days` единицами времени:
      интервал 'day' или 'week'
    """
    interval = INTERVALS.get(interval_key)
    if not interval:
        raise ValueError(f"Неподдерживаемый интервал: {interval_key}")

    session = ProductionSession(TOKEN)
    try:
        md_service = session._get_market_data(False, None)
        now = datetime.utcnow()
        start = now - timedelta(days=days)
        resp = md_service.get_candles(
            figi=figi,
            from_=start,
            to=now,
            interval=interval
        )
        candles = resp.candles
    finally:
        del session

    data = [{
        "time":  c.time,
        "open":  c.open.units + c.open.nano / 1e9,
        "high":  c.high.units + c.high.nano / 1e9,
        "low":   c.low.units + c.low.nano / 1e9,
        "close": c.close.units + c.close.nano / 1e9,
        "volume": c.volume
    } for c in candles]

    df = pd.DataFrame(data)
    if not df.empty:
        df = df.set_index("time").sort_index()
    return df
