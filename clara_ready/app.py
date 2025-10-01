# app.py  |  CLARA • Análise de Contratos
# ------------------------------------------------------------
# UX clean + Stripe checkout + análise + CET + Admin
# ------------------------------------------------------------

import os
import io
from typing import Dict, Any

import streamlit as st

# --- seus módulos (já existentes no projeto) ---
from app_modules.pdf_utils import extract_text_from_pdf
from app_modules.rules import RULES  # (mantido p/ compatibilidade futura)
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


# =============================================================================
# Configuração/constantes
# =============================================================================
APP_TITLE = "CLARA • Análise de Contratos"
VERSION = "v12.0"

st.set_page_config(page_title=APP_TITLE, page_icon="📄", layout="wide")

# =============================================================================
# Boot seguro (Stripe + DB) com mensagens claras
# =============================================================================
@st.cache_resource(show_spinner="Iniciando serviços…")
def _boot():
    # 1) Stripe Secret
    stripe_secret = st.secrets.get("STRIPE_SECRET_KEY", os.getenv("STRIPE_SECRET_KEY", ""))
    if not stripe_secret:
        raise RuntimeError(
            "Faltando STRIPE_SECRET_KEY em Settings → Secrets (Streamlit Cloud)."
        )
    init_stripe(stripe_secret)

    # 2) Database/Storage (setup leve)
    init_db()

    # 3) Admin emails
    admins_raw = st.secrets.get("admin_emails", os.getenv("ADMIN_EMAILS", ""))
    admin_set = set([e.strip() for e in admins_raw.split(",") if e.strip()])
    return {
        "admin_emails": admin_set,
        "stripe_secret_present": True,
    }


try:
    BOOT = _boot()
    st.write("🟢 Boot iniciou…  🟢 Serviços prontos.")
except Exception as e:
    st.error(f"❌ Falha ao iniciar serviços: {e}")
    st.stop()


# =============================================================================
# Helpers de sessão
# =============================================================================
def _ensure_session_defaults():
    if "profile" not in st.session_state:
        st.session_state.profile = {"nome": "", "email": "", "papel": "Contratante"}
    if "premium" not in st.session_state:
        st.session_state.premium = False
    if "free_runs_left" not in st.session_state:
        # 1 análise gratuita para degustação
        st.session_state.free_runs_left = 1
    if "cet_result" not in st.session_state:
        st.session_state.cet_result = None


_ensure_session_defaults()


# =============================================================================
# Stripe: tratar retorno do checkout via querystring
# =============================================================================
def handle_checkout_return():
    qs = st.query_params
    base_url = st.secrets.get("BASE_URL", os.getenv("BASE_URL", "")) or st.experimental_user.get("host", "")

    # sucesso
    if qs.get("success") == "true" and qs.get("session_id"):
        try:
            ok, data = verify_checkout_session(qs["session_id"])
        except Exception as e:
            st.error(f"Não foi possível confirmar o pagamento agora. Detalhe: {e}")
            ok, data = False, {}

        if ok:
            # premium liberado
            st.session_state.premium = True

            # registrar assinante (tolerante a falhas)
            try:
                log_subscriber(
                    email=st.session_state.profile.get("email", ""),
                    name=st.session_state.profile.get("nome", ""),
                    stripe_customer_id=(data.get("customer")
                                        or (data.get("subscription") or {}).get("customer")
                                        or ""),
                )
            except Exception:
                pass

            st.success("Pagamento confirmado! Premium liberado ✅")
            # limpar querystring
            st.query_params.clear()
        else:
            st.warning("Não conseguimos confirmar o pagamento. Tente novamente.")
            st.query_params.clear()

    # cancelamento
    if qs.get("canceled") == "true":
        st.info("Checkout cancelado. Você pode tentar novamente quando quiser.")
        st.query_params.clear()


