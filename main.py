import sys
import os
from dotenv import load_dotenv
load_dotenv()

print("=== TEST START ===", flush=True)
print(f"TOKEN: {os.getenv('TINKOFF_INVEST_API_TOKEN')}", flush=True)

try:
    from tinkoff_invest import ProductionSession as Client
    print("✅ ProductionSession импортирован", flush=True)
    client = Client(os.getenv('TINKOFF_INVEST_API_TOKEN'))
    print("✅ Клиент создан", flush=True)
    
    # Выводим все публичные методы
    methods = [m for m in dir(client) if not m.startswith('_')]
    print(f"Доступные методы: {methods}", flush=True)
    
    # Проверяем возможные методы для получения инструментов
    possible = ['get_instruments', 'instruments', 'get_securities', 'securities', 'get_market_data', 'market_data', 'get_tickers', 'tickers']
    for name in possible:
        if hasattr(client, name):
            print(f"Найден метод: {name}", flush=True)
            try:
                resp = getattr(client, name)()
                print(f"Результат {name}: {resp}", flush=True)
                if hasattr(resp, 'instruments'):
                    print(f"instruments: {len(resp.instruments)}", flush=True)
                elif hasattr(resp, 'payload'):
                    print(f"payload: {resp.payload}", flush=True)
            except Exception as e:
                print(f"Ошибка при вызове {name}: {e}", flush=True)
        else:
            print(f"Метод {name} отсутствует", flush=True)
            
except Exception as e:
    print(f"Ошибка: {e}", flush=True)

print("=== TEST END ===", flush=True)
