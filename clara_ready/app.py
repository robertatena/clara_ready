# app.py — CLARA • Sua Assistente Jurídica Pessoal
# Versão completa com serviços funcionais + casos campeões

import os
import io
import re
import csv
import json
import base64
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Any, Tuple, Set, List
import streamlit as st

# ---- módulos locais ----
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
VERSION = "v3.0"

st.set_page_config(page_title=APP_TITLE, page_icon="⚖️", layout="wide")

# Secrets
STRIPE_PUBLIC_KEY = st.secrets.get("STRIPE_PUBLIC_KEY", "")
STRIPE_SECRET_KEY = st.secrets.get("STRIPE_SECRET_KEY", "")
STRIPE_PRICE_ID = st.secrets.get("STRIPE_PRICE_ID", "")
BASE_URL = st.secrets.get("BASE_URL", "https://claraready.streamlit.app")

MONTHLY_PRICE_TEXT = "R$ 9,90/mês"

# -------------------------------------------------
# Estilo Moderno + CLARA Identity
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
        --clara-success: #10b981;
        --clara-warning: #f59e0b;
        --clara-danger: #ef4444;
    }
    
    .clara-hero {
        background: linear-gradient(135deg, var(--clara-dark) 0%, #1e293b 100%);
        color: white;
        padding: 4rem 0;
        text-align: center;
        border-radius: 0 0 20px 20px;
        position: relative;
        overflow: hidden;
    }
    
    .clara-hero::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: url("data:image/svg+xml,%3Csvg width='100' height='100' viewBox='0 0 100 100' xmlns='http://www.w3.org/2000/svg'%3E%3Cpath d='M11 18c3.866 0 7-3.134 7-7s-3.134-7-7-7-7 3.134-7 7 3.134 7 7 7zm48 25c3.866 0 7-3.134 7-7s-3.134-7-7-7-7 3.134-7 7 3.134 7 7 7zm-43-7c1.657 0 3-1.343 3-3s-1.343-3-3-3-3 1.343-3 3 1.343 3 3 3zm63 31c1.657 0 3-1.343 3-3s-1.343-3-3-3-3 1.343-3 3 1.343 3 3 3zM34 90c1.657 0 3-1.343 3-3s-1.343-3-3-3-3 1.343-3 3 1.343 3 3 3zm56-76c1.657 0 3-1.343 3-3s-1.343-3-3-3-3 1.343-3 3 1.343 3 3 3zM12 86c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm28-65c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm23-11c2.76 0 5-2.24 5-5s-2.24-5-5-5-5 2.24-5 5 2.24 5 5 5zm-6 60c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm29 22c2.76 0 5-2.24 5-5s-2.24-5-5-5-5 2.24-5 5 2.24 5 5 5zM32 63c2.76 0 5-2.24 5-5s-2.24-5-5-5-5 2.24-5 5 2.24 5 5 5zm57-13c2.76 0 5-2.24 5-5s-2.24-5-5-5-5 2.24-5 5 2.24 5 5 5zm-9-21c1.105 0 2-.895 2-2s-.895-2-2-2-2 .895-2 2 .895 2 2 2zM60 91c1.105 0 2-.895 2-2s-.895-2-2-2-2 .895-2 2 .895 2 2 2zM35 41c1.105 0 2-.895 2-2s-.895-2-2-2-2 .895-2 2 .895 2 2 2zM12 60c1.105 0 2-.895 2-2s-.895-2-2-2-2 .895-2 2 .895 2 2 2z' fill='%23d4af37' fill-opacity='0.1' fill-rule='evenodd'/%3E%3C/svg%3E");
        opacity: 0.3;
    }
    
    .clara-hero-content {
        max-width: 800px;
        margin: 0 auto;
        padding: 0 2rem;
        position: relative;
        z-index: 2;
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
        transition: transform 0.2s ease;
        height: 100%;
        display: flex;
        flex-direction: column;
    }
    
    .clara-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 30px rgba(0,0,0,0.12);
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
        transition: all 0.3s ease !important;
    }
    
    .clara-btn-primary:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(212, 175, 55, 0.3) !important;
    }
    
    .clara-step {
        display: flex;
        align-items: center;
        margin: 1rem 0;
        padding: 1.5rem;
        background: var(--clara-light);
        border-radius: 12px;
        border-left: 4px solid var(--clara-gold);
    }
    
    .clara-step-number {
        background: var(--clara-gold);
        color: var(--clara-dark);
        width: 40px;
        height: 40px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        font-weight: bold;
        margin-right: 1rem;
        font-size: 1.2rem;
    }
    
    .service-active {
        border: 2px solid var(--clara-gold);
        background: #fffbf0;
    }
    
    .result-success {
        border-left: 4px solid var(--clara-success);
        background: #f0fdf4;
    }
    
    .result-warning {
        border-left: 4px solid var(--clara-warning);
        background: #fffbeb;
    }
    
    .result-danger {
        border-left: 4px solid var(--clara-danger);
        background: #fef2f2;
    }
    
    .logo-container {
        display: flex;
        align-items: center;
        gap: 10px;
    }
    
    .logo-text {
        font-size: 1.8rem;
        font-weight: 700;
        color: var(--clara-gold);
        margin: 0;
    }
    
    .logo-subtitle {
        font-size: 0.8rem;
        color: var(--clara-gray);
        margin: 0;
        line-height: 1.2;
    }
    
    .premium-badge {
        background: linear-gradient(135deg, #D4AF37, #F7EF8A);
        color: var(--clara-dark);
        padding: 0.3rem 0.8rem;
        border-radius: 20px;
        font-weight: 600;
        font-size: 0.7rem;
        margin-left: 0.5rem;
    }
    
    .user-profile {
        display: flex;
        align-items: center;
        gap: 10px;
        padding: 0.5rem 1rem;
        background: var(--clara-light);
        border-radius: 10px;
        border: 1px solid #e2e8f0;
    }
    
    .user-avatar {
        width: 32px;
        height: 32px;
        border-radius: 50%;
        background: var(--clara-gold);
        display: flex;
        align-items: center;
        justify-content: center;
        color: var(--clara-dark);
        font-weight: bold;
    }
    
    .stats-container {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
        gap: 1rem;
        margin: 2rem 0;
    }
    
    .stat-card {
        background: white;
        border-radius: 12px;
        padding: 1.5rem;
        box-shadow: 0 2px 10px rgba(0,0,0,0.05);
        border-left: 4px solid var(--clara-gold);
        text-align: center;
    }
    
    .stat-value {
        font-size: 2rem;
        font-weight: 700;
        color: var(--clara-dark);
        margin: 0.5rem 0;
    }
    
    .stat-label {
        color: var(--clara-gray);
        font-size: 0.9rem;
    }
    
    .footer {
        text-align: center;
        padding: 2rem 0;
        margin-top: 3rem;
        border-top: 1px solid #e2e8f0;
        color: var(--clara-gray);
    }
    
    .testimonial-card {
        background: white;
        border-radius: 12px;
        padding: 1.5rem;
        box-shadow: 0 4px 15px rgba(0,0,0,0.08);
        margin: 1rem 0;
        border-top: 4px solid var(--clara-gold);
    }
    
    .testimonial-text {
        font-style: italic;
        margin-bottom: 1rem;
        color: var(--clara-gray);
    }
    
    .testimonial-author {
        font-weight: 600;
        color: var(--clara-dark);
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# -------------------------------------------------
# Estado da Sessão
# -------------------------------------------------
if "current_view" not in st.session_state:
    st.session_state.current_view = "home"
if "profile" not in st.session_state:
    st.session_state.profile = {"nome": "", "email": "", "cel": ""}
if "premium" not in st.session_state:
    st.session_state.premium = False
if "free_runs_left" not in st.session_state:
    st.session_state.free_runs_left = 3
if "service_data" not in st.session_state:
    st.session_state.service_data = {}
if "active_service" not in st.session_state:
    st.session_state.active_service = None
if "user_logged_in" not in st.session_state:
    st.session_state.user_logged_in = False

# -------------------------------------------------
# Serviços - Casos Campeões
# -------------------------------------------------
SERVICES = {
    "cancelamento_assinaturas": {
        "title": "📝 Cancelamento de Assinaturas",
        "icon": "📝",
        "description": "Cancele academias, apps, TV e serviços de telefonia com argumentos jurídicos",
        "category": "Consumidor",
        "steps": [
            "Informe os dados do serviço",
            "Descreva o problema",
            "Gere sua carta de cancelamento"
        ]
    },
    "cobranca_indevida": {
        "title": "💳 Cobrança Indevida",
        "icon": "💳",
        "description": "Dispute cobranças abusivas de bancos, cartões e consignados",
        "category": "Financeiro",
        "steps": [
            "Informe os dados da cobrança",
            "Descreva o problema",
            "Gere seu recurso"
        ]
    },
    "juros_abusivos": {
        "title": "📊 Juros Abusivos & CET",
        "icon": "📊",
        "description": "Calcule juros abusivos e gere cartas para renegociação",
        "category": "Financeiro",
        "steps": [
            "Informe os dados do empréstimo",
            "Calcule o CET real",
            "Gere sua carta de reclamação"
        ]
    },
    "transporte_aereo": {
        "title": "✈️ Transporte Aéreo (ANAC)",
        "icon": "✈️",
        "description": "Resolva problemas com atrasos, cancelamentos e extravios de bagagem",
        "category": "Consumidor",
        "steps": [
            "Informe os dados do voo",
            "Descreva o problema",
            "Gere sua reclamação na ANAC"
        ]
    },
    "telecom": {
        "title": "📞 Telecom (ANATEL)",
        "icon": "📞",
        "description": "Resolva problemas com internet, telefone e TV por assinatura",
        "category": "Consumidor",
        "steps": [
            "Informe os dados do serviço",
            "Descreva o problema",
            "Gere sua reclamação na ANATEL"
        ]
    },
    "energia_agua": {
        "title": "💡 Energia & Água",
        "icon": "💡",
        "description": "Dispute contas abusivas de energia elétrica e água",
        "category": "Consumidor",
        "steps": [
            "Informe os dados da conta",
            "Descreva o problema",
            "Gere seu recurso à agência reguladora"
        ]
    },
    "analise_contratos": {
        "title": "📄 Análise de Contratos",
        "icon": "📄",
        "description": "Analise contratos complexos e identifique cláusulas problemáticas",
        "category": "Jurídico",
        "steps": [
            "Envie o contrato",
            "Configure a análise",
            "Revise os resultados"
        ]
    }
}

# -------------------------------------------------
# Utils
# -------------------------------------------------
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
PHONE_RE = re.compile(r"^\+?\d{10,15}$")

def current_email() -> str:
    return (st.session_state.profile.get("email") or "").strip().lower()

def is_valid_email(v: str) -> bool:
    return bool(EMAIL_RE.match((v or "").strip()))

def is_valid_phone(v: str) -> bool:
    digits = re.sub(r"\D", "", v or "")
    return bool(PHONE_RE.match(digits))

def is_premium() -> bool:
    return st.session_state.premium

# -------------------------------------------------
# Templates de Documentos
# -------------------------------------------------
def generate_cancellation_letter(service_data: Dict) -> str:
    return f"""
CARTA DE CANCELAMENTO - {service_data.get('servico', '').upper()}

De: {service_data.get('nome', '')}
E-mail: {service_data.get('email', '')}
CPF: {service_data.get('cpf', '')}

Para: {service_data.get('empresa', '')}
CNPJ: {service_data.get('cnpj', '')}

Assunto: Cancelamento de assinatura/serviço

Prezados Senhores,

Venho por meio desta comunicar o CANCELAMENTO imediato da assinatura/serviço contratado junto à empresa {service_data.get('empresa', '')}, referente ao serviço: {service_data.get('servico', '')}.

DADOS DO CONTRATO:
- Número do contrato: {service_data.get('numero_contrato', 'Não informado')}
- Data de início: {service_data.get('data_inicio', 'Não informada')}
- Motivo do cancelamento: {service_data.get('motivo', '')}

{service_data.get('detalhes', '')}

Com fundamento no Código de Defesa do Consumidor (Lei 8.078/90), em especial nos artigos 39 e 42, solicito:

1. O cancelamento imediato do serviço;
2. O bloqueio de quaisquer cobranças futuras;
3. A confirmação do cancelamento por e-mail;
4. O reembolso proporcional de eventuais valores pagos antecipadamente, se for o caso.

Atenciosamente,

{service_data.get('nome', '')}
{service_data.get('email', '')}
{service_data.get('telefone', '')}
"""

def generate_anac_complaint(service_data: Dict) -> str:
    return f"""
RECLAMAÇÃO ANAC - {service_data.get('companhia', '').upper()}

DADOS DO PASSAGEIRO:
Nome: {service_data.get('nome', '')}
CPF: {service_data.get('cpf', '')}
E-mail: {service_data.get('email', '')}
Telefone: {service_data.get('telefone', '')}

DADOS DO VOO:
Companhia Aérea: {service_data.get('companhia', '')}
Número do Voo: {service_data.get('numero_voo', '')}
Data do Voo: {service_data.get('data_voo', '')}
Origem: {service_data.get('origem', '')}
Destino: {service_data.get('destino', '')}

DESCRIÇÃO DO PROBLEMA:
Tipo: {service_data.get('problema', '')}
Descrição detalhada: {service_data.get('detalhes', '')}
Data/Hora do ocorrido: {service_data.get('data_ocorrido', '')}

PREJUÍZOS IDENTIFICADOS:
{service_data.get('prejuizos', '')}

COM BASE NA RESOLUÇÃO ANAC 400/2016, SOLICITO:

1. {service_data.get('solicitacao1', 'Providências imediatas para resolver o ocorrido')}
2. {service_data.get('solicitacao2', 'Indenização conforme previsto em lei')}
3. {service_data.get('solicitacao3', 'Resposta formal em até 30 dias')}

Atenciosamente,

{service_data.get('nome', '')}
"""

def generate_anatel_complaint(service_data: Dict) -> str:
    return f"""
RECLAMAÇÃO ANATEL - {service_data.get('operadora', '').upper()}

DADOS DO CLIENTE:
Nome: {service_data.get('nome', '')}
CPF: {service_data.get('cpf', '')}
E-mail: {service_data.get('email', '')}
Telefone: {service_data.get('telefone', '')}

DADOS DO SERVIÇO:
Operadora: {service_data.get('operadora', '')}
Tipo de Serviço: {service_data.get('tipo_servico', '')}
Número do Contrato: {service_data.get('numero_contrato', '')}
Endereço de Instalação: {service_data.get('endereco', '')}

DESCRIÇÃO DO PROBLEMA:
{service_data.get('problema', '')}

Data do início do problema: {service_data.get('data_inicio', '')}
Já contactou a operadora? {service_data.get('contatou_operadora', 'Não')}
Protocolo na operadora: {service_data.get('protocolo_operadora', 'Não informado')}

DETALHES:
{service_data.get('detalhes', '')}

SOLICITAÇÃO:
De acordo com o Código de Defesa do Consumidor e regulamentação da ANATEL, solicito:

1. {service_data.get('solicitacao1', 'Solução imediata do problema relatado')}
2. {service_data.get('solicitacao2', 'Indenização pelos danos sofridos')}
3. {service_data.get('solicitacao3', 'Cancelamento sem multa, se for o caso')}

Atenciosamente,

{service_data.get('nome', '')}
"""

# -------------------------------------------------
# Componentes de Interface
# -------------------------------------------------
def render_logo():
    """Renderiza o logo da CLARA LAW"""
    st.markdown("""
    <div class="logo-container">
        <div>
            <div class="logo-text">CLARA LAW</div>
            <div class="logo-subtitle">Inteligência para um mundo mais claro</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

def render_navigation():
    """Navegação principal"""
    col1, col2, col3, col4, col5 = st.columns([2, 1, 1, 1, 1.5])
    
    with col1:
        render_logo()
    
    with col2:
        if st.button("🏠 Início", use_container_width=True, key="nav_home"):
            st.session_state.current_view = "home"
            st.session_state.active_service = None
            st.rerun()
    
    with col3:
        if st.button("🛡️ Serviços", use_container_width=True, key="nav_services"):
            st.session_state.current_view = "services"
            st.session_state.active_service = None
            st.rerun()
    
    with col4:
        if st.button("⭐ Premium", use_container_width=True, key="nav_premium"):
            st.session_state.current_view = "premium"
            st.rerun()
    
    with col5:
        if st.session_state.user_logged_in:
            user_name = st.session_state.profile.get('nome', 'Usuário')
            user_initials = user_name[:2].upper() if user_name else "US"
            
            st.markdown(f"""
            <div class="user-profile">
                <div class="user-avatar">{user_initials}</div>
                <div>
                    <div style="font-weight: 600; font-size: 0.9rem;">{user_name}</div>
                    <div style="font-size: 0.7rem; color: var(--clara-gray);">
                        {st.session_state.premium and '⭐ Premium' or '🔓 Básico'}
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)
        else:
            if st.button("🔐 Entrar", use_container_width=True, key="nav_login"):
                st.session_state.current_view = "login"
                st.rerun()

def render_hero_section():
    """Hero section impactante"""
    st.markdown("""
    <div class="clara-hero">
        <div class="clara-hero-content">
            <div class="clara-badge">⚖️ ASSISTENTE JURÍDICA PESSOAL</div>
            <h1 class="clara-title">Resolva problemas jurídicos sem advogado caro</h1>
            <p class="clara-subtitle">
                Use a inteligência artificial da CLARA para cancelar assinaturas, disputar cobranças, 
                reclamar de voos atrasados e muito mais. Rápido, simples e eficaz.
            </p>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("👉 Ver Serviços Disponíveis", use_container_width=True, type="primary"):
            st.session_state.current_view = "services"
            st.rerun()
    
    st.markdown("</div></div>", unsafe_allow_html=True)

def render_stats():
    """Estatísticas da plataforma"""
    st.markdown('<div class="stats-container">', unsafe_allow_html=True)
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown("""
        <div class="stat-card">
            <div class="stat-value">2.5k+</div>
            <div class="stat-label">Casos Resolvidos</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown("""
        <div class="stat-card">
            <div class="stat-value">R$ 1.2M</div>
            <div class="stat-label">Economizados</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown("""
        <div class="stat-card">
            <div class="stat-value">98%</div>
            <div class="stat-label">Taxa de Sucesso</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col4:
        st.markdown("""
        <div class="stat-card">
            <div class="stat-value">4.9★</div>
            <div class="stat-label">Avaliação dos Usuários</div>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown('</div>', unsafe_allow_html=True)

def render_testimonials():
    """Depoimentos de clientes"""
    st.markdown("""
    <div style="margin: 3rem 0;">
        <h2 style="text-align: center; margin-bottom: 2rem;">O que nossos clientes dizem</h2>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("""
        <div class="testimonial-card">
            <div class="testimonial-text">
                "Consegui cancelar minha academia que insistia em cobrar mesmo após o cancelamento. A CLARA me deu os argumentos jurídicos perfeitos!"
            </div>
            <div class="testimonial-author">- Maria S., São Paulo</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown("""
        <div class="testimonial-card">
            <div class="testimonial-text">
                "Economizei R$ 3.200 em juros abusivos de um empréstimo. A calculadora de CET foi fundamental para minha negociação."
            </div>
            <div class="testimonial-author">- João P., Rio de Janeiro</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown("""
        <div class="testimonial-card">
            <div class="testimonial-text">
                "Meu voo atrasou 6 horas e com a CLARA consegui uma indenização de R$ 1.800 da companhia aérea. Processo super simples!"
            </div>
            <div class="testimonial-author">- Ana L., Brasília</div>
        </div>
        """, unsafe_allow_html=True)

def render_services_grid():
    """Grid de serviços funcionais"""
    st.markdown("""
    <div style='text-align: center; margin: 3rem 0;'>
        <h2>Como a CLARA pode te ajudar hoje?</h2>
        <p>Escolha o serviço que você precisa:</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Filtros por categoria
    categories = list(set([service["category"] for service in SERVICES.values()]))
    selected_category = st.selectbox("Filtrar por categoria:", ["Todos"] + categories)
    
    st.markdown('<div class="clara-service-grid">', unsafe_allow_html=True)
    
    cols = st.columns(3)
    col_idx = 0
    
    for service_id, service in SERVICES.items():
        if selected_category != "Todos" and service["category"] != selected_category:
            continue
            
        with cols[col_idx]:
            is_active = st.session_state.active_service == service_id
            card_class = "clara-card service-active" if is_active else "clara-card"
            
            st.markdown(f"""
            <div class="{card_class}">
                <div style='text-align: center;'>
                    <div class="clara-feature-icon">{service['icon']}</div>
                    <h3>{service['title']}</h3>
                    <p style='color: var(--clara-gray); margin-bottom: 1.5rem;'>{service['description']}</p>
                    <small style='color: var(--clara-gold); font-weight: 600;'>{service['category']}</small>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            if st.button(f"Usar {service['title'].split(' ')[0]}", key=f"btn_{service_id}", use_container_width=True):
                if not st.session_state.user_logged_in:
                    st.session_state.current_view = "login"
                    st.rerun()
                else:
                    st.session_state.active_service = service_id
                    st.session_state.current_view = "service_detail"
                    st.rerun()
        
        col_idx = (col_idx + 1) % 3

def render_login():
    """Página de login/cadastro"""
    st.markdown("""
    <div style="max-width: 500px; margin: 0 auto;">
        <h1 style="text-align: center; margin-bottom: 2rem;">Acesse sua conta CLARA</h1>
    </div>
    """, unsafe_allow_html=True)
    
    tab1, tab2 = st.tabs(["🔐 Entrar", "📝 Cadastrar"])
    
    with tab1:
        with st.form("login_form"):
            email = st.text_input("E-mail")
            senha = st.text_input("Senha", type="password")
            
            if st.form_submit_button("Entrar", use_container_width=True):
                # Simulação de login bem-sucedido
                if email and senha:
                    st.session_state.user_logged_in = True
                    st.session_state.profile = {
                        "nome": "João Silva",
                        "email": email,
                        "cel": "(11) 99999-9999"
                    }
                    st.session_state.current_view = "home"
                    st.rerun()
                else:
                    st.error("Por favor, preencha todos os campos")
    
    with tab2:
        with st.form("register_form"):
            col1, col2 = st.columns(2)
            with col1:
                nome = st.text_input("Nome completo")
            with col2:
                cel = st.text_input("Celular")
            
            email = st.text_input("E-mail")
            senha = st.text_input("Senha", type="password")
            confirmar_senha = st.text_input("Confirmar senha", type="password")
            
            if st.form_submit_button("Criar conta", use_container_width=True):
                if nome and email and cel and senha and confirmar_senha:
                    if senha == confirmar_senha:
                        st.session_state.user_logged_in = True
                        st.session_state.profile = {
                            "nome": nome,
                            "email": email,
                            "cel": cel
                        }
                        st.session_state.current_view = "home"
                        st.rerun()
                    else:
                        st.error("As senhas não coincidem")
                else:
                    st.error("Por favor, preencha todos os campos")
    
    st.markdown("---")
    st.markdown("""
    <div style="text-align: center;">
        <p>Ou continue sem cadastro (limite de 3 análises gratuitas)</p>
    </div>
    """, unsafe_allow_html=True)
    
    if st.button("➡️ Continuar sem cadastro", use_container_width=True):
        st.session_state.current_view = "services"
        st.rerun()

def render_premium():
    """Página de assinatura premium"""
    st.markdown("""
    <div style="text-align: center; margin-bottom: 3rem;">
        <h1>⭐ CLARA Premium</h1>
        <p>Desbloqueie todo o potencial da sua assistente jurídica</p>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.markdown("""
        <div class="clara-card">
            <h3 style="text-align: center;">🔓 Plano Gratuito</h3>
            <div style="text-align: center; margin: 2rem 0;">
                <div style="font-size: 2rem; font-weight: 700;">R$ 0</div>
                <div style="color: var(--clara-gray);">para sempre</div>
            </div>
            <ul style="padding-left: 1.5rem;">
                <li>3 análises gratuitas por mês</li>
                <li>Acesso aos serviços básicos</li>
                <li>Modelos de documentos padrão</li>
                <li>Suporte por e-mail</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown("""
        <div class="clara-card" style="border: 2px solid var(--clara-gold); position: relative;">
            <div style="position: absolute; top: -10px; left: 50%; transform: translateX(-50%);">
                <span class="premium-badge">MAIS POPULAR</span>
            </div>
            <h3 style="text-align: center;">⭐ CLARA Premium</h3>
            <div style="text-align: center; margin: 2rem 0;">
                <div style="font-size: 2rem; font-weight: 700;">R$ 9,90</div>
                <div style="color: var(--clara-gray);">por mês</div>
            </div>
            <ul style="padding-left: 1.5rem;">
                <li><strong>Análises ilimitadas</strong></li>
                <li>Todos os serviços disponíveis</li>
                <li>Modelos de documentos personalizados</li>
                <li>Análise de contratos avançada</li>
                <li>Suporte prioritário</li>
                <li>Calculadora de CET completa</li>
                <li>Cancelamento a qualquer momento</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    st.markdown("""
    <div style="text-align: center; margin: 2rem 0;">
        <h3>Pronto para desbloquear todo o potencial da CLARA?</h3>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("🔄 Assinar CLARA Premium", use_container_width=True, type="primary"):
            st.session_state.premium = True
            st.success("✅ Parabéns! Você agora é um usuário CLARA Premium!")
            st.balloons()

def render_service_detail():
    """Detalhe do serviço selecionado"""
    service_id = st.session_state.active_service
    service = SERVICES.get(service_id)
    
    if not service:
        st.error("Serviço não encontrado")
        return
    
    st.markdown(f"""
    <div style="margin-bottom: 2rem;">
        <h1>{service['icon']} {service['title']}</h1>
        <p style="font-size: 1.1rem; color: var(--clara-gray);">{service['description']}</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Mostrar etapas do processo
    st.markdown("### Como funciona:")
    for i, step in enumerate(service["steps"], 1):
        st.markdown(f"""
        <div class="clara-step">
            <div class="clara-step-number">{i}</div>
            <div>{step}</div>
        </div>
        """, unsafe_allow_html=True)
    
    # Formulário específico do serviço
    st.markdown("### Preencha os dados:")
    
    with st.form(f"form_{service_id}"):
        # Campos comuns
        col1, col2 = st.columns(2)
        with col1:
            nome = st.text_input("Nome completo", value=st.session_state.profile.get("nome", ""))
        with col2:
            email = st.text_input("E-mail", value=st.session_state.profile.get("email", ""))
        
        col1, col2 = st.columns(2)
        with col1:
            cpf = st.text_input("CPF")
        with col2:
            telefone = st.text_input("Telefone", value=st.session_state.profile.get("cel", ""))
        
        # Campos específicos por serviço
        if service_id == "cancelamento_assinaturas":
            empresa = st.text_input("Nome da empresa")
            servico = st.text_input("Serviço/Assinatura")
            numero_contrato = st.text_input("Número do contrato (opcional)")
            data_inicio = st.date_input("Data de início")
            motivo = st.selectbox("Motivo do cancelamento", [
                "Serviço não satisfatório",
                "Cobranças indevidas", 
                "Mudança de endereço",
                "Problemas técnicos",
                "Outro"
            ])
            detalhes = st.text_area("Descreva detalhadamente o problema")
            
        elif service_id == "cobranca_indevida":
            empresa = st.text_input("Nome da empresa/banco")
            valor_cobranca = st.number_input("Valor da cobrança (R$)", min_value=0.0, step=0.01)
            data_cobranca = st.date_input("Data da cobrança")
            motivo = st.selectbox("Motivo da contestação", [
                "Cobrança duplicada",
                "Serviço não contratado",
                "Serviço não prestado",
                "Valor incorreto",
                "Outro"
            ])
            detalhes = st.text_area("Descreva detalhadamente o problema")
            
        elif service_id == "juros_abusivos":
            empresa = st.text_input("Nome do banco/financeira")
            valor_emprestimo = st.number_input("Valor do empréstimo (R$)", min_value=0.0, step=0.01)
            parcelas = st.number_input("Número de parcelas", min_value=1, step=1)
            valor_parcela = st.number_input("Valor da parcela (R$)", min_value=0.0, step=0.01)
            cet_informado = st.number_input("CET informado (%)", min_value=0.0, step=0.01)
            detalhes = st.text_area("Observações adicionais")
            
        elif service_id == "transporte_aereo":
            companhia = st.text_input("Companhia aérea")
            numero_voo = st.text_input("Número do voo")
            data_voo = st.date_input("Data do voo")
            origem = st.text_input("Cidade de origem")
            destino = st.text_input("Cidade de destino")
            problema = st.selectbox("Tipo de problema", [
                "Atraso no voo",
                "Cancelamento do voo", 
                "Extravio de bagagem",
                "Overbooking",
                "Má atendimento",
                "Outro"
            ])
            detalhes = st.text_area("Descreva detalhadamente o ocorrido")
            
        elif service_id == "telecom":
            operadora = st.text_input("Operadora")
            tipo_servico = st.selectbox("Tipo de serviço", [
                "Internet banda larga",
                "Telefonia fixa",
                "Telefonia móvel",
                "TV por assinatura",
                "Combos"
            ])
            endereco = st.text_input("Endereço de instalação")
            numero_contrato = st.text_input("Número do contrato")
            problema = st.selectbox("Tipo de problema", [
                "Falha no serviço",
                "Lentidão na internet",
                "Cobranças indevidas",
                "Mau atendimento",
                "Cancelamento solicitado não realizado",
                "Outro"
            ])
            detalhes = st.text_area("Descreva detalhadamente o problema")
            
        elif service_id == "analise_contratos":
            tipo_contrato = st.selectbox("Tipo de contrato", [
                "Contrato de adesão",
                "Contrato de prestação de serviços", 
                "Contrato de compra e venda",
                "Contrato de locação",
                "Contrato de trabalho",
                "Outro"
            ])
            arquivo_contrato = st.file_uploader("Envie o contrato (PDF)", type="pdf")
            detalhes = st.text_area("Alguma cláusula específica que gostaria de analisar?")
        
        # Botão de envio
        if st.form_submit_button("🔄 Gerar Documento", use_container_width=True):
            if not nome or not email:
                st.error("Por favor, preencha pelo menos nome e e-mail")
            else:
                # Salvar dados do serviço
                service_data = {
                    "nome": nome,
                    "email": email,
                    "cpf": cpf,
                    "telefone": telefone,
                    "service_id": service_id,
                    "timestamp": datetime.now().isoformat()
                }
                
                # Adicionar campos específicos
                if service_id == "cancelamento_assinaturas":
                    service_data.update({
                        "empresa": empresa,
                        "servico": servico,
                        "numero_contrato": numero_contrato,
                        "data_inicio": str(data_inicio),
                        "motivo": motivo,
                        "detalhes": detalhes
                    })
                    documento = generate_cancellation_letter(service_data)
                    
                elif service_id == "transporte_aereo":
                    service_data.update({
                        "companhia": companhia,
                        "numero_voo": numero_voo,
                        "data_voo": str(data_voo),
                        "origem": origem,
                        "destino": destino,
                        "problema": problema,
                        "detalhes": detalhes
                    })
                    documento = generate_anac_complaint(service_data)
                    
                elif service_id == "telecom":
                    service_data.update({
                        "operadora": operadora,
                        "tipo_servico": tipo_servico,
                        "endereco": endereco,
                        "numero_contrato": numero_contrato,
                        "problema": problema,
                        "detalhes": detalhes
                    })
                    documento = generate_anatel_complaint(service_data)
                    
                else:
                    documento = f"""
DOCUMENTO GERADO - {service['title']}

Dados fornecidos:
- Nome: {nome}
- E-mail: {email}
- CPF: {cpf}
- Telefone: {telefone}

Detalhes do caso:
{detalhes}

[SEU DOCUMENTO PERSONALIZADO AQUI]
"""
                
                # Mostrar resultado
                st.session_state.service_data = service_data
                st.session_state.generated_document = documento
                st.session_state.current_view = "service_result"
                st.rerun()

def render_service_result():
    """Resultado do serviço com documento gerado"""
    service_id = st.session_state.active_service
    service = SERVICES.get(service_id)
    service_data = st.session_state.service_data
    documento = st.session_state.generated_document
    
    st.markdown(f"""
    <div style="margin-bottom: 2rem;">
        <h1>✅ Documento Gerado com Sucesso!</h1>
        <p style="font-size: 1.1rem; color: var(--clara-gray);">
            Seu {service['title'].lower()} está pronto para uso.
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.markdown("### 📄 Seu documento:")
        st.text_area("Documento gerado", value=documento, height=400, key="documento_gerado")
        
        # Botões de ação
        col_btn1, col_btn2, col_btn3 = st.columns(3)
        with col_btn1:
            st.download_button(
                "📥 Baixar PDF",
                data=documento,
                file_name=f"clara_{service_id}_{datetime.now().strftime('%Y%m%d')}.txt",
                mime="text/plain",
                use_container_width=True
            )
        with col_btn2:
            st.button("📧 Enviar por e-mail", use_container_width=True)
        with col_btn3:
            st.button("🖨️ Imprimir", use_container_width=True)
    
    with col2:
        st.markdown("### 📋 Próximos passos:")
        
        if service_id == "cancelamento_assinaturas":
            st.markdown("""
            1. **Imprima** ou **salve** o documento
            2. **Envie** para a empresa por e-mail registrado
            3. **Guarde** o comprovante de envio
            4. **Acompanhe** o prazo de resposta (até 30 dias)
            5. Caso não respondam, você pode acionar o PROCON
            """)
            
        elif service_id in ["transporte_aereo", "telecom"]:
            st.markdown("""
            1. **Imprima** ou **salve** o documento
            2. **Registre** no site da ANAC/ANATEL
            3. **Anexe** comprovantes se tiver
            4. **Acompanhe** o protocolo
            5. Resposta em até 30 dias úteis
            """)
            
        else:
            st.markdown("""
            1. **Revise** o documento gerado
            2. **Personalize** se necessário
            3. **Envie** para a parte interessada
            4. **Guarde** comprovantes
            5. **Acompanhe** os prazos
            """)
        
        st.markdown("---")
        st.markdown("### 💡 Dica da CLARA:")
        st.info("""
        Sempre guarde comprovantes de envio e resposta. 
        Eles são essenciais caso precise escalar para órgãos de proteção ao consumidor.
        """)
    
    st.markdown("---")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔄 Gerar outro documento", use_container_width=True):
            st.session_state.current_view = "service_detail"
            st.rerun()
    with col2:
        if st.button("🏠 Voltar ao início", use_container_width=True):
            st.session_state.current_view = "home"
            st.session_state.active_service = None
            st.rerun()

def render_footer():
    """Rodapé do site"""
    st.markdown("""
    <div class="footer">
        <div style="margin-bottom: 1rem;">
            <strong>CLARA LAW</strong> - Sua Assistente Jurídica Pessoal
        </div>
        <div style="font-size: 0.8rem; color: var(--clara-gray);">
            © 2024 CLARA • Inteligência para um mundo mais claro • Versão 3.0
        </div>
    </div>
    """, unsafe_allow_html=True)

# -------------------------------------------------
# Main App
# -------------------------------------------------
def main():
    # Inicialização
    init_db()
    
    # Navegação
    render_navigation()
    
    # Conteúdo principal baseado na view atual
    if st.session_state.current_view == "home":
        render_hero_section()
        render_stats()
        render_services_grid()
        render_testimonials()
        
    elif st.session_state.current_view == "services":
        render_services_grid()
        
    elif st.session_state.current_view == "login":
        render_login()
        
    elif st.session_state.current_view == "premium":
        render_premium()
        
    elif st.session_state.current_view == "service_detail":
        render_service_detail()
        
    elif st.session_state.current_view == "service_result":
        render_service_result()
    
    # Rodapé
    render_footer()

if __name__ == "__main__":
    main()
