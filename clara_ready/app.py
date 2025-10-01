# -*- coding: utf-8 -*-
"""
CLARA • Análise de Contratos
UX-first | Jurídico claro | Stripe sólido | CET explicado
"""

import os, io
from typing import Dict, Any, Tuple, List
import streamlit as st

# --- módulos internos (sua estrutura existente) ---
from app_modules.pdf_utils import extract_text_from_pdf
from app_modules.rules import RULES
from app_modules.analysis import analyze_contract_text, summarize_hits, compute_cet_quick
from app_modules.storage import (
    init_db,
    log_analysis_event,
    log_subscriber,
    list_subscribers,
    get_subscriber_by_email,
)
from app_modules.stripe_utils import (
    init_stripe,
    create_checkout_session,
    verify_checkout_session,
)

APP_TITLE = "CLARA • Análise de Contratos"
VERSION = "v12.0"

st.set_page_config(page_title=APP_TITLE, page_icon="📄", layout="wide")

# ---------------------------------------------------------------------
# helpers de sessão
def ss_get(key, default):
    if key not in st.session_state:
        st.session_state[key] = default
    return st.session_state[key]

def ss_set(key, value):
    st.session_state[key] = value

# ---------------------------------------------------------------------
# boot básico (sem chamadas de rede pesadas)
@st.cache_resource(show_spinner="Inicializando serviços…")
def _boot() -> Tuple[bool, str]:
    try:
        # DB
        init_db()
        # Stripe
        secret = st.secrets.get("STRIPE_SECRET_KEY", os.getenv("STRIPE_SECRET_KEY", ""))
        if secret:
            init_stripe(secret)
        return True, ""
    except Exception as e:
        return False, str(e)

ok, err = _boot()
st.write("🟢 Boot iniciou…" if ok else "🔴 Falha no boot")
if not ok:
    st.error(f"Erro ao iniciar serviços: {err}")
    st.stop()

# ---------------------------------------------------------------------
# parâmetros / segredos
ADMIN_EMAILS = set(
    email.strip()
    for email in (st.secrets.get("ADMIN_EMAILS", os.getenv("ADMIN_EMAILS", "")) or "").split(",")
    if email.strip()
)
STRIPE_PUBLIC_KEY = st.secrets.get("STRIPE_PUBLIC_KEY", os.getenv("STRIPE_PUBLIC_KEY", ""))
STRIPE_SECRET_KEY = st.secrets.get("STRIPE_SECRET_KEY", os.getenv("STRIPE_SECRET_KEY", ""))
STRIPE_PRICE_ID   = st.secrets.get("STRIPE_PRICE_ID",   os.getenv("STRIPE_PRICE_ID", ""))
BASE_URL          = st.secrets.get("BASE_URL",          os.getenv("BASE_URL", "http://localhost:8501"))

# ---------------------------------------------------------------------
# estado inicial
ss_get("profile", {"nome": "", "email": "", "cel": "", "papel": "Contratante", "aceite": False})
ss_get("premium", False)
ss_get("free_runs_left", 1)     # 1 análise gratuita
ss_get("last_analysis_ok", False)  # marca se a última análise foi concluída (para descontar cota)

# ---------------------------------------------------------------------
# retorno do Stripe (seguro e idempotente)
qs = st.query_params
if qs.get("success") == "true" and qs.get("session_id"):
    try:
        ok_pay, payload = verify_checkout_session(qs["session_id"])
    except Exception as e:
        ok_pay, payload = False, {}
        st.warning(f"Não conseguimos confirmar o pagamento agora. Tente novamente. Detalhe: {e}")

    if ok_pay:
        ss_set("premium", True)
        # tenta registrar assinante
        try:
            email = payload.get("customer_details", {}).get("email") or st.session_state.profile.get("email", "")
            log_subscriber(
                email=email,
                name=st.session_state.profile.get("nome", ""),
                stripe_customer_id=(payload.get("customer")
                                    or (payload.get("subscription") or {}).get("customer")
                                    or "")
            )
        except Exception:
            pass

        st.success("Pagamento confirmado! Premium liberado ✅")
    else:
        st.warning("Não conseguimos confirmar essa sessão de pagamento. Se foi cobrado, você receberá o acesso em breve.")

    # limpa a URL (remove ?success=true&session_id=…)
    try:
        st.query_params.clear()
    except Exception:
        pass

