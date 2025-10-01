# -*- coding: utf-8 -*-
"""
CLARA • Análise de Contratos
UX + Direito + Finanças | Stripe sólido | CET explicado
"""

import os, io
from typing import Dict, Any, Tuple, List
import streamlit as st

# ---- seus módulos já existentes ----
from app_modules.pdf_utils import extract_text_from_pdf
from app_modules.rules import RULES
from app_modules.analysis import analyze_contract_text, summarize_hits, compute_cet_quick
from app_modules.storage import (
    init_db, log_analysis_event, log_subscriber, list_subscribers, get_subscriber_by_email
)
from app_modules.stripe_utils import (
    init_stripe, create_checkout_session, verify_checkout_session
)

APP_TITLE = "CLARA • Análise de Contratos"
VERSION   = "v13.0"

st.set_page_config(page_title=APP_TITLE, page_icon="📄", layout="wide")

# ----------------- estilos (Apple-like) -----------------
st.markdown("""
<style>
:root{
  --brand:#1d4ed8;            /* azul */
  --bg-soft:#f6f8ff;
  --ink:#0f172a;
  --muted:#6b7280;
  --ok:#16a34a;
}
html,body,[data-testid="stAppViewContainer"]{ color:var(--ink);}
h1,h2,h3{ letter-spacing:.2px; }
.hero{
  padding:28px 28px; border-radius:18px;
  background:linear-gradient(135deg,#e9eeff, #f9fbff 55%, #ffffff 100%);
  border:1px solid #e7ebff;
}
.badge{padding:6px 10px;border-radius:999px;background:#eef2ff;border:1px solid #dbe3ff;display:inline-block;}
.card{background:#fff;border:1px solid #e7ebff;border-radius:14px;padding:16px;}
.cta{
  background:var(--brand);color:#fff !important;border-radius:10px;padding:12px 16px;border:none;
}
.step{
  border-left:4px solid var(--brand);background:#fff;border-radius:12px;padding:12px;border:1px solid #e7ebff
}
.small{color:var(--muted);font-size:.92rem}
.disclaimer{background:#fffaf1;border:1px solid #ffe6bf;border-radius:12px;padding:10px}
</style>
""", unsafe_allow_html=True)

# ----------------- utils sessão -----------------
def ss_get(k, default):
    if k not in st.session_state:
        st.session_state[k] = default
    return st.session_state[k]

def ss_set(k, v): st.session_state[k] = v

# ----------------- boot leve -----------------
@st.cache_resource(show_spinner="Inicializando serviços…")
def _boot() -> Tuple[bool, str]:
    try:
        init_db()
        secret = st.secrets.get("STRIPE_SECRET_KEY", os.getenv("STRIPE_SECRET_KEY",""))
        if secret:
            init_stripe(secret)
        return True, ""
    except Exception as e:
        return False, str(e)

ok_boot, err_boot = _boot()
st.write("🟢 Boot iniciou…" if ok_boot else "🔴 Falha no boot")
if not ok_boot:
    st.error(f"Erro ao iniciar: {err_boot}")
    st.stop()

# ----------------- segredos -----------------
ADMIN_EMAILS = set(x.strip() for x in (st.secrets.get("ADMIN_EMAILS", os.getenv("ADMIN_EMAILS","")) or "").split(",") if x.strip())
STRIPE_PUBLIC_KEY = st.secrets.get("STRIPE_PUBLIC_KEY", os.getenv("STRIPE_PUBLIC_KEY",""))
STRIPE_SECRET_KEY = st.secrets.get("STRIPE_SECRET_KEY", os.getenv("STRIPE_SECRET_KEY",""))
STRIPE_PRICE_ID   = st.secrets.get("STRIPE_PRICE_ID",   os.getenv("STRIPE_PRICE_ID",""))
BASE_URL          = st.secrets.get("BASE_URL",          os.getenv("BASE_URL","http://localhost:8501"))

