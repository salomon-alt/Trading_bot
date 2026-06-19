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
_candles_lock = threading.Lock()        # Для синхронизации запросов свечей
_last_candle_request_time = 0.0         # Время последнего запроса
_CANDLE_REQUEST_MIN_INTERVAL = 0.5      # Минимальный интервал между запросами (сек)

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
                wait = 2 ** (attempt + 1)
                logging.warning(f"Ошибка 429 (слишком много запросов). Ждём {wait} секунд...")
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
        try:
            resp = _call_api("InstrumentsService/Shares")
            for item in resp.get("instruments", []):
                instruments.append({"ticker": item["ticker"], "figi": item["figi"]})
            logging.info(f"Загружено акций: {len(instruments)}")
        except Exception as e:
            logging.error(f"Ошибка Shares: {e}")

        try:
            resp = _call_api("InstrumentsService/Currencies")
            for item in resp.get("instruments", []):
                instruments.append({"ticker": item["ticker"], "figi": item["figi"]})
            logging.info(f"Загружено валют: {len(instruments)}")
        except Exception as e:
            logging.error(f"Ошибка Currencies: {e}")

        try:
            resp = _call_api("InstrumentsService/Bonds")
            for item in resp.get("instruments", []):
                instruments.append({"ticker": item["ticker"], "figi": item["figi"]})
            logging.info(f"Загружено облигаций: {len(instruments)}")
        except Exception as e:
            logging.error(f"Ошибка Bonds: {e}")

        try:
            resp = _call_api("InstrumentsService/Etfs")
            for item in resp.get("instruments", []):
                instruments.append({"ticker": item["ticker"], "figi": item["figi"]})
            logging.info(f"Загружено ETF: {len(instruments)}")
        except Exception as e:
            logging.error(f"Ошибка Etfs: {e}")

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
    global _last_candle_request_time

    interval_map = {
        "day": "DAY",
        "week": "WEEK",
        "4h": "4_HOUR",
        "1h": "HOUR"
    }
    interval = interval_map.get(interval_key)
    if not interval:
        raise ValueError(f"Неподдерживаемый интервал: {interval_key}")

    attempt_days = days
    last_error = None

    # Ограничиваем частоту запросов к свечам
    with _candles_lock:
        now_time = time.time()
        time_since_last = now_time - _last_candle_request_time
        if time_since_last < _CANDLE_REQUEST_MIN_INTERVAL:
            sleep_time = _CANDLE_REQUEST_MIN_INTERVAL - time_since_last
            logging.info(f"Пауза {sleep_time:.2f} сек для соблюдения лимита запросов к свечам")
            time.sleep(sleep_time)
        _last_candle_request_time = time.time()

    while attempt_days >= 1:
        now = datetime.utcnow()
        from_time = now - timedelta(days=attempt_days)
        from_str = from_time.strftime("%Y-%m-%dT%H:%M:%SZ")
        to_str = now.strftime("%Y-%m-%dT%H:%M:%SZ")
        payload = {"figi": figi, "from": from_str, "to": to_str, "interval": interval}
        try:
            resp = _call_api("MarketDataService/GetCandles", payload)
            candles = resp.get("candles", [])
            if not candles:
                logging.warning(f"Нет свечей для {figi} за {attempt_days} дней")
                return pd.DataFrame()
            break
        except Exception as e:
            last_error = e
            if "400" in str(e):
                logging.warning(f"Ошибка 400 для {figi} с days={attempt_days}, уменьшаем до {attempt_days//2}")
                attempt_days = max(attempt_days // 2, 1)
                continue
            else:
                logging.error(f"Ошибка GetCandles для {figi}: {e}")
                return pd.DataFrame()
    else:
        logging.error(f"Не удалось получить свечи для {figi} даже после уменьшения days. Последняя ошибка: {last_error}")
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