# =============================================================================
# Sidebar: Perfil + Administração
# =============================================================================
def sidebar_profile_and_admin():
    st.sidebar.header("🔐 Seus dados (obrigatório)")

    nome = st.sidebar.text_input("Nome completo*", value=st.session_state.profile.get("nome", ""))
    email = st.sidebar.text_input("E-mail*", value=st.session_state.profile.get("email", ""))
    papel = st.sidebar.selectbox(
        "Você é o contratante?*",
        ["Contratante", "Contratado", "Outro"],
        index=["Contratante", "Contratado", "Outro"].index(st.session_state.profile.get("papel", "Contratante")),
    )

    if st.sidebar.button("Salvar perfil", use_container_width=True):
        st.session_state.profile = {"nome": nome.strip(), "email": email.strip(), "papel": papel}
        st.sidebar.success("Dados salvos!")

        # se já é assinante no banco, liga premium
        if email.strip():
            existing = get_subscriber_by_email(email.strip())
            if existing:
                st.session_state.premium = True

    st.sidebar.markdown("---")
    st.sidebar.subheader("Administração")
    if st.session_state.profile.get("email") in BOOT["admin_emails"]:
        if st.sidebar.checkbox("Área administrativa"):
            st.sidebar.success("Admin ativo")
            with st.sidebar.expander("👥 Assinantes (lista)"):
                try:
                    subs = list_subscribers()
                    st.sidebar.write(subs)
                except Exception as e:
                    st.sidebar.error(f"Não foi possível listar assinantes: {e}")


