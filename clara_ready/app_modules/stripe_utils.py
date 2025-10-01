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

# no topo do arquivo garanta:
import stripe

def create_checkout_session(
    *, price_id: str, customer_email: str, success_url: str, cancel_url: str
) -> dict:
    """
    Cria sessão do Checkout (assinatura mensal). Retorna {"id":..., "url":...}
    ou {"error": "..."} com a mensagem real do Stripe.
    """
    # Se você usa um flag interno como _ready, mantenha-o;
    # caso não exista, remova a checagem abaixo.
    try:
        # validação básica
        if not price_id:
            return {"error": "Faltou STRIPE_PRICE_ID (precisa ser price_… do mesmo modo das chaves)."}
        if not customer_email:
            return {"error": "Informe um e-mail válido para criar a assinatura."}
        if not success_url or "{CHECKOUT_SESSION_ID}" not in success_url:
            return {"error": "success_url deve conter {CHECKOUT_SESSION_ID}."}

        sess = stripe.checkout.Session.create(
            mode="subscription",                             # assinatura mensal
            line_items=[{"price": price_id, "quantity": 1}],
            customer_email=customer_email,
            success_url=success_url,                         # ex: https://.../?success=true&session_id={CHECKOUT_SESSION_ID}
            cancel_url=cancel_url,
            allow_promotion_codes=True,
            automatic_tax={"enabled": False},
            ui_mode="hosted",
            metadata={"app": "clara_ready"},
        )
        return {"id": sess.id, "url": sess.url}

    except stripe.error.StripeError as e:
        # Mostra a causa real (ex.: “No such price…”, “You cannot use a live key with a test price”, etc.)
        msg = getattr(e, "user_message", "") or str(e)
        return {"error": msg}

    except Exception as e:
        # Outras falhas (ex.: rede, URL inválida)
        return {"error": str(e)}


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


