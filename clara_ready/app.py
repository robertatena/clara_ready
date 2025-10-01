# app.py — CLARA Ready (limpo)

import os, io
from typing import Dict, Any
import streamlit as st

# --- Módulos internos ---------------------------------------------------------
from app_modules.pdf_utils import extract_text_from_pdf
from app_modules.rules import RULES
from app_modules.analysis import analyze_contract_text, summarize_hits, compute_cet_quick
from app_modules.stripe_utils import init_stripe, create_checkout_session, verify_checkout_session
from app_modules.storage import init_db, log_analysis_event, log_subscriber, list_subscribers, get_subscriber_by_email
# ------------------------------------------------------------------------------

APP_TITLE = "CLARA • Análise de Contratos"
VERSION = "v11.1"

st.set_page_config(page_title=APP_TITLE, page_icon="🧾", layout="wide")

# --- Indicadores de vida ------------------------------------------------------
st.write("🟢 Boot iniciou…")

@st.cache_resource(show_spinner="Iniciando serviços…")
def _boot():
    """Inicializa Stripe e Storage/DB (roda 1x por sessão)."""
    stripe_secret = st.secrets.get("STRIPE_SECRET_KEY", os.getenv("STRIPE_SECRET_KEY", ""))
    if not stripe_secret:
        raise RuntimeError("Faltando STRIPE_SECRET_KEY em Settings → Secrets (Streamlit Cloud).")

    init_stripe(stripe_secret)  # não faz chamada de rede aqui
    init_db()                   # setup leve
    return True

try:
    _ = _boot()
except Exception as e:
    st.error(f"❌ Falha ao iniciar: {e}")
    st.stop()

st.write("🟢 Serviços prontos.")
# -----------------------------------------------------------------------------


# =============== Estado base ==================================================
if "profile" not in st.session_state:
    st.session_state.profile = {"nome": "", "email": "", "papel": "Contratante"}

if "premium" not in st.session_state:
    st.session_state.premium = False

if "free_runs_left" not in st.session_state:
    st.session_state.free_runs_left = 1

if "cet_result" not in st.session_state:
    st.session_state.cet_result = None
# ==============================================================================


# =============== Stripe: retorno pós-checkout ================================
def handle_stripe_return():
    """Confirma pagamento pelo session_id retornado e limpa a URL."""
    qs = st.query_params
    if qs.get("success") == "true" and qs.get("session_id"):
        sid = qs["session_id"]
        try:
            ok, data = verify_checkout_session(sid)
        except Exception as e:
            st.error(f"Não deu para confirmar o pagamento agora. Detalhe: {e}")
            return

        if ok:
            st.session_state.premium = True
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

        # Limpa os parâmetros da URL
        st.query_params.clear()

handle_stripe_return()
# ==============================================================================


# =============== Sidebar (perfil + admin) ====================================
def sidebar_profile():
    st.sidebar.header("🔐 Seus dados (obrigatório)")
    nome  = st.sidebar.text_input("Nome completo*", value=st.session_state.profile.get("nome",""), key="profile_nome")
    email = st.sidebar.text_input("E-mail*",        value=st.session_state.profile.get("email",""), key="profile_email")
    papel = st.sidebar.selectbox("Você é o contratante?*", ["Contratante","Contratado","Outro"],
                                 index=["Contratante","Contratado","Outro"].index(st.session_state.profile.get("papel","Contratante")),
                                 key="profile_papel")

    if st.sidebar.button("Salvar perfil", use_container_width=True):
        st.session_state.profile = {"nome": nome.strip(), "email": email.strip(), "papel": papel}
        st.sidebar.success("Dados salvos!")
        if email:
            existing = get_subscriber_by_email(email)
            if existing:
                st.session_state.premium = True

    st.sidebar.markdown("---")
    st.sidebar.subheader("Administração")
    admin_emails = set(st.secrets.get("admin_emails", os.getenv("ADMIN_EMAILS","").split(",")))
    if st.session_state.profile.get("email") in admin_emails:
        if st.sidebar.checkbox("Área administrativa", key="admin_toggle"):
            st.sidebar.success("Admin ativo")
            subs = list_subscribers()
            with st.sidebar.expander("👥 Assinantes"):
                st.write(subs)
# ==============================================================================


