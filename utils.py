# utils.p
import logging

# Чтобы видеть username в логах
def get_user_info(user) -> str:
    username = user.username if user.username else f"ID{user.id}"
    first_name = user.first_name or ""
    return f"{first_name} (@{username})"

from datetime import datetime

# Настраиваем логгер один раз
logger = logging.getLogger("bot_actions")
logger.setLevel(logging.INFO)

# Формат логов — красивый и читаемый
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter(
    '%(asctime)s | %(levelname)-8s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
))
logger.addHandler(handler)

def log_action(action: str, user=None, extra: str = "", level="INFO"):
    """
    Красиво логирует действие бота
    Пример: log_action("Регистрация завершена", user, "права восстановлены")
    """
    user_info = ""
    if user:
        username = user.username if user.username else f"ID{user.id}"
        first_name = user.first_name or "Без имени"
        user_info = f"{first_name} (@{username})"

    message = f"{action}"
    if user_info:
        message += f" | {user_info}"
    if extra:
        message += f" | {extra}"

    if level.upper() == "INFO":
        logger.info(message)
    elif level.upper() == "WARNING":
        logger.warning(message)
    elif level.upper() == "ERROR":
        logger.error(message)