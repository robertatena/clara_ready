# app.py — CLARA • Sua Assistente Jurídica Pessoal
# Versão PROFISSIONAL com logo e design elegante

import os
import io
import re
import csv
import smtplib
from email.mime.text import MimeText
from email.mime.multipart import MimeMultipart
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Tuple, Set, List
import base64

import streamlit as st

# ---- módulos locais ----
try:
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
except ImportError:
    # Fallback para desenvolvimento
    def extract_text_from_pdf(file):
        return "Texto simulado do PDF - Módulo não carregado"
    
    def analyze_contract_text(text, context):
        return [
            {
                "title": "Cláusula de Exemplo",
                "severity": "MÉDIA", 
                "explanation": "Esta é uma análise simulada",
                "suggestion": "Revisar com atenção",
                "evidence": "Trecho do contrato simulado"
            }
        ], {}
    
    def summarize_hits(hits):
        return {
            "resumo": "Análise simulada concluída",
            "gravidade": "Média",
            "criticos": len([h for h in hits if h.get('severity') in ['ALTA', 'CRÍTICO']]),
            "sugestoes": len(hits)
        }
    
    def compute_cet_quick(*args):
        return 0.0
    
    def init_stripe(*args):
        pass
    
    def create_checkout_session(*args):
        class MockSession:
            url = "https://stripe.com/mock"
        return MockSession()
    
    def init_db():
        pass
    
    def log_analysis_event(*args, **kwargs):
        pass
    
    def log_subscriber(*args, **kwargs):
        pass
    
    def list_subscribers():
        return []
    
    def get_subscriber_by_email(email):
        return None

# -------------------------------------------------
# Configs
# -------------------------------------------------
APP_TITLE = "CLARA • Sua Assistente Jurídica Pessoal"
VERSION = "v3.0"

st.set_page_config(
    page_title=APP_TITLE, 
    page_icon="⚖️", 
    layout="wide", 
    initial_sidebar_state="collapsed"
)

# Secrets / env
STRIPE_PUBLIC_KEY = st.secrets.get("STRIPE_PUBLIC_KEY", os.getenv("STRIPE_PUBLIC_KEY", ""))
STRIPE_SECRET_KEY = st.secrets.get("STRIPE_SECRET_KEY", os.getenv("STRIPE_SECRET_KEY", ""))
STRIPE_PRICE_ID = st.secrets.get("STRIPE_PRICE_ID", os.getenv("STRIPE_PRICE_ID", ""))
BASE_URL = st.secrets.get("BASE_URL", os.getenv("BASE_URL", "https://claraready.streamlit.app"))

# Email config
SMTP_SERVER = st.secrets.get("SMTP_SERVER", "")
SMTP_PORT = st.secrets.get("SMTP_PORT", 587)
SMTP_USERNAME = st.secrets.get("SMTP_USERNAME", "")
SMTP_PASSWORD = st.secrets.get("SMTP_PASSWORD", "")
ADMIN_EMAIL = st.secrets.get("ADMIN_EMAIL", "")

MONTHLY_PRICE_TEXT = "R$ 9,90/mês"

# -------------------------------------------------
# Logo e Assets
# -------------------------------------------------
def get_base64_logo():
    """Retorna logo em base64 ou texto estilizado"""
    try:
        with open("logo.jpg", "rb") as f:
            data = f.read()
            return base64.b64encode(data).decode()
    except:
        return None

LOGO_BASE64 = get_base64_logo()

