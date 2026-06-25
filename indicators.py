import logging
import traceback

import pandas as pd
import ta


def generate_signal(df: pd.DataFrame):

    try:

        if df.empty:
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

        if len(df) < 30:

            return {
                "signal": "HOLD",
                "score": 0,
                "score_buy": 0,
                "score_sell": 0,
                "trend": "UNKNOWN",
                "price": round(float(df["close"].iloc[-1]), 2),
                "rsi": 0,
                "adx": 0,
                "stop": None,
                "take": None,
                "reasons": []
            }

        df = df.copy()

        df["rsi"] = ta.momentum.RSIIndicator(
            close=df["close"],
            window=14
        ).rsi()

        macd = ta.trend.MACD(
            close=df["close"]
        )

        df["macd"] = macd.macd()
        df["macd_signal"] = macd.macd_signal()

        ema_long = 200 if len(df) >= 200 else 50

        df["ema50"] = ta.trend.EMAIndicator(
            close=df["close"],
            window=50
        ).ema_indicator()

        df["ema_long"] = ta.trend.EMAIndicator(
            close=df["close"],
            window=ema_long
        ).ema_indicator()

        df["adx"] = ta.trend.ADXIndicator(
            high=df["high"],
            low=df["low"],
            close=df["close"],
            window=14
        ).adx()

        df["atr"] = ta.volatility.AverageTrueRange(
            high=df["high"],
            low=df["low"],
            close=df["close"],
            window=14
        ).average_true_range()

        df["volume_sma"] = (
            df["volume"]
            .rolling(20)
            .mean()
        )

        bb = ta.volatility.BollingerBands(
            close=df["close"],
            window=20,
            window_dev=2
        )

        df["bb_high"] = bb.bollinger_hband()
        df["bb_low"] = bb.bollinger_lband()
        df["bb_mid"] = bb.bollinger_mavg()

        df = df.bfill()
        df = df.dropna()

        if len(df) < 2:

            return {
                "signal": "HOLD",
                "score": 0,
                "score_buy": 0,
                "score_sell": 0,
                "trend": "UNKNOWN",
                "price": round(float(df["close"].iloc[-1]), 2),
                "rsi": 0,
                "adx": 0,
                "stop": None,
                "take": None,
                "reasons": []
            }

        last = df.iloc[-1]
        prev = df.iloc[-2]

        score_buy = 0
        score_sell = 0

        buy_reasons = []
        sell_reasons = []

        trend = "SIDEWAYS"

        if last["ema50"] > last["ema_long"]:

            trend = "UP"

            score_buy += 25
            buy_reasons.append(
                "EMA50 выше EMA"
            )

        else:

            trend = "DOWN"

            score_sell += 25
            sell_reasons.append(
                "EMA50 ниже EMA"
            )

        if (
                prev["macd"] < prev["macd_signal"]
                and
                last["macd"] > last["macd_signal"]
        ):

            score_buy += 25
            buy_reasons.append(
                "MACD бычий крест"
            )

        if (
                prev["macd"] > prev["macd_signal"]
                and
                last["macd"] < last["macd_signal"]
        ):

            score_sell += 25
            sell_reasons.append(
                "MACD медвежий крест"
            )

        if 35 <= last["rsi"] <= 65:

            score_buy += 15
            buy_reasons.append(
                "RSI нейтральный"
            )

        if last["rsi"] >= 70:

            score_sell += 15
            sell_reasons.append(
                "RSI перекуплен"
            )

        if last["adx"] > 20:

            if trend == "UP":

                score_buy += 15
                buy_reasons.append(
                    "Сильный тренд"
                )

            else:

                score_sell += 15
                sell_reasons.append(
                    "Сильный тренд"
                )

        if (
                pd.notna(last["volume_sma"])
                and
                last["volume_sma"] > 0
        ):

            vol_ratio = (
                last["volume"]
                /
                last["volume_sma"]
            )

            if vol_ratio > 1.2:

                if trend == "UP":

                    score_buy += 10
                    buy_reasons.append(
                        "Объем выше среднего"
                    )

                else:

                    score_sell += 10
                    sell_reasons.append(
                        "Объем выше среднего"
                    )

        signal = "HOLD"
        reasons = []

        if score_buy >= 40:

            signal = "BUY"
            reasons = buy_reasons

        elif score_sell >= 40:

            signal = "SELL"
            reasons = sell_reasons

        stop = None
        take = None

        if signal == "BUY":

            stop = (
                last["close"]
                -
                last["atr"] * 2
            )

            take = (
                last["close"]
                +
                last["atr"] * 4
            )

        elif signal == "SELL":

            stop = (
                last["close"]
                +
                last["atr"] * 2
            )

            take = (
                last["close"]
                -
                last["atr"] * 4
            )

        score = max(
            score_buy,
            score_sell
        )

        return {
            "signal": signal,
            "score": round(score),
            "score_buy": round(score_buy),
            "score_sell": round(score_sell),
            "trend": trend,
            "price": round(float(last["close"]), 2),
            "rsi": round(float(last["rsi"]), 2),
            "adx": round(float(last["adx"]), 2),
            "stop": round(float(stop), 2) if stop else None,
            "take": round(float(take), 2) if take else None,
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
