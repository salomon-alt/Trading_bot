from tinkoff_invest import ProductionSession
import os
from dotenv import load_dotenv

load_dotenv()

session = ProductionSession(
    os.getenv("TINKOFF_INVEST_API_TOKEN")
)

print(session.get_instrument_by_ticker("SBER"))