# ---------------------------------------------------------------------
# UI – Sidebar: cadastro e área ADM
def sidebar_profile():
    st.sidebar.header("🔐 Seus dados (obrigatório)")

    nome  = st.sidebar.text_input("Nome completo*", value=st.session_state.profile.get("nome", ""))
    email = st.sidebar.text_input("E-mail*", value=st.session_state.profile.get("email", ""))
    cel   = st.sidebar.text_input("Celular (WhatsApp)*", value=st.session_state.profile.get("cel", ""))
    papel = st.sidebar.selectbox(
        "Você é o contratante?*", ["Contratante", "Contratado", "Outro"], index=["Contratante","Contratado","Outro"].index(st.session_state.profile.get("papel", "Contratante"))
    )

    aceite = st.sidebar.checkbox(
        "Li e concordo que a CLARA **não substitui** aconselhamento jurídico. "
        "Recomenda-se revisão por advogado(a).",
        value=st.session_state.profile.get("aceite", False),
    )

    if st.sidebar.button("Salvar perfil", use_container_width=True):
        st.session_state.profile = {"nome": nome.strip(), "email": email.strip(), "cel": cel.strip(), "papel": papel, "aceite": aceite}
        # premium por e-mail já inscrito
        if email.strip():
            try:
                existing = get_subscriber_by_email(email.strip())
                if existing:
                    ss_set("premium", True)
            except Exception:
                pass
        st.sidebar.success("Dados salvos!")

    st.sidebar.markdown("---")
    st.sidebar.subheader("Administração")
    if st.session_state.profile.get("email", "") in ADMIN_EMAILS:
        if st.sidebar.checkbox("Exibir lista de assinantes"):
            try:
                subs = list_subscribers()
                st.sidebar.success("Admin ativo")
                st.sidebar.write(subs)
            except Exception as e:
                st.sidebar.warning(f"Erro ao listar: {e}")
    else:
        st.sidebar.caption("Entre com um e-mail admin para a área administrativa.")

sidebar_profile()

