import os
import logging
import time
import threading
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

_instruments_cache = None
_instruments_lock = threading.Lock()
_last_candle_request_time = 0.0
_candles_lock = threading.Lock()
_CANDLE_MIN_INTERVAL = 1.2  # Увеличено до 1.2 секунды между запросами свечей

def init_client(token: str):
    logging.info("REST API клиент инициализирован")
    return _session

def _call_api(method: str, data: dict = None, retries: int = 2) -> dict:
    url = BASE_URL + method
    for attempt in range(retries + 1):
        try:
            resp = _session.post(url, json=data or {})
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429:
                wait = 2 ** (attempt + 1)
                logging.warning(f"Ошибка 429. Ждём {wait} сек.")
                time.sleep(wait)
                continue
            raise
    raise Exception(f"Не удалось выполнить запрос после {retries} попыток")

def _load_all_instruments():
    global _instruments_cache
    if _instruments_cache is not None:
        return _instruments_cache
    with _instruments_lock:
        if _instruments_cache is not None:
            return _instruments_cache
        instruments = []
        for method in ["Shares", "Currencies", "Bonds", "Etfs"]:
            try:
                resp = _call_api(f"InstrumentsService/{method}")
                for item in resp.get("instruments", []):
                    instruments.append({
                        "ticker": item["ticker"],
                        "figi": item["figi"]
                    })
                logging.info(f"Загружено {method}: {len(instruments)}")
            except Exception as e:
                logging.error(f"Ошибка {method}: {e}")
        _instruments_cache = instruments
        return instruments

def get_figi_by_ticker(ticker: str):
    if ticker in FIGI_CACHE:
        return FIGI_CACHE[ticker]
    instruments = _load_all_instruments()
    for inst in instruments:
        if inst["ticker"].upper() == ticker.upper():
            FIGI_CACHE[ticker] = inst["figi"]
            return inst["figi"]
    logging.warning(f"{ticker}: FIGI не найден")
    return None

def get_candles(
        figi: str,
        interval_key: str,
        days: int,
        ticker: str = None
):

    interval_map = {
        "day": "DAY",
        "week": "WEEK",
        "4h": "4_HOUR",
        "1h": "HOUR"
    }

    interval = interval_map.get(interval_key)

    if not interval:
        logging.error(f"Неизвестный интервал {interval_key}")
        return pd.DataFrame()

    now = datetime.utcnow()

    from_time = now - timedelta(days=days)

    payload = {
        "figi": figi,
        "from": from_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "to": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "interval": interval
    }

    try:

        with _candles_lock:

            global _last_candle_request_time

            diff = time.time() - _last_candle_request_time

            if diff < 2:
                time.sleep(2 - diff)

            _last_candle_request_time = time.time()

        resp = _call_api(
            "MarketDataService/GetCandles",
            payload
        )

        candles = resp.get("candles", [])

        if not candles:
            logging.warning(
                f"{ticker}: нет свечей для {interval_key}"
            )
            return pd.DataFrame()

        rows = []

        for c in candles:

            rows.append({
                "time": c["time"],
                "open": float(c["open"]["units"]) + float(c["open"]["nano"]) / 1e9,
                "high": float(c["high"]["units"]) + float(c["high"]["nano"]) / 1e9,
                "low": float(c["low"]["units"]) + float(c["low"]["nano"]) / 1e9,
                "close": float(c["close"]["units"]) + float(c["close"]["nano"]) / 1e9,
                "volume": c["volume"]
            })

        df = pd.DataFrame(rows)

        if not df.empty:
            df.sort_values(
                "time",
                inplace=True
            )

        return df.reset_index(drop=True)

    except Exception as e:

        logging.error(
            f"{ticker} {interval_key}: {e}"
        )

        return pd.DataFrame()
