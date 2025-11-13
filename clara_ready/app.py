# app.py — CLARA • Sua Assistente Jurídica Pessoal
# Versão melhorada com UX DoNotPay + Identidade CLARA
# Mantém TODAS as funcionalidades originais

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
APP_TITLE = "CLARA • Sua Assistente Jurídica Pessoal"
VERSION = "v2.0"

st.set_page_config(page_title=APP_TITLE, page_icon="⚖️", layout="wide")

# Secrets / env
STRIPE_PUBLIC_KEY = st.secrets.get("STRIPE_PUBLIC_KEY", os.getenv("STRIPE_PUBLIC_KEY", ""))
STRIPE_SECRET_KEY = st.secrets.get("STRIPE_SECRET_KEY", os.getenv("STRIPE_SECRET_KEY", ""))
STRIPE_PRICE_ID   = st.secrets.get("STRIPE_PRICE_ID",   os.getenv("STRIPE_PRICE_ID", ""))
BASE_URL          = st.secrets.get("BASE_URL",          os.getenv("BASE_URL", "https://claraready.streamlit.app"))

MONTHLY_PRICE_TEXT = "R$ 9,90/mês"

# -------------------------------------------------
# Estilo: DoNotPay Inspired + CLARA Identity
# -------------------------------------------------
st.markdown(
    """
    <style>
    :root {
        --clara-gold: #D4AF37;
        --clara-blue: #ABDBF0;
        --clara-dark: #0f172a;
        --clara-gray: #475569;
        --clara-light: #f8fafc;
    }
    
    .clara-hero {
        background: linear-gradient(135deg, var(--clara-dark) 0%, #1e293b 100%);
        color: white;
        padding: 4rem 0;
        text-align: center;
        border-radius: 0 0 20px 20px;
    }
    
    .clara-hero-content {
        max-width: 800px;
        margin: 0 auto;
        padding: 0 2rem;
    }
    
    .clara-badge {
        background: var(--clara-gold);
        color: var(--clara-dark);
        padding: 0.5rem 1.5rem;
        border-radius: 50px;
        font-weight: 700;
        font-size: 0.9rem;
        display: inline-block;
        margin-bottom: 1.5rem;
    }
    
    .clara-title {
        font-size: 3.5rem;
        font-weight: 800;
        margin: 1rem 0;
        line-height: 1.1;
    }
    
    .clara-subtitle {
        font-size: 1.3rem;
        opacity: 0.9;
        margin-bottom: 2rem;
        line-height: 1.6;
    }
    
    .clara-card {
        background: white;
        border-radius: 16px;
        padding: 2rem;
        box-shadow: 0 4px 20px rgba(0,0,0,0.08);
        border: 1px solid #e2e8f0;
        margin: 1rem 0;
    }
    
    .clara-card:hover {
        transform: translateY(-2px);
        transition: transform 0.2s ease;
    }
    
    .clara-service-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
        gap: 1.5rem;
        margin: 2rem 0;
    }
    
    .clara-feature {
        text-align: center;
        padding: 1.5rem;
    }
    
    .clara-feature-icon {
        font-size: 2.5rem;
        margin-bottom: 1rem;
    }
    
    .clara-btn-primary {
        background: var(--clara-gold) !important;
        color: var(--clara-dark) !important;
        border: none !important;
        font-weight: 600 !important;
        padding: 0.75rem 1.5rem !important;
        border-radius: 12px !important;
    }
    
    .clara-btn-primary:hover {
        background: #B8941F !important;
        transform: translateY(-1px);
    }
    
    .clara-nav {
        background: white;
        padding: 1rem 0;
        border-bottom: 1px solid #e2e8f0;
        margin-bottom: 2rem;
    }
    
    .clara-step {
        display: flex;
        align-items: center;
        margin: 1rem 0;
        padding: 1rem;
        background: var(--clara-light);
        border-radius: 12px;
        border-left: 4px solid var(--clara-gold);
    }
    
    .clara-step-number {
        background: var(--clara-gold);
        color: var(--clara-dark);
        width: 30px;
        height: 30px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        font-weight: bold;
        margin-right: 1rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# -------------------------------------------------
# Estado (mantido da versão original)
# -------------------------------------------------
if "started" not in st.session_state:
    st.session_state.started = False
if "profile" not in st.session_state:
    st.session_state.profile = {"nome": "", "email": "", "cel": "", "papel": "Contratante"}
if "premium" not in st.session_state:
    st.session_state.premium = False
if "free_runs_left" not in st.session_state:
    st.session_state.free_runs_left = 1
if "current_view" not in st.session_state:
    st.session_state.current_view = "home"

# -------------------------------------------------
# Utils / Admin / Validações (mantido da versão original)
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

# -------------------------------------------------
# CSV helpers (mantido da versão original)
# -------------------------------------------------
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

# -------------------------------------------------
# Boot (Stripe + DB) - mantido
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
# Novas Views Inspiradas no DoNotPay
# -------------------------------------------------
def render_navigation():
    """Navegação moderna inspirada no DoNotPay"""
    col1, col2, col3, col4, col5 = st.columns([2, 1, 1, 1, 1])
    
    with col1:
        st.markdown(f"<h3 style='color: var(--clara-gold); margin: 0;'>CLARA LAW</h3>", unsafe_allow_html=True)
    
    with col2:
        if st.button("🏠 Início", use_container_width=True):
            st.session_state.current_view = "home"
            st.session_state.started = False
    
    with col3:
        if st.button("🛡️ Serviços", use_container_width=True):
            st.session_state.current_view = "services"
    
    with col4:
        if st.button("📄 Analisar", use_container_width=True):
            st.session_state.current_view = "analysis"
            st.session_state.started = True
    
    with col5:
        if st.button("⭐ Premium", use_container_width=True):
            st.session_state.current_view = "premium"

def render_hero_section():
    """Hero section moderna inspirada no DoNotPay"""
    st.markdown("""
    <div class="clara-hero">
        <div class="clara-hero-content">
            <div class="clara-badge">🤖 SUA ASSISTENTE JURÍDICA PESSOAL</div>
            <h1 class="clara-title">Resolva problemas jurídicos sem complicação</h1>
            <p class="clara-subtitle">
                A CLARA usa inteligência artificial para te ajudar a entender contratos, 
                resolver disputas e proteger seus direitos de forma simples e acessível.
            </p>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("👉 Começar Agora", key="hero_cta", use_container_width=True):
            st.session_state.current_view = "services"
    
    st.markdown("</div></div>", unsafe_allow_html=True)

def render_services_view():
    """Grid de serviços ao estilo DoNotPay"""
    st.markdown("""
    <div style='text-align: center; margin: 3rem 0;'>
        <h2>Como a CLARA pode te ajudar hoje?</h2>
        <p>Escolha o serviço que você precisa:</p>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown('<div class="clara-service-grid">', unsafe_allow_html=True)
    
    services = [
        {
            "icon": "📄",
            "title": "Análise de Contratos",
            "description": "Entenda o que realmente está escrito em contratos complexos",
            "action": "Analisar Contrato"
        },
        {
            "icon": "💰", 
            "title": "Disputas Financeiras",
            "description": "Recupere cobranças indevidas e dispute taxas abusivas",
            "action": "Resolver Disputa"
        },
        {
            "icon": "🏠",
            "title": "Direito do Consumidor", 
            "description": "Proteja-se contra práticas abusivas e produtos defeituosos",
            "action": "Proteger Direitos"
        },
        {
            "icon": "📊",
            "title": "Cálculo de CET",
            "description": "Descubra o custo real de empréstimos e financiamentos",
            "action": "Calcular CET"
        },
        {
            "icon": "⚖️",
            "title": "Modelos Jurídicos",
            "description": "Acesse modelos de documentos e notificações pré-formatados",
            "action": "Ver Modelos"
        },
        {
            "icon": "🔒",
            "title": "LGPD e Privacidade",
            "description": "Entenda seus direitos sobre proteção de dados pessoais",
            "action": "Proteger Dados"
        }
    ]
    
    for i, service in enumerate(services):
        with st.container():
            st.markdown(f"""
            <div class="clara-card">
                <div style='text-align: center;'>
                    <div class="clara-feature-icon">{service['icon']}</div>
                    <h3>{service['title']}</h3>
                    <p style='color: var(--clara-gray);'>{service['description']}</p>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            if st.button(service['action'], key=f"service_{i}", use_container_width=True):
                if service['title'] == "Análise de Contratos":
                    st.session_state.current_view = "analysis"
                    st.session_state.started = True
                    st.rerun()

def render_home_view():
    """Página inicial completa"""
    render_hero_section()
    
    # Seção de valores
    st.markdown("""
    <div style='padding: 4rem 0;'>
        <div style='max-width: 800px; margin: 0 auto; text-align: center;'>
            <h2>Por que escolher a CLARA?</h2>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("""
        <div class="clara-feature">
            <div class="clara-feature-icon">🛡️</div>
            <h4>Proteção</h4>
            <p>Detecta multas abusivas, travas de cancelamento e riscos escondidos em contratos</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown("""
        <div class="clara-feature">
            <div class="clara-feature-icon">🧩</div>
            <h4>Linguagem Simples</h4>
            <p>Traduz termos jurídicos complexos para uma linguagem que qualquer pessoa entende</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown("""
        <div class="clara-feature">
            <div class="clara-feature-icon">📈</div>
            <h4>Transparência</h4>
            <p>Mostra o custo real de financiamentos e ajuda a comparar propostas</p>
        </div>
        """, unsafe_allow_html=True)
    
    # Chamada para ação
    st.markdown("""
    <div style='text-align: center; margin: 3rem 0;'>
        <h3>Pronto para resolver seus problemas jurídicos?</h3>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("🎯 Ver Todos os Serviços", use_container_width=True):
            st.session_state.current_view = "services"

# -------------------------------------------------
# Views Originais Adaptadas
# -------------------------------------------------
def first_screen():
    """Tela inicial original adaptada"""
    if st.session_state.current_view == "home":
        render_home_view()
        return
        
    if st.session_state.current_view == "services":
        render_services_view()
        return
        
    # View padrão (análise)
    st.markdown("""
    <div style='max-width: 800px; margin: 0 auto; padding: 2rem 0;'>
        <div style='text-align: center; margin-bottom: 3rem;'>
            <h1>Análise de Contratos</h1>
            <p>Envie seu contrato e a CLARA vai destacar os pontos importantes em linguagem simples</p>
        </div>
    </div>
    """, unsafe_allow_html=True)

def sidebar_profile():
    """Sidebar original mantida com melhorias visuais"""
    st.sidebar.markdown("### 👤 Seus Dados")
    
    with st.sidebar.container():
        nome  = st.text_input("Nome completo", value=st.session_state.profile.get("nome",""))
        email = st.text_input("E-mail", value=st.session_state.profile.get("email",""))
        cel   = st.text_input("Celular", value=st.session_state.profile.get("cel",""))
        papel = st.selectbox("Você é o contratante?", ["Contratante","Contratado","Outro"],
                            index=["Contratante","Contratado","Outro"].index(st.session_state.profile.get("papel","Contratante")))

        if st.button("💾 Salvar dados", use_container_width=True):
            errors = []
            if email and not is_valid_email(email):
                errors.append("E-mail inválido.")
            if cel and not is_valid_phone(cel):
                errors.append("Celular inválido.")
            if errors:
                st.error(" • ".join(errors))
            else:
                st.session_state.profile = {"nome":nome.strip(),"email":email.strip(),"cel":cel.strip(),"papel":papel}
                try: 
                    log_visit(email.strip())
                    if current_email() and get_subscriber_by_email(current_email()):
                        st.session_state.premium = True
                except Exception: pass
                st.success("Dados salvos!")

# -------------------------------------------------
# Funções Originais Mantidas (com pequenas melhorias)
# -------------------------------------------------
def upload_or_paste_section() -> str:
    st.markdown("### 📄 1) Envie o contrato")
    
    tab1, tab2 = st.tabs(["📤 Upload PDF", "📝 Colar Texto"])
    
    with tab1:
        f = st.file_uploader("Faça upload do PDF", type=["pdf"], label_visibility="collapsed")
        raw = ""
        if f:
            with st.spinner("Lendo PDF…"):
                raw = extract_text_from_pdf(f)
    
    with tab2:
        raw = st.text_area("Cole o texto do contrato:", height=200, value=raw or "", 
                          placeholder="Copie e cole o texto do contrato aqui...")
    
    return raw

def analysis_inputs() -> Dict[str, Any]:
    st.markdown("### 🎯 2) Contexto da Análise")
    
    col1, col2, col3 = st.columns(3)
    setor = col1.selectbox("Setor", ["Genérico","SaaS/Serviços","Empréstimos","Educação","Plano de saúde"])
    papel = col2.selectbox("Seu Papel", ["Contratante","Contratado","Outro"])
    valor = col3.number_input("Valor (R$)", min_value=0.0, step=100.0, 
                             help="Valor máximo envolvido no contrato")
    
    return {"setor": setor, "papel": papel, "limite_valor": valor}

def results_section(text: str, ctx: Dict[str, Any]):
    """Seção de resultados melhorada"""
    if not text.strip():
        st.warning("📝 Envie o contrato (PDF) ou cole o texto para analisar.")
        return

    if not is_premium() and st.session_state.free_runs_left <= 0:
        st.info("""
        🚀 **Você usou sua análise gratuita** 
        
        Assine o **CLARA Premium** para análises ilimitadas e recursos exclusivos!
        """)
        return

    with st.spinner("🔍 CLARA está analisando seu contrato..."):
        hits, meta = analyze_contract_text(text, ctx)

    if not is_premium():
        st.session_state.free_runs_left -= 1

    # Logs (mantido da versão original)
    email_for_log = current_email()
    log_analysis_event(email=email_for_log, meta={"setor":ctx["setor"], "papel":ctx["papel"], "len":len(text)})

    resume = summarize_hits(hits)
    
    # Resultados visuais melhorados
    st.success(f"**Análise concluída!** {resume['resumo']}")
    
    # Métricas
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Pontos Analisados", len(hits))
    with col2:
        st.metric("Gravidade", resume['gravidade'])
    with col3:
        st.metric("Pontos Críticos", resume['criticos'])
    
    # Detalhamento
    st.markdown("### 📋 Pontos de Atenção")
    for h in hits:
        with st.expander(f"{h['severity']} • {h['title']}", expanded=False):
            st.write(h.get("explanation", ""))
            if h.get("suggestion"):
                st.info(f"💡 **Como negociar:** {h['suggestion']}")
            if h.get("evidence"):
                st.text_area("📜 Trecho do contrato:", value=h["evidence"][:800], 
                           height=100, disabled=True)

# -------------------------------------------------
# Main Adaptada
# -------------------------------------------------
def main():
    # Navegação moderna
    render_navigation()
    
    # Controle de views
    if st.session_state.current_view in ["home", "services"]:
        first_screen()
        return
        
    # View de análise (original)
    if not st.session_state.started:
        first_screen()
        return

    # Sidebar mantida
    sidebar_profile()
    
    # Conteúdo principal
    st.markdown("""
    <div style='max-width: 1000px; margin: 0 auto;'>
        <div style='text-align: center; margin-bottom: 2rem;'>
            <h1>Análise de Contrato</h1>
            <p>Siga os passos abaixo para analisar seu contrato</p>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Processo guiado
    texto = upload_or_paste_section()
    ctx = analysis_inputs()
    
    st.markdown("### 🚀 3) Analisar")
    if st.button("✨ Analisar Contrato com CLARA", type="primary", use_container_width=True):
        results_section(texto, ctx)

if __name__ == "__main__":
    main()
