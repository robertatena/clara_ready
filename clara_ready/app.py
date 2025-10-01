# -*- coding: utf-8 -*-
"""
CLARA • Análise de Contratos
UX focada em clareza, conversão e estabilidade.

Precisa destes módulos no seu repositório:
- app_modules/pdf_utils.py          -> extract_text_from_pdf(file) -> str
- app_modules/rules.py              -> RULES (usado pela análise)
- app_modules/analysis.py           -> analyze_contract_text, summarize_hits, compute_cet_quick
- app_modules/stripe_utils.py       -> init_stripe, create_checkout_session, verify_checkout_session
- app_modules/storage.py            -> init_db, log_analysis_event, log_subscriber, list_subscribers, get_subscriber_by_email
"""

import os
import io
from typing import Dict, Any, Tuple, List

import streamlit as st

# ----------------- Imports dos seus módulos -----------------
from app_modules.pdf_utils import extract_text_from_pdf
from app_modules.rules import RULES
from app_modules.analysis import (
    analyze_contract_text,
    summarize_hits,
    compute_cet_quick,
)
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

# =================== Configuração básica da página ===================
APP_TITLE = "CLARA • Análise de Contratos"
VERSION   = "v12.0"

st.set_page_config(page_title=APP_TITLE, page_icon="📄", layout="wide")

# =================== Estilos suaves (UX) ============================
st.markdown("""
<style>
/* tipografia e containers */
html, body, [class*="css"]  { font-family: Inter, -apple-system, Segoe UI, Roboto, Helvetica, Arial, "Noto Sans", "Apple Color Emoji", "Segoe UI Emoji"; }
.block-container { padding-top: 1.2rem; }
/* cards leves */
.cl-card { background: #f8f9ff; border: 1px solid #e7eaff; border-radius: 14px; padding: 18px 16px; }
.cl-hero { background: linear-gradient(180deg,#ffffff 0%,#f7f9ff 100%); border: 1px solid #eef1ff; border-radius: 18px; padding: 20px; }
h1, h2, h3 { letter-spacing: .2px; }
.small { color:#6c6f7a; font-size: 0.92rem; }
kbd { background:#eef3ff; border-radius:6px; padding:2px 6px; border:1px solid #dfe6ff; }
</style>
""", unsafe_allow_html=True)

# =================== Utilitários ============================
def _get_secret(key: str, default: str = "") -> str:
    """Busca em st.secrets e, se faltar, no ambiente."""
    return str(st.secrets.get(key, os.getenv(key, default)))

def _is_premium(email: str) -> bool:
    if not email:
        return False
    try:
        return bool(get_subscriber_by_email(email))
    except Exception:
        return False

# =================== Boot protegido em cache =========================
@st.cache_resource(show_spinner="Iniciando serviços…")
def _boot() -> Tuple[str, str, str, str, set]:
    # 1) Secrets essenciais
    stripe_public = _get_secret("STRIPE_PUBLIC_KEY")
    stripe_secret = _get_secret("STRIPE_SECRET_KEY")
    stripe_price  = _get_secret("STRIPE_PRICE_ID")
    base_url      = _get_secret("BASE_URL", "https://claraready.streamlit.app")
    admin_emails  = set([e.strip() for e in _get_secret("admin_emails", "").split(",") if e.strip()])

    # 2) Inicializações leves
    if stripe_secret:
        init_stripe(stripe_secret)
    init_db()

    return stripe_public, stripe_secret, stripe_price, base_url, admin_emails

try:
    STRIPE_PUBLIC_KEY, STRIPE_SECRET_KEY, STRIPE_PRICE_ID, BASE_URL, ADMIN_EMAILS = _boot()
except Exception as e:
    st.error(f"❌ Falha ao iniciar os serviços: {e}")
    st.stop()

# “marcador de vida” — útil para perceber se o app chegou a renderizar
st.write("🟢 Boot iniciou…")

# =================== Estado global simples ===========================
if "profile" not in st.session_state:
    st.session_state.profile = {"nome": "", "email": "", "papel": "Contratante"}
if "premium" not in st.session_state:
    # se o usuário já existe como assinante, marcamos depois de salvar o e-mail
    st.session_state.premium = False
if "free_runs_left" not in st.session_state:
    st.session_state.free_runs_left = 1  # 1 análise grátis
if "show_cet" not in st.session_state:
    st.session_state.show_cet = True     # deixa a calculadora sempre à mão

