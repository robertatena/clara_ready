# app.py
# CLARA • Análise de Contratos
# UI estilo iCloud • Stripe robusto • Admin com logs & export (CSV/XLSX) • Hotjar • Linguagem simples

from __future__ import annotations

import os
import io
import re
from typing import Dict, Any, Tuple, Set, List
from datetime import datetime
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

# --- módulos locais (mantenha seus arquivos como estão) ---
from app_modules.pdf_utils import extract_text_from_pdf
from app_modules.analysis import analyze_contract_text, summarize_hits, compute_cet_quick
from app_modules.stripe_utils import init_stripe, create_checkout_session, verify_checkout_session
from app_modules.storage import (
    init_db, log_analysis_event, log_subscriber, list_subscribers, get_subscriber_by_email
)

# =============================================================================
# Configurações & Constantes
# =============================================================================
APP_TITLE = "CLARA • Análise de Contratos"
VERSION   = "v15.0"

st.set_page_config(page_title=APP_TITLE, page_icon="📄", layout="wide")

STRIPE_PUBLIC_KEY = st.secrets.get("STRIPE_PUBLIC_KEY", os.getenv("STRIPE_PUBLIC_KEY", ""))
STRIPE_SECRET_KEY = st.secrets.get("STRIPE_SECRET_KEY", os.getenv("STRIPE_SECRET_KEY", ""))
STRIPE_PRICE_ID   = st.secrets.get("STRIPE_PRICE_ID",   os.getenv("STRIPE_PRICE_ID", ""))
BASE_URL          = st.secrets.get("BASE_URL",          os.getenv("BASE_URL", "https://claraready.streamlit.app"))
HOTJAR_ID         = st.secrets.get("HOTJAR_ID",         os.getenv("HOTJAR_ID", ""))  # opcional

MONTHLY_PRICE_TEXT = "R$ 9,90/mês"

# Arquivos de log (em container ephemeral do Streamlit Cloud)
VISITS_CSV    = Path("/tmp/visits.csv")
CONSULTS_CSV  = Path("/tmp/consultas.csv")

# =============================================================================
# Helpers de Log
# =============================================================================
def _ts() -> str:
    """Timestamp ISO8601 (UTC)."""
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"

def log_visit(email: str) -> None:
    """Registra visita (e-mail + quando) em /tmp/visits.csv."""
    email = (email or "").strip().lower()
    if not email:
        return
    VISITS_CSV.parent.mkdir(parents=True, exist_ok=True)
    header_needed = not VISITS_CSV.exists()
    with VISITS_CSV.open("a", encoding="utf-8") as f:
        if header_needed:
            f.write("ts,email\n")
        f.write(f"{_ts()},{email}\n")

def read_visits() -> List[Dict[str, str]]:
    if not VISITS_CSV.exists():
        return []
    rows: List[Dict[str, str]] = []
    with VISITS_CSV.open("r", encoding="utf-8") as f:
        next(f, None)  # header
        for line in f:
            ts, email = line.strip().split(",", 1)
            rows.append({"ts": ts, "email": email})
    return rows

def log_consult(
    *,
    nome: str,
    email: str,
    cel: str,
    papel: str,
    setor: str,
    valor_max: float | int | str,
    text_len: int,
    premium: bool,
    resumo: str
) -> None:
    """Registra uma análise em /tmp/consultas.csv (para admin & export)."""
    CONSULTS_CSV.parent.mkdir(parents=True, exist_ok=True)
    header_needed = not CONSULTS_CSV.exists()
    safe_resumo = (resumo or "").replace("\n", " ").replace("\r", " ")
    with CONSULTS_CSV.open("a", encoding="utf-8") as f:
        if header_needed:
            f.write(
                "ts,nome,email,cel,papel,setor,valor_max,text_len,premium,resumo\n"
            )
        f.write(
            f"{_ts()},{nome.strip()},{email.strip().lower()},{cel.strip()},{papel},"
            f"{setor},{valor_max},{text_len},{int(bool(premium))},{safe_resumo}\n"
        )

