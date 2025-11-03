# app.py — CLARA • Sua Assistente Jurídica Pessoal
# Versão completamente reformulada - Corrigido premium, layout e análise de contratos

import os
import re
import json
from datetime import datetime
from typing import Dict, Any, List
import streamlit as st

# -------------------------------------------------
# Configuração da Página
# -------------------------------------------------
APP_TITLE = "CLARA • Sua Assistente Jurídica Pessoal"
VERSION = "v4.0"

st.set_page_config(
    page_title=APP_TITLE,
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# -------------------------------------------------
# Sistema de Análise de Contratos Baseado no PDF
# -------------------------------------------------

CONTRACT_RULES = {
    "imobiliario": [
        {
            "keyword": "indenização por benfeitorias necessárias",
            "description": "Rendência ao direito de indenização por benfeitorias necessárias",
            "risk_level": "alto",
            "points": 10,
            "legal_basis": "Contraria garantias mínimas do inquilino"
        },
        {
            "keyword": "multa.*50%",
            "description": "Multa desproporcional ao valor do contrato",
            "risk_level": "medio",
            "points": 5,
            "legal_basis": "Ex: multa de 50% em rescisão antecipada"
        },
        {
            "keyword": "renovação automática",
            "description": "Renovação automática sem notificação",
            "risk_level": "medio",
            "points": 5,
            "legal_basis": "Deve haver notificação prévia"
        },
        {
            "keyword": "foro.*fora.*domicílio",
            "description": "Cláusula que exige foro fora da residência do consumidor",
            "risk_level": "alto",
            "points": 10,
            "legal_basis": "Contraria o CDC, que garante o foro de domicílio"
        }
    ],
    "prestacao_servicos": [
        {
            "keyword": "exclusão.*responsabilidade",
            "description": "Exclusão total de responsabilidade do fornecedor",
            "risk_level": "alto",
            "points": 10,
            "legal_basis": "Mesmo em caso de erro grave - Contraria o art. 39 do CDC"
        },
        {
            "keyword": "fidelização.*multa",
            "description": "Fidelização com multa sem contrapartida",
            "risk_level": "medio",
            "points": 5,
            "legal_basis": "Sem benefícios claros para o contratante"
        }
    ],
    "financeiro": [
        {
            "keyword": "débito.*conta.*irrestrito",
            "description": "Autorização irrestrita para débito em conta",
            "risk_level": "alto",
            "points": 10,
            "legal_basis": "Sem limite claro ou autorização pontual"
        },
        {
            "keyword": "venda.*casada",
            "description": "Venda casada de produtos financeiros",
            "risk_level": "alto",
            "points": 10,
            "legal_basis": "Ex: seguro obrigatório para obter crédito"
        },
        {
            "keyword": "alteração.*unilateral.*taxa",
            "description": "Alteração unilateral de taxas",
            "risk_level": "medio",
            "points": 5,
            "legal_basis": "Sem aviso prévio e justificado"
        }
    ],
    "geral": [
        {
            "keyword": "renúncia.*direito",
            "description": "Rendência antecipada a direitos garantidos por lei",
            "risk_level": "alto",
            "points": 10,
            "legal_basis": "Ex: desistência de direito de arrependimento"
        },
        {
            "keyword": "termo.*genérico",
            "description": "Termos genéricos sem explicação acessível",
            "risk_level": "medio",
            "points": 5,
            "legal_basis": "Linguagem jurídica rebuscada e pouco clara"
        },
        {
            "keyword": "penalidade.*severa",
            "description": "Penalidades severas apenas para uma parte",
            "risk_level": "alto",
            "points": 10,
            "legal_basis": "Sem equilíbrio contratual"
        },
        {
            "keyword": "aceito.*sem.*ler",
            "description": "'Aceito sem ler' como prova de consentimento",
            "risk_level": "medio",
            "points": 5,
            "legal_basis": "Contraria o dever de informação"
        }
    ]
}

def analyze_contract_comprehensive(text: str) -> Dict[str, Any]:
    """Análise completa de contrato baseada nas regras do PDF"""
    text_lower = text.lower()
    findings = []
    total_points = 0
    
    # Analisar por categoria
    for category, rules in CONTRACT_RULES.items():
        for rule in rules:
            if re.search(rule["keyword"], text_lower):
                # Encontrar contexto
                start = max(0, text_lower.find(rule["keyword"]) - 100)
                end = min(len(text), text_lower.find(rule["keyword"]) + len(rule["keyword"]) + 100)
                context = text[start:end].replace('\n', ' ')
                
                findings.append({
                    "category": category,
                    "description": rule["description"],
                    "risk_level": rule["risk_level"],
                    "points": rule["points"],
                    "legal_basis": rule["legal_basis"],
                    "context": context
                })
                total_points += rule["points"]
    
    # Classificação de risco
    if total_points == 0:
        risk_category = "Verde (baixo risco)"
    elif total_points <= 30:
        risk_category = "Amarelo (médio risco)"
    else:
        risk_category = "Vermelho (alto risco)"
    
    return {
        "total_points": total_points,
        "risk_category": risk_category,
        "findings": findings,
        "total_findings": len(findings)
    }

def extract_text_from_pdf(pdf_file) -> str:
    """Extrai texto de arquivos PDF"""
    try:
        import PyPDF2
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        text = ""
        for page in pdf_reader.pages:
            text += page.extract_text() + "\n"
        return text
    except ImportError:
        return f"[Conteúdo do PDF: {pdf_file.name}] - Módulo PyPDF2 não disponível"
    except Exception as e:
        return f"Erro na extração do PDF: {str(e)}"

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
    
    .main-header {
        background: linear-gradient(135deg, var(--clara-dark) 0%, #1e293b 100%);
        color: white;
        padding: 3rem 0;
        text-align: center;
        border-radius: 0 0 20px 20px;
        margin-bottom: 2rem;
    }
    
    .clara-badge {
        background: var(--clara-gold);
        color: var(--clara-dark);
        padding: 0.5rem 1.5rem;
        border-radius: 50px;
        font-weight: 700;
        font-size: 0.9rem;
        display: inline-block;
        margin-bottom: 1rem;
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
    }
    
    .clara-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 30px rgba(0,0,0,0.12);
    }
    
    .service-card {
        text-align: center;
        padding: 1.5rem;
        cursor: pointer;
    }
    
    .service-icon {
        font-size: 3rem;
        margin-bottom: 1rem;
    }
    
    .risk-low {
        border-left: 4px solid var(--clara-success);
        background: #f0fdf4;
    }
    
    .risk-medium {
        border-left: 4px solid var(--clara-warning);
        background: #fffbeb;
    }
    
    .risk-high {
        border-left: 4px solid var(--clara-danger);
        background: #fef2f2;
    }
    
    .premium-card {
        border: 2px solid var(--clara-gold);
        position: relative;
    }
    
    .premium-badge {
        background: linear-gradient(135deg, #D4AF37, #F7EF8A);
        color: var(--clara-dark);
        padding: 0.3rem 1rem;
        border-radius: 20px;
        font-weight: 600;
        font-size: 0.8rem;
        position: absolute;
        top: -10px;
        left: 50%;
        transform: translateX(-50%);
    }
    
    .step-container {
        display: flex;
        align-items: center;
        margin: 1rem 0;
        padding: 1.5rem;
        background: var(--clara-light);
        border-radius: 12px;
        border-left: 4px solid var(--clara-gold);
    }
    
    .step-number {
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
    
    .stats-grid {
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
    
    .footer {
        text-align: center;
        padding: 2rem 0;
        margin-top: 3rem;
        border-top: 1px solid #e2e8f0;
        color: var(--clara-gray);
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
if "free_uses" not in st.session_state:
    st.session_state.free_uses = 3
if "active_service" not in st.session_state:
    st.session_state.active_service = None
if "user_logged_in" not in st.session_state:
    st.session_state.user_logged_in = False

# -------------------------------------------------
# Serviços Atualizados
# -------------------------------------------------
SERVICES = {
    "cancelamento_assinaturas": {
        "title": "📝 Cancelamento de Assinaturas",
        "icon": "📝",
        "description": "Cancele academias, apps, TV e serviços com base no Código de Defesa do Consumidor",
        "category": "Consumidor",
        "color": "#D4AF37"
    },
    "cobranca_indevida": {
        "title": "💳 Cobrança Indevida - Passo a Passo",
        "icon": "💳",
        "description": "Guia completo para contestar cobranças não autorizadas",
        "category": "Financeiro",
        "color": "#EF4444"
    },
    "analise_contratos": {
        "title": "📄 Análise de Contratos Inteligente",
        "icon": "📄",
        "description": "Identifique cláusulas abusivas conforme a legislação brasileira",
        "category": "Jurídico",
        "color": "#10B981"
    },
    "juros_abusivos": {
        "title": "📊 Juros Abusivos & CET",
        "icon": "📊",
        "description": "Calcule custos reais e dispute juros excessivos",
        "category": "Financeiro",
        "color": "#F59E0B"
    },
    "direito_arrependimento": {
        "title": "🔄 Direito de Arrependimento",
        "icon": "🔄",
        "description": "Exercite seu direito de arrependimento em compras online",
        "category": "Consumidor",
        "color": "#8B5CF6"
    },
    "problemas_entregas": {
        "title": "🚚 Problemas com Entregas",
        "icon": "🚚",
        "description": "Resolva atrasos, extravios e problemas com entregas",
        "category": "Consumidor",
        "color": "#06B6D4"
    }
}

# -------------------------------------------------
# Componentes de Interface
# -------------------------------------------------
def render_header():
    """Cabeçalho com navegação"""
    col1, col2, col3, col4, col5 = st.columns([2, 1, 1, 1, 1.5])
    
    with col1:
        st.markdown("""
        <div style="display: flex; align-items: center; gap: 10px;">
            <div>
                <div style="font-size: 1.8rem; font-weight: 700; color: #D4AF37; margin: 0;">CLARA LAW</div>
                <div style="font-size: 0.8rem; color: #475569; margin: 0;">Inteligência para um mundo mais claro</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        if st.button("🏠 **Início**", use_container_width=True, key="nav_home"):
            st.session_state.current_view = "home"
            st.rerun()
    
    with col3:
        if st.button("🛡️ **Serviços**", use_container_width=True, key="nav_services"):
            st.session_state.current_view = "services"
            st.rerun()
    
    with col4:
        if st.button("⭐ **Premium**", use_container_width=True, key="nav_premium"):
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
                    <div style="font-size: 0.7rem; color: #475569;">
                        {'⭐ Premium' if st.session_state.premium else f'🔓 {st.session_state.free_uses} análises'}
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)
        else:
            if st.button("🔐 **Entrar**", use_container_width=True, key="nav_login"):
                st.session_state.current_view = "login"
                st.rerun()

def render_hero():
    """Seção hero principal"""
    st.markdown("""
    <div class="main-header">
        <div class="clara-badge">⚖️ ASSISTENTE JURÍDICA PESSOAL</div>
        <h1 style="font-size: 3.5rem; font-weight: 800; margin: 1rem 0; line-height: 1.1;">
            Resolva problemas jurídicos<br>sem advogado caro
        </h1>
        <p style="font-size: 1.3rem; opacity: 0.9; margin-bottom: 2rem; line-height: 1.6;">
            Use a inteligência da CLARA para cancelar assinaturas, disputar cobranças,<br>
            analisar contratos e muito mais. Rápido, simples e eficaz.
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("🚀 Começar Agora", use_container_width=True, type="primary", key="hero_cta"):
            st.session_state.current_view = "services"
            st.rerun()

def render_stats():
    """Estatísticas da plataforma"""
    st.markdown('<div class="stats-grid">', unsafe_allow_html=True)
    
    stats = [
        {"value": "2.847", "label": "Casos Resolvidos"},
        {"value": "R$ 1.2M", "label": "Economizados"},
        {"value": "98%", "label": "Taxa de Sucesso"},
        {"value": "4.9★", "label": "Avaliação"}
    ]
    
    for stat in stats:
        st.markdown(f"""
        <div class="stat-card">
            <div style="font-size: 2rem; font-weight: 700; color: #0f172a; margin: 0.5rem 0;">{stat['value']}</div>
            <div style="color: #475569; font-size: 0.9rem;">{stat['label']}</div>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown('</div>', unsafe_allow_html=True)

def render_services_grid():
    """Grid de serviços"""
    st.markdown("""
    <div style='text-align: center; margin: 3rem 0;'>
        <h2>Como a CLARA pode te ajudar hoje?</h2>
        <p style="color: #475569;">Escolha o serviço que você precisa:</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Organizar serviços em linhas de 3
    services_list = list(SERVICES.items())
    
    for i in range(0, len(services_list), 3):
        cols = st.columns(3)
        for j, (service_id, service) in enumerate(services_list[i:i+3]):
            with cols[j]:
                st.markdown(f"""
                <div class="clara-card service-card" 
                     style="border-top: 4px solid {service['color']}; cursor: pointer;"
                     onclick="this.nextElementSibling.click()">
                    <div class="service-icon">{service['icon']}</div>
                    <h3 style="margin: 1rem 0; color: #0f172a;">{service['title']}</h3>
                    <p style="color: #475569; margin-bottom: 1.5rem;">{service['description']}</p>
                    <small style="color: {service['color']}; font-weight: 600;">{service['category']}</small>
                </div>
                """, unsafe_allow_html=True)
                
                if st.button(f"Usar {service['title'].split(' ')[0]}", 
                           key=f"btn_{service_id}", use_container_width=True):
                    if not st.session_state.user_logged_in and st.session_state.free_uses <= 0:
                        st.session_state.current_view = "premium"
                        st.rerun()
                    else:
                        st.session_state.active_service = service_id
                        st.session_state.current_view = "service_detail"
                        st.rerun()

def render_login():
    """Página de login"""
    st.markdown("""
    <div style="max-width: 500px; margin: 0 auto; text-align: center;">
        <h1 style="margin-bottom: 2rem;">Acesse sua conta CLARA</h1>
    </div>
    """, unsafe_allow_html=True)
    
    tab1, tab2 = st.tabs(["🔐 Entrar", "📝 Cadastrar"])
    
    with tab1:
        with st.form("login_form"):
            email = st.text_input("E-mail")
            senha = st.text_input("Senha", type="password")
            
            if st.form_submit_button("Entrar na Minha Conta", use_container_width=True, type="primary"):
                if email and senha:
                    st.session_state.user_logged_in = True
                    st.session_state.profile = {
                        "nome": "João Silva",
                        "email": email,
                        "cel": "(11) 99999-9999"
                    }
                    st.session_state.current_view = "home"
                    st.success("✅ Login realizado com sucesso!")
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
            
            if st.form_submit_button("Criar Minha Conta", use_container_width=True, type="primary"):
                if nome and email and cel and senha and confirmar_senha:
                    if senha == confirmar_senha:
                        st.session_state.user_logged_in = True
                        st.session_state.profile = {
                            "nome": nome,
                            "email": email,
                            "cel": cel
                        }
                        st.session_state.current_view = "home"
                        st.success("✅ Conta criada com sucesso!")
                        st.rerun()
                    else:
                        st.error("As senhas não coincidem")
                else:
                    st.error("Por favor, preencha todos os campos")
    
    st.markdown("---")
    st.markdown("""
    <div style="text-align: center;">
        <p>💡 <strong>Dica:</strong> Você pode testar 3 serviços gratuitamente sem cadastro!</p>
    </div>
    """, unsafe_allow_html=True)
    
    if st.button("➡️ Experimentar sem Cadastro", use_container_width=True):
        st.session_state.current_view = "services"
        st.rerun()

def render_premium():
    """Página premium corrigida"""
    st.markdown("""
    <div style="text-align: center; margin-bottom: 3rem;">
        <h1>⭐ CLARA Premium</h1>
        <p style="font-size: 1.2rem; color: #475569;">Desbloqueie todo o potencial da sua assistente jurídica</p>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.markdown("""
        <div class="clara-card">
            <h3 style="text-align: center;">🔓 Plano Gratuito</h3>
            <div style="text-align: center; margin: 2rem 0;">
                <div style="font-size: 2.5rem; font-weight: 700; color: #0f172a;">R$ 0</div>
                <div style="color: #475569;">para sempre</div>
            </div>
            <div style="text-align: left;">
                <p>✓ 3 análises gratuitas</p>
                <p>✓ Serviços básicos</p>
                <p>✓ Modelos padrão</p>
                <p>✓ Suporte por e-mail</p>
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown("""
        <div class="clara-card premium-card">
            <div class="premium-badge">MAIS POPULAR</div>
            <h3 style="text-align: center;">⭐ CLARA Premium</h3>
            <div style="text-align: center; margin: 2rem 0;">
                <div style="font-size: 2.5rem; font-weight: 700; color: #D4AF37;">R$ 9,90</div>
                <div style="color: #475569;">por mês • Cancele quando quiser</div>
            </div>
            <div style="text-align: left;">
                <p><strong>✓ Análises ilimitadas</strong></p>
                <p><strong>✓ Todos os serviços disponíveis</strong></p>
                <p>✓ Modelos personalizados</p>
                <p>✓ Análise de contratos avançada</p>
                <p>✓ Suporte prioritário</p>
                <p>✓ Calculadora de CET completa</p>
                <p>✓ Atualizações constantes</p>
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    st.markdown("""
    <div style="text-align: center; margin: 2rem 0;">
        <h3>💎 Pronto para desbloquear todo o potencial da CLARA?</h3>
        <p style="color: #475569;">Mais de 2.000 usuários já confiam na CLARA Premium</p>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("🔄 Assinar CLARA Premium - R$ 9,90/mês", 
                   use_container_width=True, type="primary", key="premium_btn"):
            st.session_state.premium = True
            st.session_state.free_uses = 999
            st.session_state.user_logged_in = True
            st.success("🎉 Parabéns! Você agora é um usuário CLARA Premium!")
            st.balloons()
            st.rerun()

def render_service_detail():
    """Detalhe do serviço selecionado"""
    service_id = st.session_state.active_service
    service = SERVICES.get(service_id)
    
    if not service:
        st.error("Serviço não encontrado")
        st.session_state.current_view = "services"
        st.rerun()
        return
    
    # Header do serviço
    st.markdown(f"""
    <div style="margin-bottom: 2rem;">
        <h1>{service['icon']} {service['title']}</h1>
        <p style="font-size: 1.2rem; color: #475569;">{service['description']}</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Conteúdo específico por serviço
    if service_id == "cobranca_indevida":
        render_billing_guide()
    elif service_id == "analise_contratos":
        render_contract_analysis()
    elif service_id == "cancelamento_assinaturas":
        render_cancellation_service()
    else:
        render_generic_service(service)

def render_billing_guide():
    """Guia passo a passo para cobrança indevida"""
    st.markdown("""
    ## 🚨 Guia Completo: Como Contestar Cobrança Indevida
    
    Siga estes passos para resolver seu problema:
    """)
    
    steps = [
        {
            "step": 1,
            "title": "Identifique a Cobrança",
            "description": "Verifique extratos, faturas e comprovantes. Anote data, valor e descrição.",
            "details": "• Verifique cartão de crédito, débito automático\n• Confirme se você contratou o serviço\n• Guarde todos os comprovantes"
        },
        {
            "step": 2,
            "title": "Contate o Estabelecimento",
            "description": "Entre em contato por telefone, e-mail ou aplicativo.",
            "details": "• Use o canal oficial de atendimento\n• Peça número de protocolo\n• Documente toda a conversa"
        },
        {
            "step": 3,
            "description": "Se não resolver, registre reclamação no Procon.",
            "details": "• Site: procon.sp.gov.br\n• Documentos necessários: RG, CPF, comprovantes\n• Prazo: até 30 dias para resposta"
        },
        {
            "step": 4,
            "title": "Registre no BACEN",
            "description": "Para bancos e financeiras, reclame no Banco Central.",
            "details": "• Site: bacen.gov.br/reclame\n• Prazo: 10 dias úteis\n• Gratuito e obrigatório para instituições"
        },
        {
            "step": 5,
            "title": "Juntar Provas",
            "description": "Organize toda a documentação.",
            "details": "• Comprovantes de pagamento\n• Protocolos de atendimento\n• Prints de conversas\n• Extratos bancários"
        }
    ]
    
    for step in steps:
        st.markdown(f"""
        <div class="step-container">
            <div class="step-number">{step['step']}</div>
            <div>
                <h4 style="margin: 0; color: #0f172a;">{step.get('title', f'Passo {step["step"]}')}</h4>
                <p style="margin: 0.5rem 0; color: #475569;">{step['description']}</p>
                <p style="margin: 0; font-size: 0.9rem; color: #64748b;">{step['details']}</p>
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    # Formulário para gerar documento
    st.markdown("---")
    st.markdown("### 📄 Gerar Carta de Contestação")
    
    with st.form("billing_form"):
        col1, col2 = st.columns(2)
        with col1:
            nome = st.text_input("Seu nome completo*")
            empresa = st.text_input("Nome da empresa*")
            valor = st.number_input("Valor cobrado (R$)*", min_value=0.01)
        with col2:
            data_cobranca = st.date_input("Data da cobrança*")
            numero_fatura = st.text_input("Número da fatura")
        
        descricao = st.text_area("Descreva o problema*", 
                               placeholder="Exemplo: Esta cobrança apareceu sem minha autorização, nunca contratei este serviço...")
        
        if st.form_submit_button("📄 Gerar Carta de Contestação", use_container_width=True):
            if nome and empresa and valor and descricao:
                documento = generate_billing_contestation({
                    'nome': nome,
                    'empresa': empresa,
                    'valor': valor,
                    'data_cobranca': data_cobranca.strftime("%d/%m/%Y"),
                    'numero_fatura': numero_fatura,
                    'descricao': descricao
                })
                
                st.session_state.generated_document = documento
                st.session_state.current_view = "service_result"
                st.rerun()
            else:
                st.error("Preencha todos os campos obrigatórios (*)")

def render_contract_analysis():
    """Análise de contratos inteligente"""
    st.markdown("""
    ## 🔍 Análise Inteligente de Contratos
    
    Faça upload do seu contrato para identificar cláusulas abusivas automaticamente.
    """)
    
    uploaded_file = st.file_uploader("Escolha o arquivo do contrato", type=["pdf", "txt"])
    
    if uploaded_file:
        if uploaded_file.type == "application/pdf":
            text = extract_text_from_pdf(uploaded_file)
        else:
            text = str(uploaded_file.read(), 'utf-8')
        
        st.success("✅ Contrato carregado com sucesso!")
        
        if st.button("🔍 Analisar Contrato", use_container_width=True, type="primary"):
            with st.spinner("Analisando cláusulas..."):
                analysis = analyze_contract_comprehensive(text)
            
            # Mostrar resultados
            st.markdown(f"""
            <div class="clara-card {'risk-high' if analysis['total_points'] > 30 else 'risk-medium' if analysis['total_points'] > 10 else 'risk-low'}">
                <h3>📊 Resultado da Análise</h3>
                <div style="font-size: 1.5rem; font-weight: 700; margin: 1rem 0;">
                    Pontuação: {analysis['total_points']} pontos • {analysis['risk_category']}
                </div>
                <p>Cláusulas identificadas: {analysis['total_findings']}</p>
            </div>
            """, unsafe_allow_html=True)
            
            # Detalhes das cláusulas
            if analysis['findings']:
                st.markdown("### ⚠️ Cláusulas Identificadas")
                for finding in analysis['findings']:
                    risk_color = {
                        'alto': '#EF4444',
                        'medio': '#F59E0B',
                        'baixo': '#10B981'
                    }[finding['risk_level']]
                    
                    st.markdown(f"""
                    <div style="border-left: 4px solid {risk_color}; padding: 1rem; background: #f8fafc; margin: 0.5rem 0; border-radius: 0 8px 8px 0;">
                        <div style="display: flex; justify-content: between; align-items: start;">
                            <div>
                                <strong style="color: {risk_color};">{finding['description']}</strong>
                                <div style="color: #475569; font-size: 0.9rem; margin: 0.5rem 0;">
                                    {finding['legal_basis']}
                                </div>
                                <div style="color: #64748b; font-size: 0.8rem;">
                                    Contexto: "{finding['context'][:150]}..."
                                </div>
                            </div>
                            <div style="background: {risk_color}; color: white; padding: 0.3rem 0.8rem; border-radius: 20px; font-size: 0.8rem; font-weight: 600;">
                                {finding['points']} pts
                            </div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
            
            # Gerar relatório
            documento = generate_analysis_report(analysis, text[:1000])
            st.session_state.generated_document = documento
            st.session_state.analysis_result = analysis
            
            st.markdown("---")
            st.download_button(
                "📥 Baixar Relatório Completo",
                data=documento,
                file_name=f"analise_contrato_{datetime.now().strftime('%Y%m%d')}.txt",
                mime="text/plain",
                use_container_width=True
            )

def render_cancellation_service():
    """Serviço de cancelamento"""
    with st.form("cancellation_form"):
        st.markdown("### 📋 Informações do Serviço")
        
        col1, col2 = st.columns(2)
        with col1:
            empresa = st.text_input("Nome da Empresa*")
            servico = st.text_input("Tipo de Serviço*")
            data_inicio = st.date_input("Data de Início")
        with col2:
            valor_mensal = st.number_input("Valor Mensal (R$)", min_value=0.0)
            numero_contrato = st.text_input("Número do Contrato")
        
        motivo = st.selectbox("Motivo do Cancelamento*", [
            "Serviço insatisfatório",
            "Cobranças indevidas",
            "Não consigo cancelar",
            "Problemas técnicos",
            "Mudança de endereço",
            "Outro"
        ])
        
        detalhes = st.text_area("Descreva o problema*", height=100)
        
        if st.form_submit_button("📄 Gerar Carta de Cancelamento", use_container_width=True):
            if empresa and servico and motivo and detalhes:
                documento = generate_cancellation_letter({
                    'empresa': empresa,
                    'servico': servico,
                    'data_inicio': data_inicio.strftime("%d/%m/%Y") if data_inicio else "Não informada",
                    'valor_mensal': valor_mensal,
                    'numero_contrato': numero_contrato,
                    'motivo': motivo,
                    'detalhes': detalhes,
                    'nome': st.session_state.profile.get('nome', ''),
                    'email': st.session_state.profile.get('email', '')
                })
                
                st.session_state.generated_document = documento
                st.session_state.current_view = "service_result"
                st.rerun()

def render_generic_service(service):
    """Serviço genérico"""
    st.info(f"🚧 O serviço {service['title']} está em desenvolvimento. Em breve estará disponível!")
    
    if st.button("↩️ Voltar aos Serviços", use_container_width=True):
        st.session_state.current_view = "services"
        st.rerun()

def render_service_result():
    """Resultado do serviço"""
    documento = st.session_state.get('generated_document', '')
    
    st.markdown("""
    <div style="margin-bottom: 2rem;">
        <h1>✅ Documento Gerado com Sucesso!</h1>
        <p style="font-size: 1.2rem; color: #475569;">Seu documento está pronto para uso.</p>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.text_area("Documento gerado", value=documento, height=400, label_visibility="collapsed")
        
        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            st.download_button(
                "📥 Baixar Documento",
                data=documento,
                file_name=f"documento_clara_{datetime.now().strftime('%Y%m%d')}.txt",
                mime="text/plain",
                use_container_width=True
            )
        with col_btn2:
            if st.button("🔄 Gerar Outro", use_container_width=True):
                st.session_state.current_view = "service_detail"
                st.rerun()
    
    with col2:
        st.markdown("### 💡 Próximos Passos")
        st.info("""
        1. **Revise** o documento cuidadosamente
        2. **Imprima** ou **salve** uma cópia
        3. **Envie** para a parte interessada
        4. **Guarde** o comprovante de envio
        5. **Acompanhe** os prazos de resposta
        """)
        
        if not st.session_state.premium:
            st.markdown("---")
            st.warning(f"Análises restantes: {st.session_state.free_uses}")
            if st.button("⭐ Fazer Upgrade", use_container_width=True):
                st.session_state.current_view = "premium"
                st.rerun()

def render_footer():
    """Rodapé"""
    st.markdown("""
    <div class="footer">
        <div style="margin-bottom: 1rem;">
            <strong>CLARA LAW</strong> - Sua Assistente Jurídica Pessoal
        </div>
        <div style="font-size: 0.8rem; color: #475569;">
            © 2024 CLARA • Inteligência para um mundo mais claro • Versão 4.0
        </div>
    </div>
    """, unsafe_allow_html=True)

# -------------------------------------------------
# Geradores de Documentos
# -------------------------------------------------
def generate_billing_contestation(data):
    return f"""
CARTA DE CONTESTAÇÃO - COBRANÇA INDEVIDA

De: {data['nome']}

Para: {data['empresa']}

Assunto: Contestação de cobrança indevida no valor de R$ {data['valor']:.2f}

Prezados Senhores,

Venho por meio desta contestar formalmente a cobrança no valor de R$ {data['valor']:.2f}, 
realizada em {data['data_cobranca']}, referente à fatura {data['numero_fatura']}.

MOTIVO DA CONTESTAÇÃO:
{data['descricao']}

Com fundamento no Código de Defesa do Consumidor (Lei 8.078/90), solicito:

1. O cancelamento imediato desta cobrança;
2. O estorno do valor, se já debitado;
3. A correção monetária e juros legais, se aplicável;
4. A confirmação por escrito do cancelamento.

Atenciosamente,

{data['nome']}
"""

def generate_cancellation_letter(data):
    return f"""
CARTA DE CANCELAMENTO - {data['servico'].upper()}

De: {data['nome']}
E-mail: {data.get('email', '')}

Para: {data['empresa']}

Assunto: Cancelamento de serviço/assinatura

Prezados Senhores,

Venho por meio desta comunicar o CANCELAMENTO do serviço {data['servico']}, 
contratado em {data['data_inicio']}.

MOTIVO: {data['motivo']}

DETALHES:
{data['detalhes']}

Com fundamento no Código de Defesa do Consumidor, solicito:

1. Cancelamento imediato;
2. Bloqueio de cobranças futuras;
3. Confirmação por e-mail;
4. Reembolso proporcional, se aplicável.

Atenciosamente,

{data['nome']}
{data.get('email', '')}
"""

def generate_analysis_report(analysis, contract_preview):
    return f"""
RELATÓRIO DE ANÁLISE DE CONTRATO - CLARA LAW

Data da análise: {datetime.now().strftime('%d/%m/%Y às %H:%M')}
Pontuação total: {analysis['total_points']} pontos
Classificação de risco: {analysis['risk_category']}
Total de cláusulas identificadas: {analysis['total_findings']}

RESUMO DA ANÁLISE:
{'-' * 50}

{chr(10).join([f"• {f['description']} ({f['points']} pontos - {f['risk_level'].upper()})" for f in analysis['findings']])}

DETALHES DAS CLÁUSULAS IDENTIFICADAS:
{'-' * 50}

{chr(10).join([f"""
CLÁUSULA: {f['description']}
RISCO: {f['risk_level'].upper()} ({f['points']} pontos)
BASE LEGAL: {f['legal_basis']}
CONTEXTO: {f['context'][:200]}...
""" for f in analysis['findings']])}

PRÉVIA DO CONTRATO:
{'-' * 50}

{contract_preview}...

RECOMENDAÇÕES:
1. Revise as cláusulas destacadas com atenção
2. Considere negociar termos mais favoráveis
3. Busque orientação jurídica especializada se necessário

Este relatório foi gerado automaticamente pela CLARA LAW e não substitui 
aconselhamento jurídico profissional.
"""

# -------------------------------------------------
# Main App
# -------------------------------------------------
def main():
    # Header
    render_header()
    
    # Conteúdo principal
    if st.session_state.current_view == "home":
        render_hero()
        render_stats()
        render_services_grid()
        
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
    
    # Footer
    render_footer()

if __name__ == "__main__":
    main()