# =============== Landing & Checkout ==========================================
def show_checkout_cta():
    """Botão de assinatura. Cria a sessão do Stripe e mostra link seguro."""
    email = (st.session_state.get("profile", {}) or {}).get("email", "").strip()
    price_id = st.secrets.get("STRIPE_PRICE_ID", os.getenv("STRIPE_PRICE_ID",""))
    base_url = st.secrets.get("BASE_URL", "https://claraready.streamlit.app")

    if not email:
        st.info("Informe seu e-mail em **Seus dados** (barra lateral) para assinar.")
        return
    if not price_id:
        st.error("Configuração ausente: STRIPE_PRICE_ID (tem que ser price_...).")
        return

    if st.button("💳 Assinar Premium agora", type="primary", use_container_width=True):
        sess = create_checkout_session(
            price_id=price_id,
            customer_email=email,
            success_url=f"{base_url}?success=true&session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{base_url}?canceled=true",
        )
        if sess.get("url"):
            st.link_button("👉 Abrir checkout seguro", sess["url"], use_container_width=True)
      # dentro de show_checkout_cta(), troque o else:
else:
    st.error("Não foi possível iniciar o checkout. Verifique STRIPE_PRICE_ID e chaves.")
    # debug seguro:
    st.caption("Dica: confirme se o STRIPE_PRICE_ID começa com price_ e é do mesmo ambiente das chaves (test/live).")

