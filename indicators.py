import pandas as pd
import ta


def generate_signal(df: pd.DataFrame):
    if len(df) < 60:
        return {
            "signal": "HOLD",
            "score": 0,
            "score_buy": 0,
            "score_sell": 0,
            "trend": "UNKNOWN",
            "price": float(df["close"].iloc[-1]),
            "reasons": []
        }

    df = df.copy()

    # RSI
    df["rsi"] = ta.momentum.RSIIndicator(close=df["close"], window=14).rsi()

    # MACD
    macd = ta.trend.MACD(close=df["close"])
    df["macd"] = macd.macd()
    df["macd_signal"] = macd.macd_signal()

    # EMA
    ema_long = 200 if len(df) >= 200 else 100
    df["ema50"] = ta.trend.EMAIndicator(close=df["close"], window=50).ema_indicator()
    df["ema_long"] = ta.trend.EMAIndicator(close=df["close"], window=ema_long).ema_indicator()

    # ADX
    df["adx"] = ta.trend.ADXIndicator(high=df["high"], low=df["low"], close=df["close"], window=14).adx()

    # ATR
    df["atr"] = ta.volatility.AverageTrueRange(high=df["high"], low=df["low"], close=df["close"], window=14).average_true_range()

    # Средний объём
    df["volume_sma"] = df["volume"].rolling(20).mean()

    # Bollinger Bands (добавлено)
    bb = ta.volatility.BollingerBands(close=df["close"], window=20, window_dev=2)
    df["bb_high"] = bb.bollinger_hband()
    df["bb_low"] = bb.bollinger_lband()
    df["bb_mid"] = bb.bollinger_mavg()

    df = df.dropna()
    if len(df) < 2:
        return {
            "signal": "HOLD",
            "score": 0,
            "score_buy": 0,
            "score_sell": 0,
            "trend": "UNKNOWN",
            "price": float(df["close"].iloc[-1]),
            "reasons": []
        }

    last = df.iloc[-1]
    prev = df.iloc[-2]

    score_buy = 0
    score_sell = 0
    buy_reasons = []
    sell_reasons = []

    # 1. EMA тренд
    if last["ema50"] > last["ema_long"]:
        score_buy += 25
        trend = "UP"
        buy_reasons.append("EMA50 выше EMA200")
    else:
        score_sell += 25
        trend = "DOWN"
        sell_reasons.append("EMA50 ниже EMA200")

    # 2. MACD пересечение
    if prev["macd"] < prev["macd_signal"] and last["macd"] > last["macd_signal"]:
        score_buy += 25
        buy_reasons.append("MACD бычий крест")
    if prev["macd"] > prev["macd_signal"] and last["macd"] < last["macd_signal"]:
        score_sell += 25
        sell_reasons.append("MACD медвежий крест")

    # 3. RSI
    if 35 <= last["rsi"] <= 60:
        score_buy += 15
        buy_reasons.append("RSI в нейтральной зоне")
    if last["rsi"] >= 70:
        score_sell += 15
        sell_reasons.append("RSI перекуплен")

    # 4. ADX сила тренда
    if last["adx"] > 25:
        if trend == "UP":
            score_buy += 15
            buy_reasons.append("Сильный тренд (ADX)")
        else:
            score_sell += 15
            sell_reasons.append("Сильный тренд (ADX)")

    # 5. Объём выше среднего (усилен)
    if pd.notna(last["volume_sma"]):
        vol_ratio = last["volume"] / last["volume_sma"]
        if vol_ratio > 1.0:
            if trend == "UP":
                score_buy += 10
                buy_reasons.append("Объём выше среднего")
            else:
                score_sell += 10
                sell_reasons.append("Объём выше среднего")
        if vol_ratio > 1.5:
            if trend == "UP":
                score_buy += 5
                buy_reasons.append("Объём значительно выше среднего (>1.5x)")
            else:
                score_sell += 5
                sell_reasons.append("Объём значительно выше среднего (>1.5x)")

    # 6. ATR – высокая волатильность
    atr_percent = (last["atr"] / last["close"]) * 100
    if atr_percent > 1:
        if trend == "UP":
            score_buy += 10
            buy_reasons.append("Высокая волатильность")
        else:
            score_sell += 10
            sell_reasons.append("Высокая волатильность")

    # 7. Bollinger Bands (новый блок)
    # Отскок от нижней полосы вверх (бычий)
    if last["close"] <= last["bb_low"] and last["close"] > prev["close"]:
        score_buy += 15
        buy_reasons.append("Отскок от нижней полосы Боллинджера")
    # Отскок от верхней полосы вниз (медвежий)
    if last["close"] >= last["bb_high"] and last["close"] < prev["close"]:
        score_sell += 15
        sell_reasons.append("Отскок от верхней полосы Боллинджера")

    # Определяем сигнал (порог остаётся 50)
    signal = "HOLD"
    reasons = []
    if score_buy >= 50:
        signal = "BUY"
        reasons = buy_reasons
    elif score_sell >= 50:
        signal = "SELL"
        reasons = sell_reasons

    # Стоп и тейк
    stop = None
    take = None
    if signal == "BUY":
        stop = last["close"] - last["atr"] * 2
        take = last["close"] + last["atr"] * 4
    elif signal == "SELL":
        stop = last["close"] + last["atr"] * 2
        take = last["close"] - last["atr"] * 4

    score = max(score_buy, score_sell)

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
