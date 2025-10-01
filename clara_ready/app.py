# app.py
# CLARA • Análise de Contratos — v12.1
# UX limpo, checkout Stripe estável, calculadora CET persistente e fix do admin_emails

from __future__ import annotations
import os, io
from typing import Dict, Any, List, Tuple
import streamlit as st

# --- seus módulos (mantidos no repo) ---
from app_modules.pdf_utils import extract_text_from_pdf
from app_modules.rules import RULES  # (usado nos módulos de análise)
from app_modules.analysis import analyze_contract_text, summarize_hits, compute_cet_quick
from app_modules.storage import (
    init_db, log_analysis_event, log_subscriber, list_subscribers, get_subscriber_by_email
)
from app_modules.stripe_utils import init_stripe, create_checkout_session, verify_checkout_session

APP_TITLE  = "CLARA • Análise de Contratos"
VERSION    = "v12.1"
PRICE_COPY = "R$ 9,90/mês"

st.set_page_config(page_title=APP_TITLE, page_icon="📄", layout="wide")

# ======================================================================
# 0) Utilidades
# ======================================================================

def _secret(name: str, default: str = "") -> str | Any:
    """Lê segredo do Streamlit Cloud (Settings > Secrets) ou variável de ambiente."""
    return st.secrets.get(name, os.getenv(name, default))

def _secret_to_emails(value: Any) -> List[str]:
    """
    Converte admin_emails em lista independente do formato:
    - "a@x.com, b@y.com"
    - ["a@x.com", "b@y.com"]
    - None
    """
    if value is None:
        return []
    if isinstance(value, list):
        return [str(x).strip() for x in value if str(x).strip()]
    if isinstance(value, str):
        return [x.strip() for x in value.split(",") if x.strip()]
    # qualquer outro tipo: ignora
    return []

