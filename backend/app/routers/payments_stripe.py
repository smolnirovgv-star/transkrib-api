import os
import logging
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/stripe", tags=["stripe"])

# Stripe credentials from env
STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")

PLANS = {
    "BASE":     {"amount": 500,   "currency": "usd", "description": "Transkrib SmartCut AI - Basic (10 days)",    "days": 10},
    "STANDARD": {"amount": 1900,  "currency": "usd", "description": "Transkrib SmartCut AI - Standard (30 days)", "days": 30},
    "PRO":      {"amount": 9900,  "currency": "usd", "description": "Transkrib SmartCut AI - Pro (365 days)",     "days": 365},
}


class CreateStripePaymentRequest(BaseModel):
    plan: str        # BASE / STANDARD / PRO
    user_email: str


class StripePaymentResponse(BaseModel):
    session_id: str
    checkout_url: str
    status: str


@router.post("/create", response_model=StripePaymentResponse)
async def create_stripe_payment(body: CreateStripePaymentRequest):
    plan = body.plan.upper()
    if plan not in PLANS:
        raise HTTPException(status_code=400, detail=f"Unknown plan: {plan}")

    if not STRIPE_SECRET_KEY:
        raise HTTPException(status_code=500, detail="Stripe not configured")

    try:
        import stripe
        stripe.api_key = STRIPE_SECRET_KEY

        plan_info = PLANS[plan]

        session = stripe.checkout.Session.create(
            mode="payment",
            payment_method_types=["card"],
            line_items=[{
                "price_data": {
                    "currency": plan_info["currency"],
                    "unit_amount": plan_info["amount"],
                    "product_data": {"name": plan_info["description"]},
                },
                "quantity": 1,
            }],
            metadata={"plan": plan, "user_email": body.user_email},
            customer_email=body.user_email,
            success_url="https://transkrib.su?payment=success",
            cancel_url="https://transkrib.su?payment=cancel",
        )

        return StripePaymentResponse(
            session_id=session.id,
            checkout_url=session.url,
            status=session.status,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("create_stripe_payment error")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/webhook")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    try:
        import stripe
        stripe.api_key = STRIPE_SECRET_KEY

        if STRIPE_WEBHOOK_SECRET:
            event = stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
        else:
            import json
            event = json.loads(payload)
            logger.warning("Stripe webhook signature not verified")

        logger.info("Stripe webhook: %s", event.get("type"))

        if event.get("type") != "checkout.session.completed":
            return {"ok": True}

        session = event["data"]["object"]
        metadata = session.get("metadata", {})
        plan = metadata.get("plan", "").upper()
        user_email = metadata.get("user_email", "")
        session_id = session.get("id", "")

        logger.info("Stripe payment completed: plan=%s email=%s session=%s", plan, user_email, session_id)

        if plan and user_email:
            from .payments import _activate_license
            await _activate_license(user_email, plan, session_id)

        return {"ok": True}

    except Exception as e:
        logger.exception("stripe_webhook error")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/plans")
async def get_stripe_plans():
    return {
        k: {
            "amount_cents": v["amount"],
            "amount_usd": f'{v["amount"] / 100:.2f}',
            "currency": v["currency"],
            "description": v["description"],
            "days": v["days"],
        }
        for k, v in PLANS.items()
    }
