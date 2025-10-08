# app.py
# CLARA • Análise de Contratos
# UX profissional + Linguagem simples + Stripe + Hotjar + CSV de visitas/consultas

from __future__ import annotations

import os
import io
import re
import csv
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Tuple, Set, List

import streamlit as st

# ====== MÓDULOS LOCAIS (ajuste se os nomes no seu repo forem diferentes) ======
from app_modules.pdf_utils import extract_text_from_pdf
from app_modules.analysis import analyze_contract_text, summarize_hits, compute_cet_quick
from app_modules.stripe_utils import init_stripe, create_checkout_session, verify_checkout_session
from app_modules.storage import (
    init_db,
    log_analysis_event,
    log_subscriber,
    list_subscribers,
    get_subscriber_by_email,
)

# =========================
# CONFIG & CONSTANTES
# =========================
APP_TITLE = "CLARA • Análise de Contratos"
VERSION   = "v13.5"

st.set_page_config(page_title=APP_TITLE, page_icon="📄", layout="wide")

# Stripe (Secrets → fallback para env)
STRIPE_PUBLIC_KEY = st.secrets.get("STRIPE_PUBLIC_KEY", os.getenv("STRIPE_PUBLIC_KEY", ""))
STRIPE_SECRET_KEY = st.secrets.get("STRIPE_SECRET_KEY", os.getenv("STRIPE_SECRET_KEY", ""))
STRIPE_PRICE_ID   = st.secrets.get("STRIPE_PRICE_ID",   os.getenv("STRIPE_PRICE_ID", ""))
BASE_URL          = st.secrets.get("BASE_URL",          os.getenv("BASE_URL", "https://claraready.streamlit.app"))
MONTHLY_PRICE_TEXT = "R$ 9,90/mês"

# Admin (lista de e-mails)
def _parse_admin_emails() -> Set[str]:
    raw = st.secrets.get("admin_emails", None)
    if raw is None:
        raw = os.getenv("ADMIN_EMAILS", "")
    if isinstance(raw, list):
        return {str(x).strip().lower() for x in raw if str(x).strip()}
    if isinstance(raw, str):
        return {e.strip().lower() for e in raw.split(",") if e.strip()}
    return set()

ADMIN_EMAILS = _parse_admin_emails()

# Registros locais
VISITS_CSV       = Path("/tmp/visits.csv")
CONSULTAS_CSV    = Path("/tmp/consultas.csv")
VISITS_HEADER    = ["ts_utc", "ip", "nome", "email"]
CONSULTAS_HEADER = [
    "ts_utc","ip","nome","email","cel","papel","setor","limite_valor","tamanho_texto",
    "gravidade","criticos","total_pontos"
]

# Hotjar (opcional)
HOTJAR_HJID = st.secrets.get("HOTJAR_HJID", os.getenv("HOTJAR_HJID", ""))
HOTJAR_HJSV = st.secrets.get("HOTJAR_HJSV", os.getenv("HOTJAR_HJSV", ""))

