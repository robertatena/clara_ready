# -*- coding: utf-8 -*-
"""
CLARA • Análise de Contratos — v13.0
UX focada em clareza, conversão e estabilidade:
- Onboarding (nome/celular/e-mail) obrigatório antes da análise
- Explicação do CET + calculadora estável
- Stripe Premium (R$ 9,90/mês) com query_params e mensagens claras
"""

import os
import io
from typing import Dict, Any, Tuple

import streamlit as st

# ===== seus módulos =====
from app_modules.pdf_utils import extract_text_from_pdf
from app_modules.rules import RULES
from app_modules.analysis import analyze_contract_text, summarize_hits, compute_cet_quick
from app_modules.stripe_utils import init_stripe, create_checkout_session, verify_checkout_session
from app_modules.storage import (
    init_db, log_analysis_event, log_subscriber, list_subscribers, get_subscriber_by_email
)

APP_TITLE = "CLARA • Análise de Contratos"
VERSION   = "v13.0"

st.set_page_config(page_title=APP_TITLE, page_icon="📄", layout="wide")

# ===== estilos (UX) =====
st.markdown("""
<style>
html, body, [class*="css"] {
  font-family: Inter, -apple-system, Segoe UI, Roboto, Helvetica, Arial, "Noto Sans";
}
.block-container { padding-top: 1rem; }
.cl-hero { background: linear-gradient(180deg,#ffffff 0%,#f7f9ff 100%);
  border: 1px solid #eef1ff; border-radius: 16px; padding: 20px 22px; }
.cl-card { background:#ffffff; border:1px solid #eef1ff; border-radius:14px; padding:18px; }
.small { color:#68707b; font-size:0.94rem; }
.badge { display:inline-block; padding:4px 10px; border-radius:999px; background:#eef3ff; border:1px solid #dfe6ff; color:#3850b7; font-weight:600; }
h1,h2,h3{ letter-spacing:.2px; }
hr{ margin: 8px 0 16px; }
</style>
""", unsafe_allow_html=True)

# ===== helpers =====
def _get_secret(key: str, default: str = "") -> str:
    return str(st.secrets.get(key, os.getenv(key, default)))

@st.cache_resource(show_spinner="Iniciando serviços…")
def _boot() -> Tuple[str,str,str,str,set]:
    pub = _get_secret("STRIPE_PUBLIC_KEY")
    sec = _get_secret("STRIPE_SECRET_KEY")
    pid = _get_secret("STRIPE_PRICE_ID")
    base= _get_secret("BASE_URL", "https://claraready.streamlit.app")
    admins = set([e.strip() for e in _get_secret("admin_emails","").split(",") if e.strip()])
    if sec:
        init_stripe(sec)
    init_db()
    return pub, sec, pid, base, admins

try:
    STRIPE_PUBLIC_KEY, STRIPE_SECRET_KEY, STRIPE_PRICE_ID, BASE_URL, ADMIN_EMAILS = _boot()
except Exception as e:
    st.error(f"❌ Falha ao iniciar serviços: {e}")
    st.stop()

# ===== estado =====
if "profile" not in st.session_state:
    st.session_state.profile = {"nome":"", "celular":"", "email":"", "papel":"Contratante"}
if "profile_ok" not in st.session_state:
    st.session_state.profile_ok = False
if "premium" not in st.session_state:
    st.session_state.premium = False
if "free_runs_left" not in st.session_state:
    st.session_state.free_runs_left = 1

# ===== componentes =====
def hero():
    st.markdown(f"""
    <div class="cl-hero">
      <div class="badge">Novo</div>
      <h1 style="margin:8px 0 2px">{APP_TITLE}</h1>
      <div class="small">Descubra <b>cláusulas abusivas</b>, <b>riscos ocultos</b> e <b>o que negociar</b> — em minutos.</div>
      <div class="small">Versão {VERSION}</div>
    </div>
    """, unsafe_allow_html=True)

