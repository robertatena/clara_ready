# app.py — CLARA • Análise de contratos em linguagem simples
# Tela 1 super clean (sem preto) + Tela 2 com fluxo completo
# Mantém: Stripe, CET, Admin, Hotjar, logs CSV, relatório, explicadores simples

import os
import io
import csv
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Tuple, Set, List

import streamlit as st

# ---- módulos locais (já existentes no seu projeto) ----
from app_modules.pdf_utils import extract_text_from_pdf
from app_modules.analysis import analyze_contract_text, summarize_hits, compute_cet_quick
from app_modules.stripe_utils import init_stripe, create_checkout_session, verify_checkout_session
from app_modules.storage import (
    init_db, log_analysis_event, log_subscriber, list_subscribers, get_subscriber_by_email
)

# =========================
# Config / Constantes
# =========================
APP_TITLE = "CLARA"
SUBTITLE  = "Análise de contratos em linguagem simples"
VERSION   = "v14.1"

st.set_page_config(page_title=f"{APP_TITLE} • {SUBTITLE}", page_icon="🧾", layout="wide")

# Secrets / ENV
STRIPE_PUBLIC_KEY = st.secrets.get("STRIPE_PUBLIC_KEY", os.getenv("STRIPE_PUBLIC_KEY", ""))
STRIPE_SECRET_KEY = st.secrets.get("STRIPE_SECRET_KEY", os.getenv("STRIPE_SECRET_KEY", ""))
STRIPE_PRICE_ID   = st.secrets.get("STRIPE_PRICE_ID",   os.getenv("STRIPE_PRICE_ID", ""))
BASE_URL          = st.secrets.get("BASE_URL",          os.getenv("BASE_URL", "https://claraready.streamlit.app"))
HOTJAR_ID         = st.secrets.get("HOTJAR_ID",         os.getenv("HOTJAR_ID", ""))  # ex.: "6519667"

MONTHLY_PRICE_TEXT = "R$ 9,90/mês"

# CSVs efêmeros (em disco temporário)
VISITS_CSV    = Path("/tmp/visitas.csv")
CONSULTAS_CSV = Path("/tmp/consultas.csv")

# =========================
# Estado inicial
# =========================
if "profile" not in st.session_state:
    st.session_state.profile = {"nome": "", "email": "", "cel": "", "papel": "Contratante"}
if "premium" not in st.session_state:
    st.session_state.premium = False
if "free_runs_left" not in st.session_state:
    st.session_state.free_runs_left = 1
if "started" not in st.session_state:
    st.session_state.started = False  # controla a transição Tela 1 -> Tela 2

# =========================
# Boot (Stripe + DB)
# =========================
@st.cache_resource(show_spinner="Iniciando serviços…")
def _boot() -> Tuple[bool, str]:
    try:
        if STRIPE_SECRET_KEY:
            init_stripe(STRIPE_SECRET_KEY)
        init_db()
        return True, ""
    except Exception as e:
        return False, f"Falha ao iniciar serviços: {e}"

ok_boot, msg_boot = _boot()
if not ok_boot:
    st.error(msg_boot)
    st.stop()

# =========================
# Helpers
# =========================
def _parse_admin_emails() -> Set[str]:
    raw = st.secrets.get("admin_emails", None) or os.getenv("ADMIN_EMAILS", "")
    if isinstance(raw, list):
        return {str(x).strip().lower() for x in raw if str(x).strip()}
    if isinstance(raw, str):
        return {e.strip().lower() for e in raw.split(",") if e.strip()}
    return set()

ADMIN_EMAILS = _parse_admin_emails()

def current_email() -> str:
    return (st.session_state.profile.get("email") or "").strip().lower()

def require_profile() -> bool:
    p = st.session_state.profile
    return bool((p.get("nome") or "").strip() and (p.get("email") or "").strip() and (p.get("cel") or "").strip())

def is_premium() -> bool:
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

def stripe_diagnostics() -> Tuple[bool, str]:
    miss = []
    if not STRIPE_PUBLIC_KEY: miss.append("STRIPE_PUBLIC_KEY")
    if not STRIPE_SECRET_KEY: miss.append("STRIPE_SECRET_KEY")
    if not STRIPE_PRICE_ID:   miss.append("STRIPE_PRICE_ID")
    if miss:
        return False, f"Configure: {', '.join(miss)}."
    if STRIPE_PRICE_ID.startswith("prod_"):
        return False, "Use um **price_...** (não **prod_...**)."
    if not STRIPE_PRICE_ID.startswith("price_"):
        return False, "O STRIPE_PRICE_ID deve começar com **price_...**."
    return True, ""

