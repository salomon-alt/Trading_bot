import os
import time
import logging
import threading
from datetime import datetime, timedelta

import pandas as pd
import requests
from dotenv import load_dotenv

from figi_cache import FIGI_CACHE

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

load_dotenv()

TOKEN = os.getenv("TINKOFF_INVEST_API_TOKEN")

if not TOKEN:
    raise RuntimeError(
        "Не задан TINKOFF_INVEST_API_TOKEN"
    )

BASE_URL = (
    "https://invest-public-api.tinkoff.ru/rest/"
    "tinkoff.public.invest.api.contract.v1."
)

_session = requests.Session()

_session.headers.update({
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
    "Accept": "application/json"
})

_instruments_cache = None
_instruments_lock = threading.Lock()

_last_request_time = 0.0
_request_lock = threading.Lock()


def init_client(token: str):
    logging.info("REST API клиент инициализирован")
    return _session


def _call_api(method: str, payload=None):

    url = BASE_URL + method

    response = _session.post(
        url,
        json=payload or {},
        timeout=30
    )

    if response.status_code != 200:

        logging.error(f"URL: {url}")
        logging.error(f"REQUEST: {payload}")
        logging.error(f"STATUS: {response.status_code}")
        logging.error(response.text)

        response.raise_for_status()

    return response.json()


def _load_all_instruments():

    global _instruments_cache

    if _instruments_cache is not None:
        return _instruments_cache

    with _instruments_lock:

        if _instruments_cache is not None:
            return _instruments_cache

        instruments = []

        services = [
            "Shares",
            "Currencies",
            "Bonds",
            "Etfs"
        ]

        for service in services:

            try:

                result = _call_api(
                    f"InstrumentsService/{service}"
                )

                for item in result.get(
                    "instruments",
                    []
                ):

                    instruments.append({
                        "ticker": item["ticker"],
                        "figi": item["figi"]
                    })

                logging.info(
                    f"{service}: "
                    f"{len(result.get('instruments', []))} инструментов"
                )

            except Exception as e:

                logging.exception(
                    f"{service}: {e}"
                )

        _instruments_cache = instruments

        logging.info(
            f"Всего инструментов: {len(instruments)}"
        )

        return instruments


def get_figi_by_ticker(
    ticker: str
):

    ticker = ticker.upper()

    if ticker in FIGI_CACHE:
        return FIGI_CACHE[ticker]

    for instrument in _load_all_instruments():

        if instrument["ticker"].upper() == ticker:

            FIGI_CACHE[ticker] = instrument["figi"]

            return instrument["figi"]

    logging.warning(f"{ticker}: FIGI не найден")

    return None

def get_candles(
    figi: str,
    interval_key: str,
    days: int,
    ticker: str = ""
):

    interval_map = {
        "week": "CANDLE_INTERVAL_WEEK",
        "day": "CANDLE_INTERVAL_DAY",
        "4h": "CANDLE_INTERVAL_4_HOUR",
        "1h": "CANDLE_INTERVAL_HOUR"
    }

    interval = interval_map.get(interval_key)

    if interval is None:
        logging.error(f"Неизвестный интервал: {interval_key}")
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

        global _last_request_time

        with _request_lock:

            pause = 2 - (time.time() - _last_request_time)

            if pause > 0:
                time.sleep(pause)

            _last_request_time = time.time()

        result = _call_api(
            "MarketDataService/GetCandles",
            payload
        )

        candles = result.get("candles", [])

        if not candles:

            logging.warning(
                f"{ticker} {interval_key}: свечей нет"
            )

            return pd.DataFrame()

        rows = []

        for candle in candles:

            rows.append({

                "time": candle["time"],

                "open":
                    float(candle["open"]["units"])
                    + float(candle["open"]["nano"]) / 1e9,

                "high":
                    float(candle["high"]["units"])
                    + float(candle["high"]["nano"]) / 1e9,

                "low":
                    float(candle["low"]["units"])
                    + float(candle["low"]["nano"]) / 1e9,

                "close":
                    float(candle["close"]["units"])
                    + float(candle["close"]["nano"]) / 1e9,

                "volume":
                    float(candle.get("volume", 0))
            })

        df = pd.DataFrame(rows)

        if df.empty:
            return df

        for column in (
            "open",
            "high",
            "low",
            "close",
            "volume"
        ):
            df[column] = pd.to_numeric(
                df[column],
                errors="coerce"
            )

        df.dropna(inplace=True)

        if df.empty:
            return df

        df.sort_values(
            "time",
            inplace=True
        )

        df.reset_index(
            drop=True,
            inplace=True
        )

        logging.info(
            f"{ticker} {interval_key}: "
            f"{len(df)} свечей, "
            f"цена={df.iloc[-1]['close']:.2f}"
        )

        return df

    except requests.exceptions.Timeout:

        logging.error(
            f"{ticker} {interval_key}: таймаут"
        )

    except requests.exceptions.RequestException as e:

        logging.error(
            f"{ticker} {interval_key}: HTTP ошибка {e}"
        )

    except Exception as e:

        logging.exception(
            f"{ticker} {interval_key}: {e}"
        )

    return pd.DataFrame()
