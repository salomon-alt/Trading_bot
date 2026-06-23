def get_candles(figi: str, interval_key: str, days: int, ticker: str = None):

    interval_map = {
        "day": "CANDLE_INTERVAL_DAY",
        "week": "CANDLE_INTERVAL_WEEK",
        "4h": "CANDLE_INTERVAL_4_HOUR",
        "1h": "CANDLE_INTERVAL_HOUR"
    }

    interval = interval_map.get(interval_key)

    if not interval:
        logging.error(f"Неизвестный интервал: {interval_key}")
        return pd.DataFrame()

    now = datetime.utcnow()

    from_time = now - timedelta(days=days)

    payload = {
        "figi": figi,
        "from": from_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "to": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "interval": interval
    }

    try:

        with _candles_lock:
            global _last_candle_request_time

            diff = time.time() - _last_candle_request_time

            if diff < 1.5:
                time.sleep(1.5 - diff)

            _last_candle_request_time = time.time()

        resp = _call_api(
            "MarketDataService/GetCandles",
            payload
        )

        candles = resp.get("candles", [])

        if not candles:
            return pd.DataFrame()

        rows = []

        for c in candles:

            rows.append({
                "time": c["time"],
                "open": float(c["open"]["units"]) + float(c["open"]["nano"]) / 1e9,
                "high": float(c["high"]["units"]) + float(c["high"]["nano"]) / 1e9,
                "low": float(c["low"]["units"]) + float(c["low"]["nano"]) / 1e9,
                "close": float(c["close"]["units"]) + float(c["close"]["nano"]) / 1e9,
                "volume": c["volume"]
            })

        df = pd.DataFrame(rows)

        if not df.empty:
            df.sort_values("time", inplace=True)

        return df.reset_index(drop=True)

    except Exception as e:
        logging.error(
            f"Ошибка получения свечей {figi} {interval_key}: {e}"
        )
        return pd.DataFrame()
