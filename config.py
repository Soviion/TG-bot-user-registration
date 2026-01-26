from dotenv import load_dotenv
import os

load_dotenv()  # загружает переменные из .env в os.environ

BOT_TOKEN = os.getenv("BOT_TOKEN")
BOT_USERNAME = "register_yivrbot"
CALLBACK_SECRET = os.getenv("CALLBACK_SECRET")
SUPER_ADMIN_ID = int(os.getenv("SUPER_ADMIN_ID"))

SUPABASE = {
    "host": os.getenv("SUPABASE_HOST"),
    "port": int(os.getenv("SUPABASE_PORT", 5432)),
    "database": os.getenv("SUPABASE_DB", "postgres"),
    "user": os.getenv("SUPABASE_USER"),
    "password": os.getenv("SUPABASE_PASSWORD"),
}

# Проверяем, что ничего не потеряли
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не найден в .env файле")
if not all(SUPABASE.values()):
    raise ValueError("Не все Supabase credentials найдены в .env")
