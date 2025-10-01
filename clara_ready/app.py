import os, io
from typing import Dict, Any
import streamlit as st

from app_modules.pdf_utils import extract_text_from_pdf
from app_modules.rules import RULES
from app_modules.analysis import analyze_contract_text, summarize_hits, compute_cet_quick
from app_modules.stripe_utils import init_stripe, create_checkout_session, verify_checkout_session
from app_modules.storage import init_db, log_analysis_event, log_subscriber, list_subscribers, get_subscriber_by_email

APP_TITLE = "CLARA • Análise de Contratos"
VERSION = "v11.0"

st.set_page_config(page_title=APP_TITLE, page_icon="📄", layout="wide")

# --- marcador de vida (aparece na tela se o app chegou a renderizar) ---
st.write("🟢 Boot iniciou…")

from app_modules.stripe_utils import create_checkout_session  # garanta este import no topo

def show_checkout_cta():
    """
    Mostra o botão de assinatura. Cria a sessão do Stripe e exibe o link seguro.
    """
    import os
    email = (st.session_state.get("profile", {}) or {}).get("email", "").strip()
    price_id = st.secrets.get("STRIPE_PRICE_ID", os.getenv("STRIPE_PRICE_ID", ""))
    base_url = st.secrets.get("BASE_URL", "https://claraready.streamlit.app")

    if not email:
        st.info("Informe seu e-mail em **Seus dados** (barra lateral) para assinar.")
        return
    if not price_id:
        st.error("Configuração ausente: STRIPE_PRICE_ID.")
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
        else:
            st.error("Não foi possível iniciar o checkout. Verifique STRIPE_PRICE_ID e chaves.")

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
        show_checkout_cta()  # <-- CTA aparece aqui



# --- BOOT protegido em cache (roda 1x por sessão; mostra erro em vez de travar) ---
import os
from app_modules.storage import init_db  # ajuste se seu init_db estiver em outro módulo
from app_modules.stripe_utils import init_stripe

@st.cache_resource(show_spinner="Iniciando serviços…")
def _boot():
    # 1) Secrets
    stripe_secret = st.secrets.get("STRIPE_SECRET_KEY", os.getenv("STRIPE_SECRET_KEY", ""))
    if not stripe_secret:
        raise RuntimeError("Faltando STRIPE_SECRET_KEY em Settings → Secrets (Streamlit Cloud).")

    # 2) Stripe (só define api_key; sem chamadas de rede aqui)
    init_stripe(stripe_secret)

    # 3) DB/Storage (apenas setup leve)
    init_db()

    return True

try:
    _ = _boot()
except Exception as e:
    st.error(f"❌ Falha ao iniciar: {e}")
    st.stop()

st.write("🟢 Serviços prontos.")
# -----------------------------------------------------------------------
# --- retorno do Stripe após pagamento (seguro) ---
qs = st.query_params  # nova API do Streamlit
if qs.get("success") == "true" and qs.get("session_id"):
    try:
        ok, data = verify_checkout_session(qs["session_id"])
    except Exception as e:
        st.error(f"Não deu para confirmar o pagamento agora. Detalhe: {e}")
        ok, data = False, {}

    if ok:
        # marca Premium na sessão
        st.session_state.premium = True

        # registra assinante (opcional, mas útil p/ lista de inscritos)
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

        # limpa a querystring (tira ?success=true&session_id=... da URL)
        st.query_params.clear()
    else:
        st.warning("Não conseguimos confirmar essa sessão de pagamento. Tente novamente.")
# -------------------------------------------------

# --- tratar retorno do Stripe ---
qs = st.query_params
if qs.get("success") == "true" and qs.get("session_id"):
    ok, data = verify_checkout_session(qs["session_id"])
    if ok:
        st.session_state.premium = True
        log_subscriber(
            email=st.session_state.profile.get("email", ""),
            name=st.session_state.profile.get("nome", ""),
            stripe_customer_id=(data.get("customer") or data.get("subscription", {}).get("customer") or "")
        )
        st.success("Pagamento confirmado! Premium liberado ✅")
        # limpa param da URL visualmente
        st.query_params.clear()
    else:
        st.error("Não conseguimos confirmar o pagamento. Tente novamente.")
# --------------------------------


# --- estado da calculadora CET ---
if "show_cet" not in st.session_state:
    st.session_state.show_cet = False

