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
    
    print("Пробуем get_shares()", flush=True)
    resp = client.get_shares()
    print(f"Ответ: {resp}", flush=True)
    if hasattr(resp, 'instruments'):
        print(f"Количество инструментов: {len(resp.instruments)}", flush=True)
        if len(resp.instruments) > 0:
            print(f"Первый: {resp.instruments[0].ticker} -> {resp.instruments[0].figi}", flush=True)
    else:
        print("Нет поля instruments", flush=True)
except Exception as e:
    print(f"Ошибка: {e}", flush=True)

print("=== TEST END ===", flush=True)