def read_consults() -> List[Dict[str, str]]:
    if not CONSULTS_CSV.exists():
        return []
    rows: List[Dict[str, str]] = []
    with CONSULTS_CSV.open("r", encoding="utf-8") as f:
        next(f, None)  # header
        for line in f:
            parts = line.rstrip("\n").split(",", 9)
            if len(parts) == 10:
                ts, nome, email, cel, papel, setor, valor_max, text_len, premium, resumo = parts
                rows.append({
                    "ts": ts, "nome": nome, "email": email, "cel": cel, "papel": papel,
                    "setor": setor, "valor_max": valor_max, "text_len": text_len,
                    "premium": premium, "resumo": resumo
                })
    return rows

# =============================================================================
# Admin e autenticação "leve"
# =============================================================================
def _parse_admin_emails() -> Set[str]:
    raw = st.secrets.get("admin_emails", None)
    if raw is None:
        raw = os.getenv("ADMIN_EMAILS", "")
    emails: Set[str] = set()
    if isinstance(raw, list):
        emails = {str(x).strip().lower() for x in raw if str(x).strip()}
    elif isinstance(raw, str):
        emails = {e.strip().lower() for e in raw.split(",") if e.strip()}
    return emails

ADMIN_EMAILS = _parse_admin_emails()

# =============================================================================
# CSS + Hotjar (UI inspirada em iCloud: gradientes suaves + glass cards)
# =============================================================================
st.markdown(
    """
    <style>
      :root {
        --bg1: #f6f7fb;
        --bg2: #ffffff;
        --primary: #1f4fff; /* azul Apple-like */
        --muted: #62666f;
        --glass: rgba(255,255,255,0.65);
        --glass-border: rgba(255,255,255,0.55);
      }
      /* background geral */
      .main .block-container {
        padding-top: 1.2rem;
      }
      body {
        background: radial-gradient(1200px 800px at 20% 5%, #eef2ff 0%, var(--bg1) 55%) fixed;
      }
      /* topbar simples */
      .topbar {
        position: sticky; top: 0; z-index: 1000;
        backdrop-filter: saturate(160%) blur(16px);
        background: linear-gradient(180deg, rgba(255,255,255,0.72) 0%, rgba(255,255,255,0.50) 100%);
        border-bottom: 1px solid rgba(255,255,255,0.6);
        padding: 10px 16px; border-radius: 0 0 14px 14px;
        margin-bottom: 14px;
      }
      .topbar h3 { margin: 0; font-weight: 600; letter-spacing: 0.2px; }
      .hero {
        padding: 24px; border-radius: 18px;
        background: linear-gradient(160deg, rgba(255,255,255,0.85) 0%, rgba(255,255,255,0.60) 100%);
        border: 1px solid var(--glass-border); margin-bottom: 18px;
        box-shadow: 0 6px 24px rgba(31,79,255,0.08);
        backdrop-filter: blur(10px) saturate(150%);
      }
      .pill {
        display:inline-block; padding:6px 12px; border-radius:999px;
        background:#eef2ff; border:1px solid #e3e6ff; font-size:12.5px; color:#3142c6;
      }
      .muted { color: var(--muted); }
      .card {
        border-radius: 16px; background: var(--glass);
        border: 1px solid var(--glass-border);
        padding: 18px; margin-bottom: 14px;
        box-shadow: 0 6px 18px rgba(31,79,255,0.06);
        backdrop-filter: blur(8px) saturate(140%);
      }
      .footer-note { font-size: 12.5px; color:#6e7480; }
      /* botões maiores */
      .stButton button {
        height: 44px; font-weight: 600; border-radius: 12px;
      }
      .stDownloadButton button {
        height: 44px; border-radius: 12px;
      }
      /* inputs arredondados */
      .stTextInput input, .stNumberInput input, .stSelectbox div[data-baseweb="select"] {
        border-radius: 10px !important;
      }
    </style>
    """,
    unsafe_allow_html=True,
)

