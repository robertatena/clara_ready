import stripe
from typing import Tuple, Dict, Any

_ready = False

def init_stripe(secret_key: str):
    global _ready
    if secret_key:
        stripe.api_key = secret_key
        _ready = True
    else:
        _ready = False

def create_checkout_session(price_id: str, customer_email: str, success_url: str, cancel_url: str):
    if not _ready or not price_id or not customer_email:
        return {}

    try:
        s = stripe.checkout.Session.create(
            mode="subscription",
            line_items=[{"price": price_id, "quantity": 1}],
            customer_email=customer_email,
            success_url=success_url,   # deve conter {CHECKOUT_SESSION_ID}
            cancel_url=cancel_url,
            allow_promotion_codes=True,
            billing_address_collection="auto"
        )
        return {"id": s.id, "url": s.url}
    except Exception as e:
        # opcional: logar e
        return {}


def verify_checkout_session(session_id: str) -> Tuple[bool, Dict[str,Any]]:
    if not _ready: return (False, {})
    try:
        s = stripe.checkout.Session.retrieve(session_id, expand=["customer_details"])
        return (s.payment_status == "paid", s if s.payment_status == "paid" else {})
    except Exception:
        return (False, {})