def _open_cet():
    st.session_state.show_cet = True

def _close_cet():
    st.session_state.show_cet = False
# ---------------------------------


ADMIN_EMAILS = set(st.secrets.get("admin_emails", os.getenv("ADMIN_EMAILS","").split(",")))
STRIPE_PUBLIC_KEY = st.secrets.get("STRIPE_PUBLIC_KEY", os.getenv("STRIPE_PUBLIC_KEY",""))
STRIPE_SECRET_KEY = st.secrets.get("STRIPE_SECRET_KEY", os.getenv("STRIPE_SECRET_KEY",""))
STRIPE_PRICE_ID   = st.secrets.get("STRIPE_PRICE_ID",   os.getenv("STRIPE_PRICE_ID",""))

init_db()
init_stripe(STRIPE_SECRET_KEY)

def text_input(label, key, **kwargs):  # evita IDs duplicados
    return st.text_input(label, key=key, **kwargs)

if "profile" not in st.session_state:
    st.session_state.profile = {"nome":"", "email":"", "papel":"Outro"}
if "premium" not in st.session_state:
    st.session_state.premium = False
if "free_runs_left" not in st.session_state:
    st.session_state.free_runs_left = 1

def sidebar_profile():
    st.sidebar.header("🔐 Seus dados (obrigatório)")
    nome  = text_input("Nome completo*", key="profile_nome")
    email = text_input("E-mail*", key="profile_email")
    papel = st.selectbox("Você é o contratante?*", ["Contratante","Contratado","Outro"], key="profile_papel")
    if st.sidebar.button("Salvar perfil", key="btn_save_profile"):
        st.session_state.profile = {"nome": nome, "email": email, "papel": papel}
        st.sidebar.success("Dados salvos!")
        if email:
            existing = get_subscriber_by_email(email)
            if existing:
                st.session_state.premium = True

    st.sidebar.markdown("---")
    st.sidebar.subheader("Administração")
    if st.session_state.profile.get("email") in ADMIN_EMAILS:
        if st.sidebar.checkbox("Área administrativa", key="admin_toggle"):
            subs = list_subscribers()
            st.sidebar.success("Admin ativo")
            with st.expander("👥 Assinantes"):
                st.write(subs)

def hero_and_pricing():
    st.title(APP_TITLE); st.caption(VERSION)
    col1, col2 = st.columns([3,2])
    with col1:
        st.markdown("**Clara** lê seu contrato e destaca onde **você precisa *prestar atenção***.")
    with col2:
        st.info("Plano Premium: análises ilimitadas + relatório completo")
        if STRIPE_PUBLIC_KEY and STRIPE_PRICE_ID:
            if st.button("💳 Assinar Premium", key="btn_checkout"):
                email = st.session_state.profile.get("email","")
                if not email:
                    st.warning("Informe seu e-mail no painel lateral antes de assinar.")
                else:
                    base_url = st.secrets.get("BASE_URL", "http://localhost:8501")
                    session = create_checkout_session(
                        price_id=STRIPE_PRICE_ID,
                        customer_email=email,
                        success_url=f"{base_url}?success=true&session_id={{CHECKOUT_SESSION_ID}}",
                        cancel_url=f"{base_url}?canceled=true"
                    )
                    if session.get("url"):
                        st.markdown(f"[Clique aqui para pagar]({session['url']})")
                        st.stop()
                    else:
                        st.error("Não foi possível iniciar o checkout. Verifique as chaves Stripe.")
        else:
            st.warning("Stripe não configurado. Defina STRIPE_PUBLIC_KEY/STRIPE_SECRET_KEY/STRIPE_PRICE_ID.")

def handle_checkout_result():
    params = st.experimental_get_query_params()
    if "success" in params and "session_id" in params:
        ok, payload = verify_checkout_session(params["session_id"][0])
        if ok:
            email = payload.get("customer_details", {}).get("email") or st.session_state.profile.get("email")
            if email:
                log_subscriber(
                    email=email,
                    name=st.session_state.profile.get("nome",""),
                    stripe_session_id=params["session_id"][0],
                    stripe_customer_id=payload.get("customer",""),
                )
                st.session_state.premium = True
                st.success("Pagamento confirmado! Premium liberado ✅")
        else:
            st.error("Não foi possível validar o pagamento.")

