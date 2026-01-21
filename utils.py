# utils.py
import logging
from datetime import datetime

# ================= LOGGER =================

logger = logging.getLogger("bot_actions")
logger.setLevel(logging.INFO)

if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-7s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.propagate = False


# ================= HELPERS =================

def get_user_info(user) -> str:
    if not user:
        return "SYSTEM"
    username = f"@{user.username}" if user.username else f"ID{user.id}"
    name = user.first_name or "Без имени"
    return f"{name} ({username})"


def log_action(
    action: str,
    user=None,
    handler: str | None = None,
    extra: str | None = None,
    *,
    level: str = "INFO"
):
    

    parts = [action]

    if user:
        parts.append(get_user_info(user))

    if handler:
        parts.append(handler)

    if extra:
        parts.append(extra)

    message = " | ".join(parts)

    level = level.upper()
    if level == "WARNING":
        logger.warning(message)
    elif level == "ERROR":
        logger.error(message)
    else:
        logger.info(message)



from aiogram.fsm.context import FSMContext



async def log_fsm(
    state: FSMContext,
    user,
    to_state: str | None,
    reason: str = ""
):
    """
    Лог FSM переходов в одну строку
    """
    from_state = await state.get_state()
    from_state = from_state or "None"
    to_state = to_state or "None"

    extra = f"{from_state} → {to_state}"
    if reason:
        extra += f" | {reason}"

    log_action(
        action="FSM",
        user=user,
        handler="transition",
        extra=extra
    )