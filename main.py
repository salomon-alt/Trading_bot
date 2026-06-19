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
    
    # Проверяем методы для получения инструментов
    for method_name in ['stocks', 'bonds', 'currencies', 'etfs']:
        if hasattr(client, method_name):
            print(f"=== Вызываем {method_name}() ===", flush=True)
            try:
                resp = getattr(client, method_name)()
                print(f"Тип ответа: {type(resp)}", flush=True)
                print(f"Атрибуты: {[a for a in dir(resp) if not a.startswith('_')]}", flush=True)
                if hasattr(resp, 'instruments'):
                    instruments = resp.instruments
                    print(f"Количество инструментов: {len(instruments)}", flush=True)
                    if len(instruments) > 0:
                        print(f"Пример: {instruments[0].ticker} -> {instruments[0].figi}", flush=True)
                elif hasattr(resp, 'payload'):
                    print(f"payload: {resp.payload}", flush=True)
                    if hasattr(resp.payload, 'instruments'):
                        print(f"В payload.instruments: {len(resp.payload.instruments)}", flush=True)
                        if len(resp.payload.instruments) > 0:
                            print(f"Пример: {resp.payload.instruments[0].ticker} -> {resp.payload.instruments[0].figi}", flush=True)
                else:
                    print("Нет ни instruments, ни payload", flush=True)
            except Exception as e:
                print(f"Ошибка при вызове {method_name}: {e}", flush=True)
        else:
            print(f"Метод {method_name} отсутствует", flush=True)
            
except Exception as e:
    print(f"Ошибка: {e}", flush=True)

print("=== TEST END ===", flush=True)
