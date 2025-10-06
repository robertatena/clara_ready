# app.py
# CLARA • Análise de Contratos
# UX caprichado + Stripe robusto + cadastro mínimo + admin seguro

import os
import io
from typing import Dict, Any, Tuple, Set

import streamlit as st

# ---- Módulos locais (mantenha sua estrutura) ----
from app_modules.pdf_utils import extract_text_from_pdf
from app_modules.analysis import analyze_contract_text, summarize_hits, compute_cet_quick
from app_modules.stripe_utils import (
    init_stripe,
    create_checkout_session,
    verify_checkout_session,
)
from app_modules.storage import (
    init_db,
    log_analysis_event,
    log_subscriber,
    list_subscribers,
    get_subscriber_by_email,
)
from datetime import datetime
from pathlib import Path

VISITS_CSV = Path("/tmp/visits.csv")

def log_visit(email: str):
    if not email:
        return
    VISITS_CSV.parent.mkdir(parents=True, exist_ok=True)
    with VISITS_CSV.open("a", encoding="utf-8") as f:
        f.write(f"{datetime.utcnow().isoformat()},{email}\n")

def read_visits():
    if not VISITS_CSV.exists():
        return []
    rows = []
    with VISITS_CSV.open("r", encoding="utf-8") as f:
        for line in f:
            ts, em = line.strip().split(",", 1)
            rows.append({"quando (UTC)": ts, "email": em})
    # mais recentes primeiro
    return rows[::-1]


# -------------------------------------------------
# Config & Constantes
# -------------------------------------------------
APP_TITLE = "CLARA • Análise de Contratos"
VERSION = "v12.1"

st.set_page_config(page_title=APP_TITLE, page_icon="📄", layout="wide")

# Segredos/ENV
STRIPE_PUBLIC_KEY = st.secrets.get("STRIPE_PUBLIC_KEY", os.getenv("STRIPE_PUBLIC_KEY", ""))
STRIPE_SECRET_KEY = st.secrets.get("STRIPE_SECRET_KEY", os.getenv("STRIPE_SECRET_KEY", ""))
STRIPE_PRICE_ID   = st.secrets.get("STRIPE_PRICE_ID",   os.getenv("STRIPE_PRICE_ID", ""))
BASE_URL          = st.secrets.get("BASE_URL",          os.getenv("BASE_URL", "https://claraready.streamlit.app"))

MONTHLY_PRICE_TEXT = "R$ 9,90/mês"


def _parse_admin_emails() -> Set[str]:
    """
    admin_emails pode vir como:
     - string: "a@b.com,c@d.com"
     - lista: ["a@b.com", "c@d.com"]
     - vazio/ausente
    Normalizamos em set lowercased.
    """
    raw = st.secrets.get("admin_emails", None)
    if raw is None:
        raw = os.getenv("ADMIN_EMAILS", "")

    emails: Set[str] = set()

    if isinstance(raw, list):
        emails = {str(x).strip().lower() for x in raw if str(x).strip()}
    elif isinstance(raw, str):
        emails = {e.strip().lower() for e in raw.split(",") if e.strip()}

    return emails


ADMIN_EMAILS = _parse_admin_emails()

# -------------------------------------------------
# CSS (estética)
# -------------------------------------------------
st.markdown(
    """
    <style>
      .hero {
        padding: 18px 22px; border-radius: 14px;
        background: linear-gradient(180deg, #f7f8ff 0%, #ffffff 100%);
        border: 1px solid #eceffd; margin-bottom: 14px;
      }
      .pill {
        display:inline-block; padding:4px 10px; border-radius:999px;
        background:#eef1ff; border:1px solid #e3e6ff; font-size:12.5px; color:#3142c6;
      }
      .muted { color:#5c6370; }
      .footer-note { font-size: 12.5px; color:#6e7480; }
    </style>
    """,
    unsafe_allow_html=True,
)

# -------------------------------------------------
# Estado inicial
# -------------------------------------------------
if "profile" not in st.session_state:
    st.session_state.profile = {"nome": "", "email": "", "cel": "", "papel": "Contratante"}

if "premium" not in st.session_state:
    st.session_state.premium = False

if "free_runs_left" not in st.session_state:
    st.session_state.free_runs_left = 1  # 1 análise gratuita por e-mail

