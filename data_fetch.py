import os
import subprocess
import sys
import logging
import pandas as pd
from datetime import datetime, timedelta
from dotenv import load_dotenv
from pandas import DataFrame
from figi_cache import FIGI_CACHE

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")

# -------------------------------------------------------------------
# 1. Установка официального SDK (если не установлен)
# -------------------------------------------------------------------
try:
    from tinkoff.invest import Client, CandleInterval
except ImportError:
    logging.warning("Устанавливаем официальный SDK из GitHub-архива (без зависимостей)...")
    subprocess.check_call([
        sys.executable, '-m', 'pip', 'install',
        '--no-cache-dir', '--no-deps',
        'https://github.com/Tinkoff/invest-python/archive/refs/heads/master.zip'
    ])
    from tinkoff.invest import Client, CandleInterval

# -------------------------------------------------------------------
# 2. Загрузка переменных окружения
# -------------------------------------------------------------------
load_dotenv()
TOKEN = os.getenv("TINKOFF_INVEST_API_TOKEN")
if not TOKEN:
    raise RuntimeError("TINKOFF_INVEST_API_TOKEN не задан в .env")
logging.info("TOKEN загружен")

# -------------------------------------------------------------------
# 3. Маппинг интервалов
# -------------------------------------------------------------------
INTERVAL_MAPPING = {
    "day": CandleInterval.CANDLE_INTERVAL_DAY,
    "week": CandleInterval.CANDLE_INTERVAL_WEEK,
    "4h": CandleInterval.CANDLE_INTERVAL_4_HOUR,
    "1h": CandleInterval.CANDLE_INTERVAL_HOUR,
}

# -------------------------------------------------------------------
# 4. Глобальный клиент
# -------------------------------------------------------------------
_client = None

def init_client(token: str):
    global _client
    if _client is None:
        logging.info("Инициализация клиента...")
        _client = Client(token)
        # ДИАГНОСТИКА: выводим все публичные атрибуты клиента
        logging.info("=== Доступные атрибуты клиента ===")
        attrs = [a for a in dir(_client) if not a.startswith('_')]
        for a in attrs:
            logging.info(f"  {a}")
        # Проверяем наличие instruments
        if hasattr(_client, 'instruments'):
            logging.info("Атрибут 'instruments' присутствует")
            logging.info(f"instruments содержит: {[a for a in dir(_client.instruments) if not a.startswith('_')]}")
        else:
            logging.warning("Атрибут 'instruments' отсутствует")
        # Проверяем наличие get_shares и т.п.
        for method in ['get_shares', 'get_currencies', 'get_etfs', 'get_bonds']:
            if hasattr(_client, method):
                logging.info(f"Метод {method} присутствует")
            else:
                logging.info(f"Метод {method} отсутствует")
        logging.info("=== Конец диагностики ===")
    return _client

# -------------------------------------------------------------------
# 5. Получение FIGI по тикеру
# -------------------------------------------------------------------
def get_figi_by_ticker(ticker: str):
    global _client
    if _client is None:
        raise RuntimeError("Клиент не инициализирован. Вызовите init_client()")

    if ticker in FIGI_CACHE:
        return FIGI_CACHE[ticker]

    logging.info(f"Запрос FIGI для {ticker}")
    instruments = []

    # Пробуем разные варианты
    if hasattr(_client, 'instruments'):
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
    else:
        logging.warning("client.instruments недоступен, пробуем альтернативные методы")
        # Альтернатива: если есть get_all_instruments или что-то подобное
        if hasattr(_client, 'get_all_instruments'):
            try:
                resp = _client.get_all_instruments()
                # структура может отличаться
                if hasattr(resp, 'instruments'):
                    instruments.extend(resp.instruments)
                    logging.info(f"Получено инструментов через get_all_instruments: {len(resp.instruments)}")
                else:
                    logging.warning("get_all_instruments вернул неожиданный ответ")
            except Exception as e:
                logging.error(f"Ошибка get_all_instruments: {e}")

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
# 6. Получение свечей
# -------------------------------------------------------------------
def get_candles(figi: str, interval_key: str, days: int, ticker: str = None):
    global _client
    if _client is None:
        raise RuntimeError("Клиент не инициализирован")

    interval = INTERVAL_MAPPING.get(interval_key)
    if not interval:
        raise ValueError(f"Неподдерживаемый интервал: {interval_key}")

    now = datetime.utcnow()
    from_time = now - timedelta(days=days)

    try:
        candles = _client.market_data.get_candles(
            figi=figi,
            from_=from_time,
            to=now,
            interval=interval,
        ).candles
    except Exception as e:
        logging.error(f"Ошибка при получении свечей для {figi}: {e}")
        return pd.DataFrame()

    if not candles:
        logging.warning(f"Нет свечей для {figi}")
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
