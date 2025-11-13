# app.py — CLARA • Análise de Contratos (single‑page, UX refinada)
# Home clean & alinhada + linguagem simples + Stripe + CET + logs CSV + Hotjar + Admin
# Mantém TODAS as funcionalidades e incorpora o feedback do usuário

import os
import io
import re
import csv
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Tuple, Set, List

import streamlit as st

# ---- módulos locais (mantêm sua estrutura) ----
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
# Configs
# -------------------------------------------------
APP_TITLE = "CLARA • Análise de Contratos"
VERSION = "v15.0"

st.set_page_config(page_title=APP_TITLE, page_icon="📄", layout="wide")

# Secrets / env
STRIPE_PUBLIC_KEY = st.secrets.get("STRIPE_PUBLIC_KEY", os.getenv("STRIPE_PUBLIC_KEY", ""))
STRIPE_SECRET_KEY = st.secrets.get("STRIPE_SECRET_KEY", os.getenv("STRIPE_SECRET_KEY", ""))
STRIPE_PRICE_ID   = st.secrets.get("STRIPE_PRICE_ID",   os.getenv("STRIPE_PRICE_ID", ""))
BASE_URL          = st.secrets.get("BASE_URL",          os.getenv("BASE_URL", "https://claraready.streamlit.app"))

MONTHLY_PRICE_TEXT = "R$ 9,90/mês"

# Hotjar
HOTJAR_ID = 6519667
HOTJAR_SV = 6

# CSVs
VISITS_CSV  = Path("/tmp/visitas.csv")
CONSULT_CSV = Path("/tmp/consultas.csv")

# -------------------------------------------------
# Estilo: home impecável, centralizada e responsiva
# -------------------------------------------------
st.markdown(
    """
    <style>
      :root{
        --text:#0f172a; --muted:#475569; --line:#e5e7eb;
        --brand:#4f46e5; --brand2:#6366f1; --bg:#f8fafc; --card:#ffffff;
      }

      .page-hero{
        background:
          radial-gradient(1200px 500px at 50% -150px, #eef2ff 20%, #fff 60%, #fff 100%);
        padding: 32px 0 6px;
      }
      .wrap{ max-width: 1120px; margin: 0 auto; padding: 0 24px; }
      .chip{ display:inline-block; padding:6px 12px; border-radius:999px;
        background:#eef2ff; border:1px solid #e0e7ff; color:#334155; font-weight:600; font-size:12.5px; }
      .title{ margin: 18px 0 8px; font-size: clamp(34px, 6vw, 58px);
        font-weight: 800; color: var(--text); letter-spacing:.3px; line-height:1.06; }
      .subtitle{ max-width: 900px; font-size: 19px; line-height: 1.7; color: var(--muted); margin: 0 0 18px; }

      .hero-cta .stButton > button{
        background: linear-gradient(90deg, var(--brand), var(--brand2));
        color: #fff; border: 0; border-radius: 14px; padding: 14px 22px;
        font-weight: 700; font-size: 17px; box-shadow: 0 8px 24px rgba(79,70,229,.18);
      }
      .hero-cta .stButton > button:hover{ filter: brightness(1.03); }

      .pitch{ color:var(--muted); line-height:1.75; font-size:16px; }

      .cards{ display:grid; gap:16px; grid-template-columns: repeat(3, minmax(0, 1fr)); }
      @media (max-width: 980px){ .cards{ grid-template-columns: 1fr; } }
      .card{ background:var(--card); border:1px solid var(--line); border-radius:16px; padding:18px; }
      .card h4{ margin:4px 0 6px; font-size:18px; color:var(--text);} .card p{ margin:0; color:var(--muted); font-size:15.5px;}

      .section{ background:#fff; border:1px solid var(--line); border-radius:16px; padding:18px; }
      .soft{ font-size:13px; color:#64748b; }

      /* evita scroll horizontal em expander */
      .no-overflow div[role="region"]{ overflow-x: hidden !important; }
    </style>
    """,
    unsafe_allow_html=True,
)

# -------------------------------------------------
# Estado
# -------------------------------------------------
if "started" not in st.session_state:
    st.session_state.started = False
if "profile" not in st.session_state:
    st.session_state.profile = {"nome": "", "email": "", "cel": "", "papel": "Contratante"}
if "premium" not in st.session_state:
    st.session_state.premium = False
if "free_runs_left" not in st.session_state:
    st.session_state.free_runs_left = 1

