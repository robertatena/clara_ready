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
import plotly.express as px
import plotly.graph_objects as go
from streamlit_lottie import st_lottie

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
    colors = ["#4CAF50", "#8BC34A", "#FFC107", "#FF9800", "#F44336"]
    risk_levels = ["Muito Baixo", "Baixo", "Médio", "Alto", "Muito Alto"]
    
    fig = go.Figure(go.Indicator(
        mode = "gauge+number+delta",
        value = score,
        domain = {'x': [0, 1], 'y': [0, 1]},
        title = {'text': "Nível de Risco"},
        delta = {'reference': 50},
        gauge = {
            'axis': {'range': [0, 100]},
            'bar': {'color': colors[min(score//20, 4)]},
            'steps': [
                {'range': [0, 20], 'color': "lightgray"},
                {'range': [20, 40], 'color': "lightgray"},
                {'range': [40, 60], 'color': "lightgray"},
                {'range': [60, 80], 'color': "lightgray"},
                {'range': [80, 100], 'color': "lightgray"}
            ],
            'threshold': {
                'line': {'color': "red", 'width': 4},
                'thickness': 0.75,
                'value': 90
            }
        }
    ))
    
    fig.update_layout(height=300)
    st.plotly_chart(fig, use_container_width=True)

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
    if not text.strip():
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
        
        hits, meta = analyze_contract_text(text, context)
        risk_score = risk_assessment_score(hits)
        negotiation_strategy = generate_negotiation_strategy(hits, context)
    
    if not st.session_state.premium:
        st.session_state.free_runs_left -= 1
    
    # Log da análise
    log_analysis_event(
        email=st.session_state.profile.get("email", ""),
        meta={**context, "risk_score": risk_score, "text_length": len(text)}
    )
    
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
    
    tool_tabs = st.tabs(["Calculadora CET", "Comparar Versões", "Exportar Relatório"])
    
    with tool_tabs[0]:
        advanced_cet_calculator()
    
    with tool_tabs[1]:
        st.info("🔒 Recurso Premium - Compare diferentes versões do contrato")
        if st.button("Desbloquear Comparação", type="secondary"):
            show_premium_upsell()
    
    with tool_tabs[2]:
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
    report_data = {
        "metadata": {
            "empresa": "CLARA Law",
            "versao": VERSION,
            "data_analise": datetime.now().isoformat(),
            "usuario": st.session_state.profile.get("nome", ""),
            "email": st.session_state.profile.get("email", "")
        },
        "contexto": context,
        "resumo": resume,
        "risco_total": risk_score,
        "pontos_analise": hits
    }
    
    # JSON para desenvolvedores
    json_report = json.dumps(report_data, indent=2, ensure_ascii=False)
    
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
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.download_button(
            "📥 Baixar Relatório Executivo",
            data=executive_summary.encode('utf-8'),
            file_name=f"relatorio_clara_{datetime.now().strftime('%Y%m%d_%H%M')}.txt",
            mime="text/plain"
        )
    
    with col2:
        st.download_button(
            "📊 Baixar JSON Completo",
            data=json_report.encode('utf-8'),
            file_name=f"analise_detalhada_{datetime.now().strftime('%Y%m%d_%H%M')}.json",
            mime="application/json"
        )
    
    with col3:
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
        principal = st.number_input("Valor Principal (R$)", min_value=0.0, step=1000.0)
        monthly_rate = st.number_input("Taxa de Juros Mensal (%)", min_value=0.0, step=0.1)
        installments = st.number_input("Número de Parcelas", min_value=1, step=1)
    
    with col2:
        fees = st.number_input("Taxas Administrativas (R$)", min_value=0.0, step=10.0)
        insurance = st.number_input("Seguro (R$)", min_value=0.0, step=10.0)
        other_costs = st.number_input("Outros Custos (R$)", min_value=0.0, step=10.0)
    
    total_fees = fees + insurance + other_costs
    
    if st.button("Calcular CET", use_container_width=True):
        if principal > 0 and installments > 0:
            cet = compute_cet_quick(principal, monthly_rate/100, installments, total_fees)
            
            st.success(f"**Custo Efetivo Total (CET):** {cet*100:.2f}% ao mês")
            
            # Análise comparativa
            if cet * 100 > 5:
                st.warning("⚠️ CET acima da média de mercado. Recomendamos negociar melhores condições.")
            else:
                st.info("✅ CET dentro de parâmetros razoáveis.")
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
    return "CONTRATO DE PRESTAÇÃO DE SERVIÇOS..."

def load_rental_contract_template():
    return "CONTRATO DE LOCAÇÃO RESIDENCIAL..."

# -------------------------------------------------
# Main Application
# -------------------------------------------------
def main():
    # Inicialização
    inject_custom_css()
    init_session_state()
    
    # Barra lateral
    with st.sidebar:
        render_sidebar()
    
    # Conteúdo principal
    if not st.session_state.started:
        render_landing_page()
    else:
        render_analysis_interface()

def render_sidebar():
    st.sidebar.markdown(f"""
    <div style="text-align: center; margin-bottom: 2rem;">
        <div style="font-family: 'Raleway', sans-serif; font-weight: 600; font-size: 1.5rem; color: {BRAND_COLORS['dark']};">
            CLARA Law
        </div>
        <div style="font-size: 0.8rem; color: {BRAND_COLORS['gold']};">
            Inteligência para um mundo mais claro
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Perfil do usuário
    with st.sidebar.expander("👤 Meu Perfil", expanded=True):
        render_user_profile()
    
    # Status da conta
    render_account_status()
    
    # Navegação rápida
    st.sidebar.markdown("---")
    st.sidebar.subheader("Navegação")
    
    if st.sidebar.button("🏠 Página Inicial", use_container_width=True):
        st.session_state.started = False
        st.rerun()
    
    if st.sidebar.button("📊 Histórico de Análises", use_container_width=True):
        st.session_state.show_history = True

def render_user_profile():
    nome = st.text_input("Nome Completo", value=st.session_state.profile.get("nome", ""))
    email = st.text_input("E-mail", value=st.session_state.profile.get("email", ""))
    cel = st.text_input("Celular", value=st.session_state.profile.get("cel", ""))
    empresa = st.text_input("Empresa", value=st.session_state.profile.get("empresa", ""))
    cargo = st.text_input("Cargo", value=st.session_state.profile.get("cargo", ""))
    
    if st.button("💾 Salvar Perfil", use_container_width=True):
        # Validação básica
        if email and not re.match(r"^[^\s@]+@[^\s@]+\.[^\s@]+$", email):
            st.error("Por favor, insira um e-mail válido.")
        else:
            st.session_state.profile.update({
                "nome": nome, "email": email, "cel": cel,
                "empresa": empresa, "cargo": cargo
            })
            st.success("Perfil atualizado!")

def render_account_status():
    st.sidebar.markdown("---")
    st.sidebar.subheader("Minha Conta")
    
    if st.session_state.premium:
        st.sidebar.success("💎 Conta Premium")
        st.sidebar.metric("Análises Restantes", "Ilimitadas")
    else:
        st.sidebar.warning("🆓 Conta Gratuita")
        st.sidebar.metric("Análises Restantes", st.session_state.free_runs_left)
        
        if st.sidebar.button("🚀 Fazer Upgrade", use_container_width=True):
            st.session_state.show_pricing = True

def render_landing_page():
    premium_hero_section()
    features_section()
    social_proof_section()
    
    # Call-to-action final
    st.markdown("---")
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.header("🎯 Pronto para tomar decisões mais seguras?")
        st.markdown("Comece agora sua análise gratuita e experimente o poder da CLARA Law.")
    
    with col2:
        if st.button("📄 Iniciar Análise do Contrato", use_container_width=True, type="primary"):
            st.session_state.started = True
            st.rerun()

def render_analysis_interface():
    st.header("⚖️ Análise de Contrato - CLARA Law")
    
    # Fluxo de análise
    contract_text = advanced_upload_section()
    analysis_context = context_analysis_section()
    
    st.markdown("---")
    
    if st.button("🚀 Executar Análise Completa", type="primary", use_container_width=True):
        if st.session_state.current_contract:
            advanced_analysis_results(st.session_state.current_contract, analysis_context)
        else:
            st.error("Por favor, carregue um contrato antes de executar a análise.")

if __name__ == "__main__":
    main()








