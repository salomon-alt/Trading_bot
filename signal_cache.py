"""
Кэш для предотвращения дублирования сигналов.
Хранит в памяти словарь: ключ = (ticker, timeframe, signal), значение = timestamp.
Сигнал считается дубликатом, если он уже был отправлен за последние 24 часа.
"""

import time
from typing import Tuple

# Глобальный словарь кэша
_cache: dict[Tuple[str, str, str], float] = {}
CACHE_TTL_SECONDS = 24 * 3600  # 24 часа


def is_duplicate(ticker: str, timeframe: str, signal: str) -> bool:
    """
    Проверяет, был ли уже отправлен такой сигнал для данного тикера и таймфрейма.
    Если нет – добавляет в кэш и возвращает False.
    Если есть и не истёк – возвращает True.
    Если истёк – обновляет время и возвращает False.
    """
    key = (ticker.upper(), timeframe.upper(), signal.upper())
    now = time.time()

    if key in _cache:
        last_time = _cache[key]
        if now - last_time < CACHE_TTL_SECONDS:
            return True  # дубликат
        else:
            # Истекло – обновляем
            _cache[key] = now
            return False
    else:
        _cache[key] = now
        return False


def clear_cache() -> None:
    """Очищает весь кэш (можно вызывать при перезапуске)."""
    _cache.clear()