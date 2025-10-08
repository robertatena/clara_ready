# app.py — CLARA • Análise de Contratos
# UX clean (tela inicial), linguagem simples, Stripe, logs CSV (visitas/consultas),
# Hotjar, admin, calculadora CET e relatório.

import os
import io
import csv
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Tuple, Set, List

import streamlit as st

# ---- seus módulos locais (mantém como estão no projeto) ----
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

# -------------------------------------------------
# Configs gerais
# -------------------------------------------------
APP_TITLE = "CLARA • Análise de Contratos"
VERSION = "v13.6"

st.set_page_config(page_title=APP_TITLE, page_icon="📄", layout="wide")

# Secrets / env
STRIPE_PUBLIC_KEY = st.secrets.get("STRIPE_PUBLIC_KEY", os.getenv("STRIPE_PUBLIC_KEY", ""))
STRIPE_SECRET_KEY = st.secrets.get("STRIPE_SECRET_KEY", os.getenv("STRIPE_SECRET_KEY", ""))
STRIPE_PRICE_ID   = st.secrets.get("STRIPE_PRICE_ID",   os.getenv("STRIPE_PRICE_ID", ""))
BASE_URL          = st.secrets.get("BASE_URL",          os.getenv("BASE_URL", "https://claraready.streamlit.app"))
MONTHLY_PRICE_TEXT = "R$ 9,90/mês"

# Hotjar (do seu screenshot)
HOTJAR_ID = 6519667
HOTJAR_SV = 6

# CSV paths (em /tmp para rodar no Streamlit Cloud)
VISITS_CSV  = Path("/tmp/visitas.csv")
CONSULT_CSV = Path("/tmp/consultas.csv")

# -------------------------------------------------
# Estilo simples (claro, sem preto chapado)
# -------------------------------------------------
st.markdown(
    """
    <style>
      :root { --text:#0f172a; --muted:#475569; --pill:#eef2ff; --line:#e5e7eb; }
      .hero-wrap{padding:5rem 1rem 2.5rem; text-align:center;}
      .hero-title{font-size:56px; font-weight:800; letter-spacing:.5px; color:var(--text);}
      .hero-p{max-width:940px; margin:14px auto 0; font-size:20px; color:var(--muted); line-height:1.6}
      .pill{display:inline-block;background:var(--pill); border:1px solid #e0e7ff; padding:4px 10px; border-radius:999px; font-size:12.5px; color:#334155;}
      .card{border:1px solid var(--line); border-radius:16px; padding:16px 18px; background:#ffffff}
      .soft {font-size:13px; color:#64748b;}
      .section-title{font-size:22px; font-weight:700; margin:8px 0 6px;}
    </style>
    """,
    unsafe_allow_html=True,
)

# -------------------------------------------------
# Estado inicial
# -------------------------------------------------
if "started" not in st.session_state:
    st.session_state.started = False
if "profile" not in st.session_state:
    st.session_state.profile = {"nome": "", "email": "", "cel": "", "papel": "Contratante"}
if "premium" not in st.session_state:
    st.session_state.premium = False
if "free_runs_left" not in st.session_state:
    st.session_state.free_runs_left = 1  # 1 análise gratuita por e-mail nesta sessão

# -------------------------------------------------
# Utilidades / Admin
# -------------------------------------------------
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
        if get_subscriber_by_email(email):
            st.session_state.premium = True
            return True
    except Exception:
        pass
    return False

def stripe_diagnostics() -> Tuple[bool, str]:
    miss = []
    if not STRIPE_PUBLIC_KEY: miss.append("STRIPE_PUBLIC_KEY")
    if not STRIPE_SECRET_KEY: miss.append("STRIPE_SECRET_KEY")
    if not STRIPE_PRICE_ID:   miss.append("STRIPE_PRICE_ID")
    if miss:
        return False, f"Configure os segredos ausentes: {', '.join(miss)}."
    if STRIPE_PRICE_ID.startswith("prod_"):
        return False, "Use um **price_...** (não **prod_...**). No Stripe crie um Preço e copie o ID **price_...**"
    if not STRIPE_PRICE_ID.startswith("price_"):
        return False, "O STRIPE_PRICE_ID parece inválido. Deve começar com **price_...**"
    return True, ""