def inject_hotjar():
    """Injeta o Hotjar se HOTJAR_ID estiver configurado."""
    if not HOTJAR_ID:
        return
    components.html(
        f"""
        <!-- Hotjar -->
        <script>
          (function(h,o,t,j,a,r){{
              h.hj=h.hj||function(){{(h.hj.q=h.hj.q||[]).push(arguments)}};
              h._hjSettings={{hjid:{HOTJAR_ID},hjsv:6}};
              a=o.getElementsByTagName('head')[0];
              r=o.createElement('script');r.async=1;
              r.src='https://static.hotjar.com/c/hotjar-'+h._hjSettings.hjid+'.js?sv='+h._hjSettings.hjsv;
              a.appendChild(r);
          }})(window,document,'https://static.hotjar.com/c/hotjar-','.js?sv=');
        </script>
        """,
        height=0,
    )

inject_hotjar()

# =============================================================================
# Estado inicial
# =============================================================================
if "profile" not in st.session_state:
    st.session_state.profile = {"nome": "", "email": "", "cel": "", "papel": "Contratante"}
if "premium" not in st.session_state:
    st.session_state.premium = False
if "free_runs_left" not in st.session_state:
    st.session_state.free_runs_left = 1  # 1 análise gratuita por e-mail
if "lang_level" not in st.session_state:
    st.session_state.lang_level = "Simples (recomendado)"  # seletor de linguagem

# =============================================================================
# Boot (Stripe + DB) com mensagens úteis
# =============================================================================
@st.cache_resource(show_spinner="Iniciando serviços…")
def _boot() -> Tuple[bool, str]:
    try:
        if not STRIPE_SECRET_KEY:
            return False, "Faltando STRIPE_SECRET_KEY (Settings → Secrets)."
        init_stripe(STRIPE_SECRET_KEY)
        init_db()
        return True, ""
    except Exception as e:
        return False, f"Falha ao iniciar serviços: {e}"

ok_boot, boot_msg = _boot()
st.markdown('<div class="topbar"><h3>CLARA</h3></div>', unsafe_allow_html=True)
if not ok_boot:
    st.error(boot_msg)
    st.stop()

# =============================================================================
# Linguagem simples (anti-juridiquês)
# =============================================================================
PLAIN_TERMS = {
    r"\bLGPD\b": "Lei de Proteção de Dados (regras de uso dos seus dados)",
    r"\bforo\b": "cidade/tribunal onde disputas vão ser julgadas",
    r"\bônus\b": "responsabilidade",
    r"\bmora\b": "atraso no pagamento",
    r"\bcess(a|ã)o de direitos\b": "transferência de direitos para outra parte",
    r"\brescis(ã|a)o\b": "encerrar o contrato",
    r"\bconfidencialidade\b": "dever de guardar segredo",
    r"\bindeniza(ç|c)ão\b": "pagar prejuízos",
    r"\bpenalidades?\b": "multas ou punições do contrato",
    r"\bforo de eleição\b": "local combinado para resolver brigas na justiça",
    r"\bencargos\b": "custos extras",
    r"\bônus da prova\b": "quem precisa provar na justiça",
}

def simplify_text_pt(text: str) -> str:
    """Troca juridiquês por explicações simples, mantendo sentido."""
    s = text or ""
    s = re.sub(r';\s*', '. ', s)
    for pat, repl in PLAIN_TERMS.items():
        s = re.sub(pat, repl, s, flags=re.IGNORECASE)
    s = re.sub(r"\b(in casu|destarte|outrossim|ex vi|ipso facto)\b", "", s, flags=re.IGNORECASE)
    s = re.sub(r"\s{2,}", " ", s).strip()
    return s

def one_line_summary(h: dict) -> str:
    title = (h.get("title") or "").strip()
    sev   = (h.get("severity") or "").strip()
    exp   = simplify_text_pt(h.get("explanation", ""))[:120]
    return f"[{sev}] {title}: {exp}..."

# =============================================================================
# Utilidades
# =============================================================================
def current_email() -> str:
    return (st.session_state.profile.get("email") or "").strip().lower()

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

def require_profile() -> bool:
    p = st.session_state.profile
    return bool((p.get("nome") or "").strip() and (p.get("email") or "").strip() and (p.get("cel") or "").strip())

