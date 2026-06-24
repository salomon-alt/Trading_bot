# tickers.py

TICKER_GROUPS = {
    "акции": [
        "SBER",
        "GAZP",
        "ROSN",
        "NVTK",
        "SPBE",
        "SGZH",
        "SMLT",
        "PIKK",
        "SNGS",
        "FESH",
        "SIBN",
        "MTLRP",
        "SOFL",
        "RASP",
        "RUAL",
        "VKCO",
        "POSI",
        "YDEX"
    ],

    "валюты": [
        "USD000UTSTOM",
        "CNYRUB_TOM"
    ],

    "облигации": [
        "SU26233RMFS5",
        "SU26238RMFS4",
        "SU26240RMFS0",
        "SU26248RMFS3"
    ]
}


def get_timeframes_for_ticker(ticker: str) -> list:
    return [
        "week",
        "day",
        "4h",
        "1h"
    ]
