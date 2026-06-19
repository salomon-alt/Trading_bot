print("=== main.py START ===", flush=True)
import logging
import time
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional, Any
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
from data_fetch import get_figi_by_ticker, get_candles, init_client, TOKEN
from indicators import generate_signal
from telegram_bot import send_signal
from database import init_db, save_signal
from signal_cache import is_duplicate
from tickers import TICKER_GROUPS, get_timeframes_for_ticker

# -------------------------------------------------------------------
# НАСТРОЙКА ЛОГГИРОВАНИЯ
# -------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

# ОТЛАДОЧНЫЕ СООБЩЕНИЯ (будут видны в логах)
logging.info("=== main.py запущен ===")
logging.info(f"TOKEN из data_fetch: {'✅ УСТАНОВЛЕН' if TOKEN else '❌ НЕ УСТАНОВЛЕН'}")

# -------------------------------------------------------------------
# КОНСТАНТЫ
# -------------------------------------------------------------------
SLEEP_SECONDS: int = 7200   # 2 часа
MAX_WORKERS: int = 8

TIMEZONE_OFFSET = 4
WORK_START_HOUR = 8
WORK_END_HOUR = 20

INTERVAL_DAYS = {
    "week": 1095,
    "day": 365,
    "4h": 90,
    "1h": 7,
}

# -------------------------------------------------------------------
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ (рабочее время)
# -------------------------------------------------------------------
def is_working_hours() -> bool:
    now_utc = datetime.now(timezone.utc)
    now_local = now_utc + timedelta(hours=TIMEZONE_OFFSET)
    hour = now_local.hour
    return WORK_START_HOUR <= hour < WORK_END_HOUR

def seconds_until_work_start() -> int:
    now_utc = datetime.now(timezone.utc)
    now_local = now_utc + timedelta(hours=TIMEZONE_OFFSET)
    target = now_local.replace(hour=WORK_START_HOUR, minute=0, second=0, microsecond=0)
    if now_local.hour >= WORK_END_HOUR:
        target += timedelta(days=1)
    delta = target - now_local
    return max(0, int(delta.total_seconds()))

# -------------------------------------------------------------------
# ФУНКЦИЯ ФОРМИРОВАНИЯ СООБЩЕНИЯ
# -------------------------------------------------------------------
def build_message(
    ticker: str,
    signals: Dict[str, Dict[str, Any]],
    main_timeframe: str = "day"
) -> str:
    main_sig = signals[main_timeframe]
    icon = "🟢" if main_sig["signal"] == "BUY" else "🔴"

    msg = (
        f"{icon} {main_sig['signal']}\n\n"
        f"Тикер: {ticker}\n"
        f"Рейтинг: {main_sig['score']}/100\n\n"
        f"Цена: {main_sig['price']:.2f}\n"
        f"RSI: {main_sig['rsi']}\n"
        f"ADX: {main_sig['adx']}\n"
        f"Стоп: {main_sig['stop']}\n"
        f"Цель: {main_sig['take']}\n"
    )

    if main_sig.get("rr") is not None:
        msg += f"RR: {main_sig['rr']:.2f}\n"

    msg += f"\nТаймфреймы:\n"
    order = {"week": 0, "day": 1, "4h": 2, "1h": 3}
    for tf in sorted(signals.keys(), key=lambda x: order.get(x, 99)):
        sig = signals[tf]
        label = {
            "week": "📅 WEEK (долгосрочный)",
            "day": "📊 DAY (среднесрочный)",
            "4h": "⏰ 4H (среднесрочный)",
            "1h": "🕐 1H (краткосрочный)"
        }.get(tf, tf)
        msg += f"{label}: {sig['signal']} ({sig['score']})\n"

    msg += f"\nИтоговый сигнал: {main_timeframe.upper()} – подтверждён всеми таймфреймами"

    if main_sig.get("reasons"):
        msg += "\n\nПричины:\n"
        for r in main_sig["reasons"]:
            msg += f"✓ {r}\n"

    msg += f"\n{datetime.now().strftime('%d.%m.%Y %H:%M')}"
    return msg

