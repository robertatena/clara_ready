# app.py
# CLARA • Análise de Contratos – v13.x
# Visual inspirado em páginas clean (ex.: iCloud), linguagem simples,
# e todas as funções preservadas: Stripe, CET, logs, admin, downloads, Hotjar.

import os
import io
import csv
from typing import Dict, Any, Tuple, Set, List
from datetime import datetime
from pathlib import Path

import streamlit as st

# ---------- Módulos locais (mantém sua estrutura) ----------
from app_modules.pdf_utils import extract_text_from_pdf
from app_modules.analysis import analyze_contract_text, summarize_hits, compute_cet_quick
from app_modules.stripe_utils import init_stripe, create_checkout_session, verify_checkout_session
from app_modules.storage import (
    init_db, log_analysis_event, log_subscriber,
    list_subscribers, get_subscriber_by_email,
)

# -----------------------------------------------------------
# Config & Consts
# -----------------------------------------------------------
APP_TITLE = "CLARA"
APP_SUBTITLE = "Análise de contratos"
VERSION = "v13.6"

st.set_page_config(page_title=f"{APP_TITLE} • {APP_SUBTITLE}", page_icon="✨", layout="wide")

# Segredos/ENV (Stripe/Hotjar/Base URL)
STRIPE_PUBLIC_KEY = st.secrets.get("STRIPE_PUBLIC_KEY", os.getenv("STRIPE_PUBLIC_KEY", ""))
STRIPE_SECRET_KEY = st.secrets.get("STRIPE_SECRET_KEY", os.getenv("STRIPE_SECRET_KEY", ""))
STRIPE_PRICE_ID   = st.secrets.get("STRIPE_PRICE_ID",   os.getenv("STRIPE_PRICE_ID", ""))
BASE_URL          = st.secrets.get("BASE_URL",          os.getenv("BASE_URL", "https://claraready.streamlit.app"))
HOTJAR_ID         = st.secrets.get("HOTJAR_ID",         os.getenv("HOTJAR_ID", ""))  # opcional

MONTHLY_PRICE_TEXT = "R$ 9,90/mês"

# -----------------------------------------------------------
# CSV simples para métricas locais
# -----------------------------------------------------------
VISITS_CSV = Path("/tmp/visits.csv")
CONSULTAS_CSV = Path("/tmp/consultas.csv")

