# app_modules/stripe_utils.py
from typing import Tuple, Dict, Any
import stripe
import os

_ready = False

def init_stripe(secret_key: str) -> None:
    global _ready
    if not secret_key:
        _ready = False
        return
    stripe.api_key = secret_key
    _ready = True

def create_checkout_session(*, price_id: str, customer_email: str,
                            success_url: str, cancel_url: str) -> Dict[str, Any]:
    """
    Cria sessão de checkout (subscription). Retorna {"id":..., "url":...} ou {}.
    """
    if not _ready or not price_id or not customer_email:
        return {}
    try:
        sess = stripe.checkout.Session.create(
            mode="subscription",
            line_items=[{"price": price_id, "quantity": 1}],
            customer_email=customer_email,
            success_url=success_url,   # precisa conter {CHECKOUT_SESSION_ID}
            cancel_url=cancel_url,
            allow_promotion_codes=True,
            billing_address_collection="auto",
            ui_mode="hosted"
        )
        return {"id": sess.id, "url": sess.url}
    except Exception:
        return {}

def verify_checkout_session(session_id: str) -> Tuple[bool, Dict[str, Any]]:
    """
    Confere se a sessão está paga/ativa. Retorna (ok, payload).
    """
    if not _ready or not session_id:
        return False, {}
    try:
        s = stripe.checkout.Session.retrieve(session_id, expand=["subscription"])
        paid = (s.get("payment_status") == "paid") or \
               (s.get("status") in ("complete", "open") and bool(s.get("subscription")))
        return bool(paid), s
    except Exception:
        return False, {}