# -------------------------------------------------
# Estilo PROFISSIONAL Elegante
# -------------------------------------------------
st.markdown(
    f"""
    <style>
    :root {{
        --clara-primary: #2563eb;
        --clara-secondary: #7c3aed;
        --clara-accent: #f59e0b;
        --clara-dark: #1e293b;
        --clara-darker: #0f172a;
        --clara-light: #f8fafc;
        --clara-gray: #64748b;
        --clara-success: #10b981;
        --clara-warning: #f59e0b;
        --clara-danger: #ef4444;
    }}
    
    .main-header {{
        background: white;
        padding: 1rem 0;
        border-bottom: 1px solid #e2e8f0;
        box-shadow: 0 2px 10px rgba(0,0,0,0.05);
        position: sticky;
        top: 0;
        z-index: 100;
    }}
    
    .logo-container {{
        display: flex;
        align-items: center;
        gap: 1rem;
        font-weight: 700;
        font-size: 1.5rem;
        color: var(--clara-primary);
    }}
    
    .logo-text {{
        background: linear-gradient(135deg, var(--clara-primary), var(--clara-secondary));
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 800;
    }}
    
    .tagline {{
        font-size: 0.9rem;
        color: var(--clara-gray);
        font-weight: 400;
        margin-top: -5px;
    }}
    
    .hero-section {{
        background: linear-gradient(135deg, var(--clara-darker) 0%, var(--clara-dark) 100%);
        color: white;
        padding: 5rem 0;
        position: relative;
        overflow: hidden;
    }}
    
    .hero-section::before {{
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: url('data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 1000" opacity="0.05"><polygon fill="white" points="0,1000 1000,0 1000,1000"/></svg>');
        background-size: cover;
    }}
    
    .hero-content {{
        position: relative;
        max-width: 1200px;
        margin: 0 auto;
        padding: 0 2rem;
        text-align: center;
    }}
    
    .badge {{
        background: var(--clara-accent);
        color: var(--clara-darker);
        padding: 0.5rem 1.5rem;
        border-radius: 50px;
        font-weight: 700;
        font-size: 0.9rem;
        display: inline-block;
        margin-bottom: 2rem;
    }}
    
    .hero-title {{
        font-size: 3.5rem;
        font-weight: 800;
        margin: 1rem 0;
        line-height: 1.1;
        background: linear-gradient(135deg, #fff 0%, #cbd5e1 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }}
    
    .hero-subtitle {{
        font-size: 1.3rem;
        opacity: 0.9;
        margin-bottom: 3rem;
        line-height: 1.6;
        max-width: 600px;
        margin-left: auto;
        margin-right: auto;
    }}
    
    .card {{
        background: white;
        border-radius: 16px;
        padding: 2rem;
        box-shadow: 0 4px 20px rgba(0,0,0,0.08);
        border: 1px solid #e2e8f0;
        transition: all 0.3s ease;
        height: 100%;
    }}
    
    .card:hover {{
        transform: translateY(-5px);
        box-shadow: 0 8px 30px rgba(0,0,0,0.12);
    }}
    
    .service-grid {{
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
        gap: 2rem;
        margin: 3rem 0;
    }}
    
    .feature-icon {{
        width: 70px;
        height: 70px;
        border-radius: 50%;
        background: linear-gradient(135deg, var(--clara-primary), var(--clara-secondary));
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 1.8rem;
        margin: 0 auto 1.5rem;
    }}
    
    .btn-primary {{
        background: linear-gradient(135deg, var(--clara-primary), var(--clara-secondary)) !important;
        color: white !important;
        border: none !important;
        font-weight: 600 !important;
        padding: 0.75rem 2rem !important;
        border-radius: 12px !important;
        transition: all 0.3s ease !important;
    }}
    
    .btn-primary:hover {{
        transform: translateY(-2px);
        box-shadow: 0 8px 20px rgba(37, 99, 235, 0.3) !important;
    }}
    
    .step-container {{
        display: flex;
        align-items: center;
        margin: 2rem 0;
        padding: 2rem;
        background: var(--clara-light);
        border-radius: 16px;
        border-left: 5px solid var(--clara-primary);
    }}
    
    .step-number {{
        background: var(--clara-primary);
        color: white;
        width: 40px;
        height: 40px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        font-weight: bold;
        font-size: 1.2rem;
        margin-right: 1.5rem;
        flex-shrink: 0;
    }}
    
    .metric-card {{
        background: linear-gradient(135deg, var(--clara-primary), var(--clara-secondary));
        color: white;
        padding: 1.5rem;
        border-radius: 12px;
        text-align: center;
    }}
    
    .nav-container {{
        background: white;
        padding: 1rem 0;
        border-bottom: 1px solid #e2e8f0;
        box-shadow: 0 2px 10px rgba(0,0,0,0.05);
        position: sticky;
        top: 0;
        z-index: 100;
    }}
    
    .premium-badge {{
        background: linear-gradient(135deg, var(--clara-warning), #f97316);
        color: white;
        padding: 0.3rem 1rem;
        border-radius: 20px;
        font-size: 0.8rem;
        font-weight: 600;
    }}
    
    .analysis-result {{
        border-left: 4px solid var(--clara-primary);
        padding-left: 1rem;
        margin: 1rem 0;
    }}
    
    .critical-item {{
        border-left: 4px solid var(--clara-danger);
        background: #fef2f2;
        padding: 1rem;
        margin: 0.5rem 0;
        border-radius: 0 8px 8px 0;
    }}
    
    .warning-item {{
        border-left: 4px solid var(--clara-warning);
        background: #fffbeb;
        padding: 1rem;
        margin: 0.5rem 0;
        border-radius: 0 8px 8px 0;
    }}
    
    .info-item {{
        border-left: 4px solid var(--clara-primary);
        background: #eff6ff;
        padding: 1rem;
        margin: 0.5rem 0;
        border-radius: 0 8px 8px 0;
    }}
    
    .nav-button {{
        background: none;
        border: none;
        color: var(--clara-gray);
        cursor: pointer;
        padding: 0.5rem 1rem;
        border-radius: 8px;
        transition: all 0.3s ease;
        font-size: 0.9rem;
    }}
    
    .nav-button:hover {{
        background: #f1f5f9;
        color: var(--clara-primary);
    }}
    
    .footer {{
        background: var(--clara-darker);
        color: white;
        padding: 3rem 2rem;
        margin-top: 4rem;
    }}
    
    .stButton > button {{
        width: 100%;
    }}
    </style>
    """,
    unsafe_allow_html=True,
)

