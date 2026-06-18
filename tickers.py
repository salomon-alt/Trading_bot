# tickers.py – конфигурация тикеров и таймфреймов

# ------------------------------------------------------------
# ГРУППЫ ТИКЕРОВ
# ------------------------------------------------------------

# Акции (высоколиквидные) – используем 4 таймфрейма: неделя, день, 4 часа, 1 час
STOCKS = [
    "SBER", "GAZP", "ROSN", "NVTK", "SPBE", "SGZH", "SMLT",
    "PIKK", "SNGS", "FESH", "SIBN", "MTLRP", "SOFL", "RASP",
    "RUAL", "VKCO", "POSI", "YDEX"
]

# Валюты – используем 3 таймфрейма: неделя, день, 4 часа (без 1H)
CURRENCIES = [
    "USD000UTSTOM", "CNYRUB_TOM", "GLDRUB_TOM", "SLVRUB_TOM"
]

# Облигации – используем 2 таймфрейма: неделя и день (без коротких интервалов)
BONDS = [
    "SU26233RMFS5", "SU26238RMFS4", "SU26240RMFS0", "SU26248RMFS3"
]

# ------------------------------------------------------------
# КОНФИГУРАЦИЯ ТАЙМФРЕЙМОВ ДЛЯ КАЖДОЙ ГРУППЫ
# ------------------------------------------------------------

TIMEFRAMES_BY_GROUP = {
    "stocks": ["week", "day", "4h", "1h"],   # 4 таймфрейма
    "currencies": ["week", "day", "4h"],     # 3 таймфрейма
    "bonds": ["week", "day"],                # 2 таймфрейма
}

# ------------------------------------------------------------
# СВЯЗКА ГРУПП И ТИКЕРОВ
# ------------------------------------------------------------

TICKER_GROUPS = {
    "stocks": STOCKS,
    "currencies": CURRENCIES,
    "bonds": BONDS,
}

# Для быстрого доступа к группе по тикеру (используется в main.py)
def get_group(ticker: str) -> str:
    for group, tickers in TICKER_GROUPS.items():
        if ticker in tickers:
            return group
    return "stocks"  # по умолчанию

# Получить список таймфреймов для тикера
def get_timeframes_for_ticker(ticker: str) -> list:
    group = get_group(ticker)
    return TIMEFRAMES_BY_GROUP.get(group, ["week", "day"])