def upload_or_paste_section():
    st.subheader("1) Envie o contrato")
    file = st.file_uploader("PDF do contrato", type=["pdf"], key="file_uploader_pdf")
    raw_text = ""
    if file:
        with st.spinner("Lendo PDF..."):
            raw_text = extract_text_from_pdf(file)
    st.markdown("Ou cole o texto abaixo:")
    raw_text = st.text_area("Texto do contrato", height=220, key="ta_contract_text", value=raw_text or "")
    return raw_text

def analysis_inputs():
    st.subheader("2) Contexto")
    col1, col2, col3 = st.columns(3)
    setor = col1.selectbox("Setor", ["Genérico", "SaaS/Serviços", "Empréstimos", "Educação", "Plano de saúde"], key="sel_setor")
    papel = col2.selectbox("Perfil", ["Contratante","Contratado","Outro"], key="sel_papel")
    limite_valor = col3.number_input("Valor máx. (opcional)", min_value=0.0, step=100.0, key="num_limite")
    return {"setor": setor, "papel": papel, "limite_valor": limite_valor}

def results_section(text: str, ctx: Dict[str, Any]):
    st.subheader("3) Resultado")
    if not text.strip():
        st.warning("Envie o contrato (PDF) ou cole o texto para analisar."); return
    if not st.session_state.premium and st.session_state.free_runs_left <= 0:
        st.info("Você usou sua análise gratuita. Assine o Premium para seguir."); return

    with st.spinner("Analisando..."):
        hits, meta = analyze_contract_text(text, ctx)
    if not st.session_state.premium:
        st.session_state.free_runs_left -= 1
    log_analysis_event(email=st.session_state.profile.get("email",""),
                       meta={"setor":ctx["setor"],"papel":ctx["papel"],"len":len(text)})

    resume = summarize_hits(hits)
    st.success(f"Resumo: {resume['resumo']}")
    st.write(f"Gravidade: **{resume['gravidade']}** | Pontos críticos: **{resume['criticos']}** | Total: {len(hits)}")

    for h in hits:
        with st.expander(f"{h['severity']} • {h['title']}"):
            st.write(h["explanation"])
            if h.get("suggestion"): st.markdown(f"**Sugestão:** {h['suggestion']}")
            if h.get("evidence"):   st.code(h["evidence"][:1200])

    with st.expander("📈 Calcular CET (opcional)"):
        col1, col2, col3 = st.columns(3)
        P = col1.number_input("Valor principal (R$)", min_value=0.0, step=100.0, key="cet_p")
        i = col2.number_input("Juros mensais (%)", min_value=0.0, step=0.1, key="cet_i")
        n = col3.number_input("Parcelas (n)", min_value=1, step=1, key="cet_n")
        fee = st.number_input("Taxas fixas (R$)", min_value=0.0, step=10.0, key="cet_fee")
        if st.button("Calcular CET", key="btn_calc_cet"):
            cet = compute_cet_quick(P, i/100.0, int(n), fee)
            st.write(f"**CET aproximado:** {cet*100:.2f}% a.m.")

    if st.button("📥 Baixar relatório (txt)", key="btn_download_report"):
        buff = io.StringIO()
        buff.write(f"{APP_TITLE} {VERSION}\nUsuário: {st.session_state.profile.get('nome')} <{st.session_state.profile.get('email')}>\n")
        buff.write(f"Setor: {ctx['setor']} | Perfil: {ctx['papel']}\n\n")
        buff.write(f"Resumo: {resume['resumo']} (Gravidade: {resume['gravidade']})\n\nPontos de atenção:\n")
        for h in hits:
            buff.write(f"- [{h['severity']}] {h['title']} — {h['explanation']}\n")
            if h.get("suggestion"): buff.write(f"  Sugestão: {h['suggestion']}\n")
        st.download_button("Download", buff.getvalue(), file_name="relatorio_clara.txt", mime="text/plain")

def main():
    sidebar_profile()
    hero_and_pricing()
    handle_checkout_result()
    st.markdown("---")
    text = upload_or_paste_section()
    ctx = analysis_inputs()
    st.button("🧮 Abrir calculadora de CET", on_click=_open_cet, use_container_width=True)
    if st.button("🚀 Começar análise", key="btn_run_analysis"):
        results_section(text, ctx)

if __name__ == "__main__":
    main()