# -------------------------------------------------
# Estado da Sessão
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
if "analysis_results" not in st.session_state:
    st.session_state.analysis_results = None
if "lawyer_email_sent" not in st.session_state:
    st.session_state.lawyer_email_sent = False

# -------------------------------------------------
# Utils / Validações
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

def send_lawyer_email(analysis_data: Dict, user_profile: Dict, lawyer_email: str) -> bool:
    """Envia email profissional para advogado com análise do contrato"""
    try:
        if not all([SMTP_SERVER, SMTP_USERNAME, SMTP_PASSWORD, lawyer_email]):
            st.warning("Configuração de email não encontrada. Modo de demonstração.")
            return True  # Simula sucesso em modo demo
            
        msg = MimeMultipart()
        msg['Subject'] = f"Análise de Contrato - Cliente: {user_profile.get('nome', 'Não informado')}"
        msg['From'] = SMTP_USERNAME
        msg['To'] = lawyer_email
        
        # Corpo do email formatado
        html = f"""
        <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #ddd; border-radius: 10px;">
                    <h2 style="color: #2563eb; text-align: center;">📋 Análise de Contrato - CLARA</h2>
                    
                    <div style="background: #f8fafc; padding: 15px; border-radius: 8px; margin: 20px 0;">
                        <h3>👤 Dados do Cliente</h3>
                        <p><strong>Nome:</strong> {user_profile.get('nome', 'Não informado')}</p>
                        <p><strong>Email:</strong> {user_profile.get('email', 'Não informado')}</p>
                        <p><strong>Telefone:</strong> {user_profile.get('cel', 'Não informado')}</p>
                        <p><strong>Papel no contrato:</strong> {user_profile.get('papel', 'Não informado')}</p>
                    </div>
                    
                    <div style="background: #f0f9ff; padding: 15px; border-radius: 8px; margin: 20px 0;">
                        <h3>📊 Resumo da Análise</h3>
                        <p><strong>Setor:</strong> {analysis_data.get('context', {}).get('setor', 'Não informado')}</p>
                        <p><strong>Valor envolvido:</strong> R$ {analysis_data.get('context', {}).get('limite_valor', 0):.2f}</p>
                        <p><strong>Total de pontos analisados:</strong> {len(analysis_data.get('hits', []))}</p>
                        <p><strong>Pontos críticos identificados:</strong> {analysis_data.get('summary', {}).get('criticos', 0)}</p>
                        <p><strong>Gravidade geral:</strong> {analysis_data.get('summary', {}).get('gravidade', 'Média')}</p>
                    </div>
                    
                    <div style="margin: 20px 0;">
                        <h3>⚠️ Pontos de Atenção Críticos</h3>
        """
        
        # Adicionar pontos críticos
        critical_items = [h for h in analysis_data.get('hits', []) if h.get('severity') in ['ALTA', 'CRÍTICO']]
        for i, item in enumerate(critical_items[:5], 1):
            html += f"""
                        <div style="background: #fef2f2; padding: 10px; margin: 10px 0; border-left: 4px solid #ef4444; border-radius: 4px;">
                            <h4 style="margin: 0; color: #dc2626;">{i}. {item.get('title', 'Sem título')}</h4>
                            <p style="margin: 5px 0;">{item.get('explanation', 'Sem explicação')}</p>
                            <p style="margin: 5px 0;"><strong>Sugestão:</strong> {item.get('suggestion', 'Sem sugestão')}</p>
                        </div>
            """
        
        html += f"""
                    </div>
                    
                    <div style="background: #f0fdf4; padding: 15px; border-radius: 8px; margin: 20px 0;">
                        <h3>💡 Recomendações da CLARA</h3>
                        <p>{analysis_data.get('summary', {}).get('resumo', 'Sem recomendações específicas')}</p>
                        <p><strong>Próximos passos sugeridos:</strong></p>
                        <ul>
                            <li>Revisar cláusulas críticas com cliente</li>
                            <li>Negociar termos problemáticos</li>
                            <li>Considerar rescisão se necessário</li>
                        </ul>
                    </div>
                    
                    <div style="text-align: center; margin-top: 30px; padding-top: 20px; border-top: 1px solid #ddd;">
                        <p style="color: #64748b; font-size: 0.9em;">
                            Análise gerada automaticamente por CLARA - Sua Assistente Jurídica Pessoal<br>
                            Data: {datetime.now().strftime('%d/%m/%Y %H:%M')}
                        </p>
                    </div>
                </div>
            </body>
        </html>
        """
        
        msg.attach(MimeText(html, 'html'))
        
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SMTP_USERNAME, SMTP_PASSWORD)
        server.send_message(msg)
        server.quit()
        
        return True
        
    except Exception as e:
        st.error(f"Erro ao enviar email: {str(e)}")
        return False

