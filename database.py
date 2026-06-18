import sqlite3

DB_NAME = "signals.db"


def init_db():
    conn = sqlite3.connect(DB_NAME)

    conn.execute("""
    CREATE TABLE IF NOT EXISTS signals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ticker TEXT,
        timeframe TEXT,
        signal TEXT,
        score INTEGER,
        price REAL,
        stop REAL,
        take REAL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)

    conn.commit()
    conn.close()


def save_signal(
        ticker,
        timeframe,
        signal,
        score,
        price,
        stop,
        take
):
    conn = sqlite3.connect(DB_NAME)

    conn.execute("""
    INSERT INTO signals (
        ticker,
        timeframe,
        signal,
        score,
        price,
        stop,
        take
    )
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        ticker,
        timeframe,
        signal,
        score,
        price,
        stop,
        take
    ))

    conn.commit()
    conn.close()