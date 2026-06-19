import os
import logging
import time
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

BASE_URL = "https://invest-public-api.tinkoff.ru/rest/tinkoff.public.invest.api.contract.v1."

_session = requests.Session()
_session.headers.update({
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
    "Accept": "application/json"
})

# Глобальный кэш всех инструментов (чтобы не делать повторные запросы)
_instruments_cache = None

def init_client(token: str):
    logging.info("REST API клиент инициализирован")
    return _session

def _call_api(method: str, data: dict = None, retries: int = 2) -> dict:
    url = BASE_URL + method
    for attempt in range(retries + 1):
        try:
            logging.info(f"Запрос: {url}")
            resp = _session.post(url, json=data or {})
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429:
                wait = 2 ** attempt
                logging.warning(f"Ошибка 429 (слишком много запросов). Ждём {wait} секунд...")
                time.sleep(wait)
                continue
            raise
    raise Exception(f"Не удалось выполнить запрос после {retries} попыток")

def _load_all_instruments():
    """Загружает все инструменты один раз и кэширует."""
    global _instruments_cache
    if _instruments_cache is not None:
        return _instruments_cache

    instruments = []
    try:
        resp = _call_api("InstrumentsService/GetShares")
        for item in resp.get("instruments", []):
            instruments.append({"ticker": item["ticker"], "figi": item["figi"]})
        logging.info(f"Загружено акций: {len(instruments)}")
    except Exception as e:
        logging.error(f"Ошибка GetShares: {e}")

    try:
        resp = _call_api("InstrumentsService/GetCurrencies")
        for item in resp.get("instruments", []):
            instruments.append({"ticker": item["ticker"], "figi": item["figi"]})
        logging.info(f"Загружено валют: {len(instruments)}")
    except Exception as e:
        logging.error(f"Ошибка GetCurrencies: {e}")

    try:
        resp = _call_api("InstrumentsService/GetBonds")
        for item in resp.get("instruments", []):
            instruments.append({"ticker": item["ticker"], "figi": item["figi"]})
        logging.info(f"Загружено облигаций: {len(instruments)}")
    except Exception as e:
        logging.error(f"Ошибка GetBonds: {e}")

    try:
        resp = _call_api("InstrumentsService/GetEtfs")
        for item in resp.get("instruments", []):
            instruments.append({"ticker": item["ticker"], "figi": item["figi"]})
        logging.info(f"Загружено ETF: {len(instruments)}")
    except Exception as e:
        logging.error(f"Ошибка GetEtfs: {e}")

    _instruments_cache = instruments
    return instruments

def get_figi_by_ticker(ticker: str):
    if ticker in FIGI_CACHE:
        return FIGI_CACHE[ticker]

    logging.info(f"Запрос FIGI для {ticker}")
    instruments = _load_all_instruments()

    for inst in instruments:
        if inst["ticker"].upper() == ticker.upper():
            FIGI_CACHE[ticker] = inst["figi"]
            logging.info(f"Найден FIGI для {ticker}: {inst['figi']}")
            return inst["figi"]

    logging.warning(f"{ticker}: FIGI не найден")
    return None

def get_candles(figi: str, interval_key: str, days: int, ticker: str = None):
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
        resp = _call_api("MarketDataService/GetCandles", payload)  # <--- исправлено имя метода
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
