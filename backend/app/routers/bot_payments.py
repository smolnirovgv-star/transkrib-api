"""ЮKassa payment creation and webhook handler for Telegram bot."""
import os
import uuid
import httpx
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Request
from pydantic import BaseModel

router = APIRouter()

YOOKASSA_SHOP_ID = os.getenv("YOOKASSA_SHOP_ID", "")
YOOKASSA_SECRET_KEY = os.getenv("YOOKASSA_SECRET_KEY", "")
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
BOT_USERNAME = os.getenv("TELEGRAM_BOT_USERNAME", "TranskribSmartCutBot")

PLAN_INFO = {
    "starter": {"amount": "450.00", "days": 10,   "videos_limit": 9999, "name": "⭐ Базовый"},
    "pro":     {"amount": "1700.00","days": 30,  "videos_limit": 9999, "name": "🚀 Стандарт"},
    "annual":  {"amount": "8900.00","days": 365, "videos_limit": 9999, "name": "👑 Про"},
}


class CreatePaymentRequest(BaseModel):
    telegram_id: int
    plan: str


@router.post("/api/bot/payments/yookassa/create")
async def create_payment(body: CreatePaymentRequest):
    plan_info = PLAN_INFO.get(body.plan)
    if not plan_info:
        return {"error": "Unknown plan"}
    if not YOOKASSA_SHOP_ID or not YOOKASSA_SECRET_KEY:
        return {"error": "YooKassa not configured (YOOKASSA_SHOP_ID / YOOKASSA_SECRET_KEY missing)"}

    idempotency_key = str(uuid.uuid4())
    payload = {
        "amount": {"value": plan_info["amount"], "currency": "RUB"},
        "confirmation": {
            "type": "redirect",
            "return_url": f"https://t.me/{BOT_USERNAME}",
        },
        "capture": True,
        "description": f"Transkrib {body.plan.capitalize()} — {body.telegram_id}",
        "metadata": {
            "telegram_id": str(body.telegram_id),
            "plan": body.plan,
        },
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                "https://api.yookassa.ru/v3/payments",
                json=payload,
                auth=(YOOKASSA_SHOP_ID, YOOKASSA_SECRET_KEY),
                headers={"Idempotence-Key": idempotency_key},
            )
        if resp.status_code != 200:
            return {"error": f"YooKassa error {resp.status_code}: {resp.text[:300]}"}
        data = resp.json()
        return {
            "payment_url": data["confirmation"]["confirmation_url"],
            "payment_id": data["id"],
        }
    except Exception as e:
        return {"error": str(e)[:300]}


@router.post("/api/bot/payments/yookassa/webhook")
async def yookassa_webhook(request: Request):
    try:
        body = await request.json()
    except Exception:
        return {"ok": True}

    print(f"[bot_payments] webhook event: {body.get('event')}")

    if body.get("event") != "payment.succeeded":
        return {"ok": True}

    payment = body.get("object", {})
    metadata = payment.get("metadata", {})
    telegram_id_str = metadata.get("telegram_id")
    plan = metadata.get("plan")

    if not telegram_id_str or not plan:
        print("[bot_payments] webhook: missing telegram_id or plan in metadata")
        return {"ok": True}

    plan_info = PLAN_INFO.get(plan)
    if not plan_info:
        print(f"[bot_payments] webhook: unknown plan {plan}")
        return {"ok": True}

    telegram_id = int(telegram_id_str)
    expires_at = (datetime.now(timezone.utc) + timedelta(days=plan_info["days"])).isoformat()

    # Activate plan in Supabase
    try:
        from supabase import create_client
        sb = create_client(SUPABASE_URL, SUPABASE_KEY)
        sb.table("bot_users").upsert({
            "telegram_id": telegram_id,
            "plan": plan,
            "videos_limit": plan_info["videos_limit"],
            "videos_used": 0,
            "plan_expires_at": expires_at,
        }).execute()
        print(f"[bot_payments] plan {plan} activated for {telegram_id} until {expires_at[:10]}")
    except Exception as e:
        print(f"[bot_payments] Supabase error: {e}")

    # Notify user via Telegram
    if BOT_TOKEN:
        try:
            nl = chr(10)
            msg = (
                f"✅ Оплата прошла! "
                f"Тариф {plan_info['name']} активирован." + nl
                + f"Действует до: {expires_at[:10]}" + nl + nl
                + "Отправь ссылку на видео — начинаем!"
            )
            async with httpx.AsyncClient(timeout=10.0) as client:
                await client.post(
                    f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                    json={"chat_id": telegram_id, "text": msg},
                )
        except Exception as e:
            print(f"[bot_payments] Telegram notify error: {e}")

    return {"ok": True}