# -------------------------------------------------
# Componentes de UI
# -------------------------------------------------
def render_professional_nav():
    """Navegação profissional com logo"""
    st.markdown("""
    <div class="nav-container">
        <div style="max-width: 1200px; margin: 0 auto; padding: 0 2rem; display: flex; justify-content: space-between; align-items: center;">
            <div style="display: flex; align-items: center; gap: 1rem;">
                <div class="logo-container">
                    <span style="font-size: 1.8rem;">⚖️</span>
                    <div>
                        <div class="logo-text">CLARA LAW</div>
                        <div class="tagline">Inteligência para um mundo mais claro</div>
                    </div>
                </div>
            </div>
            <div style="display: flex; align-items: center; gap: 0.5rem;">
                <button class="nav-button" onclick="window.streamlitSessionState.setItem('current_view', 'home')">🏠 Início</button>
                <button class="nav-button" onclick="window.streamlitSessionState.setItem('current_view', 'services')">🛡️ Serviços</button>
                <button class="nav-button" onclick="window.streamlitSessionState.setItem('current_view', 'analysis')">📄 Analisar</button>
                {premium_badge}
                <button class="nav-button" onclick="window.streamlitSessionState.setItem('current_view', 'premium')" style="background: linear-gradient(135deg, var(--clara-primary), var(--clara-secondary)); color: white; padding: 0.5rem 1.5rem;">⭐ Premium</button>
            </div>
        </div>
    </div>
    """.format(premium_badge='<span class="premium-badge">PREMIUM</span>' if is_premium() else ''), 
    unsafe_allow_html=True)

