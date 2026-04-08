import os
import hmac
import hashlib
import logging
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/lemon", tags=["lemonsqueezy"])

# LemonSqueezy credentials from env
LEMONSQUEEZY_API_KEY = os.environ.get("LEMONSQUEEZY_API_KEY", "")
LEMONSQUEEZY_STORE_ID = os.environ.get("LEMONSQUEEZY_STORE_ID", "339926")
LEMONSQUEEZY_WEBHOOK_SECRET = os.environ.get("LEMONSQUEEZY_WEBHOOK_SECRET", "")

# Product variant IDs per plan (set in Render env vars)
LEMONSQUEEZY_VARIANT_BASE = os.environ.get("LEMONSQUEEZY_VARIANT_BASE", "1505091")
LEMONSQUEEZY_VARIANT_STANDARD = os.environ.get("LEMONSQUEEZY_VARIANT_STANDARD", "1505187")
LEMONSQUEEZY_VARIANT_PRO = os.environ.get("LEMONSQUEEZY_VARIANT_PRO", "1505218")

PLANS = {
    "BASE":     {"price_usd": "5.00",  "description": "Transkrib SmartCut AI - Basic (10 days)",    "days": 10},
    "STANDARD": {"price_usd": "19.00", "description": "Transkrib SmartCut AI - Standard (30 days)", "days": 30},
    "PRO":      {"price_usd": "99.00", "description": "Transkrib SmartCut AI - Pro (365 days)",     "days": 365},
}

VARIANT_MAP = {
    "BASE":     lambda: LEMONSQUEEZY_VARIANT_BASE,
    "STANDARD": lambda: LEMONSQUEEZY_VARIANT_STANDARD,
    "PRO":      lambda: LEMONSQUEEZY_VARIANT_PRO,
}


class CreateLemonPaymentRequest(BaseModel):
    plan: str        # BASE / STANDARD / PRO
    user_email: str


class LemonPaymentResponse(BaseModel):
    checkout_url: str
    status: str


@router.post("/create", response_model=LemonPaymentResponse)
async def create_lemon_payment(body: CreateLemonPaymentRequest):
    plan = body.plan.upper()
    if plan not in PLANS:
        raise HTTPException(status_code=400, detail=f"Unknown plan: {plan}")

    if not LEMONSQUEEZY_API_KEY or not LEMONSQUEEZY_STORE_ID:
        raise HTTPException(status_code=500, detail="LemonSqueezy not configured")

    variant_id = VARIANT_MAP[plan]()
    if not variant_id:
        raise HTTPException(status_code=500, detail=f"Variant ID not configured for plan {plan}")

    try:
        import httpx
        payload = {
            "data": {
                "type": "checkouts",
                "attributes": {
                    "checkout_data": {
                        "email": body.user_email,
                        "custom": {"plan": plan, "user_email": body.user_email},
                    },
                    "product_options": {
                        "redirect_url": "https://transkrib.su?payment=success",
                    },
                },
                "relationships": {
                    "store": {"data": {"type": "stores", "id": LEMONSQUEEZY_STORE_ID}},
                    "variant": {"data": {"type": "variants", "id": variant_id}},
                },
            }
        }

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://api.lemonsqueezy.com/v1/checkouts",
                json=payload,
                headers={
                    "Authorization": f"Bearer {LEMONSQUEEZY_API_KEY}",
                    "Accept": "application/vnd.api+json",
                    "Content-Type": "application/vnd.api+json",
                },
                timeout=15,
            )

        if resp.status_code not in (200, 201):
            logger.error("LemonSqueezy error: %s %s", resp.status_code, resp.text)
            raise HTTPException(status_code=502, detail="Checkout creation failed")

        data = resp.json()
        checkout_url = data["data"]["attributes"]["url"]

        return LemonPaymentResponse(checkout_url=checkout_url, status="created")

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("create_lemon_payment error")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/webhook")
async def lemon_webhook(request: Request):
    payload = await request.body()
    sig_header = request.headers.get("x-signature", "")

    # Verify signature if secret is configured
    if LEMONSQUEEZY_WEBHOOK_SECRET:
        expected = hmac.new(
            LEMONSQUEEZY_WEBHOOK_SECRET.encode(),
            payload,
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(expected, sig_header):
            raise HTTPException(status_code=401, detail="Invalid webhook signature")

    try:
        import json
        event = json.loads(payload)
        event_name = event.get("meta", {}).get("event_name", "")
        logger.info("LemonSqueezy webhook: %s", event_name)

        if event_name != "order_created":
            return {"ok": True}

        custom = event.get("meta", {}).get("custom_data", {})
        plan = custom.get("plan", "").upper()
        user_email = custom.get("user_email", "")
        order_id = str(event.get("data", {}).get("id", ""))

        logger.info("LemonSqueezy order: plan=%s email=%s id=%s", plan, user_email, order_id)

        if plan and user_email:
            from .payments import _activate_license
            await _activate_license(user_email, plan, order_id)

        return {"ok": True}

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("lemon_webhook error")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/plans")
async def get_lemon_plans():
    return {
        k: {
            "price_usd": v["price_usd"],
            "description": v["description"],
            "days": v["days"],
        }
        for k, v in PLANS.items()
    }