# -------------------------------------------------
# Hotjar
# -------------------------------------------------
def inject_hotjar(hjid: int = HOTJAR_ID, hjsv: int = HOTJAR_SV):
    st.markdown(
        f"""
        <script>
          (function(h,o,t,j,a,r){{
              h.hj=h.hj||function(){{(h.hj.q=h.hj.q||[]).push(arguments)}};
              h._hjSettings={{hjid:{hjid},hjsv:{hjsv}}};
              a=o.getElementsByTagName('head')[0];
              r=o.createElement('script');r.async=1;
              r.src='https://static.hotjar.com/c/hotjar-'+h._hjSettings.hjid+'.js?sv='+h._hjSettings.hjsv;
              a.appendChild(r);
          }})(window,document,'https://static.hotjar.com/c/hotjar-','.js?sv=');
        </script>
        """,
        unsafe_allow_html=True,
    )

# -------------------------------------------------
# CSV helpers (visitas / consultas)
# -------------------------------------------------
def _ensure_csv(path: Path, header: List[str]):
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(header)

def log_visit(email: str):
    if not (email or "").strip():
        return
    _ensure_csv(VISITS_CSV, ["ts_utc", "email"])
    with VISITS_CSV.open("a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow([datetime.utcnow().isoformat(), email.strip().lower()])

def read_visits() -> List[Dict[str, str]]:
    if not VISITS_CSV.exists():
        return []
    rows: List[Dict[str, str]] = []
    with VISITS_CSV.open("r", encoding="utf-8") as f:
        for i, row in enumerate(csv.DictReader(f)):
            rows.append(row)
    return rows

def log_consultation(payload: Dict[str, Any]):
    header = ["ts_utc","nome","email","cel","papel","setor","valor_max","texto_len"]
    _ensure_csv(CONSULT_CSV, header)
    rec = [
        datetime.utcnow().isoformat(),
        st.session_state.profile.get("nome",""),
        st.session_state.profile.get("email",""),
        st.session_state.profile.get("cel",""),
        st.session_state.profile.get("papel",""),
        payload.get("setor",""),
        payload.get("valor_max",""),
        payload.get("texto_len",""),
    ]
    with CONSULT_CSV.open("a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow(rec)

def serve_csv_downloads():
    # Exibe botões para baixar os CSVs
    if VISITS_CSV.exists():
        with VISITS_CSV.open("rb") as f:
            st.download_button("📥 Baixar visitas (CSV)", f, file_name="visitas.csv", mime="text/csv")
    if CONSULT_CSV.exists():
        with CONSULT_CSV.open("rb") as f:
            st.download_button("📥 Baixar consultas (CSV)", f, file_name="consultas.csv", mime="text/csv")

# -------------------------------------------------
# Boot (Stripe + DB)
# -------------------------------------------------
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
if not ok_boot:
    st.error(boot_msg)
    st.stop()

# -------------------------------------------------
# TELA 1 — Home clean com CTA único
# -------------------------------------------------
def first_screen():
    inject_hotjar()  # métrica já na primeira visita
    st.markdown('<div class="hero-wrap">', unsafe_allow_html=True)
    st.markdown(f'<div class="pill">Nova versão • {VERSION}</div>', unsafe_allow_html=True)
    st.markdown('<div class="hero-title">CLARA</div>', unsafe_allow_html=True)
    st.markdown(
        """
        <p class="hero-p">
          Entenda seu contrato em linguagem simples. A CLARA encontra riscos, traduz “juridiquês”
          (como <b>foro</b>, <b>LGPD</b>, <b>rescisão</b>) e sugere caminhos de negociação — rápido e direto ao ponto.
        </p>
        """,
        unsafe_allow_html=True,
    )

    # CTA
    clicked = st.button("Iniciar análise do meu contrato", use_container_width=True)
    if clicked:
        st.session_state.started = True
        # limpa caches atuais (se houver)
        try: st.cache_data.clear()
        except Exception: pass
        try: st.cache_resource.clear()
        except Exception: pass
        st.rerun()

    # Educação curta e suave (sem “tom duro”)
    st.markdown(
        """
        <div style="max-width:980px; margin:28px auto 0; color:#475569;">
          <p><b>Milhões de brasileiros</b> assinam documentos legais sem entender completamente o que estão aceitando,
          colocando negócios e patrimônio em risco desnecessário.</p>
          <p>A frase <i>“Eu li e concordo com os termos e condições”</i> virou símbolo dessa rotina. A CLARA ajuda você a
          ganhar clareza antes de assinar — como um <b>apoio</b> para conversar e negociar melhor (ela não substitui um(a) advogado(a)).</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown("</div>", unsafe_allow_html=True)

# -------------------------------------------------
# Sidebar — cadastro + admin
# -------------------------------------------------
def sidebar_profile():
    st.sidebar.header("🔐 Seus dados (obrigatório)")
    nome  = st.sidebar.text_input("Nome completo*", value=st.session_state.profile.get("nome",""))
    email = st.sidebar.text_input("E-mail*",        value=st.session_state.profile.get("email",""))
    cel   = st.sidebar.text_input("Celular*",       value=st.session_state.profile.get("cel",""))
    papel = st.sidebar.selectbox("Você é o contratante?*", ["Contratante","Contratado","Outro"],
                                 index=["Contratante","Contratado","Outro"].index(st.session_state.profile.get("papel","Contratante")))

    if st.sidebar.button("Salvar perfil", use_container_width=True):
        st.session_state.profile = {"nome":nome.strip(),"email":email.strip(),"cel":cel.strip(),"papel":papel}
        # log de visita
        try: log_visit(email.strip())
        except Exception: pass
        # se já for assinante, sobe premium
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
            try:
                subs = list_subscribers()
                with st.sidebar.expander("👥 Assinantes (Stripe)", expanded=False):
                    st.write(subs if subs else "Nenhum assinante ainda.")
            except Exception as e:
                st.sidebar.error(f"Não foi possível listar assinantes: {e}")

            try:
                visits = read_visits()
                with st.sidebar.expander("👣 Últimas visitas", expanded=False):
                    if not visits:
                        st.write("Sem registros.")
                    else:
                        for v in reversed(visits[-50:]):
                            st.write(f"{v.get('ts_utc','')} — {v.get('email','')}")
            except Exception as e:
                st.sidebar.error(f"Não foi possível ler visitas: {e}")

            with st.sidebar.expander("📦 Exportar CSV", expanded=False):
                serve_csv_downloads()

# -------------------------------------------------
# Sessão de preço / Stripe
# -------------------------------------------------
def pricing_card():
    st.markdown('<div class="section-title">Plano Premium</div>', unsafe_allow_html=True)
    st.caption(f"{MONTHLY_PRICE_TEXT} • análises ilimitadas • suporte prioritário")

    okS, msgS = stripe_diagnostics()
    email = current_email()

    if not email:
        st.info("Preencha e salve seu **nome, e-mail e celular** na barra lateral para assinar.")
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
                st.success("Sessão criada! Clique abaixo para abrir o checkout seguro.")
                st.link_button("👉 Abrir checkout seguro", sess["url"], use_container_width=True)
            else:
                st.error(sess.get("error", "Stripe indisponível no momento."))
        except Exception as e:
            st.error(f"Stripe indisponível no momento. Detalhe: {e}")

def handle_checkout_result():
    qs = st.query_params
    if qs.get("success") == "true" and qs.get("session_id"):
        sid = qs["session_id"]
        try:
            ok, payload = verify_checkout_session(sid)
        except Exception as e:
            st.error(f"Não foi possível confirmar o pagamento: {e}")
            ok, payload = False, {}

        if ok:
            try:
                log_subscriber(
                    email=current_email(),
                    name=st.session_state.profile.get("nome",""),
                    stripe_customer_id=(payload.get("customer") or (payload.get("subscription") or {}).get("customer") or "")
                )
            except Exception:
                pass
            st.session_state.premium = True
            st.success("Pagamento confirmado! Premium liberado ✅")
        else:
            st.warning("Não conseguimos confirmar essa sessão. Tente novamente.")
        try: st.query_params.clear()
        except Exception: pass

# -------------------------------------------------
# Seção educativa + preço (após cadastro)
# -------------------------------------------------
def landing_block():
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown("### Tudo o que importa no seu contrato — em linguagem simples")
    st.write(
        "A CLARA destaca riscos, explica o que significam e sugere como negociar. "
        "Direto ao ponto, sem juridiquês."
    )
    cols = st.columns(3)
    with cols[0]:
        st.markdown("**🛡️ Proteção**")
        st.write("Enxerga multas fora da realidade, travas de rescisão e responsabilidades exageradas.")
    with cols[1]:
        st.markdown("**📚 Clareza**")
        st.write("Traduz termos como **foro** (onde o processo corre), **LGPD** (dados pessoais) e **rescisão**.")
    with cols[2]:
        st.markdown("**📈 CET**")
        st.write("Calcula o custo efetivo total (juros + tarifas + taxas) em contratos financeiros.")
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("")
    pricing_card()

# -------------------------------------------------
# Upload / Inputs / CET / Resultado
# -------------------------------------------------
def upload_or_paste_section() -> str:
    st.subheader("1) Envie o contrato")
    f = st.file_uploader("PDF do contrato", type=["pdf"])
    raw = ""
    if f:
        with st.spinner("Lendo PDF…"):
            raw = extract_text_from_pdf(f)
    st.markdown("Ou cole o texto abaixo:")
    raw = st.text_area("Texto do contrato", height=220, value=raw or "")
    return raw

def analysis_inputs() -> Dict[str, Any]:
    st.subheader("2) Contexto")
    c1, c2, c3 = st.columns(3)
    setor = c1.selectbox("Setor", ["Genérico","SaaS/Serviços","Empréstimos","Educação","Plano de saúde"])
    papel = c2.selectbox("Perfil", ["Contratante","Contratado","Outro"])
    valor = c3.number_input("Valor máx. (opcional)", min_value=0.0, step=100.0)
    return {"setor":setor, "papel":papel, "limite_valor":valor}

def cet_calculator_block():
    with st.expander("📈 Calculadora de CET (opcional)", expanded=False):
        c1,c2,c3 = st.columns(3)
        P   = c1.number_input("Valor principal (R$)", min_value=0.0, step=100.0, key="cet_p")
        i_m = c2.number_input("Juros mensais (%)", min_value=0.0, step=0.1, key="cet_i")
        n   = c3.number_input("Parcelas (n)", min_value=1, step=1, key="cet_n")
        fee = st.number_input("Taxas fixas totais (R$)", min_value=0.0, step=10.0, key="cet_fee")
        if st.button("Calcular CET", key="btn_calc_cet"):
            cet = compute_cet_quick(P, i_m/100.0, int(n), fee)
            st.success(f"**CET aproximado:** {cet*100:.2f}% a.m.")

def results_section(text: str, ctx: Dict[str, Any]):
    st.subheader("4) Resultado")

    if not require_profile():
        st.info("Preencha e salve **nome, e-mail e celular** na barra lateral para liberar a análise.")
        return
    if not text.strip():
        st.warning("Envie o contrato (PDF) ou cole o texto para analisar.")
        return

    # Cota free
    if not is_premium() and st.session_state.free_runs_left <= 0:
        st.info("Você usou sua análise gratuita. **Assine o Premium** para continuar.")
        return

    with st.spinner("Analisando…"):
        hits, meta = analyze_contract_text(text, ctx)

    if not is_premium():
        st.session_state.free_runs_left -= 1

    # log técnico e CSV
    email = current_email()
    log_analysis_event(email=email, meta={"setor":ctx["setor"], "papel":ctx["papel"], "len":len(text)})
    log_consultation({"setor":ctx["setor"], "valor_max":ctx["limite_valor"], "texto_len":len(text)})

    resume = summarize_hits(hits)
    st.success(f"Resumo rápido: {resume['resumo']}")
    st.write(f"Gravidade: **{resume['gravidade']}** | Pontos críticos: **{resume['criticos']}** | Total identificados: {len(hits)}")

    # Explicações simples por ponto
    for h in hits:
        with st.expander(f"{h['severity']} • {h['title']}", expanded=False):
            # linguagem simples extra
            st.write(h["explanation"])
            dica = h.get("suggestion")
            if dica:
                st.markdown(f"**Como negociar:** {dica}")
            evid = h.get("evidence")
            if evid:
                st.code(evid[:1200])

    cet_calculator_block()

    # Relatório .txt
    buff = io.StringIO()
    buff.write(f"{APP_TITLE} {VERSION}\n")
    buff.write(f"Usuário: {st.session_state.profile.get('nome')} <{email}>  •  Papel: {ctx['papel']}\n")
    buff.write(f"Setor: {ctx['setor']}  |  Valor máx.: {ctx['limite_valor']}\n\n")
    buff.write(f"Resumo: {resume['resumo']} (Gravidade: {resume['gravidade']})\n\n")
    buff.write("Pontos de atenção:\n")
    for h in hits:
        buff.write(f"- [{h['severity']}] {h['title']} — {h['explanation']}\n")
        if h.get("suggestion"):
            buff.write(f"  Como negociar: {h['suggestion']}\n")
    st.download_button("📥 Baixar relatório (txt)", data=buff.getvalue(),
                       file_name="relatorio_clara.txt", mime="text/plain")

# -------------------------------------------------
# Orquestração
# -------------------------------------------------
def main():
    if not st.session_state.started:
        first_screen()
        return

    # a partir daqui é o fluxo completo
    sidebar_profile()
    handle_checkout_result()
    landing_block()

    st.markdown("---")
    st.markdown("### Comece sua análise")
    st.caption("Preencha seus dados na barra lateral e envie o contrato.")

    texto = upload_or_paste_section()
    ctx   = analysis_inputs()

    if st.button("🚀 Começar análise", use_container_width=True):
        results_section(texto, ctx)

    st.markdown("---")
    st.markdown(
        '<p class="soft">A CLARA complementa a leitura do seu contrato e ajuda na conversa e negociação, '
        'mas não substitui a orientação de um(a) advogado(a).</p>',
        unsafe_allow_html=True
    )

if __name__ == "__main__":
    main()