# -------------------------------------------------
# Utils / Admin / Validações
# -------------------------------------------------
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
PHONE_RE = re.compile(r"^\+?\d{10,15}$")

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

def is_valid_email(v: str) -> bool:
    return bool(EMAIL_RE.match((v or "").strip()))

def is_valid_phone(v: str) -> bool:
    digits = re.sub(r"\D", "", v or "")
    return bool(PHONE_RE.match(digits))

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
    if miss: return False, f"Configure os segredos: {', '.join(miss)}."
    if STRIPE_PRICE_ID.startswith("prod_"): return False, "Use um **price_...** (não **prod_...**)."
    if not STRIPE_PRICE_ID.startswith("price_"): return False, "O STRIPE_PRICE_ID deve começar com **price_...**"
    return True, ""

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

# ---- CSV helpers ----
def _ensure_csv(path: Path, header: List[str]):
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(header)

def log_visit(email: str):
    if not (email or "").strip():
        return
    _ensure_csv(VISITS_CSV, ["ts_utc","email"])
    with VISITS_CSV.open("a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow([datetime.utcnow().isoformat(), email.strip().lower()])

def read_visits() -> List[Dict[str, str]]:
    if not VISITS_CSV.exists():
        return []
    with VISITS_CSV.open("r", encoding="utf-8") as f:
        return list(csv.DictReader(f))

def log_consultation(payload: Dict[str, Any]):
    _ensure_csv(CONSULT_CSV, ["ts_utc","nome","email","cel","papel","setor","valor_max","texto_len"])
    row = [
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
        csv.writer(f).writerow(row)

def serve_csv_downloads():
    if VISITS_CSV.exists():
        with VISITS_CSV.open("rb") as f:
            st.download_button("📥 Baixar visitas (CSV)", f, file_name="visitas.csv", mime="text/csv")
    if CONSULT_CSV.exists():
        with CONSULT_CSV.open("rb") as f:
            st.download_button("📥 Baixar consultas (CSV)", f, file_name="consultas.csv", mime="text/csv")

# -------------------------------------------------
# Boot (Stripe + DB)
# -------------------------------------------------
@st.cache_resource(show_spinner="Preparando…")
def _boot() -> Tuple[bool, str]:
    try:
        if not STRIPE_SECRET_KEY:
            return False, "Faltando STRIPE_SECRET_KEY."
        init_stripe(STRIPE_SECRET_KEY)
        init_db()
        return True, ""
    except Exception as e:
        return False, f"Falha ao iniciar serviços: {e}"

ok_boot, boot_msg = _boot()
if not ok_boot:
    st.error(boot_msg); st.stop()

# -------------------------------------------------
# Tela 1 — Home perfeita (alinhada e centrada)
# -------------------------------------------------

def first_screen():
    inject_hotjar()
    st.markdown('<div class="page-hero"><div class="wrap">', unsafe_allow_html=True)

    # chip + título + subtítulo
    st.markdown(f'<span class="chip">CLARA • {VERSION}</span>', unsafe_allow_html=True)
    st.markdown('<div class="title">Entenda o que você está assinando</div>', unsafe_allow_html=True)
    st.markdown(
        """
        <div class="subtitle">
          A CLARA lê seu contrato, explica <b>em palavras simples</b>
          e mostra o que pode ser <b>problema</b> — como multas altas,
          travas de cancelamento e responsabilidades exageradas.
        </div>
        """,
        unsafe_allow_html=True,
    )

    # CTA central real (coluna do meio)
    st.markdown('<div class="hero-cta">', unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1,1,1])
    with c2:
        if st.button("Iniciar análise do meu contrato", key="btn_start"):
            st.session_state.started = True
            try: st.cache_data.clear()
            except Exception: pass
            try: st.cache_resource.clear()
            except Exception: pass
            st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

    # pitch alinhada
    st.markdown("<div style='height:10px;'></div>", unsafe_allow_html=True)
    st.markdown(
        """
        <div class="pitch">
          <p><b>Problema real:</b> milhões de brasileiros assinam documentos sem entender por completo.
             A frase “eu li e concordo” virou símbolo dessa crise silenciosa.
             Isso expõe pessoas e empresas a riscos que poderiam ser evitados.</p>
          <p><b>Como ajudamos:</b> você envia o contrato e recebe
             <b>trechos críticos + explicações simples + dicas de negociação</b>.
             Use a CLARA como apoio para conversar com a outra parte e, se precisar, para levar ao seu advogado(a).</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # cards de valor
    st.markdown("<div style='height:16px;'></div>", unsafe_allow_html=True)
    st.markdown('<div class="cards">', unsafe_allow_html=True)
    with st.container():
        st.markdown('<div class="card"><h4>🛡️ Proteção</h4><p>Detecta multas fora da realidade, travas de cancelamento e riscos escondidos.</p></div>', unsafe_allow_html=True)
    with st.container():
        st.markdown('<div class="card"><h4>🧩 Linguagem simples</h4><p>Traduz termos como <b>foro</b> (onde um processo corre), <b>LGPD</b> (regras de dados) e <b>rescisão</b> (como encerrar).</p></div>', unsafe_allow_html=True)
    with st.container():
        st.markdown('<div class="card"><h4>📈 CET</h4><p>Mostra o custo total de um financiamento (juros + tarifas + taxas) para comparar propostas.</p></div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)  # /cards

    st.markdown('</div></div>', unsafe_allow_html=True)  # /wrap /page-hero

# -------------------------------------------------
# Sidebar — cadastro (opcional) + admin
# -------------------------------------------------

def sidebar_profile():
    st.sidebar.header("👤 Seus dados (opcional)")
    nome  = st.sidebar.text_input("Nome completo", value=st.session_state.profile.get("nome",""))
    email = st.sidebar.text_input("E-mail",        value=st.session_state.profile.get("email",""))
    cel   = st.sidebar.text_input("Celular",       value=st.session_state.profile.get("cel",""))
    papel = st.sidebar.selectbox("Você é o contratante?", ["Contratante","Contratado","Outro"],
                                 index=["Contratante","Contratado","Outro"].index(st.session_state.profile.get("papel","Contratante")))

    if st.sidebar.button("Salvar dados", use_container_width=True):
        errors = []
        if email and not is_valid_email(email):
            errors.append("E-mail inválido.")
        if cel and not is_valid_phone(cel):
            errors.append("Celular inválido (use somente números, com DDD).")
        if errors:
            st.sidebar.error(" • ".join(errors))
        else:
            st.session_state.profile = {"nome":nome.strip(),"email":email.strip(),"cel":cel.strip(),"papel":papel}
            try: log_visit(email.strip())
            except Exception: pass
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
# Preço / Stripe (banner discreto)
# -------------------------------------------------

def pricing_card():
    st.markdown('<div class="section"><div class="section-title" style="font-weight:800;">Plano Premium</div>', unsafe_allow_html=True)
    st.caption(f"{MONTHLY_PRICE_TEXT} • análises ilimitadas • suporte prioritário")

    okS, msgS = stripe_diagnostics()
    email = current_email()

    if not email:
        st.info("Preencha e salve seu e-mail na barra lateral para assinar. A análise gratuita continua liberada sem cadastro.")
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
                    st.error(sess.get("error", "Stripe indisponível no momento."))
            except Exception as e:
                st.error(f"Stripe indisponível no momento. Detalhe: {e}")
    st.markdown('</div>', unsafe_allow_html=True)


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
# Conteúdo + preço (após iniciar)
# -------------------------------------------------

def landing_block():
    st.markdown('<div class="section">', unsafe_allow_html=True)
    st.markdown("### O que você recebe")
    st.write("• Trechos críticos do contrato → **explicados em linguagem simples**.")
    st.write("• Sinais de alerta (multas altas, travas, riscos): **o que significam** e **como negociar**.")
    st.write("• **Relatório** para compartilhar com seu time ou advogado(a).")
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
    c1,c2,c3 = st.columns(3)
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
            st.success(f"**CET aproximado:** {cet*100:.2f}% ao mês")


def _wrap_text_box(label: str, content: str, h: int = 160):
    """Exibe texto sem scroll horizontal (caixa fixa e somente vertical)."""
    st.text_area(label, value=content, height=h, disabled=True)


def _build_share_email(resumo: str) -> str:
    return f"""Assunto: Solicitação de revisão de cláusulas contratuais

Olá,

Envio, por gentileza, os principais pontos identificados na análise inicial do contrato:

- {resumo}

Poderia avaliar as cláusulas destacadas (multas, reajuste, foro e responsabilidades) e sugerir eventuais ajustes de redação para mitigar riscos?

Fico à disposição.

Atenciosamente,
{st.session_state.profile.get('nome') or '—'}
"""


def results_section(text: str, ctx: Dict[str, Any]):
    st.subheader("4) Resultado")

    if not text.strip():
        st.warning("Envie o contrato (PDF) ou cole o texto para analisar.")
        return

    # Análise gratuita SEM obrigar cadastro
    if not is_premium() and st.session_state.free_runs_left <= 0:
        st.info("Você usou sua análise gratuita. **Assine o Premium** para continuar.")
        return

    with st.spinner("Analisando…"):
        hits, meta = analyze_contract_text(text, ctx)

    if not is_premium():
        st.session_state.free_runs_left -= 1

    # logs
    email_for_log = current_email()  # pode estar vazio (grátis sem cadastro)
    log_analysis_event(email=email_for_log, meta={"setor":ctx["setor"], "papel":ctx["papel"], "len":len(text)})
    log_consultation({"setor":ctx["setor"], "valor_max":ctx["limite_valor"], "texto_len":len(text)})

    resume = summarize_hits(hits)
    st.success(f"Resumo: {resume['resumo']}")
    st.write(f"Gravidade: **{resume['gravidade']}** | Pontos críticos: **{resume['criticos']}** | Itens analisados: {len(hits)}")

    # Pontos
    st.markdown("<div class='no-overflow'>", unsafe_allow_html=True)
    for h in hits:
        with st.expander(f"{h['severity']} • {h['title']}", expanded=False):
            st.write(h.get("explanation", ""))               # linguagem simples
            if h.get("suggestion"):
                st.markdown(f"**Como negociar:** {h['suggestion']}")
            if h.get("evidence"):
                # Evita scroll horizontal: caixa de texto somente leitura
                _wrap_text_box("Trecho do contrato (referência)", h["evidence"][:800])
    st.markdown("</div>", unsafe_allow_html=True)

    cet_calculator_block()

    # Relatório .txt
    buff = io.StringIO()
    buff.write(f"{APP_TITLE} {VERSION}\n")
    buff.write(f"Usuário: {st.session_state.profile.get('nome','')} <{email_for_log or 'sem e-mail'}>  •  Papel: {ctx['papel']}\n")
    buff.write(f"Setor: {ctx['setor']}  |  Valor máx.: {ctx['limite_valor']}\n\n")
    buff.write(f"Resumo: {resume['resumo']} (Gravidade: {resume['gravidade']})\n\n")
    buff.write("Pontos de atenção:\n")
    for h in hits:
        buff.write(f"- [{h['severity']}] {h['title']} — {h.get('explanation','')}\n")
        if h.get("suggestion"):
            buff.write(f"  Como negociar: {h['suggestion']}\n")
    st.download_button("📥 Baixar relatório (txt)", data=buff.getvalue(), file_name="relatorio_clara.txt", mime="text/plain")

    # Botão para gerar e-mail (copiar/baixar)
    st.markdown("### Gerar e-mail para advogado/contraparte")
    email_text = _build_share_email(resume.get('resumo', ''))
    st.text_area("Copie e cole:", email_text, height=220)
    st.download_button("Baixar e-mail (.txt)", data=email_text.encode("utf-8"), file_name="email_para_advogado.txt", mime="text/plain")

    # Ações auxiliares
    colA, colB = st.columns(2)
    with colA:
        if st.button("🔄 Recomeçar (voltar ao início)"):
            st.session_state.started = False
            st.rerun()
    with colB:
        st.caption("Dica: preencha seus dados na barra lateral para salvar histórico e assinar o Premium, se quiser.")

# -------------------------------------------------
# Main (single page)
# -------------------------------------------------

def main():
    if not st.session_state.started:
        first_screen()
        return

    # Barra lateral sempre visível
    sidebar_profile()
    handle_checkout_result()
    landing_block()

    st.markdown("---")
    st.markdown("### Comece sua análise")
    st.caption("Envie o contrato. O cadastro é opcional para a análise gratuita.")

    texto = upload_or_paste_section()
    ctx   = analysis_inputs()

    if st.button("🚀 Analisar agora", use_container_width=True):
        results_section(texto, ctx)

    st.markdown("---")
    # Banner Premium também no rodapé (discreto)
    with st.container():
        st.info("🔓 Clara Premium (opcional): relatórios ilimitados, histórico e suporte prioritário. A análise gratuita continua disponível.")

    st.markdown(
        '<p class="soft">A CLARA complementa sua leitura e negociação, mas <b>não substitui</b> a orientação de um(a) advogado(a).</p>',
        unsafe_allow_html=True
    )

if __name__ == "__main__":
    main()