# ----------------- estado inicial -----------------
ss_get("profile", {"nome":"","email":"","cel":"","papel":"Contratante","aceite":False})
ss_get("premium", False)
ss_get("free_runs_left", 1)           # 1 análise gratuita
ss_get("last_report_text", "")        # mantém último relatório para download

# ----------------- retorno do Stripe -----------------
qs = st.query_params
if qs.get("success") == "true" and qs.get("session_id"):
    try:
        ok_pay, payload = verify_checkout_session(qs["session_id"])
    except Exception as e:
        ok_pay, payload = False, {}
        st.warning(f"Não foi possível confirmar o pagamento agora. Detalhe: {e}")

    if ok_pay:
        ss_set("premium", True)
        try:
            email = payload.get("customer_details", {}).get("email") or st.session_state.profile.get("email","")
            log_subscriber(
                email=email,
                name=st.session_state.profile.get("nome",""),
                stripe_customer_id=(payload.get("customer")
                                    or (payload.get("subscription") or {}).get("customer")
                                    or "")
            )
        except Exception:
            pass
        st.success("Pagamento confirmado! Premium liberado ✅")
    else:
        st.warning("Não conseguimos confirmar essa sessão de pagamento. Se houver cobrança, o acesso será liberado em seguida.")

    try: st.query_params.clear()
    except Exception: pass

# ----------------- Sidebar: cadastro + admin -----------------
def sidebar_profile():
    st.sidebar.header("🔐 Seus dados (obrigatório)")
    p = st.session_state.profile
    nome  = st.sidebar.text_input("Nome completo*", value=p.get("nome",""))
    email = st.sidebar.text_input("E-mail*", value=p.get("email",""))
    cel   = st.sidebar.text_input("WhatsApp*", value=p.get("cel",""))
    papel = st.sidebar.selectbox("Você é o contratante?*", ["Contratante","Contratado","Outro"],
                                 index=["Contratante","Contratado","Outro"].index(p.get("papel","Contratante")))
    aceite = st.sidebar.checkbox("Li e concordo que a CLARA **não substitui** orientação jurídica.", value=p.get("aceite", False))

    if st.sidebar.button("Salvar perfil", use_container_width=True):
        st.session_state.profile = {"nome":nome.strip(),"email":email.strip(),"cel":cel.strip(),"papel":papel,"aceite":aceite}
        if email.strip():
            try:
                if get_subscriber_by_email(email.strip()):
                    ss_set("premium", True)
            except Exception:
                pass
        st.sidebar.success("Dados salvos!")

    st.sidebar.markdown("---")
    st.sidebar.subheader("Administração")
    if p.get("email","") in ADMIN_EMAILS:
        if st.sidebar.checkbox("Ver assinantes"):
            try:
                st.sidebar.write(list_subscribers())
            except Exception as e:
                st.sidebar.warning(f"Erro ao listar: {e}")
    else:
        st.sidebar.caption("Use um e-mail admin para acessar essa seção.")

sidebar_profile()

# ----------------- Hero / Landing -----------------
def hero():
    st.markdown(f"""
    <div class="hero">
      <div class="badge">Nova • {VERSION}</div>
      <h1 style="margin:8px 0 4px 0;">{APP_TITLE}</h1>
      <p class="small">Detecta <b>cláusulas abusivas</b>, <b>riscos ocultos</b> e indica <b>o que negociar</b>. Em minutos.</p>
    </div>
    """, unsafe_allow_html=True)

    colL, colR = st.columns([1.35, 1])
    with colL:
        st.markdown("## Por que usar a CLARA")
        st.markdown("- Destaca multas desproporcionais, travas de rescisão e responsabilidades exageradas")
        st.markdown("- Resume em linguagem simples e sugere **o que negociar**")
        st.markdown("- Calculadora de **CET – Custo Efetivo Total** *(juros + tarifas + taxas)*")
        st.markdown("- Relatório para compartilhar com o time ou advogado(a)")

        with st.expander("O que é CET (Custo Efetivo Total)?", expanded=False):
            st.markdown("""
            O **CET** representa **todo o custo** de um financiamento/parcelamento: juros, tarifas, seguros e demais cobranças.
            Útil para **comparar propostas de forma justa** e entender o **custo real** do dinheiro.
            """)

    with colR:
        pricing_card()

    st.markdown("## Como funciona")
    c1,c2,c3,c4 = st.columns(4)
    c1.markdown("""<div class="step"><b>1.</b> Envie o PDF ou cole o texto</div>""", unsafe_allow_html=True)
    c2.markdown("""<div class="step"><b>2.</b> Informe setor/perfil/valor</div>""", unsafe_allow_html=True)
    c3.markdown("""<div class="step"><b>3.</b> Veja <b>trechos + explicações</b></div>""", unsafe_allow_html=True)
    c4.markdown("""<div class="step"><b>4.</b> Use <b>CET</b> e baixe o relatório</div>""", unsafe_allow_html=True)

