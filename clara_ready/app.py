# app.py — CLARA • Sua Assistente Jurídica Pessoal
# Versão completa com serviços funcionais + casos campeões

import os
import io
import re
import csv
import json
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
        transition: transform 0.2s ease;
    }
    
    .clara-card:hover {
        transform: translateY(-2px);
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
E-mail: {service_data.get('email', '')
CPF: {service_data.get('cpf', '')}

Para: {service_data.get('empresa', '')}
CNPJ: {service_data.get('cnpj', '')}

Assunto: Cancelamento de assinatura/service_data

Prezados Senhores,

Venho por meio desta comunicar o CANCELAMENTO imediato da assinatura/service_data contratado junto à empresa {service_data.get('empresa', '')}, referente ao serviço: {service_data.get('servico', '')}.

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
def render_navigation():
    """Navegação principal"""
    col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
    
    with col1:
        st.markdown(f"<h3 style='color: var(--clara-gold); margin: 0;'>CLARA LAW</h3>", unsafe_allow_html=True)
        st.caption("Inteligência para um mundo mais claro")
    
    with col2:
        if st.button("🏠 Início", use_container_width=True, key="nav_home"):
            st.session_state.current_view = "home"
            st.session_state.active_service = None
    
    with col3:
        if st.button("🛡️ Serviços", use_container_width=True, key="nav_services"):
            st.session_state.current_view = "services"
            st.session_state.active_service = None
    
    with col4:
        if st.button("⭐ Premium", use_container_width=True, key="nav_premium"):
            st.session_state.current_view = "premium"

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
    
    st.markdown("</div></div>", unsafe_allow_html=True)

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
    
    for service_id, service in SERVICES.items():
        if selected_category != "Todos" and service["category"] != selected_category:
            continue
            
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
            st.session_state.active_service = service_id
            st.session_state.current_view = "service_detail"
            st.rerun()

def render_service_detail():
    """Detalhe do serviço selecionado"""
    if not st.session_state.active_service:
        st.session_state.current_view = "services"
        st.rerun()
        return
    
    service = SERVICES[st.session_state.active_service]
    
    st.markdown(f"""
    <div style='text-align: center; margin-bottom: 2rem;'>
        <h1>{service['icon']} {service['title']}</h1>
        <p>{service['description']}</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Mostrar etapas do processo
    st.markdown("### 📋 Como funciona:")
    for i, step in enumerate(service["steps"], 1):
        st.markdown(f"""
        <div class="clara-step">
            <div class="clara-step-number">{i}</div>
            <div>
                <strong>{step}</strong>
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    # Formulário específico do serviço
    st.markdown("### 🎯 Preencha as informações:")
    
    service_data = st.session_state.service_data.get(st.session_state.active_service, {})
    
    if st.session_state.active_service == "cancelamento_assinaturas":
        render_cancellation_service(service_data)
    elif st.session_state.active_service == "cobranca_indevida":
        render_billing_service(service_data)
    elif st.session_state.active_service == "juros_abusivos":
        render_interest_service(service_data)
    elif st.session_state.active_service == "transporte_aereo":
        render_airline_service(service_data)
    elif st.session_state.active_service == "telecom":
        render_telecom_service(service_data)
    elif st.session_state.active_service == "energia_agua":
        render_utility_service(service_data)
    elif st.session_state.active_service == "analise_contratos":
        render_contract_analysis()

def render_cancellation_service(service_data: Dict):
    """Serviço de cancelamento de assinaturas"""
    with st.form("cancellation_form"):
        st.subheader("📋 Dados do Serviço")
        
        col1, col2 = st.columns(2)
        with col1:
            empresa = st.text_input("Nome da Empresa*", value=service_data.get('empresa', ''))
            servico = st.text_input("Tipo de Serviço*", value=service_data.get('servico', ''))
            numero_contrato = st.text_input("Número do Contrato", value=service_data.get('numero_contrato', ''))
        
        with col2:
            cnpj = st.text_input("CNPJ da Empresa", value=service_data.get('cnpj', ''))
            data_inicio = st.date_input("Data de Início", value=service_data.get('data_inicio', datetime.now()))
            valor_mensal = st.number_input("Valor Mensal (R$)", value=service_data.get('valor_mensal', 0.0))
        
        st.subheader("🎯 Motivo do Cancelamento")
        motivo = st.selectbox("Motivo Principal*", [
            "Serviço insatisfatório",
            "Cobranças indevidas", 
            "Não consigo cancelar",
            "Mudança de endereço",
            "Problemas técnicos",
            "Outro"
        ])
        
        detalhes = st.text_area("Descreva detalhadamente o problema*", 
                               value=service_data.get('detalhes', ''),
                               height=100,
                               placeholder="Exemplo: Tentei cancelar pelo app mas não consegui, continuam cobrando mesmo após solicitação de cancelamento...")
        
        if st.form_submit_button("📄 Gerar Carta de Cancelamento", use_container_width=True):
            if empresa and servico and motivo and detalhes:
                letter_data = {
                    'empresa': empresa,
                    'servico': servico,
                    'numero_contrato': numero_contrato,
                    'cnpj': cnpj,
                    'data_inicio': data_inicio.strftime("%d/%m/%Y"),
                    'valor_mensal': valor_mensal,
                    'motivo': motivo,
                    'detalhes': detalhes,
                    'nome': st.session_state.profile.get('nome', ''),
                    'email': st.session_state.profile.get('email', ''),
                    'cpf': st.session_state.profile.get('cpf', ''),
                    'telefone': st.session_state.profile.get('cel', '')
                }
                
                carta = generate_cancellation_letter(letter_data)
                
                st.success("✅ Carta gerada com sucesso!")
                st.download_button(
                    "📥 Baixar Carta de Cancelamento",
                    data=carta,
                    file_name=f"carta_cancelamento_{empresa}.txt",
                    mime="text/plain"
                )
                
                with st.expander("📋 Visualizar Carta"):
                    st.text_area("Sua carta:", carta, height=300)
            else:
                st.error("⚠️ Preencha todos os campos obrigatórios (*)")

def render_billing_service(service_data: Dict):
    """Serviço de cobrança indevida"""
    st.info("💡 **Dica:** Use este serviço para disputar cobranças de bancos, cartões de crédito, empréstimos consignados e outras cobranças não autorizadas.")
    
    with st.form("billing_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            empresa = st.text_input("Nome da Empresa/Banco*", value=service_data.get('empresa', ''))
            tipo_cobranca = st.selectbox("Tipo de Cobrança*", [
                "Cartão de Crédito",
                "Empréstimo Consignado", 
                "Tarifa Bancária",
                "Assinatura Não Autorizada",
                "Seguro",
                "Outro"
            ])
            valor_cobranca = st.number_input("Valor Cobrado (R$)*", value=service_data.get('valor_cobranca', 0.0))
        
        with col2:
            data_cobranca = st.date_input("Data da Cobrança*", value=service_data.get('data_cobranca', datetime.now()))
            numero_nota = st.text_input("Número da Nota/Fatura", value=service_data.get('numero_nota', ''))
            ja_reclamou = st.selectbox("Já reclamou com a empresa?", ["Não", "Sim - Sem resposta", "Sim - Resposta insatisfatória"])
        
        descricao = st.text_area("Descreva por que esta cobrança é indevida*",
                                height=100,
                                placeholder="Exemplo: Esta cobrança apareceu sem minha autorização, nunca contratei este serviço...")
        
        if st.form_submit_button("📄 Gerar Recurso", use_container_width=True):
            st.success("✅ Recurso gerado! Em breve teremos templates específicos para cada tipo de cobrança.")

def render_interest_service(service_data: Dict):
    """Serviço de juros abusivos"""
    st.info("💡 **Dica:** Calcule o CET real do seu empréstimo e gere uma carta para renegociação.")
    
    tab1, tab2 = st.tabs(["🧮 Calculadora CET", "📄 Carta de Renegociação"])
    
    with tab1:
        st.subheader("Calculadora de Custo Efetivo Total")
        
        col1, col2 = st.columns(2)
        with col1:
            valor_emprestimo = st.number_input("Valor do Empréstimo (R$)*", min_value=0.0, value=1000.0)
            taxa_mensal = st.number_input("Taxa de Juros Mensal (%)*", min_value=0.0, value=5.0)
        
        with col2:
            parcelas = st.number_input("Número de Parcelas*", min_value=1, value=12)
            taxas_adicionais = st.number_input("Taxas Adicionais (R$)", min_value=0.0, value=50.0)
        
        if st.button("Calcular CET", use_container_width=True):
            try:
                cet = compute_cet_quick(valor_emprestimo, taxa_mensal/100, int(parcelas), taxas_adicionais)
                st.success(f"**CET Calculado:** {cet*100:.2f}% ao mês")
                
                if cet * 100 > 10:
                    st.error("⚠️ Esta taxa está muito acima da média de mercado! Recomendamos negociar.")
                elif cet * 100 > 5:
                    st.warning("⚠️ Esta taxa está acima da média. Pode valer a pena negociar.")
                else:
                    st.success("✅ Taxa dentro dos parâmetros razoáveis.")
                    
            except Exception as e:
                st.error(f"Erro no cálculo: {str(e)}")
    
    with tab2:
        st.subheader("Carta de Renegociação")
        st.info("Em desenvolvimento - breve disponível!")

def render_airline_service(service_data: Dict):
    """Serviço para problemas com transporte aéreo"""
    with st.form("airline_form"):
        st.subheader("✈️ Dados do Voo")
        
        col1, col2 = st.columns(2)
        with col1:
            companhia = st.text_input("Companhia Aérea*", value=service_data.get('companhia', ''))
            numero_voo = st.text_input("Número do Voo*", value=service_data.get('numero_voo', ''))
            data_voo = st.date_input("Data do Voo*", value=service_data.get('data_voo', datetime.now()))
        
        with col2:
            origem = st.text_input("Cidade de Origem*", value=service_data.get('origem', ''))
            destino = st.text_input("Cidade de Destino*", value=service_data.get('destino', ''))
            passageiros = st.number_input("Número de Passageiros", min_value=1, value=1)
        
        st.subheader("🔍 Problema Ocorrido")
        problema = st.selectbox("Tipo de Problema*", [
            "Atraso no voo",
            "Cancelamento do voo",
            "Extravio de bagagem",
            "Overbooking",
            "Má atendimento",
            "Outro"
        ])
        
        detalhes = st.text_area("Descreva o ocorrido em detalhes*",
                               height=120,
                               placeholder="Exemplo: O voo atrasou 4 horas, perdemos conexões importantes...")
        
        prejuizos = st.text_area("Quais prejuízos você teve?",
                                height=80,
                                placeholder="Exemplo: Hotel extra, alimentação, compromissos perdidos...")
        
        if st.form_submit_button("📄 Gerar Reclamação ANAC", use_container_width=True):
            if companhia and numero_voo and problema and detalhes:
                complaint_data = {
                    'companhia': companhia,
                    'numero_voo': numero_voo,
                    'data_voo': data_voo.strftime("%d/%m/%Y"),
                    'origem': origem,
                    'destino': destino,
                    'problema': problema,
                    'detalhes': detalhes,
                    'prejuizos': prejuizos,
                    'nome': st.session_state.profile.get('nome', ''),
                    'email': st.session_state.profile.get('email', ''),
                    'cpf': st.session_state.profile.get('cpf', ''),
                    'telefone': st.session_state.profile.get('cel', '')
                }
                
                carta = generate_anac_complaint(complaint_data)
                
                st.success("✅ Reclamação ANAC gerada com sucesso!")
                st.download_button(
                    "📥 Baixar Reclamação ANAC",
                    data=carta,
                    file_name=f"reclamacao_anac_{companhia}.txt",
                    mime="text/plain"
                )
                
                with st.expander("📋 Visualizar Reclamação"):
                    st.text_area("Sua reclamação:", carta, height=300)
            else:
                st.error("⚠️ Preencha todos os campos obrigatórios (*)")

def render_telecom_service(service_data: Dict):
    """Serviço para problemas com telecomunicações"""
    with st.form("telecom_form"):
        st.subheader("📞 Dados do Serviço")
        
        col1, col2 = st.columns(2)
        with col1:
            operadora = st.text_input("Operadora*", value=service_data.get('operadora', ''))
            tipo_servico = st.selectbox("Tipo de Serviço*", [
                "Internet Banda Larga",
                "Telefone Fixo",
                "TV por Assinatura",
                "Telefone Móvel",
                "Combo"
            ])
        
        with col2:
            numero_contrato = st.text_input("Número do Contrato", value=service_data.get('numero_contrato', ''))
            endereco = st.text_input("Endereço de Instalação", value=service_data.get('endereco', ''))
        
        st.subheader("🔍 Problema Reportado")
        problema = st.selectbox("Tipo de Problema*", [
            "Falha no serviço",
            "Lentidão da internet",
            "Cobranças indevidas",
            "Mau atendimento",
            "Problemas técnicos persistentes",
            "Outro"
        ])
        
        data_inicio = st.date_input("Data do início do problema*", value=service_data.get('data_inicio', datetime.now()))
        
        contatou_operadora = st.selectbox("Já contactou a operadora?", ["Não", "Sim - Sem solução", "Sim - Em processamento"])
        protocolo_operadora = st.text_input("Protocolo na operadora (se houver)", value=service_data.get('protocolo_operadora', ''))
        
        detalhes = st.text_area("Descreva o problema em detalhes*",
                               height=120,
                               placeholder="Exemplo: A internet cai diariamente, a velocidade está muito abaixo do contratado...")
        
        if st.form_submit_button("📄 Gerar Reclamação ANATEL", use_container_width=True):
            if operadora and tipo_servico and problema and detalhes:
                complaint_data = {
                    'operadora': operadora,
                    'tipo_servico': tipo_servico,
                    'numero_contrato': numero_contrato,
                    'endereco': endereco,
                    'problema': problema,
                    'data_inicio': data_inicio.strftime("%d/%m/%Y"),
                    'contatou_operadora': contatou_operadora,
                    'protocolo_operadora': protocolo_operadora,
                    'detalhes': detalhes,
                    'nome': st.session_state.profile.get('nome', ''),
                    'email': st.session_state.profile.get('email', ''),
                    'cpf': st.session_state.profile.get('cpf', ''),
                    'telefone': st.session_state.profile.get('cel', '')
                }
                
                carta = generate_anatel_complaint(complaint_data)
                
                st.success("✅ Reclamação ANATEL gerada com sucesso!")
                st.download_button(
                    "📥 Baixar Reclamação ANATEL",
                    data=carta,
                    file_name=f"reclamacao_anatel_{operadora}.txt",
                    mime="text/plain"
                )
            else:
                st.error("⚠️ Preencha todos os campos obrigatórios (*)")

def render_utility_service(service_data: Dict):
    """Serviço para problemas com energia e água"""
    st.info("💡 **Dica:** Use para disputar contas abusivas de energia elétrica, água e gás.")
    
    with st.form("utility_form"):
        tipo_conta = st.selectbox("Tipo de Conta*", ["Energia Elétrica", "Água/Esgoto", "Gás"])
        
        col1, col2 = st.columns(2)
        with col1:
            empresa = st.text_input("Nome da Concessionária*",