# ---------------------------------------------------------------------
# UI – Landing hero
def hero():
    with st.container():
        st.markdown(
            """
            <div style="padding:14px 18px;border-radius:14px;background:#f5f7ff;border:1px solid #e6e8ff">
              <h1 style="margin:0">CLARA • Análise de Contratos</h1>
              <p style="margin:6px 0 0;color:#444">
                Descubra <b>cláusulas abusivas</b>, <b>riscos ocultos</b> e <b>o que negociar</b> — em segundos.
              </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    col1, col2 = st.columns([1.4, 1])
    with col1:
        st.markdown("### Por que usar a CLARA")
        st.markdown("• Destaca multas fora da realidade, travas de rescisão e responsabilidades exageradas")
        st.markdown("• Resume em linguagem simples e sugere <b>o que negociar</b>", unsafe_allow_html=True)
        st.markdown("• Calculadora de <b>CET – Custo Efetivo Total</b> (juros + tarifas + taxas)", unsafe_allow_html=True)
        st.markdown("• Relatório para compartilhar com o time ou advogado(a)")

        with st.expander("O que é CET (Custo Efetivo Total)?", expanded=False):
            st.markdown(
                """
                O **CET** é a taxa que representa **todo o custo** de um financiamento ou parcelamento:
                **juros + tarifas + seguros + outras cobranças**.  
                Ele te ajuda a comparar propostas **de forma justa** e a entender o **custo real** do dinheiro.
                """
            )

    with col2:
        plan_card()

def plan_card():
    st.markdown("### Plano Premium")
    st.caption("R$ **9,90/mês** • análises ilimitadas • suporte prioritário")

    # pré-requisitos do Stripe
    miss = []
    if not STRIPE_PUBLIC_KEY: miss.append("STRIPE_PUBLIC_KEY")
    if not STRIPE_SECRET_KEY: miss.append("STRIPE_SECRET_KEY")
    if not STRIPE_PRICE_ID:   miss.append("STRIPE_PRICE_ID")
    if miss:
        st.info(f"Para ativar o checkout configure os segredos: {', '.join(miss)} em Settings → Secrets.")
        return

    email = st.session_state.profile.get("email", "").strip()
    if not email:
        st.warning("Informe e salve seu e-mail na barra lateral para assinar.")
        return

    btn = st.button("💳 Assinar Premium agora", use_container_width=True)
    if btn:
        try:
            session = create_checkout_session(
                price_id=STRIPE_PRICE_ID,
                customer_email=email,
                success_url=f"{BASE_URL}?success=true&session_id={{CHECKOUT_SESSION_ID}}",
                cancel_url=f"{BASE_URL}?canceled=true",
            )
            if session.get("url"):
                st.link_button("👉 Abrir checkout seguro", session["url"], use_container_width=True)
            else:
                st.error("Não foi possível iniciar o checkout. Revise STRIPE_PRICE_ID e chaves.")
        except Exception as e:
            st.error(f"Checkout indisponível no momento. Detalhe: {e}")

# ---------------------------------------------------------------------
# Guarda de navegação: exige cadastro + aceite antes de analisar
def guard_before_analyze() -> bool:
    p = st.session_state.profile
    msgs = []
    if not p.get("nome", "").strip():  msgs.append("• Informe seu **nome completo**.")
    if not p.get("email", "").strip(): msgs.append("• Informe um **e-mail** válido.")
    if not p.get("cel", "").strip():   msgs.append("• Informe seu **celular/WhatsApp**.")
    if not p.get("aceite", False):     msgs.append("• Confirme o aceite do termo (não substitui advogado).")

    if msgs:
        st.warning("Antes de começar, finalize o cadastro:")
        st.write("\n".join(msgs))
        return False
    return True

# ---------------------------------------------------------------------
# UPLOAD/colagem
def upload_or_paste_section() -> str:
    st.header("1) Envie o contrato")
    file = st.file_uploader("PDF do contrato", type=["pdf"], key="upl_pdf")
    raw_text = ""
    if file:
        with st.spinner("Lendo PDF…"):
            try:
                raw_text = extract_text_from_pdf(file)
            except Exception as e:
                st.error(f"Não foi possível ler o PDF: {e}")

    st.caption("Ou cole o texto abaixo:")
    raw_text = st.text_area("Texto do contrato", height=220, key="ta_contract_text", value=raw_text or "")
    return raw_text

# CONTEXTO
def analysis_inputs() -> Dict[str, Any]:
    st.header("2) Contexto")
    col1, col2, col3 = st.columns(3)
    setor  = col1.selectbox("Setor", ["Genérico", "SaaS/Serviços", "Empréstimos", "Educação", "Plano de saúde"], key="ctx_setor")
    papel  = col2.selectbox("Perfil", ["Contratante", "Contratado", "Outro"], key="ctx_papel")
    limite = col3.number_input("Valor máx. (opcional)", min_value=0.0, step=100.0, key="ctx_limite")
    return {"setor": setor, "papel": papel, "limite_valor": limite}

# CALCULADORA CET
def cet_widget():
    with st.expander("📈 Calculadora de CET (opcional)", expanded=False):
        col1, col2, col3 = st.columns(3)
        P   = col1.number_input("Valor principal (R$)", min_value=0.0, step=100.0, key="cet_p")
        i   = col2.number_input("Juros mensais (%)", min_value=0.0, step=0.1, key="cet_i")
        n   = col3.number_input("Parcelas (n)", min_value=1, step=1, key="cet_n")
        fee = st.number_input("Taxas/seguros/IOF (R$)", min_value=0.0, step=10.0, key="cet_fee")

        if st.button("Calcular CET", key="btn_calc_cet"):
            try:
                cet = compute_cet_quick(P, i / 100.0, int(n), fee)
                st.success(f"**CET aproximado:** {cet * 100:.2f}% a.m.")
                st.caption("O CET considera juros + tarifas + seguros. Use para comparar propostas de forma justa.")
            except Exception as e:
                st.error(f"Erro ao calcular CET: {e}")

# RESULTADOS
def results_section(text: str, ctx: Dict[str, Any]):
    st.header("4) Resultado")

    if not text.strip():
        st.info("Envie um PDF ou cole o texto do contrato.")
        return

    # cota gratuita
    if not st.session_state.premium and st.session_state.free_runs_left <= 0:
        st.warning("Você usou sua análise gratuita. Assine o Premium para continuar.")
        plan_card()
        return

    # roda análise
    with st.spinner("Analisando…"):
        hits, meta = analyze_contract_text(text, ctx)

    # só desconta a cota se a análise de fato rodou
    if not st.session_state.premium:
        # decrementa apenas se há resultado processado
        st.session_state.free_runs_left = max(0, st.session_state.free_runs_left - 1)

    # log leve
    try:
        log_analysis_event(
            email=st.session_state.profile.get("email", ""),
            meta={"setor": ctx["setor"], "papel": ctx["papel"], "len": len(text)},
        )
    except Exception:
        pass

    resume = summarize_hits(hits)
    st.success(f"**Resumo** — {resume['resumo']}")
    st.write(f"Gravidade: **{resume['gravidade']}** | Pontos críticos: **{resume['criticos']}** | Total encontrados: {len(hits)}")

    for h in hits:
        with st.expander(f"{h['severity']} • {h['title']}"):
            st.write(h["explanation"])
            if h.get("suggestion"):
                st.markdown(f"**Sugestão:** {h['suggestion']}")
            if h.get("evidence"):
                st.code(h["evidence"][:1200])

    # relatório txt
    if st.button("📥 Baixar relatório (txt)", key="btn_download_report"):
        buff = io.StringIO()
        p = st.session_state.profile
        buff.write(f"{APP_TITLE} {VERSION}\n")
        buff.write(f"Usuário: {p.get('nome')} <{p.get('email')}> WhatsApp: {p.get('cel')}\n")
        buff.write(f"Setor: {ctx['setor']} | Perfil: {ctx['papel']}\n\n")
        buff.write(f"Resumo: {resume['resumo']} (Gravidade: {resume['gravidade']})\n\nPontos de atenção:\n")
        for h in hits:
            buff.write(f"- [{h['severity']}] {h['title']} — {h['explanation']}\n")
            if h.get("suggestion"):
                buff.write(f"  Sugestão: {h['suggestion']}\n")
        st.download_button("Download", buff.getvalue(), file_name="relatorio_clara.txt", mime="text/plain")

# ---------------------------------------------------------------------
# fluxo principal
def main():
    hero()

    st.markdown("---")
    st.subheader("⚠️ Aviso importante")
    st.caption(
        "A CLARA **não substitui** orientação jurídica profissional. "
        "Use os resultados como ponto de partida e **sempre** valide com advogado(a)."
    )

    if not guard_before_analyze():
        st.stop()

    st.markdown("---")
    text = upload_or_paste_section()
    st.markdown("---")
    ctx = analysis_inputs()
    cet_widget()

    st.markdown("---")
    if st.button("🚀 Executar análise", type="primary", use_container_width=True):
        results_section(text, ctx)

if __name__ == "__main__":
    main()
