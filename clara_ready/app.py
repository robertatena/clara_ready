# app.py — CLARA • Análise de Contratos
# UX inspirado no iCloud + linguagem simples + Stripe + CET + Admin + Hotjar

import os
import io
import csv
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Tuple, Set, List

import streamlit as st

# ====== Módulos locais (mantenha os arquivos já existentes) ======
from app_modules.pdf_utils import extract_text_from_pdf
from app_modules.analysis import analyze_contract_text, summarize_hits, compute_cet_quick
from app_modules.stripe_utils import init_stripe, create_checkout_session, verify_checkout_session
from app_modules.storage import (
    init_db, log_analysis_event, log_subscriber,
    list_subscribers, get_subscriber_by_email,
)

# ================================================================
# Config / Constantes
# ================================================================
APP_TITLE = "CLARA"
SUBTITLE  = "Análise de contratos"
VERSION   = "v13.6"

st.set_page_config(page_title=f"{APP_TITLE} • {SUBTITLE}", page_icon="🧾", layout="wide")

# Secrets / ENV
STRIPE_PUBLIC_KEY = st.secrets.get("STRIPE_PUBLIC_KEY", os.getenv("STRIPE_PUBLIC_KEY", ""))
STRIPE_SECRET_KEY = st.secrets.get("STRIPE_SECRET_KEY", os.getenv("STRIPE_SECRET_KEY", ""))
STRIPE_PRICE_ID   = st.secrets.get("STRIPE_PRICE_ID",   os.getenv("STRIPE_PRICE_ID", ""))
BASE_URL          = st.secrets.get("BASE_URL",          os.getenv("BASE_URL", "https://claraready.streamlit.app"))
HOTJAR_ID         = st.secrets.get("HOTJAR_ID",         os.getenv("HOTJAR_ID", ""))  # Ex.: "6519667"

MONTHLY_PRICE_TEXT = "R$ 9,90/mês"

# Arquivos de log (simples, em disco efêmero do Streamlit Cloud)
VISITS_CSV     = Path("/tmp/visitas.csv")
CONSULTAS_CSV  = Path("/tmp/consultas.csv")

