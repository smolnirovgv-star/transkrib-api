import os
import uuid
import logging
from fastapi import APIRouter, HTTPException, Request, Header
from pydantic import BaseModel
from typing import Optional

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/payments", tags=["payments"])

# ЮKassa credentials from env
YOOKASSA_SHOP_ID = os.environ.get("YOOKASSA_SHOP_ID", "")
YOOKASSA_SECRET_KEY = os.environ.get("YOOKASSA_SECRET_KEY", "")

PLANS = {
    "BASE":     {"amount": "450.00",  "currency": "RUB", "description": "Transkrib SmartCut AI - Базовый (10 дней)",    "days": 10},
    "STANDARD": {"amount": "1700.00", "currency": "RUB", "description": "Transkrib SmartCut AI - Стандарт (30 дней)",  "days": 30},
    "PRO":      {"amount": "8900.00", "currency": "RUB", "description": "Transkrib SmartCut AI - Про (365 дней)",       "days": 365},
}


class CreatePaymentRequest(BaseModel):
    plan: str          # BASE / STANDARD / PRO
    user_email: str
    return_url: str = "https://transkrib-api.onrender.com/api/payments/success"


class PaymentResponse(BaseModel):
    payment_id: str
    confirmation_url: str
    status: str


@router.post("/create", response_model=PaymentResponse)
async def create_payment(body: CreatePaymentRequest):
    """Создать платёж в ЮКасса и вернуть ссылку для оплаты."""
    plan = body.plan.upper()
    if plan not in PLANS:
        raise HTTPException(status_code=400, detail=f"Unknown plan: {plan}")

    if not YOOKASSA_SHOP_ID or not YOOKASSA_SECRET_KEY:
        raise HTTPException(status_code=500, detail="Payment system not configured")

    try:
        import httpx
        idempotency_key = str(uuid.uuid4())
        plan_info = PLANS[plan]

        payload = {
            "amount": {"value": plan_info["amount"], "currency": plan_info["currency"]},
            "confirmation": {"type": "redirect", "return_url": body.return_url},
            "capture": True,
            "description": plan_info["description"],
            "metadata": {"plan": plan, "user_email": body.user_email},
        }

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://api.yookassa.ru/v3/payments",
                json=payload,
                auth=(YOOKASSA_SHOP_ID, YOOKASSA_SECRET_KEY),
                headers={"Idempotence-Key": idempotency_key, "Content-Type": "application/json"},
                timeout=15,
            )

        if resp.status_code not in (200, 201):
            logger.error("YooKassa error: %s %s", resp.status_code, resp.text)
            raise HTTPException(status_code=502, detail="Payment creation failed")

        data = resp.json()
        confirmation_url = data["confirmation"]["confirmation_url"]

        return PaymentResponse(
            payment_id=data["id"],
            confirmation_url=confirmation_url,
            status=data["status"],
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("create_payment error")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/webhook")
async def yookassa_webhook(request: Request):
    """Webhook от ЮКасса — обновляем лицензию после успешной оплаты."""
    try:
        event = await request.json()
        logger.info("YooKassa webhook: %s", event.get("event"))

        if event.get("event") != "payment.succeeded":
            return {"ok": True}

        payment = event.get("object", {})
        metadata = payment.get("metadata", {})
        plan = metadata.get("plan", "").upper()
        user_email = metadata.get("user_email", "")
        payment_id = payment.get("id", "")

        logger.info("Payment succeeded: plan=%s email=%s id=%s", plan, user_email, payment_id)

        if plan and user_email:
            await _activate_license(user_email, plan, payment_id)

        return {"ok": True}

    except Exception as e:
        logger.exception("webhook error")
        raise HTTPException(status_code=500, detail=str(e))


async def _activate_license(user_email: str, plan: str, payment_id: str):
    """Активировать лицензию в Supabase после оплаты."""
    try:
        import httpx
        supabase_url = os.environ.get("SUPABASE_URL", "")
        supabase_key = os.environ.get("SUPABASE_SERVICE_KEY", "")

        if not supabase_url or not supabase_key:
            logger.warning("Supabase not configured — skipping license activation")
            return

        days = PLANS.get(plan, {}).get("days", 30)

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{supabase_url}/rest/v1/user_licenses",
                json={
                    "email": user_email,
                    "plan": plan,
                    "days": days,
                    "payment_id": payment_id,
                    "active": True,
                },
                headers={
                    "apikey": supabase_key,
                    "Authorization": f"Bearer {supabase_key}",
                    "Content-Type": "application/json",
                    "Prefer": "resolution=merge-duplicates",
                },
                timeout=10,
            )
        logger.info("License activated: %s %s -> %s", user_email, plan, resp.status_code)

    except Exception as e:
        logger.exception("_activate_license error: %s", e)


@router.get("/success")
async def payment_success():
    """Страница после успешной оплаты."""
    return {
        "status": "ok",
        "message": "Оплата прошла успешно! Лицензия будет активирована в течение нескольких секунд.",
    }


@router.get("/plans")
async def get_plans():
    """Список доступных тарифов с ценами."""
    return {
        k: {"amount": v["amount"], "currency": v["currency"], "description": v["description"], "days": v["days"]}
        for k, v in PLANS.items()
    }