# =================== Sidebar (perfil + admin) =======================
def sidebar_profile():
    st.sidebar.header("🔐 Seus dados (obrigatório)")

    nome  = st.sidebar.text_input("Nome completo*", value=st.session_state.profile.get("nome", ""))
    email = st.sidebar.text_input("E-mail*", value=st.session_state.profile.get("email", ""))
    papel = st.sidebar.selectbox("Você é o contratante?*", options=["Contratante", "Contratado", "Outro"], index=["Contratante","Contratado","Outro"].index(st.session_state.profile.get("papel","Contratante")))

    if st.sidebar.button("Salvar perfil", use_container_width=True):
        st.session_state.profile = {"nome": nome.strip(), "email": email.strip(), "papel": papel}
        if email.strip():
            st.session_state.premium = _is_premium(email.strip())
        st.sidebar.success("Dados salvos!")

    # Admin compacta
    st.sidebar.markdown("---")
    st.sidebar.subheader("Administração")
    if email.strip() and email.strip() in ADMIN_EMAILS:
        if st.sidebar.checkbox("Área administrativa", key="admin_toggle"):
            try:
                subs = list_subscribers()
                st.sidebar.success("Admin ativo")
                st.sidebar.caption(f"Assinantes ({len(subs)}):")
                st.sidebar.json(subs, expanded=False)
            except Exception as e:
                st.sidebar.error(f"Erro ao carregar assinantes: {e}")