# ===== CSV utils =====
def _csv_init(path: Path, header: List[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        with path.open("w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(header)

def log_visit(email: str) -> None:
    _csv_init(VISITS_CSV, ["ts_utc", "email"])
    if not (email or "").strip():
        return
    with VISITS_CSV.open("a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow([datetime.utcnow().isoformat(), email.strip().lower()])

def read_visits() -> List[Dict[str, str]]:
    if not VISITS_CSV.exists(): return []
    with VISITS_CSV.open("r", encoding="utf-8") as f:
        return list(csv.DictReader(f))

def log_consulta(row: Dict[str, Any]) -> None:
    header = ["ts_utc","nome","email","cel","papel","setor","valor_max","text_len","premium"]
    _csv_init(CONSULTAS_CSV, header)
    with CONSULTAS_CSV.open("a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow([
            datetime.utcnow().isoformat(),
            row.get("nome",""), row.get("email",""), row.get("cel",""), row.get("papel",""),
            row.get("setor",""), row.get("valor_max",""), row.get("text_len",""), row.get("premium",""),
        ])

# =========================
# Hotjar (se houver ID)
# =========================
if HOTJAR_ID:
    st.markdown(
        f"""
        <script>
          (function(h,o,t,j,a,r){{
              h.hj=h.hj||function(){{(h.hj.q=h.hj.q||[]).push(arguments)}};
              h._hjSettings={{hjid:{int(HOTJAR_ID)},hjsv:6}};
              a=o.getElementsByTagName('head')[0];
              r=o.createElement('script');r.async=1;
              r.src='https://static.hotjar.com/c/hotjar-'+h._hjSettings.hjid+'.js?sv='+h._hjSettings.hjsv;
              a.appendChild(r);
          }})(window,document,'https://static.hotjar.com/c/hotjar-','.js?sv=');
        </script>
        """,
        unsafe_allow_html=True,
    )

# =========================
# Estilos (clean, sem preto)
# =========================
BASE_CSS = """
<style>
  html, body, [class^="css"]  { font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }
  .hero {
    min-height: 70vh; display:flex; align-items:center; justify-content:center; flex-direction:column;
    text-align:center; padding: 0 16px;
  }
  .hero-title { font-size: 72px; font-weight: 800; letter-spacing: -0.5px; margin: 8px 0 4px 0; }
  .hero-sub   { font-size: 18px; color:#667085; margin-top: 6px; max-width: 860px; }
  .cta-big {
    display:inline-block; margin-top:22px; padding:14px 26px; border-radius:999px; font-weight:700;
    background: linear-gradient(90deg, #2563eb 0%, #3b82f6 100%); color:#fff; text-decoration:none; border:0; font-size:18px;
  }
  .cta-big:hover { filter: brightness(0.97); }
  .muted { color:#6b7280; }
  .footnote { font-size:13px; color:#6e7480; max-width: 980px; }
  .pill-card { border:1px solid #edf1f7; border-radius:14px; padding:18px; background:#fff; }
</style>
"""
st.markdown(BASE_CSS, unsafe_allow_html=True)

# Oculta sidebar na Tela 1; revela na Tela 2
if not st.session_state.started:
    st.markdown("<style>[data-testid='stSidebar']{display:none;} .block-container{padding-top:0;}</style>", unsafe_allow_html=True)
else:
    st.markdown("<style>[data-testid='stSidebar']{display:block;}</style>", unsafe_allow_html=True)

# =========================
# Sidebar – Perfil + Admin (apenas depois de iniciar)
# =========================
def sidebar_profile():
    st.sidebar.header("🔐 Seus dados (obrigatório)")
    nome  = st.sidebar.text_input("Nome completo*", value=st.session_state.profile.get("nome",""))
    email = st.sidebar.text_input("E-mail*",        value=st.session_state.profile.get("email",""))
    cel   = st.sidebar.text_input("Celular*",       value=st.session_state.profile.get("cel",""))
    papel = st.sidebar.selectbox(
        "Você é o contratante?*",
        ["Contratante", "Contratado", "Outro"],
        index=["Contratante","Contratado","Outro"].index(st.session_state.profile.get("papel","Contratante"))
    )
    if st.sidebar.button("Salvar perfil", use_container_width=True):
        st.session_state.profile = {"nome":nome.strip(),"email":email.strip(),"cel":cel.strip(),"papel":papel}
        try: log_visit(email.strip())
        except Exception: pass
        try:
            if current_email() and get_subscriber_by_email(current_email()):
                st.session_state.premium = True
        except Exception: pass
        st.sidebar.success("Dados salvos!")

    # Admin
    st.sidebar.markdown("---")
    st.sidebar.subheader("Administração")
    if current_email() in ADMIN_EMAILS and st.sidebar.checkbox("Área administrativa"):
        st.sidebar.success("Admin ativo")
        colA, colB = st.sidebar.columns(2)
        with colA:
            if VISITS_CSV.exists():
                st.sidebar.download_button("⬇️ visitas.csv", VISITS_CSV.read_bytes(), "visitas.csv", "text/csv")
            else:
                st.sidebar.caption("Sem visitas ainda.")
        with colB:
            if CONSULTAS_CSV.exists():
                st.sidebar.download_button("⬇️ consultas.csv", CONSULTAS_CSV.read_bytes(), "consultas.csv", "text/csv")
            else:
                st.sidebar.caption("Sem consultas ainda.")
        try:
            subs = list_subscribers()
            with st.sidebar.expander("👥 Assinantes (Stripe)", expanded=False):
                st.write(subs or "Nenhum assinante.")
        except Exception as e:
            st.sidebar.error(f"Assinantes: {e}")
        try:
            visits = read_visits()
            with st.sidebar.expander("👣 Últimas visitas", expanded=False):
                if not visits: st.write("Sem registros.")
                else:
                    for v in visits[-50:][::-1]:
                        st.write(f"{v.get('ts_utc','')} — {v.get('email','')}")
        except Exception as e:
            st.sidebar.error(f"Visitas: {e}")

# =========================
# Tela 1 — Super clean (mensagem do problema + 1 botão)
# =========================
def first_screen():
    st.write("")
    st.markdown(
        f"""
        <div class="hero">
          <div class="hero-title">{APP_TITLE}</div>
          <div class="hero-sub">
            Entenda seu contrato em linguagem simples. A CLARA encontra riscos, traduz juridiquês e
            sugere caminhos de negociação — rápido e direto ao ponto.
          </div>
          <div style="margin-top:24px;">
            <form method="post">
              <button class="cta-big" name="start" type="submit">Iniciar análise do meu contrato</button>
            </form>
          </div>
          <div class="footnote" style="margin-top:28px; text-align:justify;">
            <p><b>Milhões de brasileiros</b> assinam documentos legais sem entender completamente o que estão aceitando,
            colocando seus negócios e patrimônio em risco desnecessário.</p>
            <p>A frase <i>“Eu li e concordo com os termos e condições”</i> virou símbolo dessa crise silenciosa no Brasil.
            Muitos empresários negligenciam a importância de compreender profundamente o que assinam, expondo suas empresas
            a vulnerabilidades que poderiam ser evitadas com mais clareza.</p>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Botão server-side (sem JS) — robusto
    if st.session_state.get("_start_clicked", False):
        st.session_state.started = True
        st.session_state["_start_clicked"] = False
        st.experimental_rerun()

    # Detecta submit do <form> (via query & workaround)
    if st.runtime.exists():  # compat
        # Streamlit não tem hook direto do <form>, então usamos um botão abaixo para garantir
        pass

    # Botão redundante visível (caso o <form> seja bloqueado por CSP)
    if st.button("Iniciar agora", use_container_width=True):
        st.session_state.started = True
        st.experimental_rerun()

# =========================
# Stripe – Pricing / checkout
# =========================
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
            st.error(msgS); return
        try:
            sess = create_checkout_session(
                price_id=STRIPE_PRICE_ID,
                customer_email=email,
                success_url=f"{BASE_URL}?success=true&session_id={{CHECKOUT_SESSION_ID}}",
                cancel_url=f"{BASE_URL}?canceled=true",
            )
            if sess.get("url"):
                st.success("Sessão criada! Clique abaixo.")
                st.link_button("👉 Abrir checkout seguro", sess["url"], use_container_width=True)
            else:
                st.error(sess.get("error","Stripe indisponível no momento."))
        except Exception as e:
            st.error(f"Stripe indisponível: {e}")

def handle_checkout_result():
    qs = st.query_params
    if qs.get("success") == "true" and qs.get("session_id"):
        sid = qs["session_id"]
        try:
            ok, payload = verify_checkout_session(sid)
        except Exception as e:
            st.error(f"Não foi possível confirmar: {e}")
            ok, payload = False, {}

        if ok:
            try:
                log_subscriber(
                    email=current_email(),
                    name=st.session_state.profile.get("nome",""),
                    stripe_customer_id=(payload.get("customer") or (payload.get("subscription") or {}).get("customer") or ""),
                )
            except Exception:
                pass
            st.session_state.premium = True
            st.success("Pagamento confirmado! Premium liberado ✅")
        else:
            st.warning("Não conseguimos confirmar esta sessão. Tente novamente.")
        try: st.query_params.clear()
        except Exception: pass

# =========================
# Fluxo da análise (Tela 2)
# =========================
def upload_or_paste_section() -> str:
    st.subheader("1) Envie o contrato")
    file = st.file_uploader("PDF do contrato", type=["pdf"])
    raw_text = ""
    if file:
        with st.spinner("Lendo PDF…"):
            raw_text = extract_text_from_pdf(file)
    st.markdown("Ou cole o texto abaixo:")
    return st.text_area("Texto do contrato", height=220, value=raw_text or "")

def analysis_inputs() -> Dict[str, Any]:
    st.subheader("2) Contexto")
    c1, c2, c3 = st.columns(3)
    setor = c1.selectbox("Setor", ["Genérico", "SaaS/Serviços", "Empréstimos", "Educação", "Plano de saúde"])
    papel = c2.selectbox("Perfil", ["Contratante","Contratado","Outro"])
    limite_valor = c3.number_input("Valor máximo (opcional, R$)", min_value=0.0, step=100.0)
    return {"setor": setor, "papel": papel, "limite_valor": limite_valor}

def cet_calculator_block():
    with st.expander("📈 Calculadora de CET (opcional)", expanded=False):
        c1, c2, c3 = st.columns(3)
        P   = c1.number_input("Valor principal (R$)", min_value=0.0, step=100.0, key="cet_p")
        i_m = c2.number_input("Juros mensais (%)", min_value=0.0, step=0.1, key="cet_i")
        n   = c3.number_input("Parcelas (n)", min_value=1, step=1, key="cet_n")
        fee = st.number_input("Taxas fixas totais (R$)", min_value=0.0, step=10.0, key="cet_fee")
        if st.button("Calcular CET", key="btn_calc_cet"):
            cet = compute_cet_quick(P, i_m/100.0, int(n), fee)
            st.success(f"**CET aproximado:** {cet*100:.2f}% a.m.")

def legal_explainers_block():
    with st.expander("📚 Explicações rápidas (jurídico em linguagem simples)", expanded=False):
        st.markdown("**Foro** → é a cidade/tribunal onde um processo corre. Se for longe, fica caro se defender.")
        st.markdown("**LGPD** → regras sobre seus dados: por quê são coletados, por quanto tempo e por quem.")
        st.markdown("**Rescisão** → como encerrar: prazos, multas, devoluções e se existe um **teto** para penalidades.")
        st.markdown("**Responsabilidade** → sem limite claro, você pode ficar exposto a valores muito altos.")
        st.markdown("**Reajuste** → quando e como o preço muda (índice, periodicidade, aviso).")

def results_section(text: str, ctx: Dict[str, Any]):
    st.subheader("4) Resultado")

    if not require_profile():
        st.info("Preencha e salve **nome, e-mail e celular** na barra lateral para liberar a análise.")
        return
    if not text.strip():
        st.warning("Envie o contrato (PDF) ou cole o texto.")
        return
    if not is_premium() and st.session_state.free_runs_left <= 0:
        st.info("Você usou sua análise gratuita. **Assine o Premium** para continuar.")
        return

    with st.spinner("Analisando…"):
        hits, meta = analyze_contract_text(text, ctx)

    if not is_premium():
        st.session_state.free_runs_left -= 1

    email = current_email()
    log_analysis_event(email=email, meta={"setor":ctx["setor"], "papel":ctx["papel"], "len":len(text)})
    log_consulta({
        "nome": st.session_state.profile.get("nome",""),
        "email": email, "cel": st.session_state.profile.get("cel",""),
        "papel": ctx["papel"], "setor": ctx["setor"],
        "valor_max": ctx["limite_valor"], "text_len": len(text), "premium": is_premium(),
    })

    resume = summarize_hits(hits)
    st.success(f"Resumo: {resume['resumo']}")
    st.write(f"Gravidade: **{resume['gravidade']}** | Pontos críticos: **{resume['criticos']}** | Total: {len(hits)}")

    for h in hits:
        with st.expander(f"{h['severity']} • {h['title']}"):
            st.write(h["explanation"])
            if h.get("suggestion"):
                st.markdown(f"**Sugestão de negociação:** {h['suggestion']}")
            if h.get("evidence"):
                st.code(h["evidence"][:1200])

    legal_explainers_block()
    cet_calculator_block()

    # Relatório (txt)
    buff = io.StringIO()
    buff.write(f"{APP_TITLE} • {SUBTITLE} {VERSION}\n")
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

# =========================
# MAIN
# =========================
def main():
    handle_checkout_result()

    # TELA 1 (clean)
    if not st.session_state.started:
        first_screen()
        return

    # TELA 2 – fluxo completo
    sidebar_profile()

    st.caption(f"{APP_TITLE} • {SUBTITLE} • {VERSION}")

    col1, col2 = st.columns([3,2])
    with col1:
        text = upload_or_paste_section()
        ctx  = analysis_inputs()
        if st.button("🚀 Rodar análise", use_container_width=True):
            results_section(text, ctx)
    with col2:
        pricing_card()

    st.markdown("---")
    st.markdown(
        "<p class='footnote'>A CLARA complementa a sua leitura e prepara a negociação. "
        "Para decisões finais, conte também com um(a) advogado(a).</p>",
        unsafe_allow_html=True,
    )

if __name__ == "__main__":
    main()