def benefits_and_social():
    col1, col2 = st.columns([1.2, 1])
    with col1:
        st.markdown("### Por que usar a Clara")
        st.markdown("- Sinaliza multas desproporcionais, travas de rescisão e riscos de responsabilidade")
        st.markdown("- Explica em linguagem simples e sugere **o que negociar**")
        st.markdown("- **CET (Custo Efetivo Total)** para contratos financeiros (juros + taxas)")
        st.markdown("- Relatório claro para compartilhar com o time ou advogado(a)")
        st.markdown("### Como funciona")
        st.markdown("1. Envie o **PDF** ou cole o **texto** do contrato")
        st.markdown("2. Escolha **setor**, **perfil** e **valor** (opcional)")
        st.markdown("3. Receba **trechos + explicação + ações sugeridas**")
    with col2:
        st.markdown("### Plano Premium")
        st.markdown("**R$ 9,90/mês** • análises ilimitadas • suporte prioritário")
        premium_cta_compact()

def premium_cta_compact():
    email = st.session_state.profile.get("email","").strip()
    if not STRIPE_PUBLIC_KEY or not STRIPE_PRICE_ID or not STRIPE_SECRET_KEY:
        st.info("Configure **STRIPE_PUBLIC_KEY**, **STRIPE_SECRET_KEY** e **STRIPE_PRICE_ID** em *Settings → Secrets*.")
        return
    if st.session_state.premium:
        st.success("✅ Você já é Premium. Obrigado!")
        return
    if not email:
        st.warning("Preencha seu e-mail no formulário de login abaixo para assinar.")
        return
    if st.button("💳 Assinar Premium agora", use_container_width=True):
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
    qs = st.query_params
    if qs.get("success") == "true" and qs.get("session_id"):
        sid = qs.get("session_id","")
        try:
            ok, data = verify_checkout_session(sid)
        except Exception as e:
            ok, data = False, {}
            st.error(f"Não deu para confirmar o pagamento agora. Detalhe: {e}")
        if ok:
            st.session_state.premium = True
            try:
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
            st.warning("Não conseguimos confirmar a sessão de pagamento. Tente novamente.")
        st.query_params.clear()

def onboarding_form():
    st.markdown("## Faça login para começar")
    st.markdown('<div class="small">Seu e-mail não será compartilhado. Usamos para liberar a versão Premium e enviar seu recibo.</div>', unsafe_allow_html=True)
    with st.form("onboarding", clear_on_submit=False):
        c1, c2 = st.columns([1,1])
        nome    = c1.text_input("Nome completo*", value=st.session_state.profile.get("nome",""))
        celular = c2.text_input("Celular (WhatsApp)*", value=st.session_state.profile.get("celular",""))
        email   = st.text_input("E-mail*", value=st.session_state.profile.get("email",""))
        papel   = st.selectbox("Você é o contratante?*", ["Contratante","Contratado","Outro"],
                               index=["Contratante","Contratado","Outro"].index(st.session_state.profile.get("papel","Contratante")))
        ok = st.form_submit_button("Salvar e continuar", use_container_width=True)
        if ok:
            nome  = (nome or "").strip()
            cel   = (celular or "").strip()
            mail  = (email or "").strip()
            if not nome or not cel or not mail:
                st.error("Por favor, preencha **nome, celular e e-mail**.")
            else:
                st.session_state.profile = {"nome": nome, "celular": cel, "email": mail, "papel": papel}
                # marca premium se já assinante
                try:
                    st.session_state.premium = bool(get_subscriber_by_email(mail))
                except Exception:
                    pass
                st.session_state.profile_ok = True
                st.success("Perfil salvo! Você já pode usar a Clara.")

def upload_or_paste_section() -> str:
    st.markdown("### 1) Envie o contrato")
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
    st.markdown("### 2) Contexto")
    col1, col2, col3 = st.columns(3)
    setor = col1.selectbox("Setor", ["Genérico","SaaS/Serviços","Empréstimos","Educação","Plano de saúde"], key="sel_setor")
    papel = col2.selectbox("Perfil", ["Contratante","Contratado","Outro"], key="sel_papel",
                           index=["Contratante","Contratado","Outro"].index(st.session_state.profile.get("papel","Contratante")))
    limite_valor = col3.number_input("Valor máx. (opcional)", min_value=0.0, step=100.0, key="num_limite")
    return {"setor": setor, "papel": papel, "limite_valor": limite_valor}