def stripe_diagnostics() -> Tuple[bool, str]:
    miss = []
    if not STRIPE_PUBLIC_KEY: miss.append("STRIPE_PUBLIC_KEY")
    if not STRIPE_SECRET_KEY: miss.append("STRIPE_SECRET_KEY")
    if not STRIPE_PRICE_ID:   miss.append("STRIPE_PRICE_ID")
    if miss:
        return False, f"Configure os segredos ausentes: {', '.join(miss)}."
    if STRIPE_PRICE_ID.startswith("prod_"):
        return False, "Use um **price_...** (não **prod_...**). Crie um Preço e copie o ID **price_...**"
    if not STRIPE_PRICE_ID.startswith("price_"):
        return False, "O STRIPE_PRICE_ID parece inválido (deve começar com **price_...**)."
    return True, ""

# =============================================================================
# Sidebar: cadastro + admin
# =============================================================================
def sidebar_profile():
    st.sidebar.header("🔐 Seus dados (obrigatório)")
    with st.sidebar.container():
        nome  = st.text_input("Nome completo*", value=st.session_state.profile.get("nome", ""))
        email = st.text_input("E-mail*",        value=st.session_state.profile.get("email", ""))
        cel   = st.text_input("Celular*",       value=st.session_state.profile.get("cel", ""))
        papel = st.selectbox(
            "Você é o contratante?*",
            ["Contratante", "Contratado", "Outro"],
            index=["Contratante","Contratado","Outro"].index(st.session_state.profile.get("papel", "Contratante"))
        )

        if st.button("Salvar perfil", use_container_width=True):
            st.session_state.profile = {"nome": nome.strip(), "email": email.strip(), "cel": cel.strip(), "papel": papel}
            try:
                log_visit(email.strip())
            except Exception:
                pass
            # sobe premium se já for assinante
            try:
                if current_email() and get_subscriber_by_email(current_email()):
                    st.session_state.premium = True
            except Exception:
                pass
            st.success("Dados salvos!")

    st.sidebar.markdown("---")
    st.sidebar.subheader("Administração")
    if current_email() in ADMIN_EMAILS and st.sidebar.checkbox("Área administrativa"):
        st.sidebar.success("Admin ativo")

        # Assinantes (Stripe)
        try:
            subs = list_subscribers()
            with st.sidebar.expander("👥 Assinantes (Stripe)", expanded=False):
                st.write(subs if subs else "Nenhum assinante localizado ainda.")
        except Exception as e:
            st.sidebar.error(f"Não foi possível listar assinantes: {e}")

        # Últimas visitas
        try:
            visits = read_visits()
            with st.sidebar.expander("👣 Últimas visitas", expanded=False):
                if not visits:
                    st.write("Sem registros ainda.")
                else:
                    for v in visits[-50:][::-1]:  # 50 mais recentes
                        st.write(f"{v['ts']} — {v['email']}")
        except Exception as e:
            st.sidebar.error(f"Não foi possível ler visitas: {e}")

        # Últimas consultas + export
        try:
            consults = read_consults()
            with st.sidebar.expander("📄 Últimas consultas (logs)", expanded=True):
                if not consults:
                    st.write("Sem registros de consultas ainda.")
                else:
                    for c in consults[-100:][::-1]:  # 100 mais recentes
                        st.write(
                            f"{c['ts']} — {c['nome']} <{c['email']}> • {c['papel']} • "
                            f"{c['setor']} • R$ {c['valor_max']} • texto={c['text_len']} • "
                            f"premium={c['premium']} • {c['resumo']}"
                        )

                # downloads (CSV e, se possível, XLSX)
                if CONSULTS_CSV.exists():
                    st.download_button(
                        "⬇️ Baixar consultas (CSV)",
                        data=CONSULTS_CSV.read_bytes(),
                        file_name="consultas.csv",
                        mime="text/csv",
                        use_container_width=True,
                    )
                    try:
                        import pandas as pd
                        df = pd.read_csv(CONSULTS_CSV)
                        buf = io.BytesIO()
                        with pd.ExcelWriter(buf, engine="xlsxwriter") as writer:
                            df.to_excel(writer, index=False, sheet_name="consultas")
                        st.download_button(
                            "⬇️ Baixar consultas (Excel)",
                            data=buf.getvalue(),
                            file_name="consultas.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            use_container_width=True,
                        )
                    except Exception:
                        pass
        except Exception as e:
            st.sidebar.error(f"Não foi possível ler consultas: {e}")