# -------------------------------------------------
# Boot único (Stripe + DB) com mensagens úteis
# -------------------------------------------------
@st.cache_resource(show_spinner="Iniciando serviços…")
def _boot() -> Tuple[bool, str]:
    try:
        if not STRIPE_SECRET_KEY:
            return False, "Faltando STRIPE_SECRET_KEY (Settings → Secrets)."
        init_stripe(STRIPE_SECRET_KEY)
        init_db()
        return True, ""
    except Exception as e:
        return False, f"Falha ao iniciar serviços: {e}"

ok_boot, boot_msg = _boot()
st.write("🟢 Boot iniciou…")
if not ok_boot:
    st.error(boot_msg)
    st.stop()

# -------------------------------------------------
# Utilidades
# -------------------------------------------------
def current_email() -> str:
    return (st.session_state.profile.get("email") or "").strip().lower()

def is_premium() -> bool:
    """Retorna se o usuário é premium, com cache em sessão."""
    if st.session_state.premium:
        return True
    email = current_email()
    if not email:
        return False
    try:
        sub = get_subscriber_by_email(email)
        if sub:
            st.session_state.premium = True
            return True
        return False
    except Exception:
        return False

def require_profile() -> bool:
    p = st.session_state.profile
    return bool((p.get("nome") or "").strip() and (p.get("email") or "").strip() and (p.get("cel") or "").strip())

def stripe_diagnostics() -> Tuple[bool, str]:
    """Diagnóstico rápido de configuração Stripe."""
    miss = []
    if not STRIPE_PUBLIC_KEY: miss.append("STRIPE_PUBLIC_KEY")
    if not STRIPE_SECRET_KEY: miss.append("STRIPE_SECRET_KEY")
    if not STRIPE_PRICE_ID:   miss.append("STRIPE_PRICE_ID")
    if miss:
        return False, f"Configure os segredos ausentes: {', '.join(miss)}."
    if STRIPE_PRICE_ID.startswith("prod_"):
        return False, "Use um **price_...** (não **prod_...**). No Stripe crie um Preço e copie o ID **price_...**"
    if not STRIPE_PRICE_ID.startswith("price_"):
        return False, "O STRIPE_PRICE_ID parece inválido. Deve começar com **price_...**"
    return True, ""

# -------------------------------------------------
# Sidebar • Cadastro mínimo + Admin
# -------------------------------------------------
def sidebar_profile():
    st.sidebar.header("🔐 Seus dados (obrigatório)")
    nome  = st.sidebar.text_input("Nome completo*", value=st.session_state.profile.get("nome", ""))
    email = st.sidebar.text_input("E-mail*",        value=st.session_state.profile.get("email", ""))
    cel   = st.sidebar.text_input("Celular*",       value=st.session_state.profile.get("cel", ""))
    papel = st.sidebar.selectbox("Você é o contratante?*", ["Contratante", "Contratado", "Outro"],
                                 index=["Contratante","Contratado","Outro"].index(st.session_state.profile.get("papel", "Contratante")))
    if st.sidebar.button("Salvar perfil"):
        st.session_state.profile = {"nome": nome.strip(), "email": email.strip(), "cel": cel.strip(), "papel": papel}
        st.sidebar.success("Dados salvos!")
        # Sobe premium se já estiver assinado
        if current_email():
            if get_subscriber_by_email(current_email()):
                st.session_state.premium = True

    st.sidebar.markdown("---")
    st.sidebar.subheader("Administração")
    if current_email() in ADMIN_EMAILS:
        if st.sidebar.checkbox("Área administrativa"):
            st.sidebar.success("Admin ativo")
            try:
                subs = list_subscribers()
                with st.sidebar.expander("👥 Assinantes (Stripe)", expanded=False):
                    st.write(subs if subs else "Nenhum assinante localizado ainda.")
            except Exception as e:
                st.sidebar.error(f"Não foi possível listar assinantes: {e}")

