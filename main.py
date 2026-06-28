import logging
import time

from datetime import datetime
from datetime import timedelta
from datetime import timezone

from typing import Dict
from typing import Any
from typing import Optional

from data_fetch import (
    get_figi_by_ticker,
    get_candles,
    init_client,
    TOKEN
)

from indicators import generate_signal

from telegram_bot import send_signal

from database import (
    init_db,
    save_signal
)

from signal_cache import is_duplicate

from tickers import (
    TICKER_GROUPS,
    get_timeframes_for_ticker
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

SLEEP_SECONDS = 7200

TIMEZONE_OFFSET = 4

WORK_START_HOUR = 8
WORK_END_HOUR = 20

INTERVAL_DAYS = {

    "week": 365,

    "day": 180,

    "4h": 60,

    "1h": 14

}

# ==========================================================
# Веса таймфреймов
# ==========================================================

TIMEFRAME_WEIGHTS = {

    "week": 40,

    "day": 30,

    "4h": 20,

    "1h": 10

}

# ==========================================================
# Минимальная уверенность
# ==========================================================

MIN_TOTAL_SCORE = 60

MIN_ADX_WEEK = 20

MIN_DAY_SCORE = 60

# ==========================================================
# Рабочее время
# ==========================================================


def is_working_hours():

    now_utc = datetime.now(timezone.utc)

    now_local = (
        now_utc +
        timedelta(hours=TIMEZONE_OFFSET)
    )

    return (
        WORK_START_HOUR
        <= now_local.hour <
        WORK_END_HOUR
    )


def seconds_until_work_start():

    now_utc = datetime.now(timezone.utc)

    now_local = (
        now_utc +
        timedelta(hours=TIMEZONE_OFFSET)
    )

    target = now_local.replace(

        hour=WORK_START_HOUR,

        minute=0,

        second=0,

        microsecond=0

    )

    if now_local.hour >= WORK_END_HOUR:

        target += timedelta(days=1)

    return int(

        (
            target -
            now_local
        ).total_seconds()

    )

# ==========================================================
# Звезды
# ==========================================================


def stars(score):

    if score >= 90:

        return "★★★★★"

    if score >= 75:

        return "★★★★☆"

    if score >= 60:

        return "★★★☆☆"

    if score >= 40:

        return "★★☆☆☆"

    return "★☆☆☆☆"


# ==========================================================
# Расчет общей уверенности
# ==========================================================


def calculate_total_score(signals):

    buy = 0

    sell = 0

    for tf, weight in TIMEFRAME_WEIGHTS.items():

        if tf not in signals:

            continue

        sig = signals[tf]

        if sig["signal"] == "BUY":

            buy += weight

        elif sig["signal"] == "SELL":

            sell += weight

    direction = "HOLD"

    score = max(buy, sell)

    if buy > sell:

        direction = "BUY"

    elif sell > buy:

        direction = "SELL"

    return {

        "signal": direction,

        "score": score,

        "buy": buy,

        "sell": sell

    }

# ==========================================================
# Анализ инструмента
# ==========================================================

def analyze_ticker(
        ticker: str
) -> Optional[Dict[str, Any]]:

    figi = get_figi_by_ticker(ticker)

    if not figi:

        logging.warning(
            f"{ticker}: FIGI не найден"
        )

        return None

    signals = {}

    # ---------------------------------------
    # Получаем сигналы всех таймфреймов
    # ---------------------------------------

    for timeframe in get_timeframes_for_ticker(ticker):

        days = INTERVAL_DAYS.get(
            timeframe,
            90
        )

        df = get_candles(
            figi,
            timeframe,
            days,
            ticker=ticker
        )

        if df.empty:

            logging.info(
                f"{ticker}: нет данных {timeframe}"
            )

            return None

        signal = generate_signal(df)

        signals[timeframe] = signal

        logging.info(

            f"{ticker} "

            f"{timeframe}: "

            f"{signal['signal']} "

            f"score={signal['score']}"

        )

    # ---------------------------------------
    # Проверяем наличие всех ТФ
    # ---------------------------------------

    required = [
        "week",
        "day",
        "4h",
        "1h"
    ]

    for tf in required:

        if tf not in signals:

            logging.info(
                f"{ticker}: отсутствует {tf}"
            )

            return None

    week = signals["week"]

    day = signals["day"]

    h4 = signals["4h"]

    h1 = signals["1h"]

    # ---------------------------------------
    # Если Day HOLD —
    # инструмент сразу отбрасываем
    # ---------------------------------------

    if day["signal"] == "HOLD":

        logging.info(

            f"{ticker}: "

            f"DAY = HOLD"

        )

        return None

    # ---------------------------------------
    # Недельный график должен иметь
    # выраженный тренд
    # ---------------------------------------

    if week["adx"] < MIN_ADX_WEEK:

        logging.info(

            f"{ticker}: "

            f"Week ADX={week['adx']} "

            f"< {MIN_ADX_WEEK}"

        )

        return None

    # ---------------------------------------
    # Дневной сигнал должен быть сильным
    # ---------------------------------------

    if day["score"] < MIN_DAY_SCORE:

        logging.info(

            f"{ticker}: "

            f"Day score "

            f"{day['score']}"

        )

        return None

    # =====================================================
    # Согласование таймфреймов
    # =====================================================

    # Week имеет высший приоритет.
    # Если Week уже имеет направление,
    # Day обязан совпадать.

    if (
        week["signal"] != "HOLD"
        and
        week["signal"] != day["signal"]
    ):

        logging.info(

            f"{ticker}: "

            f"Week={week['signal']} "

            f"Day={day['signal']}"

        )

        return None

    # ---------------------------------------------
    # 4H должен подтверждать Day.
    # HOLD допускается.
    # ---------------------------------------------

    if (
        h4["signal"] != "HOLD"
        and
        h4["signal"] != day["signal"]
    ):

        logging.info(

            f"{ticker}: "

            f"4H против Day"

        )

        return None

    # ---------------------------------------------
    # 1H используется как подтверждение
    # точки входа.
    # ---------------------------------------------

    if (
        h1["signal"] != "HOLD"
        and
        h1["signal"] != day["signal"]
    ):

        logging.info(

            f"{ticker}: "

            f"1H против Day"

        )

        return None

    # =====================================================
    # Расчет общей уверенности
    # =====================================================

    total = calculate_total_score(
        signals
    )

    logging.info(

        f"{ticker}: "

        f"BUY={total['buy']} "

        f"SELL={total['sell']} "

        f"TOTAL={total['score']}"

    )

    # ---------------------------------------------
    # Направление должно совпадать
    # ---------------------------------------------

    if total["signal"] != day["signal"]:

        logging.info(

            f"{ticker}: "

            f"Несогласованность"

        )

        return None

    # ---------------------------------------------
    # Слабые сигналы не отправляем
    # ---------------------------------------------

    if total["score"] < MIN_TOTAL_SCORE:

        logging.info(

            f"{ticker}: "

            f"Слабый сигнал "

            f"{total['score']}"

        )

        return None

    logging.info(

        f"{ticker}: "

        f"Прошел фильтр "

        f"{total['score']}/100"

    )

    return {

        "ticker": ticker,

        "signals": signals,

        "rating": total["score"],

        "direction": total["signal"],

        "stars": stars(
            total["score"]
        )

    }

# ==========================================================
# Формирование сообщения Telegram
# ==========================================================

def build_message(
        ticker: str,
        result: Dict[str, Any]
):

    signals = result["signals"]

    day = signals["day"]

    direction = result["direction"]

    rating = result["rating"]

    stars_text = result["stars"]

    if direction == "BUY":

        icon = "🟢"

    elif direction == "SELL":

        icon = "🔴"

    else:

        icon = "⚪"

    text = (
        f"{icon} <b>{direction}</b>\n\n"
        f"📈 <b>{ticker}</b>\n\n"
        f"⭐ {stars_text}\n"
        f"🎯 Уверенность: <b>{rating}%</b>\n\n"
    )

    text += (
        f"💰 Цена: {day['price']}\n"
        f"📊 RSI: {day['rsi']}\n"
        f"📈 ADX: {day['adx']}\n"
    )

    if day["stop"]:

        text += (
            f"🛑 Stop: {day['stop']}\n"
        )

    if day["take"]:

        text += (
            f"🎯 Take: {day['take']}\n"
        )

    text += "\n"

    text += (
        "──────────────\n"
        "Таймфреймы\n"
        "──────────────\n"
    )

    order = [
        "week",
        "day",
        "4h",
        "1h"
    ]

    names = {

        "week": "Week",

        "day": "Day",

        "4h": "4H",

        "1h": "1H"

    }

    for tf in order:

        s = signals[tf]

        if s["signal"] == "BUY":

            emoji = "🟢"

        elif s["signal"] == "SELL":

            emoji = "🔴"

        else:

            emoji = "⚪"

        text += (
            f"{emoji} "
            f"{names[tf]}  "
            f"{s['signal']}  "
            f"({s['score']})\n"
        )

    if day["reasons"]:

        text += "\n"

        text += (
            "Причины сигнала\n"
        )

        for reason in day["reasons"]:

            text += (
                f"✔ {reason}\n"
            )

    text += "\n"

    text += (
        datetime.now().strftime(
            "%d.%m.%Y %H:%M"
        )
    )

    return text

# ==========================================================
# Основной цикл анализа
# ==========================================================

def main_loop():

    logging.info(
        "=== Новый проход ==="
    )

    results = []

    all_tickers = []

    for tickers in TICKER_GROUPS.values():

        all_tickers.extend(tickers)

    logging.info(
        f"Всего тикеров: {len(all_tickers)}"
    )

    # -------------------------------------
    # Анализируем все инструменты
    # -------------------------------------

    for ticker in all_tickers:

        try:

            logging.info(
                f"Анализ {ticker}"
            )

            result = analyze_ticker(
                ticker
            )

            if result:

                results.append(
                    result
                )

        except Exception:

            logging.exception(
                ticker
            )

        time.sleep(2)

    logging.info(
        f"Подходящих: {len(results)}"
    )

    if not results:

        logging.info(
            "Сигналов нет"
        )

        return

    # -------------------------------------
    # Сортировка по общей уверенности
    # -------------------------------------

    results.sort(

        key=lambda x:
        x["rating"],

        reverse=True

    )

    # -------------------------------------
    # Отправляем только лучшие
    # -------------------------------------

    MAX_SIGNALS = 8

    sent = 0

    for result in results:

        if sent >= MAX_SIGNALS:

            break

        ticker = result["ticker"]

        signal = result["direction"]

        day = result["signals"]["day"]

        if is_duplicate(

                ticker,

                "DAY",

                signal

        ):

            logging.info(

                f"{ticker}: "

                f"дубликат"

            )

            continue

        save_signal(

            ticker=ticker,

            timeframe="DAY",

            signal=signal,

            score=result["rating"],

            price=day["price"],

            stop=day["stop"],

            take=day["take"]

        )

        send_signal(

            build_message(

                ticker,

                result

            )

        )

        sent += 1

        logging.info(

            f"Отправлен "

            f"{ticker} "

            f"{signal} "

            f"{result['rating']}%"

        )

        time.sleep(2)

    logging.info(

        f"Отправлено: "

        f"{sent}"

    )

# ==========================================================
# Итоговый рейтинг сигнала
# ==========================================================

def calculate_total_score(
        signals: Dict[str, Dict[str, Any]]
):

    weights = {

        "week": 0.40,

        "day": 0.30,

        "4h": 0.20,

        "1h": 0.10

    }

    buy = 0.0
    sell = 0.0

    for tf, weight in weights.items():

        s = signals[tf]

        if s["signal"] == "BUY":

            buy += s["score"] * weight

        elif s["signal"] == "SELL":

            sell += s["score"] * weight

    buy = round(buy)
    sell = round(sell)

    if buy > sell:

        signal = "BUY"
        score = buy

    elif sell > buy:

        signal = "SELL"
        score = sell

    else:

        signal = "HOLD"
        score = 0

    return {

        "signal": signal,

        "buy": buy,

        "sell": sell,

        "score": score

    }


# ==========================================================
# Звезды качества сигнала
# ==========================================================

def stars(score: int):

    if score >= 90:
        return "★★★★★"

    if score >= 80:
        return "★★★★☆"

    if score >= 70:
        return "★★★☆☆"

    if score >= 60:
        return "★★☆☆☆"

    return "★☆☆☆☆"