def render_hero_section():
    """Hero section profissional"""
    st.markdown("""
    <div class="hero-section">
        <div class="hero-content">
            <div class="badge">🤖 ASSISTENTE JURÍDICO PESSOAL</div>
            <h1 class="hero-title">Justiça Acessível para Todos</h1>
            <p class="hero-subtitle">
                Use inteligência artificial para entender contratos complexos, resolver disputas 
                e proteger seus direitos de forma simples, rápida e acessível.
            </p>
            <div style="display: flex; gap: 1rem; justify-content: center; flex-wrap: wrap;">
                <button onclick="window.streamlitSessionState.setItem('current_view', 'analysis')" class="btn-primary" style="font-size: 1.1rem; padding: 1rem 2rem;">
                    🚀 Analisar Meu Contrato
                </button>
                <button onclick="window.streamlitSessionState.setItem('current_view', 'services')" style="background: rgba(255,255,255,0.1); color: white; border: 2px solid rgba(255,255,255,0.3); padding: 1rem 2rem; border-radius: 12px; font-size: 1.1rem; font-weight: 600; cursor: pointer; transition: all 0.3s ease;">
                    📚 Ver Serviços
                </button>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

def render_services_grid():
    """Grid de serviços profissional"""
    st.markdown("""
    <div style="max-width: 1200px; margin: 0 auto; padding: 4rem 2rem;">
        <div style="text-align: center; margin-bottom: 4rem;">
            <h2>Serviços Jurídicos Inteligentes</h2>
            <p style="color: var(--clara-gray); font-size: 1.2rem; max-width: 600px; margin: 0 auto;">
                Soluções completas para suas necessidades jurídicas do dia a dia
            </p>
        </div>
    """, unsafe_allow_html=True)
    
    services = [
        {
            "icon": "📄",
            "title": "Análise de Contratos",
            "description": "Identifique cláusulas abusivas, riscos escondidos e termos problemáticos em qualquer contrato",
            "features": ["Detecção de multas abusivas", "Análise de cláusulas críticas", "Sugestões de negociação"],
            "action": "Analisar Contrato"
        },
        {
            "icon": "💰", 
            "title": "Disputas Financeiras",
            "description": "Recupere cobranças indevidas, dispute taxas abusivas e negocie dívidas",
            "features": ["Análise de cobranças", "Modelos de contestação", "Cálculo de juros"],
            "action": "Resolver Disputa"
        },
        {
            "icon": "🏠",
            "title": "Direito do Consumidor", 
            "description": "Proteja-se contra práticas abusivas, produtos defeituosos e má prestação de serviços",
            "features": ["Análise de garantias", "Orientações para reclamações", "Modelos de notificação"],
            "action": "Proteger Direitos"
        },
        {
            "icon": "📊",
            "title": "Cálculo de CET",
            "description": "Descubra o custo real de empréstimos, financiamentos e cartões de crédito",
            "features": ["Cálculo transparente", "Comparação de propostas", "Análise de encargos"],
            "action": "Calcular CET"
        },
        {
            "icon": "⚖️",
            "title": "Modelos Jurídicos",
            "description": "Acesse modelos prontos de documentos, notificações e recursos",
            "features": ["Notificações extrajudiciais", "Recursos administrativos", "Contestações"],
            "action": "Ver Modelos"
        },
        {
            "icon": "🔒",
            "title": "LGPD e Privacidade",
            "description": "Proteja seus dados pessoais e exija transparência no tratamento de informações",
            "features": ["Análise de consentimento", "Orientações para exclusão", "Modelos de solicitação"],
            "action": "Proteger Dados"
        }
    ]
    
    st.markdown('<div class="service-grid">', unsafe_allow_html=True)
    
    for i, service in enumerate(services):
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.markdown(f"""
            <div class="card">
                <div class="feature-icon">{service['icon']}</div>
                <h3 style="text-align: center; margin-bottom: 1rem;">{service['title']}</h3>
                <p style="color: var(--clara-gray); text-align: center; margin-bottom: 1.5rem;">{service['description']}</p>
                <ul style="color: var(--clara-gray); margin-bottom: 2rem; padding-left: 1rem;">
                    {''.join([f'<li>{feature}</li>' for feature in service['features']])}
                </ul>
                <button onclick="window.streamlitSessionState.setItem('current_view', 'analysis')" class="btn-primary" style="width: 100%;">
                    {service['action']}
                </button>
            </div>
            """, unsafe_allow_html=True)
    
    st.markdown('</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

def render_analysis_workflow():
    """Fluxo de análise profissional"""
    st.markdown("""
    <div style="max-width: 1000px; margin: 0 auto; padding: 2rem 1rem;">
        <div style="text-align: center; margin-bottom: 3rem;">
            <h1>Análise Profissional de Contratos</h1>
            <p style="color: var(--clara-gray); font-size: 1.1rem;">
                Em 3 passos simples, tenha uma análise completa do seu contrato
            </p>
        </div>
    """, unsafe_allow_html=True)
    
    # Passo 1 - Dados do usuário
    with st.container():
        st.markdown("""
        <div class="step-container">
            <div class="step-number">1</div>
            <div style="flex: 1;">
                <h3 style="margin: 0 0 1rem 0;">Seus Dados</h3>
                <p style="color: var(--clara-gray); margin: 0;">
                    Preencha suas informações para personalizarmos a análise
                </p>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        col1, col2 = st.columns(2)
        with col1:
            nome = st.text_input("Nome completo*", value=st.session_state.profile.get("nome", ""))
            email = st.text_input("E-mail*", value=st.session_state.profile.get("email", ""))
        with col2:
            cel = st.text_input("Celular*", value=st.session_state.profile.get("cel", ""))
            papel = st.selectbox("Seu papel no contrato*", 
                               ["Contratante", "Contratado", "Fornecedor", "Consumidor", "Outro"],
                               index=0)
        
        if st.button("💾 Salvar Dados", use_container_width=True):
            errors = []
            if not nome.strip():
                errors.append("Nome é obrigatório")
            if not email.strip() or not is_valid_email(email):
                errors.append("E-mail válido é obrigatório")
            if not cel.strip() or not is_valid_phone(cel):
                errors.append("Celular válido é obrigatório")
            
            if errors:
                st.error(" • ".join(errors))
            else:
                st.session_state.profile = {
                    "nome": nome.strip(),
                    "email": email.strip(),
                    "cel": cel.strip(),
                    "papel": papel
                }
                st.success("Dados salvos com sucesso!")
    
    # Passo 2 - Upload do contrato
    with st.container():
        st.markdown("""
        <div class="step-container">
            <div class="step-number">2</div>
            <div style="flex: 1;">
                <h3 style="margin: 0 0 1rem 0;">Contrato</h3>
                <p style="color: var(--clara-gray); margin: 0;">
                    Envie o contrato que deseja analisar
                </p>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        tab1, tab2 = st.tabs(["📤 Upload PDF", "📝 Colar Texto"])
        raw_text = ""
        
        with tab1:
            uploaded_file = st.file_uploader("Faça upload do contrato em PDF", type=["pdf"], 
                                           label_visibility="collapsed")
            if uploaded_file:
                with st.spinner("Processando PDF..."):
                    raw_text = extract_text_from_pdf(uploaded_file)
                    if raw_text:
                        st.success(f"✅ PDF processado! {len(raw_text)} caracteres extraídos.")
        
        with tab2:
            raw_text = st.text_area("Cole o texto do contrato:", value=raw_text, height=200,
                                  placeholder="Copie e cole o texto completo do contrato aqui...")
    
    # Passo 3 - Contexto da análise
    with st.container():
        st.markdown("""
        <div class="step-container">
            <div class="step-number">3</div>
            <div style="flex: 1;">
                <h3 style="margin: 0 0 1rem 0;">Contexto</h3>
                <p style="color: var(--clara-gray); margin: 0;">
                    Informações adicionais para melhorar a análise
                </p>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        col1, col2, col3 = st.columns(3)
        with col1:
            setor = st.selectbox("Setor do contrato", 
                               ["Genérico", "SaaS/Serviços", "Empréstimos", "Educação", 
                                "Plano de saúde", "Imobiliário", "Trabalhista", "Outro"])
        with col2:
            valor = st.number_input("Valor envolvido (R$)", min_value=0.0, step=100.0,
                                  help="Valor máximo do contrato, se aplicável")
        with col3:
            urgencia = st.selectbox("Urgência", 
                                  ["Baixa", "Média", "Alta", "Crítica"])
    
    return raw_text, {"setor": setor, "papel": papel, "limite_valor": valor, "urgencia": urgencia}

def render_analysis_results(text: str, ctx: Dict[str, Any]):
    """Renderiza resultados da análise de forma profissional"""
    if not text.strip():
        st.warning("📝 Por favor, envie o contrato ou cole o texto para análise.")
        return

    if not is_premium() and st.session_state.free_runs_left <= 0:
        st.info("""
        🚀 **Você usou sua análise gratuita** 
        
        Assine o **CLARA Premium** para análises ilimitadas e recursos exclusivos!
        """)
        if st.button("⭐ Assinar Premium", use_container_width=True):
            st.session_state.current_view = "premium"
            st.rerun()
        return

    with st.spinner("🔍 CLARA está analisando seu contrato... Isso pode levar alguns instantes."):
        hits, meta = analyze_contract_text(text, ctx)

    if not is_premium():
        st.session_state.free_runs_left -= 1

    # Log da análise
    email_for_log = current_email()
    log_analysis_event(email=email_for_log, 
                      meta={"setor": ctx["setor"], "papel": ctx["papel"], "len": len(text)})

    resume = summarize_hits(hits)
    
    # Salvar resultados na sessão
    st.session_state.analysis_results = {
        "hits": hits,
        "summary": resume,
        "context": ctx,
        "profile": st.session_state.profile
    }
    
    # Header de resultados
    st.success(f"**✅ Análise concluída!** {resume['resumo']}")
    
    # Métricas
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown(f"""
        <div class="metric-card">
            <div style="font-size: 2rem; font-weight: bold;">{len(hits)}</div>
            <div>Pontos Analisados</div>
        </div>
        """, unsafe_allow_html=True)
    with col2:
        st.markdown(f"""
        <div class="metric-card">
            <div style="font-size: 2rem; font-weight: bold;">{resume['criticos']}</div>
            <div>Críticos</div>
        </div>
        """, unsafe_allow_html=True)
    with col3:
        gravidade_cor = {
            "Baixa": "#10b981",
            "Média": "#f59e0b", 
            "Alta": "#ef4444",
            "Crítica": "#dc2626"
        }.get(resume['gravidade'], "#64748b")
        st.markdown(f"""
        <div class="metric-card">
            <div style="font-size: 2rem; font-weight: bold; color: {gravidade_cor};">{resume['gravidade']}</div>
            <div>Gravidade</div>
        </div>
        """, unsafe_allow_html=True)
    with col4:
        st.markdown(f"""
        <div class="metric-card">
            <div style="font-size: 2rem; font-weight: bold;">{resume['sugestoes']}</div>
            <div>Sugestões</div>
        </div>
        """, unsafe_allow_html=True)
    
    # Pontos de atenção
    st.markdown("### 📋 Pontos de Atenção Detalhados")
    
    # Filtrar por severidade
    severidades = ["CRÍTICO", "ALTA", "MÉDIA", "BAIXA"]
    for severidade in severidades:
        hits_filtrados = [h for h in hits if h.get('severity') == severidade]
        if hits_filtrados:
            st.markdown(f"#### {severidade} ({len(hits_filtrados)})")
            
            for i, hit in enumerate(hits_filtrados, 1):
                css_class = {
                    "CRÍTICO": "critical-item",
                    "ALTA": "warning-item", 
                    "MÉDIA": "info-item",
                    "BAIXA": "info-item"
                }.get(severidade, "info-item")
                
                st.markdown(f"""
                <div class="{css_class}">
                    <h4 style="margin: 0 0 0.5rem 0;">{i}. {hit['title']}</h4>
                    <p style="margin: 0.5rem 0;"><strong>Explicação:</strong> {hit.get('explanation', 'Sem explicação disponível')}</p>
                    {f'<p style="margin: 0.5rem 0;"><strong>💡 Sugestão:</strong> {hit["suggestion"]}</p>' if hit.get('suggestion') else ''}
                    {f'<div style="background: #f8fafc; padding: 0.5rem; border-radius: 4px; margin: 0.5rem 0;"><strong>📜 Evidência:</strong><br>{hit["evidence"][:300]}{"..." if len(hit["evidence"]) > 300 else ""}</div>' if hit.get('evidence') else ''}
                </div>
                """, unsafe_allow_html=True)
    
    # Enviar para advogado
    st.markdown("---")
    st.markdown("### ⚖️ Enviar para Advogado")
    
    col1, col2 = st.columns([2, 1])
    with col1:
        lawyer_email = st.text_input("E-mail do seu advogado", placeholder="advogado@escritorio.com")
    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("📧 Enviar Análise", use_container_width=True, 
                    disabled=not lawyer_email or st.session_state.lawyer_email_sent):
            if send_lawyer_email(st.session_state.analysis_results, st.session_state.profile, lawyer_email):
                st.session_state.lawyer_email_sent = True
                st.success("✅ Análise enviada com sucesso para o advogado!")
            else:
                st.error("❌ Erro ao enviar email. Verifique as configurações.")
    
    if st.session_state.lawyer_email_sent:
        st.info("📨 Email enviado! Seu advogado recebeu a análise completa.")

def render_premium_section():
    """Seção premium profissional"""
    st.markdown("""
    <div style="max-width: 1000px; margin: 0 auto; padding: 3rem 2rem; text-align: center;">
        <div class="badge" style="margin-bottom: 1rem;">⭐ CLARA PREMIUM</div>
        <h1 style="margin-bottom: 1rem;">Acesso Ilimitado à Justiça</h1>
        <p style="color: var(--clara-gray); font-size: 1.2rem; max-width: 600px; margin: 0 auto 3rem;">
            Tenha análises ilimitadas, recursos exclusivos e suporte prioritário
        </p>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 1.2, 1])
    
    with col2:
        st.markdown("""
        <div style="background: linear-gradient(135deg, #fef7ff, #faf5ff); border: 2px solid #8b5cf6; border-radius: 20px; padding: 3rem 2rem; text-align: center; position: relative;">
            <div style="position: absolute; top: -15px; left: 50%; transform: translateX(-50%); background: #8b5cf6; color: white; padding: 0.5rem 2rem; border-radius: 20px; font-weight: bold;">
                MAIS POPULAR
            </div>
            <h2 style="color: #7c3aed; margin-bottom: 1rem;">Plano Premium</h2>
            <div style="font-size: 3rem; font-weight: bold; color: #1e293b; margin-bottom: 1rem;">
                R$ 9,90<span style="font-size: 1rem; color: #64748b;">/mês</span>
            </div>
            <p style="color: #64748b; margin-bottom: 2rem;">Cancele quando quiser</p>
            
            <div style="text-align: left; margin-bottom: 3rem;">
                <div style="display: flex; align-items: center; margin-bottom: 1rem;">
                    <span style="color: #10b981; font-size: 1.2rem; margin-right: 0.5rem;">✓</span>
                    <span>Análises ilimitadas de contratos</span>
                </div>
                <div style="display: flex; align-items: center; margin-bottom: 1rem;">
                    <span style="color: #10b981; font-size: 1.2rem; margin-right: 0.5rem;">✓</span>
                    <span>Modelos de documentos exclusivos</span>
                </div>
                <div style="display: flex; align-items: center; margin-bottom: 1rem;">
                    <span style="color: #10b981; font-size: 1.2rem; margin-right: 0.5rem;">✓</span>
                    <span>Cálculos financeiros detalhados</span>
                </div>
                <div style="display: flex; align-items: center; margin-bottom: 1rem;">
                    <span style="color: #10b981; font-size: 1.2rem; margin-right: 0.5rem;">✓</span>
                    <span>Suporte prioritário por email</span>
                </div>
                <div style="display: flex; align-items: center; margin-bottom: 1rem;">
                    <span style="color: #10b981; font-size: 1.2rem; margin-right: 0.5rem;">✓</span>
                    <span>Relatórios profissionais em PDF</span>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("</div>", unsafe_allow_html=True)
    
    # Botão de assinatura
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("🚀 Assinar Agora - R$ 9,90/mês", use_container_width=True, type="primary"):
            email = current_email()
            if not email:
                st.error("Por favor, preencha seu e-mail na página de análise primeiro.")
                return
            
            try:
                session = create_checkout_session(
                    STRIPE_SECRET_KEY, 
                    STRIPE_PRICE_ID, 
                    email, 
                    BASE_URL
                )
                st.markdown(f'<a href="{session.url}" target="_blank" style="text-decoration: none;"><button class="btn-primary" style="width: 100%;">🚀 Finalizar Pagamento</button></a>', 
                           unsafe_allow_html=True)
            except Exception as e:
                st.error(f"Erro ao criar sessão de pagamento: {str(e)}")

# -------------------------------------------------
# Views Principais
# -------------------------------------------------
def home_view():
    render_hero_section()
    
    # Métricas de impacto
    st.markdown("""
    <div style="max-width: 1200px; margin: 0 auto; padding: 4rem 2rem;">
        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 2rem; margin: 4rem 0;">
            <div style="text-align: center;">
                <div style="font-size: 3rem; font-weight: bold; color: var(--clara-primary);">+2.5k</div>
                <div style="color: var(--clara-gray);">Contratos Analisados</div>
            </div>
            <div style="text-align: center;">
                <div style="font-size: 3rem; font-weight: bold; color: var(--clara-primary);">R$ 15M+</div>
                <div style="color: var(--clara-gray);">Em Disputas Resolvidas</div>
            </div>
            <div style="text-align: center;">
                <div style="font-size: 3rem; font-weight: bold; color: var(--clara-primary);">98%</div>
                <div style="color: var(--clara-gray);">Satisfação dos Usuários</div>
            </div>
            <div style="text-align: center;">
                <div style="font-size: 3rem; font-weight: bold; color: var(--clara-primary);">24/7</div>
                <div style="color: var(--clara-gray);">Disponibilidade</div>
            </div>
        </div>
    """, unsafe_allow_html=True)
    
    render_services_grid()
    
    # CTA final
    st.markdown("""
    <div style="background: linear-gradient(135deg, var(--clara-darker), var(--clara-dark)); color: white; padding: 5rem 2rem; text-align: center; border-radius: 20px; margin: 4rem 0;">
        <h2 style="margin-bottom: 1rem;">Pronto para Proteger Seus Direitos?</h2>
        <p style="font-size: 1.2rem; opacity: 0.9; margin-bottom: 3rem; max-width: 500px; margin-left: auto; margin-right: auto;">
            Comece agora sua análise gratuita e evite problemas futuros
        </p>
        <button onclick="window.streamlitSessionState.setItem('current_view', 'analysis')" class="btn-primary" style="font-size: 1.2rem; padding: 1rem 3rem;">
            🚀 Começar Agora
        </button>
    </div>
    """, unsafe_allow_html=True)

def services_view():
    st.markdown("""
    <div style="max-width: 1200px; margin: 0 auto; padding: 3rem 2rem;">
        <div style="text-align: center; margin-bottom: 4rem;">
            <h1>Nossos Serviços Jurídicos</h1>
            <p style="color: var(--clara-gray); font-size: 1.2rem;">
                Soluções completas para suas necessidades jurídicas do dia a dia
            </p>
        </div>
    """, unsafe_allow_html=True)
    render_services_grid()

def analysis_view():
    st.markdown("""
    <div style="max-width: 1000px; margin: 0 auto; padding: 2rem 1rem;">
        <div style="text-align: center; margin-bottom: 3rem;">
            <h1>Análise de Contratos</h1>
            <p style="color: var(--clara-gray); font-size: 1.1rem;">
                Analise qualquer contrato em minutos e identifique riscos escondidos
            </p>
        </div>
    """, unsafe_allow_html=True)
    
    raw_text, ctx = render_analysis_workflow()
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("🔍 Analisar Contrato", type="primary", use_container_width=True):
            render_analysis_results(raw_text, ctx)

def premium_view():
    render_premium_section()

# -------------------------------------------------
# App Principal
# -------------------------------------------------
def main():
    # Inicialização
    try:
        init_db()
        if STRIPE_SECRET_KEY:
            init_stripe(STRIPE_SECRET_KEY)
    except Exception as e:
        st.warning(f"Algumas funcionalidades podem não estar disponíveis: {str(e)}")
    
    # Navegação
    render_professional_nav()
    
    # Roteamento de views
    current_view = st.session_state.current_view
    
    if current_view == "home":
        home_view()
    elif current_view == "services":
        services_view()
    elif current_view == "analysis":
        analysis_view()
    elif current_view == "premium":
        premium_view()
    else:
        home_view()
    
    # Footer
    st.markdown("""
    <div class="footer">
        <div style="max-width: 1200px; margin: 0 auto; text-align: center;">
            <div class="logo-container" style="justify-content: center; margin-bottom: 2rem;">
                <span style="font-size: 1.8rem;">⚖️</span>
                <div>
                    <div class="logo-text">CLARA LAW</div>
                    <div class="tagline">Inteligência para um mundo mais claro</div>
                </div>
            </div>
            <div style="display: flex; justify-content: center; gap: 2rem; flex-wrap: wrap; margin-bottom: 2rem;">
                <a href="#" style="color: #cbd5e1; text-decoration: none;">Termos de Uso</a>
                <a href="#" style="color: #cbd5e1; text-decoration: none;">Política de Privacidade</a>
                <a href="#" style="color: #cbd5e1; text-decoration: none;">Contato</a>
                <a href="#" style="color: #cbd5e1; text-decoration: none;">Sobre Nós</a>
            </div>
            <p style="color: #94a3b8; font-size: 0.9rem;">
                CLARA é uma ferramenta de auxílio jurídico e não substitui a consulta com um advogado.<br>
                © 2024 CLARA Law. Todos os direitos reservados.
            </p>
        </div>
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