def stripe_diagnostics() -> Tuple[bool, str]:
    miss = []
    if not STRIPE_PUBLIC_KEY: miss.append("STRIPE_PUBLIC_KEY")
    if not STRIPE_SECRET_KEY: miss.append("STRIPE_SECRET_KEY")
    if not STRIPE_PRICE_ID:   miss.append("STRIPE_PRICE_ID")
    if miss:
        return False, f"Configure os segredos ausentes: {', '.join(miss)}."
    if STRIPE_PRICE_ID.startswith("prod_"):
        return False, "Use um **price_...** (não **prod_...**). Crie um preço no Stripe e coloque o ID correto."
    if not STRIPE_PRICE_ID.startswith("price_"):
        return False, "STRIPE_PRICE_ID parece inválido. Ele deve começar com **price_...**"
    return True, ""

def pricing_card():
    st.markdown("### Plano Premium")
    st.caption("R$ **9,90/mês** • análises ilimitadas • suporte prioritário")

    okS, msgS = stripe_diagnostics()
    if not okS:
        st.error(f"Não foi possível iniciar o checkout. {msgS}")
        return

    email = st.session_state.profile.get("email","").strip()
    if not email:
        st.info("Informe e salve seu e-mail na barra lateral para assinar.")
        return

  if st.button("💳 Assinar Premium agora", use_container_width=True):
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
        # Agora aparece o motivo real (ex.: “No such price”, “live key com price de teste”, etc.)
        st.error(sess.get("error", "Stripe indisponível no momento. Tente novamente."))

# ----------------- guardas -----------------
def guard_before_analyze() -> bool:
    p = st.session_state.profile
    falta = []
    if not p.get("nome","").strip():  falta.append("• Nome completo")
    if not p.get("email","").strip(): falta.append("• E-mail")
    if not p.get("cel","").strip():   falta.append("• WhatsApp")
    if not p.get("aceite", False):    falta.append("• Aceite do termo (“não substitui advogado”)")
    if falta:
        st.warning("Finalize o cadastro para começar:")
        st.write("\n".join(falta))
        return False
    return True

# ----------------- seções de fluxo -----------------
def upload_or_paste_section() -> str:
    st.header("1) Envie o contrato")
    f = st.file_uploader("PDF do contrato", type=["pdf"], key="upl_pdf")
    txt = ""
    if f:
        with st.spinner("Lendo PDF…"):
            try:
                txt = extract_text_from_pdf(f)
            except Exception as e:
                st.error(f"Falha ao ler o PDF: {e}")
    st.caption("Ou cole o texto abaixo:")
    return st.text_area("Texto do contrato", height=220, key="ta_contract_text", value=txt or "")

def analysis_inputs() -> Dict[str, Any]:
    st.header("2) Contexto")
    a,b,c = st.columns(3)
    setor  = a.selectbox("Setor", ["Genérico","SaaS/Serviços","Empréstimos","Educação","Plano de saúde"], key="ctx_setor")
    papel  = b.selectbox("Perfil", ["Contratante","Contratado","Outro"], key="ctx_papel")
    limite = c.number_input("Valor máx. (opcional)", min_value=0.0, step=100.0, key="ctx_limite")
    return {"setor":setor,"papel":papel,"limite_valor":limite}

