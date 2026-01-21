import json
from datetime import datetime, timezone

SUPER_ADMIN_ID = 8350043917

async def publish_admin_action(
    rabbit,
    *,
    action: str,
    admin,
    target=None,
    chat_id: int | None = None
):
    if admin.id == SUPER_ADMIN_ID:
        return  # супер-админ не логируется

    event = {
        "event": "ADMIN_ACTION",
        "action": action,
        "admin": {
            "telegram_id": admin.id,
            "username": admin.username
        },
        "target": {
            "telegram_id": target.id,
            "username": target.username
        } if target else None,
        "chat_id": chat_id,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

    await rabbit.publish(
        exchange="admin.actions",
        routing_key="admin.action",
        body=json.dumps(event)
    )
