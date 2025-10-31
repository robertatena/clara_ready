import os
import io
import re
import csv
import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Any, Tuple, Set, List, Optional
import uuid

import streamlit as st
import pandas as pd
import altair as alt

# ---- módulos locais ----
from app_modules.pdf_utils import extract_text_from_pdf, extract_pdf_metadata
from app_modules.analysis import (
    analyze_contract_text, 
    summarize_hits, 
    compute_cet_quick,
    risk_assessment_score,
    generate_negotiation_strategy
)
from app_modules.stripe_utils import init_stripe, create_checkout_session, verify_checkout_session
from app_modules.storage import (
    init_db,
    log_analysis_event,
    log_subscriber,
    list_subscribers,
    get_subscriber_by_email,
    get_user_history,
    save_contract_draft
)

# -------------------------------------------------
# Configurações Avançadas
# -------------------------------------------------
APP_TITLE = "CLARA Law"
APP_SUBTITLE = "Inteligência para um mundo mais claro"
VERSION = "v2.0"

st.set_page_config(
    page_title=APP_TITLE,
    page_icon="⚖️", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# Cores da marca conforme brandbook
BRAND_COLORS = {
    "gold": "#D4AF37",
    "blue": "#ABDBF0", 
    "white": "#FFFFFF",
    "gray": "#F2F2F2",
    "dark": "#0f172a"
}

# Secrets
STRIPE_PUBLIC_KEY = st.secrets.get("STRIPE_PUBLIC_KEY", "")
STRIPE_SECRET_KEY = st.secrets.get("STRIPE_SECRET_KEY", "")
STRIPE_PRICE_ID = st.secrets.get("STRIPE_PRICE_ID", "")
BASE_URL = st.secrets.get("BASE_URL", "https://claralaw.streamlit.app")

# -------------------------------------------------
# Sistema de Estilos Avançado
# -------------------------------------------------
def inject_custom_css():
    st.markdown(f"""
    <style>
        :root {{
            --gold: {BRAND_COLORS['gold']};
            --blue: {BRAND_COLORS['blue']};
            --white: {BRAND_COLORS['white']};
            --gray: {BRAND_COLORS['gray']};
            --dark: {BRAND_COLORS['dark']};
        }}
        
        .main {{
            background: linear-gradient(135deg, var(--white) 0%, var(--gray) 100%);
        }}
        
        .clara-hero {{
            background: 
                radial-gradient(ellipse at 30% 50%, var(--blue) 0%, transparent 60%),
                radial-gradient(ellipse at 70% 20%, var(--gold) 0%, transparent 50%),
                linear-gradient(135deg, var(--white) 0%, var(--gray) 100%);
            padding: 80px 0 60px;
            border-radius: 0 0 40px 40px;
            margin-bottom: 40px;
        }}
        
        .clara-logo {{
            font-family: 'Raleway', sans-serif;
            font-weight: 600;
            font-size: 2.5rem;
            color: var(--dark);
            margin-bottom: 1rem;
        }}
        
        .clara-subtitle {{
            font-family: 'Montserrat', sans-serif;
            font-weight: 300;
            font-size: 1.4rem;
            color: var(--dark);
            opacity: 0.8;
            margin-bottom: 2rem;
        }}
        
        .feature-card {{
            background: var(--white);
            border-radius: 20px;
            padding: 30px;
            border: 1px solid rgba(212, 175, 55, 0.2);
            box-shadow: 0 8px 32px rgba(0,0,0,0.05);
            transition: transform 0.3s ease, box-shadow 0.3s ease;
            height: 100%;
        }}
        
        .feature-card:hover {{
            transform: translateY(-5px);
            box-shadow: 0 12px 40px rgba(212, 175, 55, 0.15);
        }}
        
        .feature-icon {{
            font-size: 2.5rem;
            margin-bottom: 1rem;
            color: var(--gold);
        }}
        
        .risk-badge {{
            background: linear-gradient(135deg, #ff6b6b, #ee5a52);
            color: white;
            padding: 8px 16px;
            border-radius: 20px;
            font-size: 0.8rem;
            font-weight: 600;
        }}
        
        .medium-risk-badge {{
            background: linear-gradient(135deg, #ffa726, #ff9800);
            color: white;
            padding: 8px 16px;
            border-radius: 20px;
            font-size: 0.8rem;
            font-weight: 600;
        }}
        
        .low-risk-badge {{
            background: linear-gradient(135deg, #66bb6a, #4caf50);
            color: white;
            padding: 8px 16px;
            border-radius: 20px;
            font-size: 0.8rem;
            font-weight: 600;
        }}
        
        .premium-badge {{
            background: linear-gradient(135deg, var(--gold), #b8941f);
            color: var(--dark);
            padding: 6px 12px;
            border-radius: 12px;
            font-size: 0.7rem;
            font-weight: 700;
            text-transform: uppercase;
        }}
        
        .clara-button {{
            background: linear-gradient(135deg, var(--gold), #b8941f);
            color: var(--dark);
            border: none;
            border-radius: 15px;
            padding: 15px 30px;
            font-weight: 700;
            font-size: 1.1rem;
            transition: all 0.3s ease;
            box-shadow: 0 4px 15px rgba(212, 175, 55, 0.3);
        }}
        
        .clara-button:hover {{
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(212, 175, 55, 0.4);
        }}
        
        .stats-card {{
            background: var(--white);
            border-radius: 15px;
            padding: 20px;
            border-left: 4px solid var(--gold);
            box-shadow: 0 4px 15px rgba(0,0,0,0.05);
        }}
        
        .contract-preview {{
            background: var(--gray);
            border-radius: 10px;
            padding: 20px;
            border: 2px dashed var(--blue);
            margin: 10px 0;
        }}
        
        .risk-meter {{
            background: linear-gradient(90deg, #4CAF50 0%, #8BC34A 20%, #FFC107 40%, #FF9800 60%, #F44336 100%);
            height: 20px;
            border-radius: 10px;
            margin: 10px 0;
            position: relative;
        }}
        
        .risk-indicator {{
            position: absolute;
            top: -5px;
            width: 4px;
            height: 30px;
            background: var(--dark);
            border-radius: 2px;
        }}
    </style>
    """, unsafe_allow_html=True)

# -------------------------------------------------
# Estado da Sessão Avançado
# -------------------------------------------------
def init_session_state():
    defaults = {
        "started": False,
        "premium": False,
        "user_id": str(uuid.uuid4()),
        "profile": {
            "nome": "", "email": "", "cel": "", 
            "papel": "Contratante", "empresa": "", "cargo": ""
        },
        "free_runs_left": 2,
        "current_contract": None,
        "analysis_history": [],
        "contract_drafts": [],
        "onboarding_complete": False
    }
    
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

# -------------------------------------------------
# Componentes Reutilizáveis
# -------------------------------------------------
def clara_logo():
    st.markdown(f"""
    <div style="text-align: center; margin-bottom: 2rem;">
        <div class="clara-logo">CLARA Law</div>
        <div class="clara-subtitle">Inteligência para um mundo mais claro</div>
    </div>
    """, unsafe_allow_html=True)

def feature_card(icon: str, title: str, description: str, premium: bool = False):
    premium_badge = "<span class='premium-badge'>Premium</span>" if premium else ""
    st.markdown(f"""
    <div class="feature-card">
        <div class="feature-icon">{icon}</div>
        <h3>{title} {premium_badge}</h3>
        <p>{description}</p>
    </div>
    """, unsafe_allow_html=True)

def risk_meter(score: int):
    """Medidor de risco usando HTML/CSS puro"""
    position = min(score, 100)
    
    st.markdown(f"""
    <div style="margin: 20px 0;">
        <div style="display: flex; justify-content: space-between; margin-bottom: 5px;">
            <span style="font-size: 0.8rem; color: #4CAF50;">0</span>
            <span style="font-size: 0.8rem; color: #666;">Nível de Risco: {score}/100</span>
            <span style="font-size: 0.8rem; color: #F44336;">100</span>
        </div>
        <div class="risk-meter">
            <div class="risk-indicator" style="left: {position}%;"></div>
        </div>
        <div style="display: flex; justify-content: space-between; margin-top: 5px;">
            <span style="font-size: 0.7rem; color: #4CAF50;">Muito Baixo</span>
            <span style="font-size: 0.7rem; color: #FFC107;">Médio</span>
            <span style="font-size: 0.7rem; color: #F44336;">Muito Alto</span>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Indicador de nível de risco
    if score >= 80:
        st.error("⚠️ **Risco Muito Alto** - Recomendamos revisão urgente com especialista")
    elif score >= 60:
        st.warning("🔶 **Risco Alto** - Atenção necessária a várias cláusulas")
    elif score >= 40:
        st.info("🔸 **Risco Médio** - Alguns pontos requerem atenção")
    elif score >= 20:
        st.success("✅ **Risco Baixo** - Contrato relativamente seguro")
    else:
        st.success("🛡️ **Risco Muito Baixo** - Contrato bem estruturado")

# -------------------------------------------------
# Tela Inicial Premium
# -------------------------------------------------
def premium_hero_section():
    st.markdown('<div class="clara-hero">', unsafe_allow_html=True)
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        clara_logo()
        
        st.markdown("""
        <h1 style='font-size: 3.5rem; font-weight: 800; color: var(--dark); margin-bottom: 1.5rem;'>
            Entenda cada linha<br>do seu contrato
        </h1>
        
        <p style='font-size: 1.3rem; color: var(--dark); opacity: 0.8; margin-bottom: 2.5rem; line-height: 1.6;'>
            A CLARA Law descomplica documentos jurídicos com inteligência artificial, 
            destacando riscos, explicando cláusulas e sugerindo melhorias em linguagem simples.
        </p>
        """, unsafe_allow_html=True)
        
        c1, c2 = st.columns([1, 1])
        with c1:
            if st.button("📄 Analisar Meu Contrato", use_container_width=True, key="hero_analyze"):
                st.session_state.started = True
                st.rerun()
        with c2:
            if st.button("🎥 Ver Demonstração", use_container_width=True, type="secondary"):
                st.session_state.show_demo = True
    
    with col2:
        # Espaço para animação Lottie ou imagem da marca
        st.markdown("""
        <div style='text-align: center; padding: 2rem;'>
            <div style='font-size: 4rem; margin-bottom: 1rem;'>⚖️</div>
            <h3 style='color: var(--dark);'>Análise Jurídica Inteligente</h3>
            <p style='color: var(--dark); opacity: 0.7;'>Tecnologia + Expertise Jurídica</p>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown('</div>', unsafe_allow_html=True)

def features_section():
    st.header("✨ Por que escolher a CLARA Law?")
    
    cols = st.columns(3)
    
    with cols[0]:
        feature_card("🛡️", "Proteção Contra Riscos", 
                    "Identificamos cláusulas abusivas, multas excessivas e termos prejudiciais antes que você assine.")
    
    with cols[1]:
        feature_card("🧠", "Explicações Simples", 
                    "Traduzimos juridiquês para português claro. Entenda foro, multa rescisória, confidencialidade e mais.")
    
    with cols[2]:
        feature_card("💼", "Estratégias de Negociação", 
                    "Receba sugestões práticas para negociar melhorias no contrato com a outra parte.")

    cols2 = st.columns(3)
    
    with cols2[0]:
        feature_card("📈", "Calculadora Financeira", 
                    "Calcule CET, multas e valores reais do contrato. Tome decisões com dados concretos.", premium=True)
    
    with cols2[1]:
        feature_card("📊", "Relatórios Detalhados", 
                    "Gere relatórios profissionais para compartilhar com sua equipe ou advogado.", premium=True)
    
    with cols2[2]:
        feature_card("🔔", "Alertas Inteligentes", 
                    "Monitoramos mudanças legais que podem afetar seus contratos.", premium=True)

def social_proof_section():
    st.header("🏆 Confiado por milhares de usuários")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown('<div class="stats-card">', unsafe_allow_html=True)
        st.metric("Contratos Analisados", "15.000+", "+28%")
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col2:
        st.markdown('<div class="stats-card">', unsafe_allow_html=True)
        st.metric("Riscos Identificados", "42.000+", "+15%")
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col3:
        st.markdown('<div class="stats-card">', unsafe_allow_html=True)
        st.metric("Economia Estimada", "R$ 8,2 Mi", "+32%")
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col4:
        st.markdown('<div class="stats-card">', unsafe_allow_html=True)
        st.metric("Satisfação", "4.9/5", "⭐")
        st.markdown('</div>', unsafe_allow_html=True)

# -------------------------------------------------
# Sistema de Análise Avançado
# -------------------------------------------------
def advanced_upload_section():
    st.header("1. 📄 Envie seu contrato")
    
    tab1, tab2, tab3 = st.tabs(["Upload PDF", "Cole o Texto", "Modelos"])
    
    with tab1:
        uploaded_file = st.file_uploader(
            "Arraste o PDF aqui ou clique para procurar", 
            type=["pdf"],
            help="Suporte para PDFs com texto selecionável (não escaneados)"
        )
        
        if uploaded_file:
            with st.spinner("🔍 Analisando estrutura do documento..."):
                try:
                    metadata = extract_pdf_metadata(uploaded_file)
                    text_content = extract_text_from_pdf(uploaded_file)
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        st.info(f"📑 Páginas: {metadata.get('pages', 'N/A')}")
                        st.info(f"📏 Tamanho: {metadata.get('size', 'N/A')}")
                    
                    with col2:
                        st.info(f"✍️ Palavras: {len(text_content.split())}")
                        st.info(f"📊 Caracteres: {len(text_content)}")
                    
                    st.session_state.current_contract = text_content
                    st.success("✅ Documento carregado com sucesso!")
                except Exception as e:
                    st.error(f"❌ Erro ao processar PDF: {str(e)}")
    
    with tab2:
        text_input = st.text_area(
            "Cole o texto do contrato aqui:",
            height=300,
            placeholder="Exemplo: Pelo presente instrumento particular, as partes mutuamente se obrigam...",
            help="Cole o texto completo do contrato para análise"
        )
        if text_input:
            st.session_state.current_contract = text_input
            st.success("✅ Texto carregado para análise!")
    
    with tab3:
        st.subheader("Modelos de Contrato")
        template_cols = st.columns(2)
        
        with template_cols[0]:
            if st.button("📝 Contrato de Prestação de Serviços", use_container_width=True):
                st.session_state.current_contract = load_service_contract_template()
                st.success("✅ Modelo carregado! Adapte conforme necessário.")
        
        with template_cols[1]:
            if st.button("🏠 Contrato de Locação Residencial", use_container_width=True):
                st.session_state.current_contract = load_rental_contract_template()
                st.success("✅ Modelo carregado! Adapte conforme necessário.")
    
    return st.session_state.current_contract

def context_analysis_section():
    st.header("2. 🎯 Contexto da Análise")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        contract_type = st.selectbox(
            "Tipo de Contrato",
            ["Prestação de Serviços", "Locação", "Empréstimo", "Compra e Venda", "Trabalho", "Outro"]
        )
        
        industry = st.selectbox(
            "Setor/Área",
            ["Tecnologia", "Saúde", "Educação", "Financeiro", "Imobiliário", "Varejo", "Outro"]
        )
    
    with col2:
        your_role = st.selectbox(
            "Seu Papel",
            ["Contratante", "Contratado", "Prestador", "Cliente", "Fornecedor"]
        )
        
        contract_value = st.number_input(
            "Valor do Contrato (R$)",
            min_value=0.0,
            step=1000.0,
            format="%.2f"
        )
    
    with col3:
        urgency = st.select_slider(
            "Urgência da Análise",
            options=["Baixa", "Média", "Alta", "Crítica"]
        )
        
        priority_areas = st.multiselect(
            "Áreas de Interesse Especial",
            ["Multas e Penalidades", "Confidencialidade", "Prazo e Renovação", 
             "Garantias", "Responsabilidades", "Rescisão", "Jurisdição"]
        )
    
    return {
        "contract_type": contract_type,
        "industry": industry,
        "your_role": your_role,
        "contract_value": contract_value,
        "urgency": urgency,
        "priority_areas": priority_areas
    }

def advanced_analysis_results(text: str, context: Dict[str, Any]):
    if not text or not text.strip():
        st.warning("Por favor, carregue um contrato para análise.")
        return
    
    # Verificação de limite gratuito
    if not st.session_state.premium and st.session_state.free_runs_left <= 0:
        show_premium_upsell()
        return
    
    with st.spinner("🔍 CLARA está analisando seu contrato..."):
        progress_bar = st.progress(0)
        
        # Simulação de progresso para melhor UX
        for i in range(100):
            progress_bar.progress(i + 1)
        
        try:
            hits, meta = analyze_contract_text(text, context)
            risk_score = risk_assessment_score(hits)
            negotiation_strategy = generate_negotiation_strategy(hits, context)
        except Exception as e:
            st.error(f"❌ Erro na análise: {str(e)}")
            return
    
    if not st.session_state.premium:
        st.session_state.free_runs_left -= 1
    
    # Log da análise
    try:
        log_analysis_event(
            email=st.session_state.profile.get("email", ""),
            meta={**context, "risk_score": risk_score, "text_length": len(text)}
        )
    except Exception:
        pass  # Ignora erros de log
    
    # Header dos resultados
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
        resume = summarize_hits(hits)
        st.success(f"**Resumo da Análise:** {resume['resumo']}")
    
    with col2:
        st.metric("Pontos Críticos", resume['criticos'])
    
    with col3:
        st.metric("Gravidade", resume['gravidade'])
    
    # Medidor de Risco
    st.header("📊 Medidor de Risco do Contrato")
    risk_meter(risk_score)
    
    # Análise Detalhada
    st.header("🔍 Análise Detalhada por Cláusula")
    
    for i, hit in enumerate(hits):
        risk_color = {
            "Alto": "risk-badge",
            "Médio": "medium-risk-badge", 
            "Baixo": "low-risk-badge"
        }.get(hit['severity'], "low-risk-badge")
        
        with st.expander(
            f"{hit['severity']} • {hit['title']} • " + 
            f"<span class='{risk_color}'>{hit['severity']}</span>", 
            expanded=i < 2  # Expande os dois primeiros por padrão
        ):
            col_a, col_b = st.columns([3, 1])
            
            with col_a:
                st.markdown(f"**📝 Explicação:** {hit.get('explanation', '')}")
                
                if hit.get('suggestion'):
                    st.markdown(f"**💡 Sugestão de Negociação:** {hit['suggestion']}")
                
                if hit.get('legal_basis'):
                    st.markdown(f"**⚖️ Base Legal:** {hit['legal_basis']}")
            
            with col_b:
                if hit.get('evidence'):
                    with st.container():
                        st.markdown("**📄 Trecho Original:**")
                        st.text(hit['evidence'][:500] + ("..." if len(hit['evidence']) > 500 else ""))
    
    # Estratégia de Negociação
    if negotiation_strategy:
        st.header("🎯 Estratégia de Negociação Recomendada")
        st.markdown(negotiation_strategy)
    
    # Ferramentas Adicionais
    st.header("🛠️ Ferramentas Adicionais")
    
    tool_tabs = st.tabs(["Calculadora CET", "Exportar Relatório"])
    
    with tool_tabs[0]:
        advanced_cet_calculator()
    
    with tool_tabs[1]:
        export_advanced_report(hits, resume, context, risk_score)

# -------------------------------------------------
# Funções Auxiliares
# -------------------------------------------------
def show_premium_upsell():
    st.warning("""
    🚀 **Você atingiu o limite de análises gratuitas!**
    
    Com o **CLARA Law Premium** você recebe:
    • Análises ilimitadas
    • Relatórios detalhados
    • Calculadora financeira avançada
    • Comparação de versões
    • Suporte prioritário
    """)
    
    if st.button("💎 Desbloquear Premium Agora", type="primary"):
        st.session_state.show_pricing = True

def export_advanced_report(hits, resume, context, risk_score):
    # Relatório executivo em texto
    executive_summary = f"""
    RELATÓRIO DE ANÁLISE - CLARA Law
    =================================
    
    Contrato: {context.get('contract_type', 'Não especificado')}
    Data da Análise: {datetime.now().strftime('%d/%m/%Y %H:%M')}
    Usuário: {st.session_state.profile.get('nome', 'Não informado')}
    
    RESUMO EXECUTIVO:
    {resume['resumo']}
    
    PONTOS CRÍTICOS: {resume['criticos']}
    NÍVEL DE GRAVIDADE: {resume['gravidade']}
    SCORE DE RISCO: {risk_score}/100
    
    DESTAQUES DA ANÁLISE:
    """
    
    for i, hit in enumerate(hits[:5], 1):
        executive_summary += f"\n{i}. [{hit['severity']}] {hit['title']}\n"
    
    executive_summary += f"""
    
    RECOMENDAÇÕES:
    1. Revise os pontos classificados como 'Alto Risco' com atenção
    2. Considere negociar as cláusulas problemáticas
    3. Consulte um advogado para validação final
    
    ---
    CLARA Law - Inteligência para um mundo mais claro
    Este relatório foi gerado automaticamente e não substitui aconselhamento jurídico profissional.
    """
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.download_button(
            "📥 Baixar Relatório Executivo",
            data=executive_summary.encode('utf-8'),
            file_name=f"relatorio_clara_{datetime.now().strftime('%Y%m%d_%H%M')}.txt",
            mime="text/plain"
        )
    
    with col2:
        st.download_button(
            "📧 Gerar E-mail para Advogado",
            data=generate_lawyer_email(resume, hits).encode('utf-8'),
            file_name=f"email_advogado_{datetime.now().strftime('%Y%m%d_%H%M')}.txt",
            mime="text/plain"
        )

def advanced_cet_calculator():
    st.subheader("Calculadora de Custo Efetivo Total")
    
    col1, col2 = st.columns(2)
    
    with col1:
        principal = st.number_input("Valor Principal (R$)", min_value=0.0, step=1000.0, key="cet_principal")
        monthly_rate = st.number_input("Taxa de Juros Mensal (%)", min_value=0.0, step=0.1, key="cet_rate")
        installments = st.number_input("Número de Parcelas", min_value=1, step=1, key="cet_installments")
    
    with col2:
        fees = st.number_input("Taxas Administrativas (R$)", min_value=0.0, step=10.0, key="cet_fees")
        insurance = st.number_input("Seguro (R$)", min_value=0.0, step=10.0, key="cet_insurance")
        other_costs = st.number_input("Outros Custos (R$)", min_value=0.0, step=10.0, key="cet_other")
    
    total_fees = fees + insurance + other_costs
    
    if st.button("Calcular CET", use_container_width=True, key="btn_calc_cet"):
        if principal > 0 and installments > 0:
            try:
                cet = compute_cet_quick(principal, monthly_rate/100, installments, total_fees)
                
                st.success(f"**Custo Efetivo Total (CET):** {cet*100:.2f}% ao mês")
                
                # Análise comparativa
                if cet * 100 > 5:
                    st.warning("⚠️ CET acima da média de mercado. Recomendamos negociar melhores condições.")
                else:
                    st.info("✅ CET dentro de parâmetros razoáveis.")
            except Exception as e:
                st.error(f"Erro no cálculo: {str(e)}")
        else:
            st.error("Por favor, preencha os valores principal e número de parcelas.")

def generate_lawyer_email(resume, hits):
    critical_points = [h for h in hits if h['severity'] in ['Alto', 'Médio']][:3]
    
    email_content = f"""
Prezado(a) Advogado(a),

Solicito sua análise profissional do contrato em anexo, com atenção especial aos seguintes pontos identificados pela CLARA Law:

RESUMO DA ANÁLISE AUTOMÁTICA:
{resume['resumo']}

PONTOS QUE REQUEREM ATENÇÃO ESPECIAL:

"""
    
    for i, point in enumerate(critical_points, 1):
        email_content += f"{i}. {point['title']}\n"
        email_content += f"   Risco: {point['severity']}\n"
        email_content += f"   Contexto: {point.get('explanation', '')}\n\n"
    
    email_content += f"""
Solicito sua avaliação sobre:
- Legalidade das cláusulas problemáticas
- Sugestões de redação alternativa
- Riscos adicionais não detectados
- Estratégias de negociação

Atenciosamente,
{st.session_state.profile.get('nome', 'Cliente')}
"""
    
    return email_content

# -------------------------------------------------
# Funções de Modelo (placeholder)
# -------------------------------------------------
def load_service_contract_template():
    return """CONTRATO DE PRESTAÇÃO DE SERVIÇOS

ENTRE:
[NOME DA CONTRATANTE], [nacionalidade], [estado civil], [profissão], 
portador(a) do CPF nº [número] e RG nº [número], residente e 
domiciliado(a) na [endereço completo], doravante denominada CONTRATANTE;

E:
[NOME DA CONTRATADA], [nacionalidade], [estado civil], [profissão], 
portador(a) do CPF nº [número] e RG nº [número], residente e 
domiciliado(a) na [endereço completo], doravante denominada CONTRATADA.

As partes acima identificadas têm, entre si, justo e acertado o 
presente Contrato de Prestação de Serviços, que se regerá pelas 
cláusulas seguintes:

CLÁUSULA 1ª - DO OBJETO
O presente contrato tem por objeto a prestação de serviços de 
[descrição detalhada dos serviços] pela CONTRATADA para a CONTRATANTE.

CLÁUSULA 2ª - DO PRAZO
O presente contrato vigorará pelo prazo de [número] meses, 
iniciando-se em [data] e terminando em [data], podendo ser renovado 
mediante acordo entre as partes.

CLÁUSULA 3ª - DO VALOR E FORMA DE PAGAMENTO
Os serviços serão remunerados pelo valor mensal de R$ [valor], 
a ser pago até o dia [dia] de cada mês, mediante [forma de pagamento].

CLÁUSULA 4ª - DAS OBRIGAÇÕES DAS PARTES
4.1. São obrigações da CONTRATADA:
a) Executar os serviços com diligência e capacidade técnica;
b) Manter sigilo sobre informações da CONTRATANTE;

4.2. São obrigações da CONTRATANTE:
a) Fornecer informações necessárias à execução dos serviços;
b) Efetuar os pagamentos nos prazos estipulados;

E por estarem assim justas e acertadas, assinam o presente contrato 
em duas vias de igual teor e forma.

[Local], [data]

___________________________
[Nome da Contratante]

___________________________
[Nome da Contratada]"""

def load_rental_contract_template():
    return """CONTRATO DE LOCAÇÃO RESIDENCIAL

ENTRE:
[NOME DO LOCADOR], [nacionalidade], [estado civil], [profissão], 
portador(a) do CPF nº [número] e RG nº [número], residente e 
domiciliado(a) na [endereço completo], doravante denominado LOCADOR;

E:
[NOME DO LOCATÁRIO], [nacionalidade], [estado civil], [profissão], 
portador(a) do CPF nº [número] e RG nº [número], residente e 
domiciliado(a) na [endereço completo], doravante denominado LOCATÁRIO.

Celebram as partes o presente Contrato de Locação Residencial, 
que se regerá pelas cláusulas seguintes:

CLÁUSULA 1ª - DO IMÓVEL
Fica locado ao LOCATÁRIO o imóvel residencial situado à 
[endereço completo do imóvel], com as seguintes características:
[descrição detalhada do imóvel].

CLÁUSULA 2ª - DO PRAZO
A locação terá o prazo de [número] meses, iniciando-se em [data] 
e terminando em [data].

CLÁUSULA 3ª - DO ALUGUEL
3.1. O aluguel mensal será de R$ [valor], a ser pago até o 
dia [dia] de cada mês.

3.2. O reajuste do aluguel obedecerá aos índices [especificar índice] 
ou variação do IGP-M, o que for menor.

CLÁUSULA 4ª - DAS GARANTIAS
4.1. Como garantia do fiel cumprimento do contrato, o LOCATÁRIO 
depositará em favor do LOCADOR o equivalente a [número] meses de aluguel.

CLÁUSULA 5ª - DAS CONDIÇÕES GERAIS
5.1. O LOCATÁRIO obriga-se a usar o imóvel para fins exclusivamente 
residenciais.

5.2. É vedado ao LOCATÁRIO ceder, transferir ou sublocar o