# =============================================================================
# Landing vendedora + CTA de assinatura
# =============================================================================
def premium_card():
    st.markdown(
        """
        <div style="padding:18px;border:1px solid #e6e8ff;background:#f8f9ff;border-radius:14px">
          <div style="font-weight:600;font-size:18px;margin-bottom:8px">
            Plano Premium
          </div>
          <div style="color:#222;margin-bottom:8px">
            <b>R$ 9,90/mês</b> • Análises ilimitadas • Relatório completo • Suporte prioritário
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    email = st.session_state.profile.get("email", "").strip()
    price_id = st.secrets.get("STRIPE_PRICE_ID", os.getenv("STRIPE_PRICE_ID", ""))
    base_url = st.secrets.get("BASE_URL", os.getenv("BASE_URL", "")) or "https://claraready.streamlit.app"

    if st.session_state.premium:
        st.success("Você já é Premium. Obrigado! 💙")
        return

    if st.button("💳 Assinar Premium agora", type="primary", use_container_width=True):
        if not email:
            st.warning("Informe seu e-mail em **Seus dados** (barra lateral) para assinar.")
            return
        if not price_id:
            st.error("Configuração ausente: STRIPE_PRICE_ID.")
            return

        try:
            sess = create_checkout_session(
                price_id=price_id,
                customer_email=email,
                success_url=f"{base_url}?success=true&session_id={{CHECKOUT_SESSION_ID}}",
                cancel_url=f"{base_url}?canceled=true",
            )
        except Exception as e:
            st.error(f"Erro ao iniciar checkout: {e}")
            return

        url = (sess or {}).get("url")
        if url:
            st.link_button("👉 Abrir checkout seguro", url, use_container_width=True)
        else:
            st.error("Não foi possível iniciar o checkout. Verifique STRIPE_PRICE_ID e chaves.")


def landing():
    st.markdown(
        f"""
        <div style="padding:18px 20px;border-radius:16px;background:#fbfbfe;border:1px solid #eef0ff">
          <h1 style="margin:0">{APP_TITLE}</h1>
          <div style="color:#444;margin-top:6px">
            Clara lê seu contrato e destaca <b>cláusulas abusivas</b>, <b>riscos</b> e <b>o que negociar</b> — em minutos.
          </div>
          <div style="color:#666;margin-top:6px">Versão {VERSION}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col1, col2 = st.columns([1.4, 1])
    with col1:
        st.markdown("### Por que usar a CLARA")
        st.markdown("• Enxerga multas elevadas e travas de rescisão")
        st.markdown("• Resume riscos em linguagem simples")
        st.markdown("• Sugere ações objetivas de negociação")
        st.markdown("• Calculadora de CET para contratos financeiros")
        st.markdown("• Área admin com lista de assinantes")
    with col2:
        premium_card()


# =============================================================================
# Entrada de contrato + contexto
# =============================================================================
def upload_or_paste():
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


# =============================================================================
# Calculadora de CET (com persistência)
# =============================================================================
def show_cet_calculator():
    with st.expander("📈 Calcular CET (opcional)", expanded=False):
        col1, col2, col3 = st.columns(3)
        P = col1.number_input("Valor principal (R$)", min_value=0.0, step=100.0, key="cet_p")
        j = col2.number_input("Juros mensais (%)", min_value=0.0, step=0.1, key="cet_i")  # %
        n = col3.number_input("Parcelas (n)", min_value=1, step=1, key="cet_n")
        fee = st.number_input("Taxas fixas (R$)", min_value=0.0, step=10.0, key="cet_fee")

        if st.button("Calcular CET", key="btn_calc_cet"):
            if P <= 0 or int(n) <= 0:
                st.warning("Preencha um valor principal > 0 e número de parcelas ≥ 1.")
            else:
                try:
                    cet = compute_cet_quick(P, float(j) / 100.0, int(n), float(fee))
                    st.session_state.cet_result = float(cet)
                except Exception as e:
                    st.session_state.cet_result = None
                    st.error(f"Não foi possível calcular o CET: {e}")

        if st.session_state.cet_result is not None:
            st.success(f"**CET aproximado:** {st.session_state.cet_result * 100:.2f}% a.m.")


# =============================================================================
# Execução da análise + relatório
# =============================================================================
def run_analysis(text: str, ctx: Dict[str, Any]):
    st.subheader("3) Resultado")
    if not text.strip():
        st.warning("Envie o contrato (PDF) ou cole o texto para analisar.")
        return

    # limita grátis
    if not st.session_state.premium and st.session_state.free_runs_left <= 0:
        st.info("Você usou sua análise gratuita. Assine o Premium para seguir.")
        return

    with st.spinner("Analisando…"):
        hits, meta = analyze_contract_text(text, ctx)

    if not st.session_state.premium:
        st.session_state.free_runs_left -= 1

    # analytics
    try:
        log_analysis_event(
            email=st.session_state.profile.get("email", ""),
            meta={"setor": ctx["setor"], "papel": ctx["papel"], "len": len(text)},
        )
    except Exception:
        pass

    resume = summarize_hits(hits)
    st.success(f"Resumo: {resume['resumo']}")
    st.write(f"Gravidade: **{resume['gravidade']}** | Pontos críticos: **{resume['criticos']}** | Total: {len(hits)}")

    for h in hits:
        with st.expander(f"{h['severity']} • {h['title']}"):
            st.write(h["explanation"])
            if h.get("suggestion"):
                st.markdown(f"**Sugestão:** {h['suggestion']}")
            if h.get("evidence"):
                st.code(h["evidence"][:1200])

    # calculadora independente
    show_cet_calculator()

    # export txt simples (sem PII sensível)
    if st.button("📥 Baixar relatório (txt)"):
        buff = io.StringIO()
        buff.write(f"{APP_TITLE} {VERSION}\n")
        buff.write(f"Usuário: {st.session_state.profile.get('nome','')} <{st.session_state.profile.get('email','')}>\n")
        buff.write(f"Setor: {ctx['setor']} | Perfil: {ctx['papel']}\n\n")
        buff.write(f"Resumo: {resume['resumo']} (Gravidade: {resume['gravidade']})\n\nPontos de atenção:\n")
        for h in hits:
            buff.write(f"- [{h['severity']}] {h['title']} — {h['explanation']}\n")
            if h.get("suggestion"):
                buff.write(f"  Sugestão: {h['suggestion']}\n")
        st.download_button("Download", buff.getvalue(), file_name="relatorio_clara.txt", mime="text/plain")


# =============================================================================
# Main
# =============================================================================
def main():
    # 1) Tratar retorno do Stripe se houver (?success=?/canceled=)
    handle_checkout_return()

    # 2) Sidebar (perfil + admin)
    sidebar_profile_and_admin()

    # 3) Landing vendedora + CTA
    landing()
    st.markdown("---")

    # 4) Fluxo principal
    text = upload_or_paste()
    ctx = analysis_inputs()

    colA, colB = st.columns([1, 1])
    with colA:
        if st.button("🚀 Começar análise", use_container_width=True):
            run_analysis(text, ctx)
    with colB:
        # Acesso rápido à calculadora a qualquer momento
        show_cet_calculator()


if __name__ == "__main__":
    main()
