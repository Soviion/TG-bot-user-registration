from dotenv import load_dotenv
import os

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
BOT_USERNAME = "register_yivrbot"
CALLBACK_SECRET = os.getenv("CALLBACK_SECRET")
SUPER_ADMIN_ID = int(os.getenv("SUPER_ADMIN_ID", "8350043917"))
ROOT_ID = int(os.getenv("ROOT_ID", "8350043917"))

DATABASE = {
    "host": os.getenv("DB_HOST"),
    "port": os.getenv("DB_PORT"),
    "database": os.getenv("DB_DB", "postgres"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
}

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не найден в .env файле")
if not all(DATABASE.values()):
    raise ValueError("Не все Supabase credentials найдены в .env")
