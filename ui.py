import tkinter as tk
from tkinter import messagebox, simpledialog
from data_fetch import get_figi_by_ticker, get_candles

def start_ui():
    root = tk.Tk()
    root.title("Trading Bot")

    tk.Label(root, text="API TOKEN:").pack(pady=(10, 0))
    token_entry = tk.Entry(root, width=60)
    token_entry.pack()

    tk.Label(root, text="TICKER (например, SBER):").pack(pady=(10, 0))
    ticker_entry = tk.Entry(root, width=20)
    ticker_entry.pack()

    def on_submit():
        token = token_entry.get().strip()
        ticker = ticker_entry.get().strip().upper()
        if not token or not ticker:
            messagebox.showerror("Ошибка", "Оба поля должны быть заполнены.")
            return

        try:
            figi = get_figi_by_ticker(token, ticker)
        except Exception as e:
            messagebox.showerror("Ошибка FIGI", str(e))
            return

        try:
            df = get_candles(token, figi, days=5)
        except Exception as e:
            messagebox.showerror("Ошибка свечей", str(e))
            return

        # Показываем краткий результат
        last = df.iloc[-1] if not df.empty else None
        msg = f"FIGI: {figi}"
        if last is not None:
            msg += f"\nПоследняя свеча — Close: {last['close']:.2f}, Volume: {last['volume']}"
        messagebox.showinfo("Результат", msg)

    tk.Button(root, text="Получить данные", command=on_submit).pack(pady=20)
    root.mainloop()