def cet_explainer_and_calc():
    st.markdown("### 3) CET — Custo Efetivo Total")
    st.markdown("""
**O que é?** O CET é a taxa que resume **todo o custo do contrato** em percentual ao mês: engloba juros + tarifas + encargos.  
Use para comparar propostas: **quanto menor o CET, melhor** para você.
""")
    c1, c2, c3, c4 = st.columns(4)
    P   = c1.number_input("Valor principal (R$)", min_value=0.0, step=100.0, key="cet_p")
    i_m = c2.number_input("Juros mensais (%)", min_value=0.0, step=0.1, key="cet_i")
    n   = c3.number_input("Parcelas (n)", min_value=1, step=1, key="cet_n")
    fee = c4.number_input("Taxas fixas (R$)", min_value=0.0, step=10.0, key="cet_fee")
    if st.button("Calcular CET", key="btn_calc_cet", use_container_width=True):
        try:
            cet_m = compute_cet_quick(P, i_m/100.0, int(n), fee)
            st.success(f"**CET aproximado:** {cet_m*100:.2f}% a.m.")
        except Exception as e:
            st.error(f"Não foi possível calcular o CET: {e}")

def results_section(text: str, ctx: Dict[str, Any]) -> None:
    st.markdown("### 4) Resultado")
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
    try:
        log_analysis_event(
            email=st.session_state.profile.get("email",""),
            meta={"setor":ctx["setor"],"papel":ctx["papel"],"len":len(text)}
        )
    except Exception:
        pass

    resume = summarize_hits(hits)
    st.success(f"**Resumo:** {resume['resumo']}")
    st.write(f"Gravidade: **{resume['gravidade']}** | Pontos críticos: **{resume['criticos']}** | Total de achados: **{len(hits)}**")

    for h in hits:
        title = f"{h.get('severity','')}: {h.get('title','')}".strip(": ")
        with st.expander(title):
            st.write(h.get("explanation",""))
            if h.get("suggestion"):
                st.markdown(f"**Sugestão:** {h['suggestion']}")
            if h.get("evidence"):
                st.code((h.get("evidence") or "")[:1200])

    if st.button("📥 Baixar relatório (txt)", key="btn_download_report", use_container_width=True):
        buff = io.StringIO()
        p = st.session_state.profile
        buff.write(f"{APP_TITLE} {VERSION}\nUsuário: {p.get('nome')} | Cel: {p.get('celular')} | Email: {p.get('email')}\n")
        buff.write(f"Setor: {ctx['setor']} | Perfil: {ctx['papel']}\n\n")
        buff.write(f"Resumo: {resume['resumo']} (Gravidade: {resume['gravidade']})\n\nPontos de atenção:\n")
        for h in hits:
            buff.write(f"- [{h.get('severity','')}] {h.get('title','')} — {h.get('explanation','')}\n")
            if h.get("suggestion"):
                buff.write(f"  Sugestão: {h['suggestion']}\n")
        st.download_button("Download do relatório", buff.getvalue(),
                           file_name="relatorio_clara.txt", mime="text/plain", use_container_width=True)

def admin_sidebar():
    email = st.session_state.profile.get("email","").strip()
    st.sidebar.markdown("---")
    st.sidebar.subheader("Administração")
    if email and email in ADMIN_EMAILS:
        if st.sidebar.checkbox("Área administrativa", key="admin_toggle"):
            try:
                subs = list_subscribers()
                st.sidebar.success("Admin ativo")
                st.sidebar.caption(f"Assinantes ({len(subs)}):")
                st.sidebar.json(subs, expanded=False)
            except Exception as e:
                st.sidebar.error(f"Erro ao carregar assinantes: {e}")
    else:
        st.sidebar.caption("Para acesso admin, inclua seu e-mail em `admin_emails` (Secrets).")

# ===== fluxo principal =====
def main():
    # hero + benefícios + CTA
    hero()
    benefits_and_social()

    # retorno stripe
    handle_stripe_return()

    st.markdown("---")

    # onboarding (obrigatório antes de analisar)
    onboarding_form()

    # admin
    admin_sidebar()

    # trava de uso: sem login, nada de análise
    if not st.session_state.profile_ok:
        st.info("Preencha e salve o formulário de login acima para habilitar a análise e o checkout.")
        return

    # entradas
    with st.container():
        st.markdown("## Comece aqui")
        text = upload_or_paste_section()
        ctx  = analysis_inputs()
        cet_explainer_and_calc()

        # ação
        run = st.button("🚀 Rodar análise agora", type="primary", use_container_width=True)
        if run:
            results_section(text, ctx)

if __name__ == "__main__":
    main()
