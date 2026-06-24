TICKER_GROUPS = {
    "валюты": [
        "USD000UTSTOM"
    ]
}


def get_timeframes_for_ticker(ticker: str):
    return ["day"]


def get_timeframes_for_ticker(ticker: str):

    if ticker in [
        "USD000UTSTOM",
        "CNYRUB_TOM",
        "GLDRUB_TOM",
        "SLVRUB_TOM"
    ]:
        return ["day", "1h"]

    return ["week", "day", "4h", "1h"]
