import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional, List

from data_fetch import get_figi_by_ticker, get_candles, init_client, TOKEN
from indicators import generate_signal
from telegram_bot import send_signal
from database import init_db, save_signal
from signal_cache import is_duplicate
from tickers import TICKER_GROUPS, get_timeframes_for_ticker

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

SLEEP_SECONDS = 7200

TIMEZONE_OFFSET = 4
WORK_START_HOUR = 8
WORK_END_HOUR = 20

INTERVAL_DAYS = {
    "week": 730,
    "day": 365,
    "4h": 120,
    "1h": 30,
}


def is_working_hours():
    now_utc = datetime.now(timezone.utc)
    now_local = now_utc + timedelta(hours=TIMEZONE_OFFSET)

    return WORK_START_HOUR <= now_local.hour < WORK_END_HOUR


def seconds_until_work_start():
    now_utc = datetime.now(timezone.utc)
    now_local = now_utc + timedelta(hours=TIMEZONE_OFFSET)

    target = now_local.replace(
        hour=WORK_START_HOUR,
        minute=0,
        second=0,
        microsecond=0
    )

    if now_local.hour >= WORK_END_HOUR:
        target += timedelta(days=1)

    return int((target - now_local).total_seconds())


def build_message(
        ticker: str,
        signals: Dict[str, Dict[str, Any]]
):
    day = signals["day"]

    icon = "🟢" if day["signal"] == "BUY" else "🔴"

    text = (
        f"{icon} {day['signal']}\n\n"
        f"Тикер: {ticker}\n"
        f"Рейтинг: {day['score']}/100\n\n"
        f"Цена: {day['price']}\n"
        f"RSI: {day['rsi']}\n"
        f"ADX: {day['adx']}\n"
        f"Стоп: {day['stop']}\n"
        f"Цель: {day['take']}\n"
    )

    text += "\nТаймфреймы:\n"

    for tf in ["week", "day", "4h", "1h"]:
        if tf in signals:
            text += (
                f"{tf.upper()}: "
                f"{signals[tf]['signal']} "
                f"({signals[tf]['score']})\n"
            )

    if day["reasons"]:
        text += "\nПричины:\n"

        for reason in day["reasons"]:
            text += f"✓ {reason}\n"

    text += (
        f"\n"
        f"{datetime.now().strftime('%d.%m.%Y %H:%M')}"
    )

    return text


def analyze_ticker(
        ticker: str
) -> Optional[Dict[str, Any]]:

    figi = get_figi_by_ticker(ticker)

    if not figi:
        return None

    signals = {}

    for timeframe in get_timeframes_for_ticker(ticker):

        days = INTERVAL_DAYS.get(timeframe, 365)

        df = get_candles(
            figi,
            timeframe,
            days,
            ticker=ticker
        )

        if df.empty:
            logging.info(
                f"{ticker}: "
                f"{timeframe} данные не получены"
            )
            return None

        signals[timeframe] = generate_signal(df)

    day_signal = signals["day"]

    if day_signal["signal"] == "HOLD":
        return None

    for tf, sig in signals.items():

        if tf == "day":
            continue

        if (
                day_signal["signal"] == "BUY"
                and sig["signal"] == "SELL"
        ):
            return None

        if (
                day_signal["signal"] == "SELL"
                and sig["signal"] == "BUY"
        ):
            return None

    return {
        "ticker": ticker,
        "signals": signals
    }


def main_loop():

    logging.info("=== Новый проход ===")

    results = []

    all_tickers = []

    for tickers in TICKER_GROUPS.values():
        all_tickers.extend(tickers)

    for ticker in all_tickers:

        try:

            result = analyze_ticker(ticker)

            if result:
                results.append(result)

        except Exception as e:

            logging.exception(
                f"{ticker}: {e}"
            )

        time.sleep(2)

    if not results:

        logging.info(
            "Подходящих сигналов не найдено"
        )

        return

    results.sort(
        key=lambda x:
        x["signals"]["day"]["score"],
        reverse=True
    )

    for result in results:

        ticker = result["ticker"]

        signal = (
            result["signals"]["day"]["signal"]
        )

        if is_duplicate(
                ticker,
                "DAY",
                signal
        ):
            continue

        day = result["signals"]["day"]

        save_signal(
            ticker=ticker,
            timeframe="DAY",
            signal=signal,
            score=day["score"],
            price=day["price"],
            stop=day["stop"],
            take=day["take"]
        )

        send_signal(
            build_message(
                ticker,
                result["signals"]
            )
        )

        logging.info(
            f"Отправлен сигнал "
            f"{ticker} "
            f"{signal}"
        )

        time.sleep(2)


if __name__ == "__main__":

    init_db()

    init_client(TOKEN)

    while True:

        try:

            if is_working_hours():

                main_loop()

                logging.info(
                    f"Сон "
                    f"{SLEEP_SECONDS // 60} минут"
                )

                time.sleep(
                    SLEEP_SECONDS
                )

            else:

                wait = (
                    seconds_until_work_start()
                )

                logging.info(
                    f"Не рабочее время. "
                    f"Сон {wait // 60} минут"
                )

                time.sleep(wait)

        except Exception as e:

            logging.exception(e)

            time.sleep(60)