# =================== Seção: apresentação / landing ===================
def landing_hero_and_benefits():
    st.markdown(
        f"""
        <div class="cl-hero">
          <div class="small">Descubra <b>cláusulas abusivas</b>, <b>riscos ocultos</b> e <b>o que negociar</b> — em segundos.</div>
          <h1 style="margin: 6px 0 0">{APP_TITLE}</h1>
          <div class="small">Versão {VERSION}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    left, right = st.columns([1.2, 1])
    with left:
        st.markdown("## Por que usar a CLARA")
        st.markdown("- Destaca multas desproporcionais, travas de rescisão e riscos de responsabilidade")
        st.markdown("- Resume em linguagem simples e sugere **o que negociar**")
        st.markdown("- Calculadora **CET** para contratos financeiros (juros e taxas)")
        st.markdown("- Relatório pronto para compartilhar")
        st.markdown("### Como funciona")
        st.markdown("1. Envie o **PDF** ou cole o **texto** do contrato")
        st.markdown("2. Selecione **setor**, **perfil** e **valor** (opcional)")
        st.markdown("3. Receba **trechos + explicação + ações sugeridas**")

    with right:
        plan_card()

# =================== Stripe: CTA + fluxo seguro ======================
def plan_card():
    st.markdown("## Plano Premium")
    st.markdown("**R$ 9,90/mês** • análises ilimitadas • suporte prioritário")

    email = st.session_state.profile.get("email", "").strip()
    if not STRIPE_PUBLIC_KEY or not STRIPE_PRICE_ID or not STRIPE_SECRET_KEY:
        st.warning("Stripe ainda não está configurado. Defina **STRIPE_PUBLIC_KEY**, **STRIPE_SECRET_KEY** e **STRIPE_PRICE_ID** em *Settings → Secrets*.")
        return

    if not email:
        st.info("Informe seu **e-mail** na barra lateral para habilitar o checkout.")
        return

    if st.session_state.premium:
        st.success("✅ Você já é Premium. Obrigado!")
        return

    if st.button("💳 Assinar Premium agora", type="primary", use_container_width=True):
        try:
            sess = create_checkout_session(
                price_id=STRIPE_PRICE_ID,
                customer_email=email,
                success_url=f"{BASE_URL}?success=true&session_id={{CHECKOUT_SESSION_ID}}",
                cancel_url=f"{BASE_URL}?canceled=true",
            )
            if sess.get("url"):
                st.link_button("👉 Abrir checkout seguro", sess["url"], use_container_width=True)
            else:
                st.error("Não foi possível iniciar o checkout. Verifique STRIPE_PRICE_ID e chaves.")
        except Exception as e:
            st.error(f"Falha ao criar sessão de pagamento: {e}")

def handle_stripe_return():
    """Trata retorno do Stripe via querystring (?success=true&session_id=...)."""
    qs = st.query_params
    if qs.get("success") == "true" and qs.get("session_id"):
        session_id = qs.get("session_id", "")
        try:
            ok, data = verify_checkout_session(session_id)
        except Exception as e:
            ok, data = False, {}
            st.error(f"Não deu para confirmar o pagamento agora. Detalhe: {e}")

        if ok:
            st.session_state.premium = True
            # registra assinante
            try:
                log_subscriber(
                    email=st.session_state.profile.get("email", ""),
                    name=st.session_state.profile.get("nome", ""),
                    stripe_customer_id=(data.get("customer")
                                        or (data.get("subscription") or {}).get("customer")
                                        or "")
                )
            except Exception:
                pass

            st.success("Pagamento confirmado! Premium liberado ✅")
        else:
            st.warning("Não conseguimos confirmar essa sessão de pagamento. Tente novamente.")

        # limpa os parâmetros da URL
        st.query_params.clear()

# =================== Upload/Texto + contexto =========================
def upload_or_paste_section() -> str:
    st.subheader("1) Envie o contrato")
    file = st.file_uploader("PDF do contrato", type=["pdf"], key="file_uploader_pdf")
    raw_text = ""
    if file:
        with st.spinner("Lendo PDF..."):
            try:
                raw_text = extract_text_from_pdf(file) or ""
            except Exception as e:
                st.error(f"Não consegui ler o PDF (tente outro arquivo ou cole o texto). Detalhe: {e}")
                raw_text = ""
    st.markdown("Ou cole o texto abaixo:")
    raw_text = st.text_area("Texto do contrato", height=220, key="ta_contract_text", value=raw_text)
    return raw_text

def analysis_inputs() -> Dict[str, Any]:
    st.subheader("2) Contexto")
    col1, col2, col3 = st.columns(3)
    setor = col1.selectbox("Setor", ["Genérico", "SaaS/Serviços", "Empréstimos", "Educação", "Plano de saúde"], key="sel_setor")
    papel = col2.selectbox("Perfil", ["Contratante", "Contratado", "Outro"], key="sel_papel")
    limite_valor = col3.number_input("Valor máx. (opcional)", min_value=0.0, step=100.0, key="num_limite")
    return {"setor": setor, "papel": papel, "limite_valor": limite_valor}

# =================== Calculadora CET (sempre estável) ================
def cet_calculator() -> None:
    st.subheader("🔢 Calculadora rápida de CET (opcional)")
    c1, c2, c3, c4 = st.columns([1, 1, 1, 1])

    P   = c1.number_input("Valor principal (R$)", min_value=0.0, step=100.0, key="cet_p")
    i_m = c2.number_input("Juros mensais (%)", min_value=0.0, step=0.1, key="cet_i")
    n   = c3.number_input("Parcelas (n)", min_value=1, step=1, key="cet_n")
    fee = c4.number_input("Taxas fixas (R$)", min_value=0.0, step=10.0, key="cet_fee")

    if st.button("Calcular CET", key="btn_calc_cet", use_container_width=True):
        try:
            cet_m = compute_cet_quick(P, i_m/100.0, int(n), fee)  # retorna em fração
            st.success(f"**CET aproximado:** {cet_m*100:.2f}% a.m.")
        except Exception as e:
            st.error(f"Não foi possível calcular o CET: {e}")

# =================== Resultado da análise ============================
def results_section(text: str, ctx: Dict[str, Any]) -> None:
    st.subheader("3) Resultado")
    if not text.strip():
        st.info("Envie o contrato (PDF) **ou** cole o texto para analisar.")
        return

    if (not st.session_state.premium) and st.session_state.free_runs_left <= 0:
        st.warning("Você usou sua análise gratuita. Assine o Premium para continuar.")
        return

    with st.spinner("Analisando..."):
        try:
            hits, meta = analyze_contract_text(text, ctx)
        except Exception as e:
            st.error(f"Opa, algo deu errado na análise. Detalhe: {e}")
            return

    if not st.session_state.premium:
        st.session_state.free_runs_left -= 1

    # log
    try:
        log_analysis_event(
            email=st.session_state.profile.get("email", ""),
            meta={"setor": ctx["setor"], "papel": ctx["papel"], "len": len(text)}
        )
    except Exception:
        pass

    resume = summarize_hits(hits)
    st.success(f"**Resumo:** {resume['resumo']}")
    st.write(f"Gravidade: **{resume['gravidade']}** | Pontos críticos: **{resume['criticos']}** | Total de achados: **{len(hits)}**")

    for h in hits:
        title = f"{h.get('severity','')}: {h.get('title','')}".strip(": ")
        with st.expander(title):
            st.write(h.get("explanation", ""))
            if h.get("suggestion"):
                st.markdown(f"**Sugestão:** {h['suggestion']}")
            if h.get("evidence"):
                st.code((h.get("evidence") or "")[:1200])

    # Export TXT
    if st.button("📥 Baixar relatório (txt)", key="btn_download_report", use_container_width=True):
        buff = io.StringIO()
        p = st.session_state.profile
        buff.write(f"{APP_TITLE} {VERSION}\nUsuário: {p.get('nome')} <{p.get('email')}>\n")
        buff.write(f"Setor: {ctx['setor']} | Perfil: {ctx['papel']}\n\n")
        buff.write(f"Resumo: {resume['resumo']} (Gravidade: {resume['gravidade']})\n\nPontos de atenção:\n")
        for h in hits:
            buff.write(f"- [{h.get('severity','')}] {h.get('title','')} — {h.get('explanation','')}\n")
            if h.get("suggestion"):
                buff.write(f"  Sugestão: {h['suggestion']}\n")
        st.download_button("Download do relatório", buff.getvalue(), file_name="relatorio_clara.txt", mime="text/plain", use_container_width=True)

# =================== Orquestração ============================
def main():
    # 1) Lateral + retorno Stripe
    sidebar_profile()
    handle_stripe_return()

    # 2) Hero/benefícios + CTA
    landing_hero_and_benefits()

    st.markdown("---")

    # 3) Entrada e contexto
    text = upload_or_paste_section()
    ctx  = analysis_inputs()

    # 4) Calculadora sempre disponível (estável)
    cet_calculator()

    # 5) Rodar análise
    run = st.button("🚀 Começar análise", type="primary", use_container_width=True)
    if run:
        results_section(text, ctx)

if __name__ == "__main__":
    main()