def landing_page():
    st.markdown(
        """
        <div style="padding:12px 16px;border-radius:12px;background:#f8f9ff;border:1px solid #e6e8ff">
          <h1 style="margin:0">CLARA • Análise de Contratos</h1>
          <p style="margin:6px 0 0;color:#444">
            Descubra <b>cláusulas abusivas</b>, <b>riscos ocultos</b> e <b>o que negociar</b> – em segundos.
          </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col1, col2 = st.columns([1.3, 1])
    with col1:
        st.markdown("### Por que usar a CLARA")
        st.markdown("• Destaca multas e travas de rescisão")
        st.markdown("• Resume riscos em linguagem simples")
        st.markdown("• Sugere ações objetivas de negociação")
        st.markdown("• Calculadora de CET para contratos financeiros")
        st.markdown("• Área administrativa com lista de assinantes")

        st.markdown("### Como funciona")
        st.markdown("1) Faça upload do PDF **ou** cole o texto")
        st.markdown("2) Selecione o contexto (setor, perfil, teto)")
        st.markdown("3) Receba **trecho + explicação + ação**")

    with col2:
        st.markdown("### Plano Premium")
        st.markdown("**R$ 29/mês** • análises ilimitadas • suporte prioritário")
        show_checkout_cta()
# ==============================================================================


# =============== Entrada do contrato & contexto ==============================
def upload_or_paste_section() -> str:
    st.subheader("1) Envie o contrato")
    file = st.file_uploader("PDF do contrato", type=["pdf"], key="file_uploader_pdf")
    raw_text = ""
    if file:
        with st.spinner("Lendo PDF..."):
            raw_text = extract_text_from_pdf(file) or ""
    st.markdown("Ou cole o texto abaixo:")
    return st.text_area("Texto do contrato", height=220, key="ta_contract_text", value=raw_text)

def analysis_inputs() -> Dict[str, Any]:
    st.subheader("2) Contexto")
    col1, col2, col3 = st.columns(3)
    setor = col1.selectbox("Setor", ["Genérico", "SaaS/Serviços", "Empréstimos", "Educação", "Plano de saúde"], key="sel_setor")
    perfil = col2.selectbox("Perfil", ["Contratante","Contratado","Outro"], key="sel_papel")
    limite = col3.number_input("Valor máx. (opcional)", min_value=0.0, step=100.0, key="num_limite")
    return {"setor": setor, "papel": perfil, "limite_valor": limite}
# ==============================================================================


# =============== Resultado & CET =============================================
def results_section(text: str, ctx: Dict[str, Any]):
    st.subheader("3) Resultado")

    if not text.strip():
        st.warning("Envie o contrato (PDF) ou cole o texto para analisar.")
        return

    if not st.session_state.premium and st.session_state.free_runs_left <= 0:
        st.info("Você usou sua análise gratuita. Assine o Premium para seguir.")
        return

    with st.spinner("Analisando..."):
        hits, meta = analyze_contract_text(text, ctx)

    if not st.session_state.premium:
        st.session_state.free_runs_left -= 1

    log_analysis_event(email=st.session_state.profile.get("email",""),
                       meta={"setor":ctx["setor"],"papel":ctx["papel"],"len":len(text)})

    resumo = summarize_hits(hits)
    st.success(f"Resumo: {resumo['resumo']}")
    st.write(f"Gravidade: **{resumo['gravidade']}** | Pontos críticos: **{resumo['criticos']}** | Total: {len(hits)}")

    for h in hits:
        with st.expander(f"{h['severity']} • {h['title']}"):
            st.write(h["explanation"])
            if h.get("suggestion"):
                st.markdown(f"**Sugestão:** {h['suggestion']}")
            if h.get("evidence"):
                st.code(h["evidence"][:1200])

    # CET — mantém resultado em session_state para não “sumir”
    with st.expander("📈 Calcular CET (opcional)", expanded=False):
        col1, col2, col3 = st.columns(3)
        P   = col1.number_input("Valor principal (R$)", min_value=0.0, step=100.0, key="cet_p")
        j   = col2.number_input("Juros mensais (%)",  min_value=0.0, step=0.1,  key="cet_i")
        n   = col3.number_input("Parcelas (n)",       min_value=1,   step=1,    key="cet_n")
        fee = st.number_input("Taxas fixas (R$)",     min_value=0.0, step=10.0, key="cet_fee")

        if st.button("Calcular CET", key="btn_calc_cet"):
            cet = compute_cet_quick(P, j/100.0, int(n), fee)
            st.session_state.cet_result = cet

        if st.session_state.cet_result is not None:
            st.info(f"**CET aproximado:** {st.session_state.cet_result*100:.2f}% a.m.")

    # Relatório simples (txt)
    if st.button("📥 Baixar relatório (txt)", key="btn_download_report"):
        buff = io.StringIO()
        p = st.session_state.profile
        buff.write(f"{APP_TITLE} {VERSION}\nUsuário: {p.get('nome')} <{p.get('email')}>\n")
        buff.write(f"Setor: {ctx['setor']} | Perfil: {ctx['papel']}\n\n")
        buff.write(f"Resumo: {resumo['resumo']} (Gravidade: {resumo['gravidade']})\n\nPontos de atenção:\n")
        for h in hits:
            buff.write(f"- [{h['severity']}] {h['title']} — {h['explanation']}\n")
            if h.get("suggestion"):
                buff.write(f"  Sugestão: {h['suggestion']}\n")
        st.download_button("Download", buff.getvalue(), file_name="relatorio_clara.txt", mime="text/plain")
# ==============================================================================


# =============== Página principal ============================================
def main():
    sidebar_profile()
   def landing_page():
    st.markdown(
        """
        <div style="padding:18px 20px;border-radius:14px;background:#f7f9ff;
                    border:1px solid #e6e8ff; margin-bottom:16px">
          <h1 style="margin:0">CLARA • Análise de Contratos</h1>
          <p style="margin:8px 0 0;color:#374151;font-size:15px">
            Detecte <b>cláusulas abusivas</b>, <b>riscos ocultos</b> e <b>o que negociar</b> — em minutos, sem juridiquês.
          </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col1, col2 = st.columns([1.4, 1])
    with col1:
        st.markdown("### Por que usar a CLARA")
        st.markdown("• Sinaliza multas desproporcionais e travas de rescisão")
        st.markdown("• Resume riscos em linguagem simples")
        st.markdown("• Sugere **ações práticas** para negociar")
        st.markdown("• Inclui **calculadora de CET** para contratos financeiros")
        st.markdown("• Área **admin** com lista de assinantes")

        with st.expander("Perguntas frequentes"):
            st.markdown("**Posso testar?** Sim, 1 análise gratuita.")
            st.markdown("**Posso cancelar?** Sim, a qualquer momento.")
            st.markdown("**Quais arquivos?** PDF com texto ou colando o conteúdo.")

    with col2:
        st.markdown("### Plano Premium")
        st.markdown("**R$ 9,90/mês** • análises ilimitadas • relatório completo • suporte prioritário")
        show_checkout_cta()