# ================================================================
# CSS (hero estilo iCloud) + micro tema
# ================================================================
st.markdown(
    """
    <style>
      html, body, [class^="css"]  { font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }
      .hero {
        padding: 48px 24px 40px 24px;
        text-align: center;
        background: linear-gradient(180deg, #ffffff 0%, #f8fbff 100%);
        border: 1px solid #eef2f7; border-radius: 18px;
      }
      .hero-title {
        font-size: 64px; font-weight: 750; letter-spacing: -1px; margin: 12px 0 0 0;
      }
      .hero-sub {
        font-size: 14px; color:#6b7280; margin-top: 8px;
      }
      .cloud-badge {
        display:inline-block; padding:6px 12px; border-radius:999px;
        background:#eef1ff; color:#3340c0; border:1px solid #e3e7ff; font-size:12px;
      }
      .pill-card {
        border:1px solid #edf1f7; border-radius:14px; padding:18px; background:#fff;
      }
      .muted { color:#6b7280; }
      .footnote { font-size:12.5px; color:#6e7480; }
      .cta-big {
        display:inline-block; padding:14px 28px; border-radius:999px; font-weight:650;
        background:#111; color:#fff; text-decoration:none; border:1px solid #111;
      }
      .cta-big:hover { filter: brightness(0.96); }
      .section-title { font-size:22px; font-weight:700; margin: 18px 0 6px 0; }
      .card-title { font-weight:700; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ================================================================
# JS – Hotjar (se houver ID)
# ================================================================
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

# ================================================================
# Estado inicial
# ================================================================
if "profile" not in st.session_state:
    st.session_state.profile = {"nome": "", "email": "", "cel": "", "papel": "Contratante"}
if "premium" not in st.session_state:
    st.session_state.premium = False
if "free_runs_left" not in st.session_state:
    st.session_state.free_runs_left = 1
if "started" not in st.session_state:
    st.session_state.started = False  # controla o botão “Iniciar análise do meu contrato”

# ================================================================
# Boot (Stripe + DB)
# ================================================================
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

# ================================================================
# Helpers
# ================================================================
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

# ===== Logs simples em CSV =====
def _csv_init(path: Path, header: List[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        with path.open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(header)

def log_visit(email: str) -> None:
    _csv_init(VISITS_CSV, ["ts_utc", "email"])
    if not (email or "").strip():
        return
    with VISITS_CSV.open("a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow([datetime.utcnow().isoformat(), email.strip().lower()])

def read_visits() -> List[Dict[str, str]]:
    if not VISITS_CSV.exists():
        return []
    rows: List[Dict[str, str]] = []
    with VISITS_CSV.open("r", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            rows.append(dict(row))
    return rows

def log_consulta(row: Dict[str, Any]) -> None:
    header = ["ts_utc","nome","email","cel","papel","setor","valor_max","text_len","premium"]
    _csv_init(CONSULTAS_CSV, header)
    with CONSULTAS_CSV.open("a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow([
            datetime.utcnow().isoformat(),
            row.get("nome",""), row.get("email",""), row.get("cel",""), row.get("papel",""),
            row.get("setor",""), row.get("valor_max",""), row.get("text_len",""), row.get("premium",""),
        ])

# ================================================================
# Sidebar – Cadastro + Admin
# ================================================================
def sidebar_profile():
    st.sidebar.header("🔐 Seus dados (obrigatório)")
    nome  = st.sidebar.text_input("Nome completo*", value=st.session_state.profile.get("nome", ""))
    email = st.sidebar.text_input("E-mail*",        value=st.session_state.profile.get("email", ""))
    cel   = st.sidebar.text_input("Celular*",       value=st.session_state.profile.get("cel", ""))
    papel = st.sidebar.selectbox(
        "Você é o contratante?*",
        ["Contratante", "Contratado", "Outro"],
        index=["Contratante","Contratado","Outro"].index(st.session_state.profile.get("papel","Contratante"))
    )

    if st.sidebar.button("Salvar perfil", use_container_width=True):
        st.session_state.profile = {
            "nome": nome.strip(), "email": email.strip(), "cel": cel.strip(), "papel": papel
        }
        try:
            log_visit(email.strip())
        except Exception:
            pass
        # Se já é assinante, ativa premium
        try:
            if current_email() and get_subscriber_by_email(current_email()):
                st.session_state.premium = True
        except Exception:
            pass
        st.sidebar.success("Dados salvos!")

    # ----- Admin
    st.sidebar.markdown("---")
    st.sidebar.subheader("Administração")
    if current_email() in ADMIN_EMAILS:
        if st.sidebar.checkbox("Área administrativa"):
            st.sidebar.success("Admin ativo")
            colA, colB = st.sidebar.columns(2)
            with colA:
                if st.sidebar.button("⬇️ Baixar visitas CSV"):
                    if VISITS_CSV.exists():
                        st.download_button("Download visitas.csv", data=VISITS_CSV.read_bytes(),
                                           file_name="visitas.csv", mime="text/csv")
                    else:
                        st.info("Sem arquivo de visitas ainda.")
            with colB:
                if st.sidebar.button("⬇️ Baixar consultas CSV"):
                    if CONSULTAS_CSV.exists():
                        st.download_button("Download consultas.csv", data=CONSULTAS_CSV.read_bytes(),
                                           file_name="consultas.csv", mime="text/csv")
                    else:
                        st.info("Sem arquivo de consultas ainda.")

            # Assinantes
            try:
                subs = list_subscribers()
                with st.sidebar.expander("👥 Assinantes (Stripe)", expanded=False):
                    st.write(subs if subs else "Nenhum assinante ainda.")
            except Exception as e:
                st.sidebar.error(f"Assinantes: {e}")

            # Visitas recentes
            try:
                visits = read_visits()
                with st.sidebar.expander("👣 Últimas visitas", expanded=False):
                    if not visits:
                        st.write("Sem registros.")
                    else:
                        for v in visits[-50:][::-1]:
                            st.write(f"{v.get('ts_utc','')} — {v.get('email','')}")
            except Exception as e:
                st.sidebar.error(f"Visitas: {e}")

# ================================================================
# Hero / Landing (estilo iCloud) + CTA
# ================================================================
def landing_hero():
    st.markdown(
        f"""
        <div class="hero">
          <div class="cloud-badge">{SUBTITLE} • {VERSION}</div>
          <div class="hero-title">{APP_TITLE}</div>
          <p class="hero-sub">Tudo o que importa no seu contrato — explicado em linguagem simples.</p>
          <div style="margin-top:22px;">
            <a class="cta-big" href="#iniciar">Iniciar análise do meu contrato</a>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("#### 🛡️ Proteção")
        st.markdown(
            "<div class='pill-card'>Enxerga multas fora da realidade, travas de rescisão e "
            "responsabilidades exageradas.</div>", unsafe_allow_html=True,
        )
    with c2:
        st.markdown("#### 🗣️ Clareza")
        st.markdown(
            "<div class='pill-card'>Tradução de juridiquês em palavras do dia a dia: "
            "<b>foro</b> (onde o processo corre), <b>LGPD</b> (como dados são usados), "
            "<b>rescisão</b> (como sair sem dor de cabeça).</div>", unsafe_allow_html=True,
        )
    with c3:
        st.markdown("#### 📈 CET")
        st.markdown(
            "<div class='pill-card'>Calcula o custo efetivo total (juros + taxas + tarifas) "
            "em contratos financeiros.</div>", unsafe_allow_html=True,
        )

    st.markdown("### Como funciona")
    st.markdown("1) Envie o PDF ou cole o texto do contrato.")
    st.markdown("2) Informe o contexto (setor, perfil e — se quiser — um valor).")
    st.markdown("3) Receba **trecho + explicação simples + sugestão de negociação**.")
    st.markdown("4) (Opcional) Calcule o **CET** para comparar propostas.")

    st.info(
        "A CLARA complementa a análise do seu contrato — "
        "pense nela como um **apoio** para triagem e preparo da negociação. "
        "Para decisões finais, conte também com um(a) advogado(a)."
    )

# ================================================================
# Stripe – card de preço e checkout
# ================================================================
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
            st.error(msgS)
            return
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
                st.error(sess.get("error", "Stripe indisponível no momento."))
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
        try:
            st.query_params.clear()
        except Exception:
            pass

# ================================================================
# Fluxo de análise
# ================================================================
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
    with st.expander("📚 Explicações rápidas (jurídico, em linguagem simples)", expanded=False):
        st.markdown("**Foro** → é a cidade/tribunal onde um processo corre. Se for muito longe, ficar caro se defender.")
        st.markdown("**LGPD** → lei que diz como seus dados podem ser coletados e usados. O contrato deve explicar o porquê, por quanto tempo e quem pode acessar.")
        st.markdown("**Rescisão** → como cada lado pode encerrar o contrato. Olhe prazos, multas, devoluções e se há “teto” para penalidades.")
        st.markdown("**Responsabilidade** → limite para perdas. Se não houver limite, você pode ficar exposto a valores muito altos.")
        st.markdown("**Reajuste** → quando e como o valor muda (índice, periodicidade, notificação).")

def results_section(text: str, ctx: Dict[str, Any]):
    st.subheader("4) Resultado")

    if not require_profile():
        st.info("Preencha e salve **nome, e-mail e celular** na barra lateral para liberar a análise.")
        return
    if not text.strip():
        st.warning("Envie o contrato (PDF) ou cole o texto.")
        return

    # Free x Premium
    if not is_premium() and st.session_state.free_runs_left <= 0:
        st.info("Você usou sua análise gratuita. **Assine o Premium** para continuar.")
        return

    with st.spinner("Analisando…"):
        hits, meta = analyze_contract_text(text, ctx)

    if not is_premium():
        st.session_state.free_runs_left -= 1

    # Log de uso + consulta CSV
    email = current_email()
    log_analysis_event(email=email, meta={"setor": ctx["setor"], "papel": ctx["papel"], "len": len(text)})
    log_consulta({
        "nome": st.session_state.profile.get("nome",""),
        "email": email,
        "cel": st.session_state.profile.get("cel",""),
        "papel": ctx["papel"], "setor": ctx["setor"],
        "valor_max": ctx["limite_valor"], "text_len": len(text),
        "premium": is_premium(),
    })

    resume = summarize_hits(hits)
    st.success(f"Resumo: {resume['resumo']}")
    st.write(
        f"Gravidade: **{resume['gravidade']}** | Pontos críticos: **{resume['criticos']}** | "
        f"Total identificados: {len(hits)}"
    )

    # Lista dos pontos com explicações enxutas
    for h in hits:
        with st.expander(f"{h['severity']} • {h['title']}"):
            # Tornar linguagem mais acessível
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

# ================================================================
# Orquestração
# ================================================================
def main():
    sidebar_profile()
    handle_checkout_result()

    # Cabeçalho fino
    st.markdown(
        f"<div class='cloud-badge'>{APP_TITLE} • {SUBTITLE} • {VERSION}</div>",
        unsafe_allow_html=True,
    )

    landing_hero()

    st.markdown('<div id="iniciar"></div>', unsafe_allow_html=True)
    st.markdown("")

    # CTA “Iniciar” (além do âncora do botão)
    if st.button("▶️ Iniciar análise do meu contrato", use_container_width=True):
        st.session_state.started = True

    st.markdown("---")

    # Coluna à direita: plano
    col1, col2 = st.columns([3,2])
    with col1:
        st.caption("Preencha seus dados na barra lateral antes de começar.")
        text = upload_or_paste_section() if st.session_state.started else ""
        ctx  = analysis_inputs() if st.session_state.started else {"setor":"Genérico","papel":"Contratante","limite_valor":0.0}

        if st.session_state.started and st.button("🚀 Rodar análise", use_container_width=True):
            results_section(text, ctx)
    with col2:
        pricing_card()

    st.markdown("---")
    st.markdown(
        "<p class='footnote'>"
        "No Brasil, \"li e concordo\" virou quase automático — e isso expõe empresas a riscos evitáveis. "
        "A CLARA ajuda você a entender o que está assinando com linguagem direta, "
        "mostrando onde negociar para reduzir custos e incertezas."
        "</p>",
        unsafe_allow_html=True,
    )

if __name__ == "__main__":
    main()




