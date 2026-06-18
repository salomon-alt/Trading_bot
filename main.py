import logging
import time
from datetime import datetime
from typing import List, Dict, Optional, Any

# Импорт из data_fetch – после того, как в нём выполнится установка SDK
from data_fetch import get_figi_by_ticker, get_candles, init_client, TOKEN
from indicators import generate_signal
from telegram_bot import send_signal
from database import init_db, save_signal
from signal_cache import is_duplicate

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

TICKERS: List[str] = [
    "SBER",
    "GAZP",
    "ROSN",
    "NVTK",
    "SPBE",
    "USD000UTSTOM",
    "CNYRUB_TOM",
    "GLDRUB_TOM",
    "SLVRUB_TOM",
]

SLEEP_SECONDS: int = 3600


def build_message(
    ticker: str,
    signal: str,
    score: int,
    price: float,
    rsi: float,
    adx: float,
    stop: Optional[float],
    take: Optional[float],
    reasons: List[str],
    rr: Optional[float] = None
) -> str:
    """Формирует текст сообщения с причинами и RR."""
    icon = "🟢" if signal == "BUY" else "🔴"
    msg = (
        f"{icon} {signal}\n\n"
        f"Тикер: {ticker}\n"
        f"Рейтинг: {score}/100\n\n"
        f"Цена: {price:.2f}\n"
        f"RSI: {rsi}\n"
        f"ADX: {adx}\n"
        f"Стоп: {stop}\n"
        f"Цель: {take}\n"
    )
    if rr is not None:
        msg += f"RR: {rr:.2f}\n"
    if reasons:
        msg += "\nПричины:\n"
        for r in reasons:
            msg += f"✓ {r}\n"
    msg += f"\n{datetime.now().strftime('%d.%m.%Y %H:%M')}"
    return msg


def analyze_ticker(ticker: str) -> Optional[Dict[str, Any]]:
    """Анализирует один тикер, возвращает сигнал или None."""
    figi = get_figi_by_ticker(ticker)
    if not figi:
        logging.warning(f"{ticker}: FIGI не найден")
        return None

    week_df = get_candles(figi, interval_key="week", days=1095)
    day_df = get_candles(figi, interval_key="day", days=365)

    logging.info(f"{ticker}: DAY={len(day_df)} WEEK={len(week_df)}")

    if week_df.empty or day_df.empty:
        return None

    week_signal = generate_signal(week_df)
    day_signal = generate_signal(day_df)

    logging.info(
        f"{ticker} | "
        f"DAY={day_signal['signal']} "
        f"score={day_signal['score']} | "
        f"WEEK={week_signal['signal']} "
        f"score={week_signal['score']}"
    )

    # Фильтры по недельному таймфрейму
    if day_signal["signal"] == "BUY":
        if week_signal["signal"] not in ("BUY", "HOLD"):
            logging.info(f"{ticker}: BUY не подтвержден (WEEK={week_signal['signal']})")
            return None
    elif day_signal["signal"] == "SELL":
        if week_signal["signal"] not in ("SELL", "HOLD"):
            logging.info(f"{ticker}: SELL не подтвержден (WEEK={week_signal['signal']})")
            return None
    else:
        logging.info(f"{ticker}: HOLD (score={day_signal['score']})")
        return None

    return {
        "ticker": ticker,
        **day_signal
    }


def main_loop() -> None:
    """Основной цикл анализа всех тикеров."""
    logging.info("=== Новый проход ===")
    signals: List[Dict[str, Any]] = []

    for ticker in TICKERS:
        try:
            result = analyze_ticker(ticker)
            if result:
                signals.append(result)
        except Exception as e:
            logging.exception(f"{ticker}: {e}")

    if not signals:
        logging.info("Подходящих сигналов не найдено")
        return

    signals.sort(key=lambda x: x["score"], reverse=True)

    for signal_data in signals:
        ticker = signal_data["ticker"]
        signal = signal_data["signal"]

        if is_duplicate(ticker, "DAY", signal):
            logging.info(f"{ticker}: дубликат сигнала")
            continue

        save_signal(
            ticker=ticker,
            timeframe="DAY",
            signal=signal,
            score=signal_data["score"],
            price=signal_data["price"],
            stop=signal_data["stop"],
            take=signal_data["take"]
        )

        msg = build_message(
            ticker=ticker,
            signal=signal,
            score=signal_data["score"],
            price=signal_data["price"],
            rsi=signal_data["rsi"],
            adx=signal_data["adx"],
            stop=signal_data["stop"],
            take=signal_data["take"],
            reasons=signal_data.get("reasons", []),
            rr=signal_data.get("rr")
        )

        send_signal(msg)
        logging.info(f"Отправлен сигнал: {ticker} {signal} ({signal_data['score']}/100)")


if __name__ == "__main__":
    init_db()
    # Инициализируем клиент Tinkoff один раз
    init_client(TOKEN)

    while True:
        try:
            main_loop()
        except Exception as e:
            logging.exception(e)
        logging.info(f"Сон {SLEEP_SECONDS // 60} минут")
        time.sleep(SLEEP_SECONDS)
