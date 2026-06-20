import os
import subprocess
import sys
import logging
import pandas as pd
from datetime import datetime, timedelta
from dotenv import load_dotenv
from figi_cache import FIGI_CACHE

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")

# -------------------------------------------------------------------
# 1. Установка официального SDK (если не установлен)
# -------------------------------------------------------------------
try:
    from tinkoff.invest import Client, CandleInterval
except ImportError:
    logging.warning("Официальный SDK не найден, устанавливаем...")
    subprocess.check_call([
        sys.executable, '-m', 'pip', 'install',
        '--no-cache-dir', '--no-deps',
        'tinkoff-investments'
    ])
    from tinkoff.invest import Client, CandleInterval

load_dotenv()
TOKEN = os.getenv("TINKOFF_INVEST_API_TOKEN")
if not TOKEN:
    raise RuntimeError("TINKOFF_INVEST_API_TOKEN не задан в .env")

# -------------------------------------------------------------------
# 2. Маппинг интервалов
# -------------------------------------------------------------------
INTERVAL_MAPPING = {
    "day": CandleInterval.CANDLE_INTERVAL_DAY,
    "week": CandleInterval.CANDLE_INTERVAL_WEEK,
    "4h": CandleInterval.CANDLE_INTERVAL_4_HOUR,
    "1h": CandleInterval.CANDLE_INTERVAL_HOUR,
}

_client = None

def init_client(token: str):
    global _client
    if _client is None:
        _client = Client(token)
        logging.info("Официальный клиент инициализирован")
    return _client

# -------------------------------------------------------------------
# 3. Получение FIGI по тикеру (с кэшированием)
# -------------------------------------------------------------------
def get_figi_by_ticker(ticker: str):
    global _client
    if _client is None:
        raise RuntimeError("Клиент не инициализирован. Вызовите init_client()")

    if ticker in FIGI_CACHE:
        return FIGI_CACHE[ticker]

    logging.info(f"Запрос FIGI для {ticker}")
    instruments = []
    try:
        resp = _client.instruments.shares()
        instruments.extend(resp.instruments)
        logging.info(f"Получено акций: {len(resp.instruments)}")
    except Exception as e:
        logging.error(f"Ошибка shares: {e}")

    try:
        resp = _client.instruments.currencies()
        instruments.extend(resp.instruments)
        logging.info(f"Получено валют: {len(resp.instruments)}")
    except Exception as e:
        logging.error(f"Ошибка currencies: {e}")

    try:
        resp = _client.instruments.etfs()
        instruments.extend(resp.instruments)
        logging.info(f"Получено ETF: {len(resp.instruments)}")
    except Exception as e:
        logging.error(f"Ошибка etfs: {e}")

    try:
        resp = _client.instruments.bonds()
        instruments.extend(resp.instruments)
        logging.info(f"Получено облигаций: {len(resp.instruments)}")
    except Exception as e:
        logging.error(f"Ошибка bonds: {e}")

    logging.info(f"Всего инструментов: {len(instruments)}")
    if instruments:
        for inst in instruments[:5]:
            logging.info(f"Пример: {inst.ticker} -> {inst.figi}")
    else:
        logging.warning("Нет ни одного инструмента!")

    for inst in instruments:
        if inst.ticker.upper() == ticker.upper():
            FIGI_CACHE[ticker] = inst.figi
            logging.info(f"Найден FIGI для {ticker}: {inst.figi}")
            return inst.figi

    logging.warning(f"{ticker}: FIGI не найден")
    return None

# -------------------------------------------------------------------
# 4. Получение свечей
# -------------------------------------------------------------------
def get_candles(figi: str, interval_key: str, days: int, ticker: str = None):
    global _client
    if _client is None:
        raise RuntimeError("Клиент не инициализирован")

    interval = INTERVAL_MAPPING.get(interval_key)
    if not interval:
        raise ValueError(f"Неподдерживаемый интервал: {interval_key}")

    # Пробуем получить свечи, постепенно уменьшая период при ошибке 400
    attempt_days = days
    last_error = None
    while attempt_days >= 1:
        now = datetime.utcnow()
        from_time = now - timedelta(days=attempt_days)
        try:
            candles = _client.market_data.get_candles(
                figi=figi,
                from_=from_time,
                to=now,
                interval=interval,
            ).candles
            if not candles:
                logging.warning(f"Нет свечей для {figi} за {attempt_days} дней")
                return pd.DataFrame()
            break
        except Exception as e:
            last_error = e
            if "400" in str(e) or "INVALID_ARGUMENT" in str(e):
                logging.warning(f"Ошибка 400 для {figi} с days={attempt_days}, уменьшаем до {attempt_days//2}")
                attempt_days = max(attempt_days // 2, 1)
                continue
            else:
                logging.error(f"Ошибка get_candles для {figi}: {e}")
                return pd.DataFrame()
    else:
        logging.error(f"Не удалось получить свечи для {figi} даже после уменьшения days. Последняя ошибка: {last_error}")
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