# -------------------------------------------------
# Hero + Benefícios + Passo-a-passo + FAQ CET + Aviso legal
# -------------------------------------------------
def landing_block():
    with st.container():
        st.markdown(
            f"""
            <div class="hero">
              <div class="pill">Nova versão • {VERSION}</div>
              <h1 style="margin:8px 0 4px 0;">{APP_TITLE}</h1>
              <p class="muted" style="margin:0;">
                Descubra <b>cláusulas abusivas</b>, <b>riscos ocultos</b> e <b>o que negociar</b> — em segundos.
              </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        c1, c2 = st.columns([1.2, 1])
        with c1:
            st.markdown("### Por que usar a CLARA")
            st.markdown("• Destaca multas fora da realidade; travas de rescisão e responsabilidades exageradas")
            st.markdown("• Resume em linguagem simples e sugere **o que negociar**")
            st.markdown("• Calculadora de **CET – Custo Efetivo Total** (juros + tarifas + taxas)")
            st.markdown("• Relatório para compartilhar com seu time ou advogado(a)")
            with st.expander("O que é CET (Custo Efetivo Total)?"):
                st.write(
                    "O **CET** é a taxa que representa **todo o custo** de um financiamento ou parcelamento "
                    "(juros + tarifas + seguros + outras cobranças). Ajuda a comparar propostas e enxergar "
                    "o custo real além do “só juros”."
                )

            st.markdown("### Como funciona")
            st.markdown("1. Envie o PDF ou cole o texto do contrato")
            st.markdown("2. Selecione **setor**, **perfil** e (opcional) valor")
            st.markdown("3. Receba **trecho + explicação + ação de negociação**")
            st.markdown("4. (Opcional) Calcule o **CET**")
            st.info("**Aviso legal**: A CLARA **não substitui um(a) advogado(a)**. Use para triagem e preparo da negociação.")

        with c2:
            pricing_card()

# -------------------------------------------------
# Stripe • Pricing e CTA
# -------------------------------------------------
def pricing_card():
    st.markdown("### Plano Premium")
    st.caption(f"{MONTHLY_PRICE_TEXT} • análises ilimitadas • suporte prioritário")

    okS, msgS = stripe_diagnostics()
    email = current_email()

    if not email:
        st.info("Informe e salve seu **nome, e-mail e celular** na barra lateral para assinar.")
        return

    if st.button("💳 Assinar Premium agora", use_container_width=True):
        if not okS:
            st.error(msgS)
            return
        try:
            sess = create_checkout_session(
                price_id=STRIPE_PRICE_ID,
                customer_email=email,
                success_url=f"{BASE_URL}?success=true&session_id={{CHECKOUT_SESSION_ID}}",
                cancel_url=f"{BASE_URL}?canceled=true",
            )
            if sess.get("url"):
                st.success("Sessão criada! Clique abaixo para abrir o checkout seguro.")
                st.link_button("👉 Abrir checkout seguro", sess["url"], use_container_width=True)
            else:
                st.error(sess.get("error", "Stripe indisponível no momento. Tente novamente."))
        except Exception as e:
            st.error(f"Stripe indisponível no momento. Detalhe: {e}")

# -------------------------------------------------
# Tratamento do retorno do Stripe (seguro)
# -------------------------------------------------
def handle_checkout_result():
    qs = st.query_params  # Streamlit 1.37+
    if qs.get("success") == "true" and qs.get("session_id"):
        session_id = qs["session_id"]
        try:
            ok, payload = verify_checkout_session(session_id)
        except Exception as e:
            st.error(f"Não foi possível confirmar o pagamento: {e}")
            ok, payload = False, {}

        if ok:
            email = current_email()
            try:
                log_subscriber(
                    email=email,
                    name=st.session_state.profile.get("nome", ""),
                    stripe_customer_id=(payload.get("customer")
                                       or (payload.get("subscription") or {}).get("customer")
                                       or ""),
                )
            except Exception:
                pass
            st.session_state.premium = True
            st.success("Pagamento confirmado! Premium liberado ✅")
        else:
            st.warning("Não conseguimos confirmar essa sessão de pagamento. Tente novamente.")
        # Limpa a querystring
        try:
            st.query_params.clear()
        except Exception:
            pass

# -------------------------------------------------
# Upload & Inputs & CET & Resultados
# -------------------------------------------------
def upload_or_paste_section() -> str:
    st.subheader("1) Envie o contrato")
    file = st.file_uploader("PDF do contrato", type=["pdf"])
    raw_text = ""
    if file:
        with st.spinner("Lendo PDF…"):
            raw_text = extract_text_from_pdf(file)
    st.markdown("Ou cole o texto abaixo:")
    raw_text = st.text_area("Texto do contrato", height=220, value=raw_text or "")
    return raw_text

def analysis_inputs() -> Dict[str, Any]:
    st.subheader("2) Contexto")
    col1, col2, col3 = st.columns(3)
    setor = col1.selectbox("Setor", ["Genérico", "SaaS/Serviços", "Empréstimos", "Educação", "Plano de saúde"])
    papel = col2.selectbox("Perfil", ["Contratante", "Contratado", "Outro"])
    limite_valor = col3.number_input("Valor máx. (opcional)", min_value=0.0, step=100.0)
    return {"setor": setor, "papel": papel, "limite_valor": limite_valor}

def cet_calculator_block():
    with st.expander("📈 Calculadora de CET (opcional)", expanded=False):
        col1, col2, col3 = st.columns(3)
        P   = col1.number_input("Valor principal (R$)", min_value=0.0, step=100.0, key="cet_p")
        i_m = col2.number_input("Juros mensais (%)", min_value=0.0, step=0.1, key="cet_i")
        n   = col3.number_input("Parcelas (n)", min_value=1, step=1, key="cet_n")
        fee = st.number_input("Taxas fixas totais (R$)", min_value=0.0, step=10.0, key="cet_fee")
        if st.button("Calcular CET", key="btn_calc_cet"):
            cet = compute_cet_quick(P, i_m / 100.0, int(n), fee)
            st.success(f"**CET aproximado:** {cet*100:.2f}% a.m.")

def results_section(text: str, ctx: Dict[str, Any]):
    st.subheader("4) Resultado")
    email = current_email()

    if not require_profile():
        st.info("Preencha e salve **nome, e-mail e celular** na barra lateral para liberar a análise.")
        return

    if not text.strip():
        st.warning("Envie o contrato (PDF) ou cole o texto para analisar.")
        return

    # Free/Premium
    if not is_premium():
        if st.session_state.free_runs_left <= 0:
            st.info("Você usou sua análise gratuita. **Assine o Premium** para continuar.")
            return

    with st.spinner("Analisando…"):
        hits, meta = analyze_contract_text(text, ctx)

    if not is_premium():
        st.session_state.free_runs_left -= 1

    # log de uso (útil p/ admin)
    log_analysis_event(email=email, meta={"setor": ctx["setor"], "papel": ctx["papel"], "len": len(text)})

    resume = summarize_hits(hits)
    st.success(f"Resumo: {resume['resumo']}")
    st.write(f"Gravidade: **{resume['gravidade']}** | Pontos críticos: **{resume['criticos']}** | Total identificados: {len(hits)}")

    for h in hits:
        with st.expander(f"{h['severity']} • {h['title']}", expanded=False):
            st.write(h["explanation"])
            if h.get("suggestion"):
                st.markdown(f"**Sugestão:** {h['suggestion']}")
            if h.get("evidence"):
                st.code(h["evidence"][:1200])

    cet_calculator_block()

    # Relatório (corrigido)
    buff = io.StringIO()
    buff.write(f"{APP_TITLE} {VERSION}\n")
    buff.write(f"Usuário: {st.session_state.profile.get('nome')} <{email}>  •  Papel: {ctx['papel']}\n")
    buff.write(f"Setor: {ctx['setor']}  |  Valor máx.: {ctx['limite_valor']}\n\n")
    buff.write(f"Resumo: {resume['resumo']} (Gravidade: {resume['gravidade']})\n\n")
    buff.write("Pontos de atenção:\n")
    for h in hits:
        buff.write(f"- [{h['severity']}] {h['title']} — {h['explanation']}\n")
        if h.get("suggestion"):
            buff.write(f"  Sugestão: {h['suggestion']}\n")
    st.download_button("📥 Baixar relatório (txt)", data=buff.getvalue(),
                       file_name="relatorio_clara.txt", mime="text/plain")

# -------------------------------------------------
# Orquestração
# -------------------------------------------------
def main():
    sidebar_profile()
    handle_checkout_result()
    landing_block()

    st.markdown("---")
    st.markdown("### Comece sua análise")
    st.caption("Preencha os seus dados na barra lateral antes de enviar o contrato.")

    text = upload_or_paste_section()
    ctx  = analysis_inputs()

    st.markdown("")
    if st.button("🚀 Começar análise", use_container_width=True):
        results_section(text, ctx)

    st.markdown("---")
    st.markdown(
        '<p class="footer-note">A CLARA auxilia na leitura e entendimento de contratos, '
        'mas <b>não substitui</b> a avaliação de um(a) advogado(a).</p>',
        unsafe_allow_html=True
    )

if __name__ == "__main__":
    main()

