import os
import logging
import pandas as pd
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv
from figi_cache import FIGI_CACHE

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")

load_dotenv()
TOKEN = os.getenv("TINKOFF_INVEST_API_TOKEN")
if not TOKEN:
    raise RuntimeError("TINKOFF_INVEST_API_TOKEN не задан в .env")

# Базовый URL для REST API
BASE_URL = "https://invest-public-api.tinkoff.ru/rest/tinkoff.public.invest.api.contract.v1."

# Глобальный клиент не нужен – используем requests
_session = requests.Session()
_session.headers.update({
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
    "Accept": "application/json"
})

def init_client(token: str):
    # Ничего не делаем, токен уже в сессии
    logging.info("REST API клиент инициализирован")
    return _session

def _call_api(method: str, data: dict = None) -> dict:
    """Универсальный вызов REST API."""
    url = BASE_URL + method
    resp = _session.post(url, json=data or {})
    resp.raise_for_status()
    return resp.json()

def get_figi_by_ticker(ticker: str):
    if ticker in FIGI_CACHE:
        return FIGI_CACHE[ticker]

    logging.info(f"Запрос FIGI для {ticker}")
    instruments = []

    # Получаем акции
    try:
        resp = _call_api("InstrumentsService/GetShares")
        for item in resp.get("instruments", []):
            instruments.append({
                "ticker": item["ticker"],
                "figi": item["figi"]
            })
    except Exception as e:
        logging.error(f"Ошибка GetShares: {e}")

    # Получаем валюты
    try:
        resp = _call_api("InstrumentsService/GetCurrencies")
        for item in resp.get("instruments", []):
            instruments.append({
                "ticker": item["ticker"],
                "figi": item["figi"]
            })
    except Exception as e:
        logging.error(f"Ошибка GetCurrencies: {e}")

    # Получаем облигации
    try:
        resp = _call_api("InstrumentsService/GetBonds")
        for item in resp.get("instruments", []):
            instruments.append({
                "ticker": item["ticker"],
                "figi": item["figi"]
            })
    except Exception as e:
        logging.error(f"Ошибка GetBonds: {e}")

    # Получаем ETF
    try:
        resp = _call_api("InstrumentsService/GetEtfs")
        for item in resp.get("instruments", []):
            instruments.append({
                "ticker": item["ticker"],
                "figi": item["figi"]
            })
    except Exception as e:
        logging.error(f"Ошибка GetEtfs: {e}")

    logging.info(f"Всего инструментов: {len(instruments)}")
    for inst in instruments[:5]:
        logging.info(f"Пример: {inst['ticker']} -> {inst['figi']}")

    for inst in instruments:
        if inst["ticker"].upper() == ticker.upper():
            FIGI_CACHE[ticker] = inst["figi"]
            logging.info(f"Найден FIGI для {ticker}: {inst['figi']}")
            return inst["figi"]

    logging.warning(f"{ticker}: FIGI не найден")
    return None

def get_candles(figi: str, interval_key: str, days: int, ticker: str = None):
    # Маппинг интервалов для REST
    interval_map = {
        "day": "DAY",
        "week": "WEEK",
        "4h": "4_HOUR",
        "1h": "HOUR"
    }
    interval = interval_map.get(interval_key)
    if not interval:
        raise ValueError(f"Неподдерживаемый интервал: {interval_key}")

    now = datetime.utcnow()
    from_time = now - timedelta(days=days)

    payload = {
        "figi": figi,
        "from": from_time.isoformat() + "Z",
        "to": now.isoformat() + "Z",
        "interval": interval
    }

    try:
        resp = _call_api("MarketDataService/GetCandles", payload)
        candles = resp.get("candles", [])
    except Exception as e:
        logging.error(f"Ошибка GetCandles для {figi}: {e}")
        return pd.DataFrame()

    if not candles:
        logging.warning(f"Нет свечей для {figi}")
        return pd.DataFrame()

    data = []
    for c in candles:
        open_price = float(c["open"]["units"]) + float(c["open"]["nano"]) / 1e9
        high_price = float(c["high"]["units"]) + float(c["high"]["nano"]) / 1e9
        low_price = float(c["low"]["units"]) + float(c["low"]["nano"]) / 1e9
        close_price = float(c["close"]["units"]) + float(c["close"]["nano"]) / 1e9

        if min(open_price, high_price, low_price, close_price) <= 0:
            continue

        data.append({
            "time": c["time"],
            "open": open_price,
            "high": high_price,
            "low": low_price,
            "close": close_price,
            "volume": c["volume"]
        })

    df = pd.DataFrame(data)
    if df.empty:
        return df

    df = df.sort_values("time").reset_index(drop=True)
    return df