def _ensure_csv(path: Path, header: List[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        with path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(header)

def log_visit(email: str) -> None:
    if not (email or "").strip():
        return
    _ensure_csv(VISITS_CSV, ["ts_utc", "email"])
    with VISITS_CSV.open("a", encoding="utf-8", newline="") as f:
        csv.writer(f).writerow([datetime.utcnow().isoformat(), email.strip().lower()])

def read_visits() -> List[Dict[str, str]]:
    if not VISITS_CSV.exists():
        return []
    rows: List[Dict[str, str]] = []
    with VISITS_CSV.open("r", encoding="utf-8") as f:
        r = csv.DictReader(f)
        rows = list(r)
    return rows

def log_consulta(payload: Dict[str, Any]) -> None:
    header = [
        "ts_utc", "nome", "email", "cel", "papel",
        "setor", "limite_valor", "texto_len", "premium"
    ]
    _ensure_csv(CONSULTAS_CSV, header)
    with CONSULTAS_CSV.open("a", encoding="utf-8", newline="") as f:
        csv.writer(f).writerow([
            datetime.utcnow().isoformat(),
            payload.get("nome", ""), payload.get("email",""),
            payload.get("cel",""), payload.get("papel",""),
            payload.get("setor",""), payload.get("limite_valor",""),
            payload.get("texto_len",0), payload.get("premium", False),
        ])

def read_consultas() -> List[Dict[str, str]]:
    if not CONSULTAS_CSV.exists():
        return []
    with CONSULTAS_CSV.open("r", encoding="utf-8") as f:
        return list(csv.DictReader(f))

# -----------------------------------------------------------
# CSS – visual clean (hero + cards + grid)
# -----------------------------------------------------------
st.markdown("""
<style>
  :root { --brand:#1C1C1E; --sub:#8E8E93; --card:#F7F8FA; --line:#ECEEF3; --pill:#EEF1FF; }
  .hero-wrap{
    margin:10px 0 18px 0; padding:26px 28px; border-radius:18px;
    background:linear-gradient(180deg,#11131A 0%,#171925 100%);
    color:#fff; border:1px solid #24273a;
  }
  .hero-title{ font-size:42px; font-weight:800; letter-spacing:-0.02em; margin:0; }
  .hero-sub{ margin-top:6px; color:#cfd3e0; font-size:14.5px }
  .pill { display:inline-block; padding:6px 12px; border-radius:999px;
          background:#202336; color:#9fb2ff; font-size:12px; border:1px solid #303552 }
  .cta { padding:12px 18px; border-radius:12px; font-weight:600; border:1px solid #2b2f44; background:#2B2F44; color:#fff }
  .cta:hover { filter:brightness(1.08) }
  .card { background:var(--card); border:1px solid var(--line); border-radius:16px; padding:16px 18px }
  .muted { color:var(--sub) }
  .note { font-size:12.5px; color:#5d6470 }
  .section-title { font-size:22px; font-weight:700; margin-top:4px }
</style>
""", unsafe_allow_html=True)

# Hotjar (opcional)
if HOTJAR_ID:
    st.markdown(f"""
    <script>
    (function(h,o,t,j,a,r){{
      h.hj=h.hj||function(){{(h.hj.q=h.hj.q||[]).push(arguments)}};
      h._hjSettings={{hjid:{int(HOTJAR_ID)},hjsv:6}};
      a=o.getElementsByTagName('head')[0];
      r=o.createElement('script');r.async=1;
      r.src='https://static.hotjar.com/c/hotjar-'+h._hjSettings.hjid+'.js?sv='+h._hjSettings.hjsv;
      a.appendChild(r);
    }})(window,document,window.location,document.createElement('script'));
    </script>
    """, unsafe_allow_html=True)

# -----------------------------------------------------------
# Estado inicial
# -----------------------------------------------------------
if "profile" not in st.session_state:
    st.session_state.profile = {"nome":"", "email":"", "cel":"", "papel":"Contratante"}
if "premium" not in st.session_state:
    st.session_state.premium = False
if "free_runs_left" not in st.session_state:
    st.session_state.free_runs_left = 1
if "started" not in st.session_state:
    st.session_state.started = False

# -----------------------------------------------------------
# Boot (Stripe + DB)
# -----------------------------------------------------------
@st.cache_resource(show_spinner="Iniciando serviços…")
def _boot() -> Tuple[bool, str]:
    try:
        if STRIPE_SECRET_KEY:
            init_stripe(STRIPE_SECRET_KEY)
        init_db()
        return True, ""
    except Exception as e:
        return False, f"Falha ao iniciar: {e}"

ok_boot, boot_msg = _boot()
if not ok_boot:
    st.error(boot_msg)
    st.stop()

# -----------------------------------------------------------
# Helpers
# -----------------------------------------------------------
def _parse_admin_emails() -> Set[str]:
    raw = st.secrets.get("admin_emails", os.getenv("ADMIN_EMAILS", ""))
    if isinstance(raw, list):
        return {str(x).strip().lower() for x in raw if str(x).strip()}
    if isinstance(raw, str):
        return {e.strip().lower() for e in raw.split(",") if e.strip()}
    return set()
ADMIN_EMAILS = _parse_admin_emails()

def current_email() -> str:
    return (st.session_state.profile.get("email") or "").strip().lower()

def is_premium() -> bool:
    if st.session_state.premium:
        return True
    em = current_email()
    if not em:
        return False
    try:
        sub = get_subscriber_by_email(em)
        if sub:
            st.session_state.premium = True
            return True
    except Exception:
        pass
    return False

def require_profile() -> bool:
    p = st.session_state.profile
    return all([(p.get("nome") or "").strip(), (p.get("email") or "").strip(), (p.get("cel") or "").strip()])

def stripe_diagnostics() -> Tuple[bool, str]:
    miss = []
    if not STRIPE_PUBLIC_KEY: miss.append("STRIPE_PUBLIC_KEY")
    if not STRIPE_SECRET_KEY: miss.append("STRIPE_SECRET_KEY")
    if not STRIPE_PRICE_ID:   miss.append("STRIPE_PRICE_ID")
    if miss: return False, "Faltam segredos: " + ", ".join(miss)
    if STRIPE_PRICE_ID.startswith("prod_"):
        return False, "Use o **ID de preço** que começa com **price_...** (não prod_...)."
    if not STRIPE_PRICE_ID.startswith("price_"):
        return False, "O STRIPE_PRICE_ID deve começar com **price_...**."
    return True, ""

# “Glossário” simples – deixa termos claros
GLOSS = {
    "foro": "foro (cidade/tribunal onde a disputa acontece)",
    "LGPD": "LGPD (lei que protege seus dados pessoais)",
    "rescisão": "rescisão (encerrar o contrato)",
}

def simplify_terms(text: str) -> str:
    out = text
    for k,v in GLOSS.items():
        out = out.replace(k, v)
    return out

# -----------------------------------------------------------
# Sidebar – cadastro + admin
# -----------------------------------------------------------
def sidebar_profile():
    st.sidebar.header("🔐 Seus dados (obrigatório)")
    nome  = st.sidebar.text_input("Nome completo*", value=st.session_state.profile.get("nome",""))
    email = st.sidebar.text_input("E-mail*",        value=st.session_state.profile.get("email",""))
    cel   = st.sidebar.text_input("Celular*",       value=st.session_state.profile.get("cel",""))
    papel = st.sidebar.selectbox("Você é o contratante?*", ["Contratante","Contratado","Outro"],
                                 index=["Contratante","Contratado","Outro"].index(st.session_state.profile.get("papel","Contratante")))

    if st.sidebar.button("Salvar perfil", use_container_width=True):
        st.session_state.profile = {"nome":nome.strip(), "email":email.strip(), "cel":cel.strip(), "papel":papel}
        try: log_visit(email.strip())
        except Exception: pass
        try:
            if current_email() and get_subscriber_by_email(current_email()):
                st.session_state.premium = True
        except Exception: pass
        st.sidebar.success("Dados salvos!")

    st.sidebar.markdown("---")
    st.sidebar.subheader("Administração")
    if current_email() in ADMIN_EMAILS:
        if st.sidebar.checkbox("Área administrativa"):
            st.sidebar.success("Admin ativo")

            # Assinantes
            try:
                subs = list_subscribers()
                with st.sidebar.expander("👥 Assinantes (Stripe)", expanded=False):
                    st.write(subs if subs else "Nenhum assinante ainda.")
            except Exception as e:
                st.sidebar.error(f"Erro ao listar assinantes: {e}")

            # Visitas
            try:
                visits = read_visits()
                with st.sidebar.expander("👣 Últimas visitas", expanded=False):
                    if not visits: st.write("Sem registros ainda.")
                    else:
                        for v in visits[-50:][::-1]:
                            st.write(f"{v.get('ts_utc','')} — {v.get('email','')}")
                # Download
                if VISITS_CSV.exists():
                    st.download_button("📥 Baixar visitas (CSV)", VISITS_CSV.read_bytes(),
                                       file_name="visitas.csv", mime="text/csv")
            except Exception as e:
                st.sidebar.error(f"Erro ao ler visitas: {e}")

            # Consultas
            try:
                cons = read_consultas()
                with st.sidebar.expander("🗂️ Consultas (últimas)", expanded=False):
                    st.write(cons[-30:] if cons else "Sem consultas ainda.")
                if CONSULTAS_CSV.exists():
                    st.download_button("📥 Baixar consultas (CSV)", CONSULTAS_CSV.read_bytes(),
                                       file_name="consultas.csv", mime="text/csv")
            except Exception as e:
                st.sidebar.error(f"Erro ao ler consultas: {e}")

# -----------------------------------------------------------
# Landing – estilo “iCloud”
# -----------------------------------------------------------
def landing():
    st.markdown(
        f"""
        <div class="hero-wrap">
          <div class="pill">{APP_SUBTITLE} • {VERSION}</div>
          <h1 class="hero-title">{APP_TITLE}</h1>
          <p class="hero-sub">
            Tudo o que importa no seu contrato — em linguagem simples.
            A CLARA destaca riscos, explica o que significam e mostra como negociar.
          </p>
        </div>
        """, unsafe_allow_html=True
    )

    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("""<div class="card">
        <b>🛡️ Proteção</b><br>
        Enxerga multas fora da realidade, travas e responsabilidades exageradas.
        </div>""", unsafe_allow_html=True)
    with col2:
        st.markdown("""<div class="card">
        <b>📖 Clareza</b><br>
        Traduz “juridiquês” (ex.: <i>foro</i>, <i>LGPD</i>, <i>rescisão</i>) em termos comuns.
        </div>""", unsafe_allow_html=True)
    with col3:
        st.markdown("""<div class="card">
        <b>📈 CET</b><br>
        Calcula o custo efetivo total (juros + tarifas + taxas) em contratos financeiros.
        </div>""", unsafe_allow_html=True)

    st.markdown("<div class='section-title'>Por que isso importa?</div>", unsafe_allow_html=True)
    st.markdown(
        """
        • A frase “Li e concordo com os termos” virou símbolo de um problema silencioso no Brasil.  
        • Muita gente assina sem entender e expõe o próprio negócio a riscos desnecessários.  
        • A CLARA ajuda a **entender antes de assinar**: simples, rápida e com foco no que realmente importa.
        """)
    st.markdown("<br>", unsafe_allow_html=True)

    cta = st.button("🚀 Começar agora", type="primary", use_container_width=True)
    if cta: st.session_state.started = True

# -----------------------------------------------------------
# Pricing / Stripe
# -----------------------------------------------------------
def pricing_card():
    st.markdown("<div class='section-title'>Plano Premium</div>", unsafe_allow_html=True)
    st.caption(f"{MONTHLY_PRICE_TEXT} • análises ilimitadas • suporte prioritário")

    okS, msgS = stripe_diagnostics()
    email = current_email()

    if not email:
        st.info("Informe e salve **nome, e-mail e celular** na barra lateral para assinar.")
        return

    if st.button("💳 Assinar Premium agora", use_container_width=True):
        if not okS:
            st.error(msgS); return
        try:
            sess = create_checkout_session(
                price_id=STRIPE_PRICE_ID,
                customer_email=email,
                success_url=f"{BASE_URL}?success=true&session_id={{CHECKOUT_SESSION_ID}}",
                cancel_url=f"{BASE_URL}?canceled=true",
            )
            if sess.get("url"):
                st.success("Sessão criada. Abra o checkout seguro:")
                st.link_button("👉 Abrir checkout", sess["url"], use_container_width=True)
            else:
                st.error(sess.get("error", "Stripe indisponível. Tente de novo."))
        except Exception as e:
            st.error(f"Stripe indisponível: {e}")

def handle_checkout_result():
    qs = st.query_params
    if qs.get("success") == "true" and qs.get("session_id"):
        sid = qs["session_id"]
        try:
            ok, data = verify_checkout_session(sid)
        except Exception as e:
            st.error(f"Não foi possível confirmar o pagamento: {e}")
            ok, data = False, {}
        if ok:
            try:
                log_subscriber(
                    email=current_email(),
                    name=st.session_state.profile.get("nome",""),
                    stripe_customer_id=(data.get("customer")
                        or (data.get("subscription") or {}).get("customer") or "")
                )
            except Exception: pass
            st.session_state.premium = True
            st.success("Pagamento confirmado! Premium liberado ✅")
        else:
            st.warning("Não conseguimos confirmar essa sessão. Tente novamente.")
        try: st.query_params.clear()
        except Exception: pass

# -----------------------------------------------------------
# Fluxo de análise
# -----------------------------------------------------------
def upload_or_paste_section() -> str:
    st.markdown("<div class='section-title'>1) Envie o contrato</div>", unsafe_allow_html=True)
    file = st.file_uploader("PDF do contrato (ou cole o texto abaixo)", type=["pdf"])
    raw = ""
    if file:
        with st.spinner("Lendo PDF…"):
            raw = extract_text_from_pdf(file)
    raw = st.text_area("Texto do contrato", height=220, value=raw or "")
    return raw

def analysis_inputs() -> Dict[str, Any]:
    st.markdown("<div class='section-title'>2) Contexto</div>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns(3)
    setor = col1.selectbox("Setor", ["Genérico","SaaS/Serviços","Empréstimos","Educação","Plano de saúde"])
    papel = col2.selectbox("Perfil", ["Contratante","Contratado","Outro"])
    limite_valor = col3.number_input("Valor máx. (opcional)", min_value=0.0, step=100.0)
    return {"setor":setor, "papel":papel, "limite_valor":limite_valor}

def cet_calculator_block():
    with st.expander("📈 Calculadora de CET (opcional)"):
        c1, c2, c3 = st.columns(3)
        P   = c1.number_input("Valor principal (R$)", min_value=0.0, step=100.0, key="cet_p")
        i_m = c2.number_input("Juros mensais (%)",   min_value=0.0, step=0.1,   key="cet_i")
        n   = c3.number_input("Parcelas (n)",        min_value=1,   step=1,     key="cet_n")
        fee = st.number_input("Taxas fixas totais (R$)", min_value=0.0, step=10.0, key="cet_fee")
        if st.button("Calcular CET", key="btn_calc_cet"):
            cet = compute_cet_quick(P, i_m/100.0, int(n), fee)
            st.success(f"**CET aproximado:** {cet*100:.2f}% a.m.")

def results_section(text: str, ctx: Dict[str, Any]):
    st.markdown("<div class='section-title'>3) Resultado</div>", unsafe_allow_html=True)

    if not require_profile():
        st.info("Preencha e salve **nome, e-mail e celular** na barra lateral para liberar a análise.")
        return
    if not text.strip():
        st.warning("Envie o PDF ou cole o texto do contrato.")
        return

    # Free/Premium
    if not is_premium() and st.session_state.free_runs_left <= 0:
        st.info("Você usou sua análise gratuita. Assine o Premium para continuar."); return

    with st.spinner("Analisando…"):
        hits, meta = analyze_contract_text(text, ctx)

    if not is_premium():
        st.session_state.free_runs_left -= 1

    # Logs
    log_analysis_event(email=current_email(), meta={"setor":ctx["setor"],"papel":ctx["papel"],"len":len(text)})
    log_consulta({
        "nome": st.session_state.profile.get("nome",""),
        "email": current_email(), "cel": st.session_state.profile.get("cel",""),
        "papel": st.session_state.profile.get("papel",""),
        "setor": ctx["setor"], "limite_valor": ctx["limite_valor"],
        "texto_len": len(text), "premium": is_premium()
    })

    resumo = summarize_hits(hits)
    st.success(f"Resumo rápido: {resumo['resumo']}")
    st.caption(f"Gravidade: **{resumo['gravidade']}** • Pontos críticos: **{resumo['criticos']}** • Itens encontrados: {len(hits)}")

    # Explicações simplificadas
    for h in hits:
        title = simplify_terms(h['title'])
        expl  = simplify_terms(h['explanation'])
        with st.expander(f"{h['severity']} • {title}"):
            st.write(expl)
            if h.get("suggestion"):
                st.markdown(f"**Sugestão prática:** {simplify_terms(h['suggestion'])}")
            if h.get("evidence"):
                st.code(h["evidence"][:1200])

    cet_calculator_block()

    # Relatório
    buff = io.StringIO()
    buff.write(f"{APP_TITLE} {APP_SUBTITLE} {VERSION}\n")
    buff.write(f"Usuário: {st.session_state.profile.get('nome')} <{current_email()}>\n")
    buff.write(f"Perfil: {ctx['papel']} • Setor: {ctx['setor']} • Valor máx.: {ctx['limite_valor']}\n\n")
    buff.write(f"Resumo: {resumo['resumo']} (Gravidade: {resumo['gravidade']})\n\n")
    buff.write("Pontos de atenção:\n")
    for h in hits:
        buff.write(f"- [{h['severity']}] {simplify_terms(h['title'])} — {simplify_terms(h['explanation'])}\n")
        if h.get("suggestion"):
            buff.write(f"  Sugestão: {simplify_terms(h['suggestion'])}\n")
    st.download_button("📥 Baixar relatório (txt)", buff.getvalue(), file_name="relatorio_clara.txt", mime="text/plain")

# -----------------------------------------------------------
# Main
# -----------------------------------------------------------
def main():
    sidebar_profile()
    handle_checkout_result()

    # Header minimalista
    colA, colB = st.columns([3,2])
    with colA:
        st.markdown(f"### {APP_TITLE}  <span class='muted'>{APP_SUBTITLE} • {VERSION}</span>", unsafe_allow_html=True)
    with colB:
        st.markdown(" ")  # respiro

    # Landing ou fluxo
    if not st.session_state.started:
        landing()
        st.markdown("---")
        st.markdown("#### Como funciona")
        st.markdown("1) Envie o PDF ou cole o texto do contrato")
        st.markdown("2) Ajuste o contexto (setor, perfil e valor opcional)")
        st.markdown("3) Receba **trecho + explicação simples + sugestão de negociação**")
        st.markdown("4) (Opcional) **Calcule o CET**")
        st.info("A **CLARA complementa** o trabalho jurídico. Pense nela como **apoio para triagem e preparo** — para depois conversar com seu advogado ou time.")
        st.markdown("---")
        pricing_card()
        return

    # Fluxo de análise
    text = upload_or_paste_section()
    ctx  = analysis_inputs()
    st.markdown("")
    if st.button("🚀 Analisar agora", use_container_width=True):
        results_section(text, ctx)

    st.markdown("---")
    st.info("A **CLARA complementa** a orientação de um(a) advogado(a). É um **apoio prático** para entender antes de assinar.")

if __name__ == "__main__":
    main()