def _hero(text: str):
    st.markdown(
        f"""
        <div style="padding:16px 18px;border-radius:14px;background:#f8faff;border:1px solid #e5ebff">
          <h1 style="margin:0">{APP_TITLE}</h1>
          <p style="margin:10px 0 0;color:#374151;font-size:16px">{text}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

def _read_query() -> Dict[str, str]:
    """Compat para pegar query params em versões diferentes do Streamlit."""
    try:
        qp = dict(st.query_params)  # 1.33+
        # st.query_params devolve valores já 'str'
        return {k: v for k, v in qp.items()}
    except Exception:
        # fallback
        try:
            q = st.experimental_get_query_params()
            return {k: v[0] if isinstance(v, list) and v else str(v) for k, v in q.items()}
        except Exception:
            return {}

# ======================================================================
# 1) Boot seguro (roda 1x por sessão)
# ======================================================================

@st.cache_resource(show_spinner="Iniciando serviços…")
def _boot() -> Tuple[bool, str]:
    try:
        # Stripe
        sk = _secret("STRIPE_SECRET_KEY")
        if not sk:
            return False, "Faltando STRIPE_SECRET_KEY em Settings → Secrets."
        init_stripe(sk)

        # DB/Storage
        init_db()

        return True, ""
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"

ok, err = _boot()
st.write("🟢 Boot iniciou…" if ok else "🔴 Boot falhou")
if not ok:
    st.error(f"Não foi possível iniciar os serviços. Detalhe: {err}")
    st.stop()

# ======================================================================
# 2) Estado básico
# ======================================================================

if "profile" not in st.session_state:
    st.session_state.profile = {"nome":"", "email":"", "papel":"Contratante"}

if "premium" not in st.session_state:
    st.session_state.premium = False

if "free_runs_left" not in st.session_state:
    st.session_state.free_runs_left = 1  # 1 análise grátis por visitante

# CET persistente
if "cet" not in st.session_state:
    st.session_state.cet = {"P": 0.0, "i": 0.0, "n": 12, "fee": 0.0, "result": None}

# ======================================================================
# 3) Sidebar — “Seus dados”
# ======================================================================

def sidebar_profile():
    st.sidebar.header("🔐 Seus dados (obrigatório)")
    nome  = st.sidebar.text_input("Nome completo*", value=st.session_state.profile.get("nome",""), key="profile_nome")
    email = st.sidebar.text_input("E-mail*",        value=st.session_state.profile.get("email",""), key="profile_email")
    papel = st.sidebar.selectbox("Você é o contratante?*", ["Contratante","Contratado","Outro"], key="profile_papel")

    if st.sidebar.button("Salvar perfil", use_container_width=True):
        st.session_state.profile = {"nome": nome.strip(), "email": email.strip(), "papel": papel}
        st.sidebar.success("Dados salvos!")
        # Se já for assinante, libera premium no login
        if email.strip():
            if get_subscriber_by_email(email.strip()):
                st.session_state.premium = True

    # Administração (lista de assinantes) — e-mails admin vindos como string OU lista
    admins_raw = _secret("admin_emails", None)
    admin_emails = set(_secret_to_emails(admins_raw))

    st.sidebar.markdown("---")
    st.sidebar.subheader("Administração")
    if st.session_state.profile.get("email") in admin_emails:
        if st.sidebar.checkbox("Área administrativa"):
            subs = list_subscribers()
            st.sidebar.success("Admin ativo")
            st.sidebar.write(subs)

sidebar_profile()

# ======================================================================
# 4) Landing e CTA (Stripe)
# ======================================================================

def show_checkout_cta():
    """Mostra o botão de assinatura. Cria a sessão do Stripe e exibe o link seguro."""
    email    = st.session_state.profile.get("email","").strip()
    price_id = _secret("STRIPE_PRICE_ID")
    base_url = _secret("BASE_URL", "https://claraready.streamlit.app")

    st.info(f"**{PRICE_COPY}** • análises ilimitadas • suporte prioritário")

    if not email:
        st.warning("Preencha seu **e-mail** na barra lateral para assinar.")
        return
    if not price_id:
        st.error("Configuração ausente: STRIPE_PRICE_ID.")
        return

    if st.button("💳 Assinar Premium agora", type="primary", use_container_width=True, key="btn_subscribe"):
        try:
            session = create_checkout_session(
                price_id=price_id,
                customer_email=email,
                success_url=f"{base_url}?success=true&session_id={{CHECKOUT_SESSION_ID}}",
                cancel_url=f"{base_url}?canceled=true",
            )
        except Exception as e:
            st.error(f"Erro ao criar sessão de pagamento: {e}")
            return

        if session.get("url"):
            st.link_button("👉 Abrir checkout seguro", session["url"], use_container_width=True)
        else:
            st.error("Não foi possível iniciar o checkout. Verifique STRIPE_PRICE_ID e chaves.")

def landing():
    _hero("Descubra **cláusulas abusivas**, **riscos ocultos** e **o que negociar** — em segundos.")
    col1, col2 = st.columns([1.25, 1])
    with col1:
        st.markdown("### Por que usar a CLARA")
        st.markdown("• Destaca multas desproporcionais, travas de rescisão e riscos de responsabilidade")
        st.markdown("• Resume em linguagem simples e sugere **o que negociar**")
        st.markdown("• Calculadora **CET** para contratos financeiros (juros e taxas)")
        st.markdown("• Relatório para compartilhar com o time ou advogado(a)")

        st.markdown("### Como funciona")
        st.markdown("1) Envie o PDF **ou** cole o texto do contrato")
        st.markdown("2) Selecione **setor**, **perfil** e **valor** (opcional)")
        st.markmarkdown("3) Receba **trechos + explicações + ação recomendada**")

    with col2:
        st.markdown("### Plano Premium")
        show_checkout_cta()

landing()

# ======================================================================
# 5) Tratar retorno do Stripe (URL ?success=true&session_id=...)
# ======================================================================

def handle_checkout_return():
    qs = _read_query()
    if qs.get("success") == "true" and qs.get("session_id"):
        try:
            ok, data = verify_checkout_session(qs["session_id"])
        except Exception as e:
            st.error(f"Não foi possível confirmar o pagamento agora. Detalhe: {e}")
            ok, data = False, {}

        if ok:
            st.session_state.premium = True
            try:
                # registra assinante
                log_subscriber(
                    email=st.session_state.profile.get("email",""),
                    name=st.session_state.profile.get("nome",""),
                    stripe_customer_id=(data.get("customer")
                        or (data.get("subscription") or {}).get("customer")
                        or "")
                )
            except Exception:
                pass
            st.success("Pagamento confirmado! Premium liberado ✅")
        else:
            st.warning("Não conseguimos confirmar essa sessão de pagamento. Tente novamente.")
        # limpa a querystring (sem recarregar a página)
        try:
            st.query_params.clear()
        except Exception:
            pass

handle_checkout_return()

# ======================================================================
# 6) Upload/colagem + contexto
# ======================================================================

def input_contract() -> str:
    st.markdown("### 1) Envie o contrato")
    file = st.file_uploader("PDF do contrato", type=["pdf"], key="u_pdf")
    text = ""
    if file:
        with st.spinner("Lendo PDF…"):
            text = extract_text_from_pdf(file) or ""
    st.markdown("Ou cole o texto abaixo:")
    text = st.text_area("Texto do contrato", value=text, height=220, key="ta_text")
    return text

def input_context() -> Dict[str, Any]:
    st.markdown("### 2) Contexto")
    c1, c2, c3 = st.columns(3)
    setor   = c1.selectbox("Setor", ["Genérico", "SaaS/Serviços", "Empréstimos", "Educação", "Plano de saúde"], key="ctx_setor")
    perfil  = c2.selectbox("Perfil", ["Contratante", "Contratado", "Outro"], key="ctx_perfil")
    limite  = c3.number_input("Valor máx. (opcional)", min_value=0.0, step=100.0, key="ctx_limite")
    return {"setor": setor, "papel": perfil, "limite_valor": limite}

# ======================================================================
# 7) Calculadora CET (persistente, não some)
# ======================================================================

def cet_block():
    st.markdown("### 3) Calculadora CET (opcional)")
    with st.form("cet_form", clear_on_submit=False):
        c1, c2, c3, c4 = st.columns(4)
        st.session_state.cet["P"]   = c1.number_input("Principal (R$)", min_value=0.0, step=100.0, value=float(st.session_state.cet["P"]), key="cet_P")
        st.session_state.cet["i"]   = c2.number_input("Juros mensais (%)", min_value=0.0, step=0.1,  value=float(st.session_state.cet["i"]), key="cet_i")
        st.session_state.cet["n"]   = c3.number_input("Parcelas (n)",      min_value=1,   step=1,    value=int(st.session_state.cet["n"]), key="cet_n")
        st.session_state.cet["fee"] = c4.number_input("Taxas fixas (R$)",  min_value=0.0, step=10.0, value=float(st.session_state.cet["fee"]), key="cet_fee")

        submitted = st.form_submit_button("Calcular CET")
        if submitted:
            P   = float(st.session_state.cet["P"])
            i_m = float(st.session_state.cet["i"]) / 100.0
            n   = int(st.session_state.cet["n"])
            fee = float(st.session_state.cet["fee"])
            try:
                result = compute_cet_quick(P, i_m, n, fee)
            except Exception:
                result = None
            st.session_state.cet["result"] = result

    if st.session_state.cet["result"] is not None:
        st.success(f"**CET aproximado:** {st.session_state.cet['result']*100:.2f}% a.m.")

# ======================================================================
# 8) Resultado da análise
# ======================================================================

def results(text: str, ctx: Dict[str, Any]):
    st.markdown("### 4) Resultado")
    if not text.strip():
        st.info("Envie o contrato (PDF) ou cole o texto para analisar.")
        return
    if not st.session_state.premium and st.session_state.free_runs_left <= 0:
        st.warning("Você usou sua análise gratuita. Assine o Premium para continuar.")
        return

    with st.spinner("Analisando…"):
        hits, meta = analyze_contract_text(text, ctx)

    if not st.session_state.premium:
        st.session_state.free_runs_left -= 1

    # log simples
    try:
        log_analysis_event(
            email=st.session_state.profile.get("email",""),
            meta={"setor":ctx["setor"], "papel":ctx["papel"], "len":len(text)}
        )
    except Exception:
        pass

    # resumo + cartões
    resumo = summarize_hits(hits)
    st.success(f"**Resumo:** {resumo['resumo']}")
    st.caption(f"Gravidade: **{resumo['gravidade']}** | Pontos críticos: **{resumo['criticos']}** | Total: {len(hits)}")

    for h in hits:
        with st.expander(f"{h['severity']} • {h['title']}", expanded=False):
            st.write(h["explanation"])
            if h.get("suggestion"):
                st.markdown(f"**Sugestão:** {h['suggestion']}")
            if h.get("evidence"):
                st.code(h["evidence"][:1500])

    # relatório txt
    if st.download_button(
        "📥 Baixar relatório (txt)",
        data=_build_report_txt(text, ctx, resumo, hits),
        file_name="relatorio_clara.txt",
        mime="text/plain",
        use_container_width=True
    ):
        pass

def _build_report_txt(text: str, ctx: Dict[str, Any], resumo: Dict[str,Any], hits) -> str:
    buff = io.StringIO()
    buff.write(f"{APP_TITLE} {VERSION}\n")
    buff.write(f"Usuário: {st.session_state.profile.get('nome')} <{st.session_state.profile.get('email')}>\n")
    buff.write(f"Setor: {ctx['setor']} | Perfil: {ctx['papel']}\n\n")
    buff.write(f"Resumo: {resumo['resumo']} (Gravidade: {resumo['gravidade']})\n\nPontos de atenção:\n")
    for h in hits:
        buff.write(f"- [{h['severity']}] {h['title']} — {h['explanation']}\n")
        if h.get("suggestion"):
            buff.write(f"  Sugestão: {h['suggestion']}\n")
    return buff.getvalue()

# ======================================================================
# 9) Orquestração da página
# ======================================================================

st.markdown("---")
contract_text = input_contract()
context       = input_context()

with st.expander("🧮 Calculadora de CET (opcional)", expanded=False):
    cet_block()

col_run, col_hint = st.columns([1,2])
run_clicked = col_run.button("🚀 Começar análise", type="primary", use_container_width=True)
col_hint.caption("Dica: para contratos financeiros/educação, ver o CET ajuda na decisão.")

if run_clicked:
    results(contract_text, context)

st.caption(f"{VERSION} • Feito com ❤️ para facilitar sua vida contratual. Não substitui um advogado")