# =========================
# ESTILO (inspirado em iCloud)
# =========================
st.markdown(
    """
    <style>
      :root {
        --bg: #0b0c10;
        --panel: #0f1116;
        --ink: #e8eaed;
        --ink-mute: #b7bdc7;
        --brand: #6aa6ff;
        --brand-2: #9b8cff;
        --stroke: #1b1f2a;
        --ok: #22c55e;
        --warn: #f59e0b;
      }
      .app-shell {
        background: radial-gradient(1200px 600px at 10% -10%, rgba(106,166,255,.18), transparent 50%),
                    radial-gradient(900px 500px at 90% -20%, rgba(155,140,255,.14), transparent 55%),
                    linear-gradient(180deg, #0b0c10 0%, #0b0c10 100%);
        padding: 12px 0 6px 0;
        border-bottom: 1px solid var(--stroke);
        margin-bottom: 12px;
      }
      .nav-bar {
        display:flex; align-items:center; gap:18px; padding: 8px 6px 0 6px;
      }
      .logo {
        background: linear-gradient(135deg, var(--brand), var(--brand-2));
        -webkit-background-clip:text; background-clip:text; color: transparent;
        font-weight: 800; letter-spacing:.2px; font-size: 22px;
      }
      .pill {
        color: var(--ink); background: rgba(255,255,255,.06);
        border: 1px solid var(--stroke); padding: 3px 10px; border-radius: 999px; font-size: 12px;
      }
      .hero {
        margin: 10px 0 6px 0; padding: 18px 20px; border-radius: 16px;
        background: linear-gradient(180deg, rgba(255,255,255,.03), rgba(255,255,255,.02));
        border: 1px solid var(--stroke);
      }
      .section-title { font-size: 20px; font-weight: 700; color: var(--ink); margin: 8px 0 6px; }
      .muted { color: var(--ink-mute); }
      .card {
        border:1px solid var(--stroke); border-radius:16px; padding:14px;
        background: rgba(255,255,255,.02);
      }
      .cta {
        border-radius:12px; border:1px solid var(--stroke);
        background: linear-gradient(180deg, rgba(255,255,255,.06), rgba(255,255,255,.03));
        padding: 12px; margin-top:4px;
      }
      .footer-note { font-size: 13px; color: var(--ink-mute); }
      .ok { color: var(--ok); }
      .warn { color: var(--warn); }
      /* streamlit defaults polidos */
      .stTextInput>div>div>input, textarea {
        background: rgba(255,255,255,.02)!important; color: var(--ink)!important;
      }
      .stSelectbox>div>div { background: rgba(255,255,255,.02)!important; color: var(--ink)!important; }
      .stDownloadButton, .stButton>button { border-radius:10px!important; }
    </style>
    <div class="app-shell">
      <div class="nav-bar">
        <div class="logo">CLARA</div>
        <span class="pill">Análise de contratos • {ver}</span>
      </div>
    </div>
    """.replace("{ver}", VERSION),
    unsafe_allow_html=True,
)

