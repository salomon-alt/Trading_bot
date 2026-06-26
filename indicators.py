import logging
import traceback

import pandas as pd
import ta


def generate_signal(df: pd.DataFrame):

    try:

        # -------------------------
        # Проверки входных данных
        # -------------------------

        if df is None or df.empty:

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

        if len(df) < 20:

            price = 0

            if len(df):

                price = round(float(df["close"].iloc[-1]), 2)

            return {
                "signal": "HOLD",
                "score": 0,
                "score_buy": 0,
                "score_sell": 0,
                "trend": "UNKNOWN",
                "price": price,
                "rsi": 0,
                "adx": 0,
                "stop": None,
                "take": None,
                "reasons": []
            }

        df = df.copy()

        # -------------------------
        # Выбор EMA
        # -------------------------

        candles = len(df)

        if candles >= 220:

            ema_fast = 50
            ema_slow = 200

        elif candles >= 80:

            ema_fast = 20
            ema_slow = 50

        else:

            ema_fast = 10
            ema_slow = 30

        # -------------------------
        # RSI
        # -------------------------

        df["rsi"] = ta.momentum.RSIIndicator(
            close=df["close"],
            window=14
        ).rsi()

        # -------------------------
        # MACD
        # -------------------------

        macd = ta.trend.MACD(
            close=df["close"],
            window_fast=12,
            window_slow=26,
            window_sign=9
        )

        df["macd"] = macd.macd()
        df["macd_signal"] = macd.macd_signal()
        df["macd_hist"] = macd.macd_diff()

        # -------------------------
        # EMA
        # -------------------------

        df["ema_fast"] = ta.trend.EMAIndicator(
            close=df["close"],
            window=ema_fast
        ).ema_indicator()

        df["ema_slow"] = ta.trend.EMAIndicator(
            close=df["close"],
            window=ema_slow
        ).ema_indicator()

        # -------------------------
        # ADX
        # -------------------------

        adx = ta.trend.ADXIndicator(
            high=df["high"],
            low=df["low"],
            close=df["close"],
            window=14
        )

        df["adx"] = adx.adx()

        # -------------------------
        # ATR
        # -------------------------

        atr = ta.volatility.AverageTrueRange(
            high=df["high"],
            low=df["low"],
            close=df["close"],
            window=14
        )

        df["atr"] = atr.average_true_range()

        # -------------------------
        # Bollinger
        # -------------------------

        bb = ta.volatility.BollingerBands(
            close=df["close"],
            window=20,
            window_dev=2
        )

        df["bb_upper"] = bb.bollinger_hband()
        df["bb_middle"] = bb.bollinger_mavg()
        df["bb_lower"] = bb.bollinger_lband()

        # -------------------------
        # Объем
        # -------------------------

        df["volume_ma"] = (
            df["volume"]
            .rolling(20)
            .mean()
        )

        # -------------------------
        # Очистка
        # -------------------------

        df = df.bfill()
        df = df.ffill()
        df = df.dropna()

        if len(df) < 2:

            last_price = 0

            if len(df):

                last_price = round(float(df["close"].iloc[-1]), 2)

            return {
                "signal": "HOLD",
                "score": 0,
                "score_buy": 0,
                "score_sell": 0,
                "trend": "UNKNOWN",
                "price": last_price,
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

        # --------------------------------------------------
        # Определение тренда
        # --------------------------------------------------

        if (
            last["close"] > last["ema_fast"]
            and
            last["ema_fast"] > last["ema_slow"]
        ):

            trend = "UP"

        elif (
            last["close"] < last["ema_fast"]
            and
            last["ema_fast"] < last["ema_slow"]
        ):

            trend = "DOWN"

        else:

            trend = "SIDEWAYS"

        # --------------------------------------------------
        # EMA
        # --------------------------------------------------

        if trend == "UP":

            score_buy += 20
            buy_reasons.append(
                "Цена выше EMA"
            )

        elif trend == "DOWN":

            score_sell += 20
            sell_reasons.append(
                "Цена ниже EMA"
            )

        # --------------------------------------------------
        # MACD
        # --------------------------------------------------

        bullish_cross = (
            prev["macd"] <= prev["macd_signal"]
            and
            last["macd"] > last["macd_signal"]
        )

        bearish_cross = (
            prev["macd"] >= prev["macd_signal"]
            and
            last["macd"] < last["macd_signal"]
        )

        if bullish_cross:

            score_buy += 20

            buy_reasons.append(
                "MACD бычий"
            )

        if bearish_cross:

            score_sell += 20

            sell_reasons.append(
                "MACD медвежий"
            )

        # --------------------------------------------------
        # RSI
        # --------------------------------------------------

        if last["rsi"] <= 35:

            score_buy += 15

            buy_reasons.append(
                "RSI перепродан"
            )

        elif last["rsi"] >= 65:

            score_sell += 15

            sell_reasons.append(
                "RSI перекуплен"
            )

        # --------------------------------------------------
        # ADX
        # --------------------------------------------------

        strong_trend = False

        if last["adx"] >= 25:

            strong_trend = True

            if trend == "UP":

                score_buy += 20

                buy_reasons.append(
                    "Сильный тренд"
                )

            elif trend == "DOWN":

                score_sell += 20

                sell_reasons.append(
                    "Сильный тренд"
                )

        # --------------------------------------------------
        # Объем
        # --------------------------------------------------

        if (
            pd.notna(last["volume_ma"])
            and
            last["volume_ma"] > 0
        ):

            volume_ratio = (
                last["volume"]
                /
                last["volume_ma"]
            )

            if volume_ratio >= 1.5:

                if trend == "UP":

                    score_buy += 10

                    buy_reasons.append(
                        "Рост объема"
                    )

                elif trend == "DOWN":

                    score_sell += 10

                    sell_reasons.append(
                        "Рост объема"
                    )

        # --------------------------------------------------
        # Bollinger
        # --------------------------------------------------

        if last["close"] <= last["bb_lower"]:

            score_buy += 10

            buy_reasons.append(
                "Нижняя Bollinger"
            )

        elif last["close"] >= last["bb_upper"]:

            score_sell += 10

            sell_reasons.append(
                "Верхняя Bollinger"
            )

        # --------------------------------------------------
        # MACD Histogram
        # --------------------------------------------------

        if last["macd_hist"] > 0:

            score_buy += 5

        elif last["macd_hist"] < 0:

            score_sell += 5

        # --------------------------------------------------
        # Дополнительная фильтрация
        # --------------------------------------------------

        confirmations_buy = 0
        confirmations_sell = 0

        if trend == "UP":
            confirmations_buy += 1

        if trend == "DOWN":
            confirmations_sell += 1

        if bullish_cross:
            confirmations_buy += 1

        if bearish_cross:
            confirmations_sell += 1

        if last["rsi"] <= 35:
            confirmations_buy += 1

        if last["rsi"] >= 65:
            confirmations_sell += 1

        if strong_trend:

            if trend == "UP":

                confirmations_buy += 1

            elif trend == "DOWN":

                confirmations_sell += 1

        if (
            pd.notna(last["volume_ma"])
            and
            last["volume_ma"] > 0
        ):

            if volume_ratio >= 1.5:

                if trend == "UP":

                    confirmations_buy += 1

                elif trend == "DOWN":

                    confirmations_sell += 1

        # =====================================================
        # ТРЕНД
        # =====================================================

        trend = "SIDEWAYS"

        if (
            last["ema20"] > last["ema50"] > last["ema_long"]
        ):
            trend = "UP"

        elif (
            last["ema20"] < last["ema50"] < last["ema_long"]
        ):
            trend = "DOWN"

        score_buy = 0
        score_sell = 0

        buy_reasons = []
        sell_reasons = []

        # =====================================================
        # EMA
        # =====================================================

        if trend == "UP":

            score_buy += 30
            buy_reasons.append(
                "EMA выстроены вверх"
            )

        elif trend == "DOWN":

            score_sell += 30
            sell_reasons.append(
                "EMA выстроены вниз"
            )

        # =====================================================
        # MACD
        # =====================================================

        if (
            prev["macd"] < prev["macd_signal"]
            and
            last["macd"] > last["macd_signal"]
        ):

            score_buy += 20
            buy_reasons.append(
                "MACD бычий крест"
            )

        elif (
            prev["macd"] > prev["macd_signal"]
            and
            last["macd"] < last["macd_signal"]
        ):

            score_sell += 20
            sell_reasons.append(
                "MACD медвежий крест"
            )

        # =====================================================
        # RSI
        # =====================================================

        if (
            trend == "UP"
            and
            45 <= last["rsi"] <= 65
        ):

            score_buy += 15
            buy_reasons.append(
                "RSI подтверждает рост"
            )

        elif (
            trend == "DOWN"
            and
            35 <= last["rsi"] <= 55
        ):

            score_sell += 15
            sell_reasons.append(
                "RSI подтверждает падение"
            )

        if last["rsi"] < 30:

            score_buy += 5

        elif last["rsi"] > 70:

            score_sell += 5

        # =====================================================
        # ADX
        # =====================================================

        if last["adx"] >= 25:

            if trend == "UP":

                score_buy += 20
                buy_reasons.append(
                    "Сильный восходящий тренд"
                )

            elif trend == "DOWN":

                score_sell += 20
                sell_reasons.append(
                    "Сильный нисходящий тренд"
                )

        # =====================================================
        # Объем
        # =====================================================

        if last["volume_sma"] > 0:

            volume_ratio = (
                last["volume"]
                /
                last["volume_sma"]
            )

            if volume_ratio >= 1.5:

                if trend == "UP":

                    score_buy += 10
                    buy_reasons.append(
                        "Повышенный объем"
                    )

                elif trend == "DOWN":

                    score_sell += 10
                    sell_reasons.append(
                        "Повышенный объем"
                    )

        # =====================================================
        # Bollinger
        # =====================================================

        if (
            trend == "UP"
            and
            last["close"] > last["bb_mid"]
        ):

            score_buy += 5

        elif (
            trend == "DOWN"
            and
            last["close"] < last["bb_mid"]
        ):

            score_sell += 5

        # =====================================================
        # ATR
        # =====================================================

        atr_percent = (
            last["atr"]
            /
            last["close"]
        ) * 100

        if atr_percent > 8:

            score_buy -= 10
            score_sell -= 10