# -------------------------------------------------------------------
# БЕЗОПАСНОЕ ПОЛУЧЕНИЕ СВЕЧЕЙ (с повторными попытками)
# -------------------------------------------------------------------
def safe_get_candles(figi: str, interval_key: str, days: int, ticker: str, max_retries: int = 2) -> Optional[pd.DataFrame]:
    attempt_days = days
    for attempt in range(max_retries + 1):
        try:
            df = get_candles(figi, interval_key, attempt_days, ticker=ticker)
            return df
        except Exception as e:
            logging.warning(f"Ошибка при получении свечей для {figi} (попытка {attempt+1}): {e}")
            if attempt == max_retries:
                logging.error(f"Не удалось получить свечи для {figi} после {max_retries} попыток")
                return None
            attempt_days = max(attempt_days // 2, 1)
            continue
    return None

# -------------------------------------------------------------------
# АНАЛИЗ ОДНОГО ТИКЕРА
# -------------------------------------------------------------------
def analyze_ticker(ticker: str) -> Optional[Dict[str, Any]]:
    figi = get_figi_by_ticker(ticker)
    if not figi:
        logging.warning(f"{ticker}: FIGI не найден")
        return None

    timeframes = get_timeframes_for_ticker(ticker)
    if not timeframes:
        return None

    all_signals = {}
    for tf in timeframes:
        days = INTERVAL_DAYS.get(tf, 365)
        df = safe_get_candles(figi, tf, days, ticker)
        if df is None or df.empty:
            logging.info(f"{ticker}: {tf} – данные не загружены")
            return None
        signal = generate_signal(df)
        all_signals[tf] = signal

    log_parts = [f"{tf}={all_signals[tf]['signal']} {all_signals[tf]['score']}" for tf in timeframes]
    logging.info(f"{ticker}: {' | '.join(log_parts)}")

    if "day" not in all_signals:
        logging.warning(f"{ticker}: нет дневного таймфрейма")
        return None

    day_signal = all_signals["day"]
    day_sig = day_signal["signal"]

    if day_sig == "HOLD":
        logging.info(f"{ticker}: HOLD (score={day_signal['score']})")
        return None

    for tf, sig in all_signals.items():
        if tf == "day":
            continue
        if day_sig == "BUY" and sig["signal"] == "SELL":
            logging.info(f"{ticker}: BUY не подтверждён ({tf}={sig['signal']})")
            return None
        if day_sig == "SELL" and sig["signal"] == "BUY":
            logging.info(f"{ticker}: SELL не подтверждён ({tf}={sig['signal']})")
            return None

    return {
        "ticker": ticker,
        "signals": all_signals,
        "main_timeframe": "day"
    }

# -------------------------------------------------------------------
# ОСНОВНОЙ ЦИКЛ
# -------------------------------------------------------------------
def main_loop() -> None:
    logging.info("=== Новый проход ===")
    results: List[Dict[str, Any]] = []

    all_tickers = []
    for group, tickers in TICKER_GROUPS.items():
        all_tickers.extend(tickers)

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_ticker = {
            executor.submit(analyze_ticker, ticker): ticker
            for ticker in all_tickers
        }

        for future in as_completed(future_to_ticker):
            ticker = future_to_ticker[future]
            try:
                result = future.result()
                if result:
                    results.append(result)
            except Exception as e:
                logging.exception(f"{ticker}: ошибка в потоке: {e}")

    if not results:
        logging.info("Подходящих сигналов не найдено")
        return

    results.sort(key=lambda x: x["signals"]["day"]["score"], reverse=True)

    for data in results:
        ticker = data["ticker"]
        day_sig = data["signals"]["day"]["signal"]

        if is_duplicate(ticker, "DAY", day_sig):
            logging.info(f"{ticker}: дубликат сигнала (кэш)")
            continue

        save_signal(
            ticker=ticker,
            timeframe="DAY",
            signal=day_sig,
            score=data["signals"]["day"]["score"],
            price=data["signals"]["day"]["price"],
            stop=data["signals"]["day"]["stop"],
            take=data["signals"]["day"]["take"]
        )

        msg = build_message(
            ticker=ticker,
            signals=data["signals"],
            main_timeframe="day"
        )

        send_signal(msg)
        logging.info(f"Отправлен сигнал: {ticker} {day_sig} (DAY score={data['signals']['day']['score']})")

# -------------------------------------------------------------------
# ТОЧКА ВХОДА
# -------------------------------------------------------------------
if __name__ == "__main__":
    if not TOKEN:
        raise RuntimeError("TINKOFF_INVEST_API_TOKEN не задан в .env")

    init_db()
    logging.info("=== Вызываем init_client ===")
    init_client(TOKEN)
    logging.info("=== init_client завершен ===")

    while True:
        try:
            if is_working_hours():
                main_loop()
                logging.info(f"Сон {SLEEP_SECONDS // 60} минут до следующего прохода")
                time.sleep(SLEEP_SECONDS)
            else:
                wait_seconds = seconds_until_work_start()
                wait_minutes = wait_seconds // 60
                logging.info(f"Не рабочее время (с 20:00 до 8:00). Сон {wait_minutes} минут до 8:00.")
                time.sleep(wait_seconds)
        except Exception as e:
            logging.exception(e)
            time.sleep(60)
