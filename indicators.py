import logging
import traceback

import pandas as pd
import ta


# --------------------------------------------------------
# Вспомогательные функции
# --------------------------------------------------------

def empty_signal():

    return {
        "signal": "HOLD",
        "score": 0,
        "score_buy": 0,
        "score_sell": 0,
        "trend": "UNKNOWN",
        "price": 0,
        "rsi": 0,
        "adx": 0,
        "stop": None,
        "take": None,
        "reasons": []
    }


def generate_signal(df: pd.DataFrame):

    try:

        # -----------------------------------------
        # Проверки
        # -----------------------------------------

        if df is None or df.empty:
            return empty_signal()

        if len(df) < 50:

            result = empty_signal()

            result["price"] = round(
                float(df["close"].iloc[-1]), 2
            )

            return result

        df = df.copy()

        # -----------------------------------------
        # RSI
        # -----------------------------------------

        df["rsi"] = ta.momentum.RSIIndicator(
            close=df["close"],
            window=14
        ).rsi()

        # -----------------------------------------
        # EMA
        # -----------------------------------------

        df["ema20"] = ta.trend.EMAIndicator(
            close=df["close"],
            window=20
        ).ema_indicator()

        df["ema50"] = ta.trend.EMAIndicator(
            close=df["close"],
            window=50
        ).ema_indicator()

        ema_long = 200 if len(df) >= 220 else 100

        df["ema200"] = ta.trend.EMAIndicator(
            close=df["close"],
            window=ema_long
        ).ema_indicator()

        # -----------------------------------------
        # MACD
        # -----------------------------------------

        macd = ta.trend.MACD(
            close=df["close"]
        )

        df["macd"] = macd.macd()

        df["macd_signal"] = macd.macd_signal()

        df["macd_hist"] = macd.macd_diff()

        # -----------------------------------------
        # ADX
        # -----------------------------------------

        adx = ta.trend.ADXIndicator(

            high=df["high"],
            low=df["low"],
            close=df["close"],
            window=14

        )

        df["adx"] = adx.adx()

        df["di_plus"] = adx.adx_pos()

        df["di_minus"] = adx.adx_neg()

        # -----------------------------------------
        # ATR
        # -----------------------------------------

        atr = ta.volatility.AverageTrueRange(

            high=df["high"],
            low=df["low"],
            close=df["close"],
            window=14

        )

        df["atr"] = atr.average_true_range()

        # -----------------------------------------
        # Bollinger
        # -----------------------------------------

        bb = ta.volatility.BollingerBands(

            close=df["close"],
            window=20,
            window_dev=2

        )

        df["bb_high"] = bb.bollinger_hband()

        df["bb_low"] = bb.bollinger_lband()

        df["bb_mid"] = bb.bollinger_mavg()

        # -----------------------------------------
        # Объем
        # -----------------------------------------

        df["volume_ma"] = (
            df["volume"]
            .rolling(20)
            .mean()
        )

        # -----------------------------------------
        # Очистка
        # -----------------------------------------

        df = df.bfill()

        df = df.dropna()

        if len(df) < 5:
            return empty_signal()

        last = df.iloc[-1]

        prev = df.iloc[-2]

        prev2 = df.iloc[-3]

        score_buy = 0

        score_sell = 0

        buy_reasons = []

        sell_reasons = []

        trend = "SIDEWAYS"

        # --------------------------------------------------
        # Определение глобального тренда
        # --------------------------------------------------

        ema_up = (
            last["ema20"] >
            last["ema50"] >
            last["ema200"]
        )

        ema_down = (
            last["ema20"] <
            last["ema50"] <
            last["ema200"]
        )

        ema20_rising = last["ema20"] > prev["ema20"]
        ema50_rising = last["ema50"] > prev["ema50"]

        ema20_falling = last["ema20"] < prev["ema20"]
        ema50_falling = last["ema50"] < prev["ema50"]

        if ema_up and ema20_rising and ema50_rising:

            trend = "UP"

            score_buy += 35

            buy_reasons.append(
                "Восходящий тренд EMA"
            )

        elif ema_down and ema20_falling and ema50_falling:

            trend = "DOWN"

            score_sell += 35

            sell_reasons.append(
                "Нисходящий тренд EMA"
            )

        # --------------------------------------------------
        # ADX
        # --------------------------------------------------

        if last["adx"] >= 25:

            if trend == "UP":

                score_buy += 15

                buy_reasons.append(
                    "Сильный тренд ADX"
                )

            elif trend == "DOWN":

                score_sell += 15

                sell_reasons.append(
                    "Сильный тренд ADX"
                )

        elif last["adx"] < 18:

            buy_reasons.append(
                "Флэт"
            )

            sell_reasons.append(
                "Флэт"
            )

        # --------------------------------------------------
        # DI+
        # --------------------------------------------------

        if last["di_plus"] > last["di_minus"]:

            score_buy += 10

            buy_reasons.append(
                "DI+ выше DI-"
            )

        elif last["di_minus"] > last["di_plus"]:

            score_sell += 10

            sell_reasons.append(
                "DI- выше DI+"
            )

        # --------------------------------------------------
        # MACD
        # --------------------------------------------------

        if (

            prev["macd"] <
            prev["macd_signal"]

            and

            last["macd"] >
            last["macd_signal"]

            and

            last["macd_hist"] >
            prev["macd_hist"]

        ):

            score_buy += 20

            buy_reasons.append(
                "MACD бычий крест"
            )

        elif (

            prev["macd"] >
            prev["macd_signal"]

            and

            last["macd"] <
            last["macd_signal"]

            and

            last["macd_hist"] <
            prev["macd_hist"]

        ):

            score_sell += 20

            sell_reasons.append(
                "MACD медвежий крест"
            )
        # --------------------------------------------------
        # RSI
        # --------------------------------------------------

        if trend == "UP":

            if 45 <= last["rsi"] <= 65:

                score_buy += 15

                buy_reasons.append(
                    "RSI поддерживает рост"
                )

            elif last["rsi"] < 35:

                score_buy += 10

                buy_reasons.append(
                    "RSI перепродан"
                )

            elif last["rsi"] > 75:

                score_sell += 10

                sell_reasons.append(
                    "Сильная перекупленность"
                )

        elif trend == "DOWN":

            if 35 <= last["rsi"] <= 55:

                score_sell += 15

                sell_reasons.append(
                    "RSI поддерживает снижение"
                )

            elif last["rsi"] > 70:

                score_sell += 10

                sell_reasons.append(
                    "RSI перекуплен"
                )

            elif last["rsi"] < 25:

                score_buy += 10

                buy_reasons.append(
                    "Сильная перепроданность"
                )

        # --------------------------------------------------
        # Bollinger Bands
        # --------------------------------------------------

        if last["close"] > last["bb_high"]:

            score_sell += 10

            sell_reasons.append(
                "Цена выше Bollinger"
            )

        elif last["close"] < last["bb_low"]:

            score_buy += 10

            buy_reasons.append(
                "Цена ниже Bollinger"
            )

        elif (

            last["close"] > last["bb_mid"]

            and

            trend == "UP"

        ):

            score_buy += 5

        elif (

            last["close"] < last["bb_mid"]

            and

            trend == "DOWN"

        ):

            score_sell += 5

        # --------------------------------------------------
        # Объем
        # --------------------------------------------------

        if last["volume_sma"] > 0:

            volume_ratio = (
                last["volume"] /
                last["volume_sma"]
            )

            if volume_ratio >= 1.5:

                if trend == "UP":

                    score_buy += 15

                    buy_reasons.append(
                        "Высокий объем"
                    )

                elif trend == "DOWN":

                    score_sell += 15

                    sell_reasons.append(
                        "Высокий объем"
                    )

            elif volume_ratio >= 1.2:

                if trend == "UP":

                    score_buy += 8

                elif trend == "DOWN":

                    score_sell += 8

        # --------------------------------------------------
        # Положение цены относительно EMA20
        # --------------------------------------------------

        if trend == "UP":

            if last["close"] > last["ema20"]:

                score_buy += 10

                buy_reasons.append(
                    "Цена выше EMA20"
                )

        elif trend == "DOWN":

            if last["close"] < last["ema20"]:

                score_sell += 10

                sell_reasons.append(
                    "Цена ниже EMA20"
                )

        # --------------------------------------------------
        # Импульс
        # --------------------------------------------------

        momentum = (
            last["close"] -
            df["close"].iloc[-6]
        ) / df["close"].iloc[-6] * 100

        if momentum > 3:

            score_buy += 10

            buy_reasons.append(
                "Положительный импульс"
            )

        elif momentum < -3:

            score_sell += 10

            sell_reasons.append(
                "Отрицательный импульс"
            )
                    # =====================================================
        # ФОРМИРОВАНИЕ СИГНАЛА
        # =====================================================

        signal = "HOLD"
        reasons = []

        threshold = 70

        if (
            score_buy >= threshold
            and score_buy > score_sell
        ):
            signal = "BUY"
            reasons = buy_reasons

        elif (
            score_sell >= threshold
            and score_sell > score_buy
        ):
            signal = "SELL"
            reasons = sell_reasons

        # -----------------------------------------------------

        stop = None
        take = None

        if signal == "BUY":

            stop = last["close"] - last["atr"] * 2.2
            take = last["close"] + last["atr"] * 4.5

        elif signal == "SELL":

            stop = last["close"] + last["atr"] * 2.2
            take = last["close"] - last["atr"] * 4.5

        score = max(score_buy, score_sell)

        return {

            "signal": signal,

            "score": int(score),

            "score_buy": int(score_buy),

            "score_sell": int(score_sell),

            "trend": trend,

            "price": round(float(last["close"]), 2),

            "rsi": round(float(last["rsi"]), 2),

            "adx": round(float(last["adx"]), 2),

            "stop": (
                round(float(stop), 2)
                if stop is not None
                else None
            ),

            "take": (
                round(float(take), 2)
                if take is not None
                else None
            ),

            "reasons": reasons
        }

    except Exception as e:

        logging.error(
            f"Ошибка indicators.py: {e}"
        )

        logging.error(
            traceback.format_exc()
        )

        return {

            "signal": "HOLD",

            "score": 0,

            "score_buy": 0,

            "score_sell": 0,

            "trend": "UNKNOWN",

            "price": 0,

            "rsi": 0,

            "adx": 0,

            "stop": None,

            "take": None,

            "reasons": []
        }
