import os
import logging
import pandas as pd
from datetime import datetime, timedelta
from dotenv import load_dotenv
from figi_cache import FIGI_CACHE

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")

# -------------------------------------------------------------------
# 1. Импорт неофициального SDK
# -------------------------------------------------------------------
try:
    from tinkoff_invest import ProductionSession as Client
except ImportError:
    raise ImportError("Установите tinkoff-invest: pip install tinkoff-invest==1.0.5")

load_dotenv()
TOKEN = os.getenv("TINKOFF_INVEST_API_TOKEN")
if not TOKEN:
    raise RuntimeError("TINKOFF_INVEST_API_TOKEN не задан в .env")

# -------------------------------------------------------------------
# 2. Глобальный клиент (единый для всех запросов)
# -------------------------------------------------------------------
_client = None

def init_client(token: str):
    global _client
    if _client is None:
        _client = Client(token)
        logging.info("Клиент ProductionSession инициализирован")
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
        resp = _client.stocks()
        if hasattr(resp, 'instruments'):
            instruments.extend(resp.instruments)
            logging.info(f"Получено акций: {len(resp.instruments)}")
    except Exception as e:
        logging.error(f"Ошибка stocks: {e}")

    try:
        resp = _client.bonds()
        if hasattr(resp, 'instruments'):
            instruments.extend(resp.instruments)
            logging.info(f"Получено облигаций: {len(resp.instruments)}")
    except Exception as e:
        logging.error(f"Ошибка bonds: {e}")

    try:
        resp = _client.currencies()
        if hasattr(resp, 'instruments'):
            instruments.extend(resp.instruments)
            logging.info(f"Получено валют: {len(resp.instruments)}")
    except Exception as e:
        logging.error(f"Ошибка currencies: {e}")

    try:
        resp = _client.etfs()
        if hasattr(resp, 'instruments'):
            instruments.extend(resp.instruments)
            logging.info(f"Получено ETF: {len(resp.instruments)}")
    except Exception as e:
        logging.error(f"Ошибка etfs: {e}")

    logging.info(f"Всего инструментов собрано: {len(instruments)}")
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
# 4. Получение свечей (с автоматическим уменьшением периода при ошибке)
# -------------------------------------------------------------------
def get_candles(figi: str, interval_key: str, days: int, ticker: str = None):
    global _client
    if _client is None:
        raise RuntimeError("Клиент не инициализирован")

    # Маппинг интервалов для неофициального SDK
    interval_map = {
        "day": "day",
        "week": "week",
        "4h": "4hour",
        "1h": "hour"
    }
    interval = interval_map.get(interval_key)
    if not interval:
        raise ValueError(f"Неподдерживаемый интервал: {interval_key}")

    attempt_days = days
    last_error = None

    while attempt_days >= 1:
        now = datetime.utcnow()
        from_time = now - timedelta(days=attempt_days)
        from_str = from_time.isoformat()
        to_str = now.isoformat()

        try:
            resp = _client.get_candles(
                figi=figi,
                from_=from_str,
                to=to_str,
                interval=interval
            )
            candles = resp.payload.candles
            if not candles:
                logging.warning(f"Нет свечей для {figi} за {attempt_days} дней")
                return pd.DataFrame()
            break
        except Exception as e:
            last_error = e
            if "400" in str(e) or "InvalidArgument" in str(e):
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