# Hotjar (injeta só se configurado)
if HOTJAR_HJID and HOTJAR_HJSV:
    st.markdown(
        f"""
        <!-- Hotjar -->
        <script>
        (function(h,o,t,j,a,r){{
            h.hj=h.hj||function(){{(h.hj.q=h.hj.q||[]).push(arguments)}};
            h._hjSettings={{hjid:{HOTJAR_HJID},hjsv:{HOTJAR_HJSV}}};
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
# ESTADO INICIAL
# =========================
if "profile" not in st.session_state:
    st.session_state.profile = {"nome": "", "email": "", "cel": "", "papel": "Contratante"}
if "premium" not in st.session_state:
    st.session_state.premium = False
if "free_runs_left" not in st.session_state:
    st.session_state.free_runs_left = 1

# =========================
# BOOT (Stripe + DB)
# =========================
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
st.write("🟢 Serviços prontos." if ok_boot else "⚠️ Erro ao iniciar.")
if not ok_boot:
    st.error(boot_msg)
    st.stop()

# =========================
# HELPERS
# =========================
def _ip() -> str:
    return st.session_state.get("_client_ip", "")

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

def ensure_csv(path: Path, header: List[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists() or path.stat().st_size == 0:
        with path.open("w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(header)

def log_visit() -> None:
    if not current_email():
        return
    ensure_csv(VISITS_CSV, VISITS_HEADER)
    with VISITS_CSV.open("a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow([datetime.utcnow().isoformat(), _ip(),
                                st.session_state.profile.get("nome",""), current_email()])

def log_consulta(ctx: Dict[str, Any], text_len: int, resumo: Dict[str, Any]) -> None:
    ensure_csv(CONSULTAS_CSV, CONSULTAS_HEADER)
    row = [
        datetime.utcnow().isoformat(),
        _ip(),
        st.session_state.profile.get("nome",""),
        current_email(),
        st.session_state.profile.get("cel",""),
        st.session_state.profile.get("papel",""),
        ctx.get("setor",""),
        ctx.get("limite_valor",""),
        text_len,
        resumo.get("gravidade",""),
        resumo.get("criticos",""),
        resumo.get("total", 0) if "total" in resumo else len(str(resumo.get("criticos","")).split(",")),
    ]
    with CONSULTAS_CSV.open("a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow(row)

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
        return False, "O STRIPE_PRICE_ID deve começar com **price_...**"
    return True, ""

# -------- Tradutor de juridiquês (substitui por linguagem simples) --------
GLOSSARIO = {
    r"\bforo\b": "cidade/tribunal onde o caso seria julgado",
    r"foro exclusivo": "regra que fixa uma única cidade/tribunal para qualquer disputa (pode encarecer sua defesa)",
    r"\blgpd\b": "Lei Geral de Proteção de Dados (regras para guardar/usar seus dados com segurança)",
    r"\bônus\b": "juros",
    r"\brescisão\b": "fim do contrato",
    r"\bresilição\b": "terminar o contrato sem motivo específico",
    r"\bcláusula penal\b": "multa",
    r"\bônus moratórios\b": "juros por atraso",
    r"\bexigibilidade\b": "quando a cobrança pode ser feita",
    r"\brevogação\b": "cancelamento",
}

def simplifica(texto: str) -> str:
    out = texto
    for padrao, claro in GLOSSARIO.items():
        out = re.sub(padrao, claro, out, flags=re.IGNORECASE)
    # tornar frases mais conversacionais
    out = out.replace("deverá", "precisa").replace("deverá ser", "precisa ser").replace("poderá", "pode")
    return out

# =========================
# SIDEBAR (perfil + admin)
# =========================
def sidebar_profile():
    st.sidebar.header("🔐 Seus dados (obrigatório)")
    nome  = st.sidebar.text_input("Nome completo*", value=st.session_state.profile.get("nome",""))
    email = st.sidebar.text_input("E-mail*",        value=st.session_state.profile.get("email",""))
    cel   = st.sidebar.text_input("Celular*",       value=st.session_state.profile.get("cel",""))
    papel = st.sidebar.selectbox(
        "Você é o contratante?*",
        ["Contratante","Contratado","Outro"],
        index=["Contratante","Contratado","Outro"].index(st.session_state.profile.get("papel","Contratante"))
    )
    if st.sidebar.button("Salvar perfil", use_container_width=True):
        st.session_state.profile = {"nome":nome.strip(), "email":email.strip(), "cel":cel.strip(), "papel":papel}
        try:
            log_visit()
        except Exception:
            pass
        try:
            if current_email() and get_subscriber_by_email(current_email()):
                st.session_state.premium = True
        except Exception:
            pass
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
                    st.write(subs if subs else "Nenhum assinante localizado ainda.")
            except Exception as e:
                st.sidebar.error(f"Assinantes: {e}")

            # Visitas
            try:
                ensure_csv(VISITS_CSV, VISITS_HEADER)
                with st.sidebar.expander("👣 Últimas visitas", expanded=False):
                    rows = VISITS_CSV.read_text(encoding="utf-8").splitlines()
                    if len(rows) <= 1:
                        st.write("Sem registros ainda.")
                    else:
                        for line in rows[-50:][::-1][:-1]:  # últimas 50 (exclui header por segurança)
                            parts = line.split(",")
                            if len(parts) >= 4:
                                ts, ip, nm, em = parts[:4]
                                st.write(f"{ts} — {em} ({nm}) {('• '+ip) if ip else ''}")
                    st.download_button(
                        "⬇️ Baixar visitas (CSV)",
                        data=VISITS_CSV.read_bytes(), file_name="visitas.csv",
                        mime="text/csv", use_container_width=True
                    )
            except Exception as e:
                st.sidebar.error(f"Visitas: {e}")

            # Consultas
            try:
                ensure_csv(CONSULTAS_CSV, CONSULTAS_HEADER)
                with st.sidebar.expander("📄 Consultas (últimas)", expanded=False):
                    rows = CONSULTAS_CSV.read_text(encoding="utf-8").splitlines()
                    if len(rows) <= 1:
                        st.write("Sem consultas ainda.")
                    else:
                        for line in rows[-50:][::-1]:
                            parts = line.split(",")
                            ts = parts[0] if parts else ""
                            em = parts[3] if len(parts) > 3 else ""
                            setor = parts[6] if len(parts) > 6 else ""
                            st.write(f"{ts} — {em} • {setor}")
                    st.download_button(
                        "⬇️ Baixar consultas (CSV)",
                        data=CONSULTAS_CSV.read_bytes(), file_name="consultas.csv",
                        mime="text/csv", use_container_width=True
                    )
            except Exception as e:
                st.sidebar.error(f"Consultas: {e}")

# =========================
# LANDING + PLANO
# =========================
def pricing_card():
    st.markdown('<div class="section-title">Plano Premium</div>', unsafe_allow_html=True)
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
                st.success("Sessão criada! Abra o checkout seguro abaixo.")
                st.link_button("👉 Abrir checkout seguro", sess["url"], use_container_width=True)
            else:
                st.error(sess.get("error", "Stripe indisponível no momento. Tente novamente."))
        except Exception as e:
            st.error(f"Stripe indisponível no momento. Detalhe: {e}")

def landing_block():
    st.markdown(
        """
        <div class="hero">
          <div class="section-title">Tudo o que importa no seu contrato — em linguagem simples</div>
          <div class="muted">A CLARA destaca riscos, explica o que significam e sugere como negociar. Rápido e direto ao ponto.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown('<div class="card">🛡️ <b>Proteção</b><br><span class="muted">Enxerga multas fora da realidade, travas e responsabilidades exageradas.</span></div>', unsafe_allow_html=True)
    with c2:
        st.markdown('<div class="card">🗣️ <b>Clareza</b><br><span class="muted">Tradução de juridiquês: “foro”, “LGPD”, “rescisão”… em termos comuns.</span></div>', unsafe_allow_html=True)
    with c3:
        st.markdown('<div class="card">📊 <b>CET</b><br><span class="muted">Calcula o custo efetivo total (juros + tarifas + taxas) em contratos financeiros.</span></div>', unsafe_allow_html=True)

    st.markdown("")
    st.markdown('<div class="section-title">Como funciona</div>', unsafe_allow_html=True)
    st.markdown(
        """
        1) Envie o PDF ou cole o texto do contrato  
        2) Informe o contexto (setor, perfil e opcionalmente um valor)  
        3) Receba: **trecho + explicação simples + sugestão de negociação**  
        4) (Opcional) Calcule o **CET**  
        """)
    st.info(
        "A CLARA **complementa** a análise do seu contrato, mas **não substitui** a orientação de um(a) advogado(a). "
        "Pense nela como um **apoio** para triagem e preparo da sua conversa/negociação."
    )

# =========================
# RETORNO DO STRIPE
# =========================
def handle_checkout_result():
    qs = st.query_params
    if qs.get("success") == "true" and qs.get("session_id"):
        session_id = qs["session_id"]
        try:
            ok, payload = verify_checkout_session(session_id)
        except Exception as e:
            st.error(f"Não foi possível confirmar o pagamento: {e}")
            ok, payload = False, {}

        if ok:
            try:
                log_subscriber(
                    email=current_email(),
                    name=st.session_state.profile.get("nome",""),
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

# =========================
# FLUXO DE ANÁLISE
# =========================
def upload_or_paste_section() -> str:
    st.markdown('<div class="section-title">1) Envie o contrato</div>', unsafe_allow_html=True)
    file = st.file_uploader("PDF do contrato", type=["pdf"])
    raw_text = ""
    if file:
        with st.spinner("Lendo PDF…"):
            raw_text = extract_text_from_pdf(file)
    st.markdown("Ou cole o texto abaixo:")
    raw_text = st.text_area("Texto do contrato", height=220, value=raw_text or "")
    return raw_text

def analysis_inputs() -> Dict[str, Any]:
    st.markdown('<div class="section-title">2) Contexto</div>', unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    setor = c1.selectbox("Setor", ["Genérico", "SaaS/Serviços", "Empréstimos", "Educação", "Plano de saúde"])
    papel = c2.selectbox("Perfil", ["Contratante", "Contratado", "Outro"])
    limite_valor = c3.number_input("Valor máx. (opcional)", min_value=0.0, step=100.0)
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

def results_section(text: str, ctx: Dict[str, Any]):
    st.markdown('<div class="section-title">4) Resultado</div>', unsafe_allow_html=True)

    if not require_profile():
        st.info("Preencha e salve **nome, e-mail e celular** na barra lateral para liberar a análise.")
        return

    if not text.strip():
        st.warning("Envie o contrato (PDF) ou cole o texto para analisar.")
        return

    if not is_premium() and st.session_state.free_runs_left <= 0:
        st.info("Você utilizou sua análise gratuita. **Assine o Premium** para continuar.")
        return

    with st.spinner("Analisando…"):
        hits, _meta = analyze_contract_text(text, ctx)

    if not is_premium():
        st.session_state.free_runs_left -= 1

    try:
        log_analysis_event(email=current_email(), meta={"setor":ctx["setor"], "papel":ctx["papel"], "len":len(text)})
    except Exception:
        pass

    # Resumo + simplificação de linguagem
    for h in hits:
        h["title"] = simplifica(h["title"])
        h["explanation"] = simplifica(h["explanation"])
        if h.get("suggestion"):
            h["suggestion"] = simplifica(h["suggestion"])

    resumo = summarize_hits(hits)  # {"resumo","gravidade","criticos"}
    resumo["total"] = len(hits)

    # Resumo rápido (cards)
    st.markdown(
        f"""
        <div class="card">
          <b>Resumo</b><br>
          <span class="muted">{simplifica(resumo['resumo'])}</span><br>
          Gravidade: <b>{resumo['gravidade']}</b> • Pontos críticos: <b>{resumo['criticos']}</b> • Total: <b>{len(hits)}</b>
        </div>
        """, unsafe_allow_html=True
    )

    # Itens detalhados (sem aninhar expander)
    for h in hits:
        with st.expander(f"{h['severity']} • {h['title']}", expanded=False):
            st.write(h["explanation"])
            if h.get("suggestion"):
                st.markdown(f"**Como agir:** {h['suggestion']}")
            evidence = h.get("evidence")
            if evidence:
                st.code(evidence[:1200])

    cet_calculator_block()

    # Relatório simples
    buff = io.StringIO()
    buff.write(f"{APP_TITLE} {VERSION}\n")
    buff.write(f"Usuário: {st.session_state.profile.get('nome')} <{current_email()}>  •  Papel: {ctx['papel']}\n")
    buff.write(f"Setor: {ctx['setor']}  |  Valor máx.: {ctx['limite_valor']}\n\n")
    buff.write(f"Resumo: {simplifica(resumo['resumo'])} (Gravidade: {resumo['gravidade']})\n\n")
    buff.write("Pontos de atenção:\n")
    for h in hits:
        buff.write(f"- [{h['severity']}] {h['title']} — {h['explanation']}\n")
        if h.get("suggestion"):
            buff.write(f"  Como agir: {h['suggestion']}\n")

    st.download_button("📥 Baixar relatório (txt)", data=buff.getvalue(),
                       file_name="relatorio_clara.txt", mime="text/plain",
                       use_container_width=True)

    # Registro no CSV de consultas
    try:
        log_consulta(ctx=ctx, text_len=len(text), resumo=resumo)
    except Exception:
        pass

# =========================
# ORQUESTRAÇÃO
# =========================
def pricing_section():
    st.markdown('<div class="section-title">Plano Premium</div>', unsafe_allow_html=True)
    pricing_card()

def main():
    sidebar_profile()
    handle_checkout_result()
    landing_block()

    st.markdown("---")
    text = upload_or_paste_section()
    ctx  = analysis_inputs()

    cta_col1, cta_col2 = st.columns([1,1])
    with cta_col1:
        if st.button("🚀 Começar análise", use_container_width=True):
            results_section(text, ctx)
    with cta_col2:
        pricing_section()

    st.markdown("---")
    st.markdown(
        '<p class="footer-note">A CLARA ajuda você a entender o contrato e preparar a negociação, '
        'mas <b>não substitui</b> a orientação de um(a) advogado(a).</p>',
        unsafe_allow_html=True
    )

if __name__ == "__main__":
    main()