# =============================================================================
# Landing: benefícios + preço + aviso legal (suave)
# =============================================================================
def pricing_card():
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown("#### Plano Premium")
    st.caption(f"{MONTHLY_PRICE_TEXT} • análises ilimitadas • suporte prioritário")

    okS, msgS = stripe_diagnostics()
    email = current_email()

    if not email:
        st.info("Informe e salve seu **nome, e-mail e celular** na barra lateral para assinar.")
        st.markdown('</div>', unsafe_allow_html=True)
        return

    if st.button("💳 Assinar Premium agora", use_container_width=True):
        if not okS:
            st.error(msgS)
        else:
            try:
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
                    st.error(sess.get("error", "Stripe indisponível no momento. Tente novamente."))
            except Exception as e:
                st.error(f"Stripe indisponível no momento. Detalhe: {e}")
    st.markdown('</div>', unsafe_allow_html=True)

def landing_block():
    st.markdown(
        f"""
        <div class="hero">
          <div class="pill">Nova versão • {VERSION}</div>
          <h1 style="margin:10px 0 6px 0;">{APP_TITLE}</h1>
          <p class="muted" style="margin:0;">
            Encontre cláusulas sensíveis, entenda riscos e saiba como negociar — em minutos.
          </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    c1, c2 = st.columns([1.25, 1])
    with c1:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown("### Por que usar a CLARA")
        st.markdown("• Destaca multas altas, travas de rescisão e responsabilidades exageradas")
        st.markdown("• Explica em linguagem simples e sugere **o que negociar**")
        st.markdown("• Calculadora de **CET – Custo Efetivo Total** (juros + tarifas + taxas)")
        st.markdown("• Relatório para compartilhar com seu time ou advogado(a)")
        with st.expander("O que é CET (Custo Efetivo Total)?"):
            st.write(
                "O **CET** é a taxa que representa **todo o custo** de um financiamento/parcelamento "
                "(juros + tarifas + seguros + outras cobranças). Ajuda a comparar propostas e enxergar "
                "o custo real além do “só juros”."
            )
        st.markdown("### Como funciona")
        st.markdown("1) Envie o PDF **ou** cole o texto do contrato")
        st.markdown("2) Selecione **setor**, **perfil** e (opcional) valor")
        st.markdown("3) Receba **trecho + explicação + plano de ação**")
        st.markdown("4) (Opcional) Calcule o **CET**")
        st.info("**Nota**: A CLARA é um apoio inteligente que **complementa** o trabalho de profissionais do Direito; "
                "não substitui orientação jurídica individual.")
        st.markdown('</div>', unsafe_allow_html=True)
    with c2:
        pricing_card()

# =============================================================================
# Stripe: retorno seguro
# =============================================================================
def handle_checkout_result():
    qs = st.query_params  # Streamlit 1.37+
    if qs.get("success") == "true" and qs.get("session_id"):
        session_id = qs["session_id"]
        try:
            ok, payload = verify_checkout_session(session_id)
        except Exception as e:
            st.error(f"Não foi possível confirmar o pagamento: {e}")
            ok, payload = False, {}

        if ok:
            email = current_email()
            try:
                log_subscriber(
                    email=email,
                    name=st.session_state.profile.get("nome", ""),
                    stripe_customer_id=(payload.get("customer")
                                        or (payload.get("subscription") or {}).get("customer")
                                        or ""),
                )
            except Exception:
                pass
            st.session_state.premium = True
            st.success("Pagamento confirmado! Premium liberado ✅")
        else:
            st.warning("Não conseguimos confirmar essa sessão de pagamento. Tente novamente.")
        try:
            st.query_params.clear()
        except Exception:
            pass

# =============================================================================
# Entrada (upload/texto) + Inputs + CET + Resultado
# =============================================================================
def upload_or_paste_section() -> str:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("1) Envie o contrato")
    file = st.file_uploader("PDF do contrato", type=["pdf"])
    raw_text = ""
    if file:
        with st.spinner("Lendo PDF…"):
            raw_text = extract_text_from_pdf(file)
    st.markdown("Ou cole o texto abaixo:")
    raw_text = st.text_area("Texto do contrato", height=220, value=raw_text or "")
    st.markdown('</div>', unsafe_allow_html=True)
    return raw_text

def analysis_inputs() -> Dict[str, Any]:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("2) Contexto")
    col1, col2, col3 = st.columns(3)
    setor = col1.selectbox("Setor", ["Genérico", "SaaS/Serviços", "Empréstimos", "Educação", "Plano de saúde"])
    papel = col2.selectbox("Perfil", ["Contratante", "Contratado", "Outro"])
    valor_max = col3.number_input("Valor máx. (opcional)", min_value=0.0, step=100.0)
    st.session_state.lang_level = st.radio(
        "Nível de linguagem",
        ["Simples (recomendado)", "Técnico"],
        index=0, horizontal=True
    )
    st.markdown('</div>', unsafe_allow_html=True)
    return {"setor": setor, "papel": papel, "limite_valor": valor_max}

def cet_calculator_block():
    st.markdown('<div class="card">', unsafe_allow_html=True)
    with st.expander("📈 Calculadora de CET (opcional)", expanded=False):
        col1, col2, col3 = st.columns(3)
        P   = col1.number_input("Valor principal (R$)", min_value=0.0, step=100.0, key="cet_p")
        i_m = col2.number_input("Juros mensais (%)", min_value=0.0, step=0.1, key="cet_i")
        n   = col3.number_input("Parcelas (n)", min_value=1, step=1, key="cet_n")
        fee = st.number_input("Taxas fixas totais (R$)", min_value=0.0, step=10.0, key="cet_fee")
        if st.button("Calcular CET", key="btn_calc_cet"):
            cet = compute_cet_quick(P, i_m / 100.0, int(n), fee)
            st.success(f"**CET aproximado:** {cet*100:.2f}% a.m.")
    st.markdown('</div>', unsafe_allow_html=True)

def results_section(text: str, ctx: Dict[str, Any]):
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("4) Resultado")

    if not require_profile():
        st.info("Preencha e salve **nome, e-mail e celular** na barra lateral para liberar a análise.")
        st.markdown('</div>', unsafe_allow_html=True)
        return
    if not text.strip():
        st.warning("Envie o contrato (PDF) ou cole o texto para analisar.")
        st.markdown('</div>', unsafe_allow_html=True)
        return

    # Free / Premium
    if not is_premium() and st.session_state.free_runs_left <= 0:
        st.info("Você usou sua análise gratuita. **Assine o Premium** para continuar.")
        st.markdown('</div>', unsafe_allow_html=True)
        return

    with st.spinner("Analisando…"):
        hits, _meta = analyze_contract_text(text, ctx)

    if not is_premium():
        st.session_state.free_runs_left -= 1

    # Log de uso (telemetria leve)
    email = current_email()
    log_analysis_event(email=email, meta={"setor": ctx["setor"], "papel": ctx["papel"], "len": len(text)})

    # Resumo + registro detalhado para admin
    resume = summarize_hits(hits)
    resumo_uma_linha = simplify_text_pt(resume.get("resumo", ""))
    st.success(f"Resumo em 1 frase: {resumo_uma_linha}")
    st.write(f"Gravidade: **{resume['gravidade']}** | Pontos críticos: **{resume['criticos']}** | Total identificados: {len(hits)}")

    try:
        log_consult(
            nome=st.session_state.profile.get("nome",""),
            email=email,
            cel=st.session_state.profile.get("cel",""),
            papel=ctx["papel"],
            setor=ctx["setor"],
            valor_max=ctx["limite_valor"],
            text_len=len(text),
            premium=is_premium(),
            resumo=resumo_uma_linha
        )
    except Exception:
        pass

    # Resumo rápido (1 linha por ponto)
    with st.expander("🧭 Resumo rápido (1 linha por ponto)", expanded=True):
        for h in hits[:5]:
            st.write("• " + one_line_summary(h))

    # Lista detalhada com linguagem simples vs técnica
    for h in hits:
        titulo = h.get("title", "Ponto de atenção")
        sev    = h.get("severity", "Médio")
        explic = h.get("explanation", "")
        sugest = h.get("suggestion", "")
        evid   = h.get("evidence", "")

        if st.session_state.get("lang_level") == "Simples (recomendado)":
            explic_s = simplify_text_pt(explic)
            sugest_s = simplify_text_pt(sugest) if sugest else ""
        else:
            explic_s = explic
            sugest_s = sugest

        with st.expander(f"{sev} • {titulo}", expanded=False):
            st.markdown("**O problema**")
            st.write(explic_s or "—")

            st.markdown("**O que isso significa pra você**")
            impacto = "Pode gerar custos inesperados, risco jurídico ou travar a rescisão do contrato."
            if re.search(r"mult(a|as)|penal", explic, flags=re.I):
                impacto = "Pode gerar multa alta se você atrasar ou quiser encerrar o contrato."
            elif re.search(r"foro|jurisdi", explic, flags=re.I):
                impacto = "Se houver disputa, você pode ter de ir a um tribunal longe da sua cidade."
            elif re.search(r"dado(s)? pessoais|LGPD", explic, flags=re.I):
                impacto = "Seus dados podem ser usados de forma ampla; há risco de descumprir a Lei de Proteção de Dados."
            st.write(simplify_text_pt(impacto))

            st.markdown("**O que fazer agora**")
            acao = sugest_s or "Peça para ajustar a cláusula, limitar responsabilidades e manter o foro na sua cidade."
            st.write(acao)

            if evid:
                with st.expander("📎 Trecho do contrato (evidência)"):
                    st.code(evid[:1200])

    st.markdown('</div>', unsafe_allow_html=True)

    cet_calculator_block()

    # Relatório (download .txt)
    st.markdown('<div class="card">', unsafe_allow_html=True)
    buff = io.StringIO()
    buff.write(f"{APP_TITLE} {VERSION}\n")
    buff.write(f"Usuário: {st.session_state.profile.get('nome')} <{email}>  •  Papel: {ctx['papel']}\n")
    buff.write(f"Setor: {ctx['setor']}  |  Valor máx.: {ctx['limite_valor']}\n\n")
    buff.write(f"Resumo: {resumo_uma_linha} (Gravidade: {resume['gravidade']})\n\n")
    buff.write("Pontos de atenção:\n")
    for h in hits:
        buff.write(f"- [{h['severity']}] {h['title']} — {simplify_text_pt(h.get('explanation',''))}\n")
        if h.get("suggestion"):
            buff.write(f"  Sugestão: {simplify_text_pt(h['suggestion'])}\n")
    st.download_button(
        "📥 Baixar relatório (txt)",
        data=buff.getvalue(),
        file_name="relatorio_clara.txt",
        mime="text/plain",
        use_container_width=True,
    )
    st.markdown('</div>', unsafe_allow_html=True)

# =============================================================================
# Orquestração
# =============================================================================
def main():
    sidebar_profile()
    handle_checkout_result()
    landing_block()

    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown("### Comece sua análise")
    st.caption("Preencha seus dados na barra lateral antes de enviar o contrato.")
    st.markdown('</div>', unsafe_allow_html=True)

    text = upload_or_paste_section()
    ctx  = analysis_inputs()

    st.markdown("")
    if st.button("🚀 Começar análise", use_container_width=True):
        results_section(text, ctx)

    st.markdown("---")
    st.markdown(
        '<p class="footer-note">A CLARA é um apoio inteligente que '
        '<b>complementa</b> o trabalho de profissionais do Direito; '
        'não substitui orientação jurídica individual.</p>',
        unsafe_allow_html=True
    )

if __name__ == "__main__":
    main()