def cet_widget():
    with st.expander("📈 Calculadora de CET (opcional)", expanded=False):
        a,b,c = st.columns(3)
        P   = a.number_input("Valor principal (R$)", min_value=0.0, step=100.0, key="cet_p")
        i   = b.number_input("Juros mensais (%)", min_value=0.0, step=0.1, key="cet_i")
        n   = c.number_input("Parcelas (n)", min_value=1, step=1, key="cet_n")
        fee = st.number_input("Taxas/seguros/IOF (R$)", min_value=0.0, step=10.0, key="cet_fee")
        if st.button("Calcular CET", key="btn_calc_cet"):
            try:
                cet = compute_cet_quick(P, i/100.0, int(n), fee)
                st.success(f"**CET aproximado:** {cet*100:.2f}% a.m.")
                st.caption("CET = juros + tarifas + seguros. Compare propostas pelo CET.")
            except Exception as e:
                st.error(f"Erro ao calcular CET: {e}")

def results_section(text: str, ctx: Dict[str, Any]):
    st.header("4) Resultado")

    if not text.strip():
        st.info("Envie um PDF ou cole o texto do contrato.")
        return

    # cota grátis
    if not st.session_state.premium and st.session_state.free_runs_left <= 0:
        st.warning("Você usou sua análise gratuita. Assine o Premium para continuar.")
        pricing_card()
        return

    with st.spinner("Analisando…"):
        hits, meta = analyze_contract_text(text, ctx)

    # desconta só após concluir
    if not st.session_state.premium:
        st.session_state.free_runs_left = max(0, st.session_state.free_runs_left - 1)

    # log não-crítico
    try:
        log_analysis_event(st.session_state.profile.get("email",""),
                           {"setor":ctx["setor"], "papel":ctx["papel"], "len":len(text)})
    except Exception:
        pass

    resume = summarize_hits(hits)
    st.success(f"**Resumo** — {resume['resumo']}")
    st.write(f"Gravidade: **{resume['gravidade']}** | Pontos críticos: **{resume['criticos']}** | Total encontrados: {len(hits)}")

    for h in hits:
        with st.expander(f"{h['severity']} • {h['title']}"):
            st.write(h["explanation"])
            if h.get("suggestion"): st.markdown(f"**Sugestão:** {h['suggestion']}")
            if h.get("evidence"):   st.code(h["evidence"][:1200])

    # ------- relatório sempre disponível após resultado -------
    p = st.session_state.profile
    buff = io.StringIO()
    buff.write(f"{APP_TITLE} {VERSION}\n")
    buff.write(f"Usuário: {p.get('nome')} <{p.get('email')}> WhatsApp: {p.get('cel')}\n")
    buff.write(f"Setor: {ctx['setor']} | Perfil: {ctx['papel']}\n\n")
    buff.write(f"Resumo: {resume['resumo']} (Gravidade: {resume['gravidade']})\n\nPontos de atenção:\n")
    for h in hits:
        buff.write(f"- [{h['severity']}] {h['title']} — {h['explanation']}\n")
        if h.get("suggestion"): buff.write(f"  Sugestão: {h['suggestion']}\n")

    report_text = buff.getvalue()
    ss_set("last_report_text", report_text)  # guarda para reuso
    st.download_button("📥 Baixar relatório (txt)", report_text,
                       file_name="relatorio_clara.txt", mime="text/plain", use_container_width=True)

# ----------------- fluxo principal -----------------
def main():
    hero()

    st.markdown("---")
    st.markdown('<div class="disclaimer small">A CLARA **não substitui** aconselhamento jurídico. '
                'Use como apoio e valide com advogado(a).</div>', unsafe_allow_html=True)

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

