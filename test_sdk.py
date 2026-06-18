from tinkoff_invest import ProductionSession
import os
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("TINKOFF_INVEST_API_TOKEN")

print("TOKEN OK")

session = ProductionSession(TOKEN)

print("SESSION OK")

print(dir(session))