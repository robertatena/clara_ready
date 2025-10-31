import os
import io
import re
import csv
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional
import uuid

import streamlit as st
import pandas as pd
import PyPDF2
from io import BytesIO

# ==================================================
# CONFIGURAÇÕES GLOBAIS
# ==================================================
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

# ==================================================
# SISTEMA DE ESTILOS
# ==================================================
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
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 0.7rem;
            font-weight: 600;
        }}
        
        .medium-risk-badge {{
            background: linear-gradient(135deg, #ffa726, #ff9800);
            color: white;
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 0.7rem;
            font-weight: 600;
        }}
        
        .low-risk-badge {{
            background: linear-gradient(135deg, #66bb6a, #4caf50);
            color: white;
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 0.7rem;
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
        
        .stats-card {{
            background: var(--white);
            border-radius: 15px;
            padding: 20px;
            border-left: 4px solid var(--gold);
            box-shadow: 0 4px 15px rgba(0,0,0,0.05);
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
        
        .section-divider {{
            background: linear-gradient(90deg, var(--gold), var(--blue));
            height: 3px;
            border-radius: 2px;
            margin: 30px 0;
        }}
    </style>
    """, unsafe_allow_html=True)

# ==================================================
# MÓDULOS DE ANÁLISE DE PDF
# ==================================================
def extract_text_from_pdf(file):
    """Extrai texto de um arquivo PDF"""
    try:
        pdf_reader = PyPDF2.PdfReader(file)
        text = ""
        for page in pdf_reader.pages:
            text += page.extract_text() + "\n"
        return text
    except Exception as e:
        return f"Erro ao extrair texto do PDF: {str(e)}"

def extract_pdf_metadata(file):
    """Extrai metadados básicos do PDF"""
    try:
        pdf_reader = PyPDF2.PdfReader(file)
        return {
            "pages": len(pdf_reader.pages),
            "size": f"{len(file.getvalue()) / 1024:.1f}KB"
        }
    except Exception:
        return {"pages": 0, "size": "N/A"}

# ==================================================
# MÓDULOS DE ANÁLISE DE CONTRATO
# ==================================================
def analyze_contract_text(text, context):
    """Analisa o texto do contrato e retorna pontos de atenção"""
    # Padrões de busca para cláusulas problemáticas
    patterns = {
        "Alto": [
            (r"multa.*(\d{2,3})%", "Multa percentual alta detectada"),
            (r"juros.*(\d{2,3})%", "Juros elevados identificados"),
            (r"exclusiv[ao].*responsabilidade", "Cláusula de exclusão de responsabilidade"),
            (r"renúncia.*direitos", "Possível renúncia de direitos"),
        ],
        "Médio": [
            (r"foro.*[ée]leito", "Foro de eleição restritivo"),
            (r"confidencialidade.*perpetua", "Confidencialidade perpétua"),
            (r"rescisão.*unilateral", "Rescisão unilateral"),
            (r"alteração.*unilateral", "Alteração unilateral do contrato"),
        ],
        "Baixo": [
            (r"prazo.*indeterminado", "Prazo indeterminado"),
            (r"renovação.*automática", "Renovação automática"),
            (r"notificação.*[ée]letrônica", "Notificação eletrônica"),
        ]
    }
    
    hits = []
    
    for severity, pattern_list in patterns.items():
        for pattern, title in pattern_list:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                start = max(0, match.start() - 100)
                end = min(len(text), match.end() + 100)
                evidence = text[start:end].strip()
                
                hit = {
                    "severity": severity,
                    "title": title,
                    "explanation": generate_explanation(title, severity, context),
                    "suggestion": generate_suggestion(title, severity),
                    "evidence": evidence
                }
                hits.append(hit)
    
    # Se não encontrou padrões, cria análise genérica
    if not hits:
        hits = [{
            "severity": "Baixo",
            "title": "Análise inicial concluída",
            "explanation": "O contrato parece bem estruturado. Recomendamos revisão de advogado para validação completa.",
            "suggestion": "Consulte um profissional para análise detalhada de cláusulas específicas.",
            "evidence": text[:200] + "..." if len(text) > 200 else text
        }]
    
    meta = {
        "analysis_time": datetime.now().isoformat(),
        "words_processed": len(text.split()),
        "risk_factors": len(hits)
    }
    
    return hits, meta

def generate_explanation(title, severity, context):
    """Gera explicação baseada no tipo de cláusula"""
    explanations = {
        "Multa percentual alta detectada": f"Multas acima de 10% podem ser consideradas abusivas segundo o CDC, especialmente para {context.get('your_role', 'contratante')}.",
        "Juros elevados identificados": "Taxas de juros muito altas podem caracterizar anatocismo (juros sobre juros), prática vedada pelo código civil.",
        "Cláusula de exclusão de responsabilidade": "Cláusulas que excluem totalmente a responsabilidade de uma parte podem ser nulas por ferir a boa-fé objetiva.",
        "Foro de eleição restritivo": f"O foro escolhido pode dificultar o acesso à justiça para o {context.get('your_role', 'contratante')}, especialmente se for distante de seu domicílio.",
        "Confidencialidade perpétua": "Obrigações de confidencialidade sem prazo determinado podem ser excessivas e limitar futuras atividades profissionais.",
        "Rescisão unilateral": "Cláusulas que permitem rescisão sem justa causa podem gerar insegurança jurídica para ambas as partes.",
    }
    return explanations.get(title, f"Cláusula identificada como {severity.lower()} risco. Recomendamos análise detalhada.")

def generate_suggestion(title, severity):
    """Gera sugestões de negociação"""
    suggestions = {
        "Multa percentual alta detectada": "Negociar redução para 2-10% do valor devido, conforme razoabilidade.",
        "Juros elevados identificados": "Sugerir taxa de 1% ao mês + TR ou outro índice oficial.",
        "Cláusula de exclusão de responsabilidade": "Propor redação que limite responsabilidade a casos de dolo ou culpa grave.",
        "Foro de eleição restritivo": "Sugerir foro do domicílio do consumidor ou local de execução do contrato.",
        "Confidencialidade perpétua": "Estabelecer prazo de 2-5 anos para obrigação de confidencialidade.",
        "Rescisão unilateral": "Incluir prazo de aviso prévio e motivos específicos para rescisão.",
    }
    return suggestions.get(title, "Consulte um advogado para orientação específica sobre esta cláusula.")

def summarize_hits(hits):
    """Resume os pontos encontrados na análise"""
    high_risk = len([h for h in hits if h['severity'] == 'Alto'])
    medium_risk = len([h for h in hits if h['severity'] == 'Médio'])
    low_risk = len([h for h in hits if h['severity'] == 'Baixo'])
    
    total = len(hits)
    
    if high_risk > 0:
        gravidade = "Alta"
        resumo = f"⚠️ {high_risk} ponto(s) de alto risco identificado(s). Recomendamos revisão urgente."
    elif medium_risk > 0:
        gravidade = "Média"
        resumo = f"🔶 {medium_risk} ponto(s) de médio risco. Atenção necessária."
    else:
        gravidade = "Baixa"
        resumo = f"✅ {total} ponto(s) identificado(s). Contrato aparenta estar em boas condições."
    
    return {
        "resumo": resumo,
        "gravidade": gravidade,
        "criticos": high_risk,
        "total": total
    }

def risk_assessment_score(hits):
    """Calcula score de risco baseado nos pontos encontrados"""
    score = 0
    for hit in hits:
        if hit['severity'] == 'Alto':
            score += 25
        elif hit['severity'] == 'Médio':
            score += 15
        else:
            score += 5
    
    return min(100, score)

def generate_negotiation_strategy(hits, context):
    """Gera estratégia de negociação personalizada"""
    high_risk = [h for h in hits if h['severity'] == 'Alto']
    medium_risk = [h for h in hits if h['severity'] == 'Médio']
    
    strategy = f"## 🎯 Estratégia de Negociação para {context.get('your_role', 'você')}\n\n"
    
    if high_risk:
        strategy += "### 🔴 Prioridade Máxima (Alto Risco):\n"
        for i, hit in enumerate(high_risk[:3], 1):
            strategy += f"{i}. **{hit['title']}** - {hit['suggestion']}\n"
        strategy += "\n"
    
    if medium_risk:
        strategy += "### 🟡 Prioridade Média:\n"
        for i, hit in enumerate(medium_risk[:2], 1):
            strategy += f"{i}. **{hit['title']}** - {hit['suggestion']}\n"
    
    if not high_risk and not medium_risk:
        strategy += "### ✅ Contrato Bem Equilibrado\n"
        strategy += "O contrato apresenta riscos administráveis. Foque em ajustes menores e clarificações.\n"
    
    strategy += f"\n**💡 Dica:** Como {context.get('your_role', 'contratante')}, concentre-se em proteger seus direitos fundamentais."
    
    return strategy

# ==================================================
# MÓDULOS FINANCEIROS
# ==================================================
def compute_cet_quick(principal, rate, installments, fees):
    """Calcula Custo Efetivo Total aproximado"""
    try:
        if rate == 0:
            rate = 0.01  # Taxa mínima para evitar divisão por zero
        
        # Cálculo simplificado do CET
        monthly_payment = (principal * rate) / (1 - (1 + rate) ** -installments)
        total_paid = monthly_payment * installments + fees
        cet = ((total_paid / principal) ** (1/installments)) - 1
        
        return max(0.01, cet)  # Retorna pelo menos 1%
    except Exception:
        return 0.02  # Fallback de 2%

# ==================================================
# COMPONENTES DE UI
# ==================================================
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
    """Medidor de risco visual"""
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

# ==================================================
# ESTADO DA SESSÃO
# ==================================================
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
        "current_analysis": None
    }
    
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

# ==================================================
# TELAS DA APLICAÇÃO
# ==================================================
def premium_hero_section():
    st.markdown('<div class="clara-hero">', unsafe_allow_html=True)
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        clara_logo()
        
        st.markdown("""
        <h1 style='font-size: 3rem; font-weight: 800; color: #0f172a; margin-bottom: 1.5rem;'>
            Entenda cada linha<br>do seu contrato
        </h1>
        
        <p style='font-size: 1.2rem; color: #0f172a; opacity: 0.8; margin-bottom: 2.5rem; line-height: 1.6;'>
            A CLARA Law descomplica documentos jurídicos com inteligência artificial, 
            destacando riscos, explicando cláusulas e sugerindo melhorias em linguagem simples.
        </p>
        """, unsafe_allow_html=True)
        
        col1, col2 = st.columns([1, 1])
        with col1:
            if st.button("📄 Analisar Meu Contrato", use_container_width=True, type="primary"):
                st.session_state.started = True
                st.rerun()
        with col2:
            if st.button("ℹ️ Como Funciona", use_container_width=True):
                st.info("""
                1. **Envie** seu contrato em PDF ou cole o texto
                2. **Configure** o contexto da análise
                3. **Receba** insights em linguagem simples
                4. **Negocie** com confiança
                """)
    
    with col2:
        st.markdown("""
        <div style='text-align: center; padding: 2rem;'>
            <div style='font-size: 4rem; margin-bottom: 1rem;'>⚖️</div>
            <h3 style='color: #0f172a;'>Análise Jurídica Inteligente</h3>
            <p style='color: #0f172a; opacity: 0.7;'>Tecnologia + Expertise Jurídica</p>
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

    st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
    
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
        st.metric("Contratos Analisados", "15.847", "+28%")
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col2:
        st.markdown('<div class="stats-card">', unsafe_allow_html=True)
        st.metric("Riscos Identificados", "42.156", "+15%")
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col3:
        st.markdown('<div class="stats-card">', unsafe_allow_html=True)
        st.metric("Economia Estimada", "R$ 8,2 Mi", "+32%")
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col4:
        st.markdown('<div class="stats-card">', unsafe_allow_html=True)
        st.metric("Satisfação", "4.9/5", "⭐")
        st.markdown('</div>', unsafe_allow_html=True)

def upload_section():
    st.header("1. 📄 Envie seu contrato")
    
    tab1, tab2 = st.tabs(["Upload PDF", "Cole o Texto"])
    
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
                        st.info(f"✍️ Palavras: {len(text_content.split())}")
                    
                    with col2:
                        st.info(f"📏 Tamanho: {metadata.get('size', 'N/A')}")
                        st.info(f"📊 Caracteres: {len(text_content)}")
                    
                    st.session_state.current_contract = text_content
                    st.success("✅ Documento carregado com sucesso!")
                    
                    # Preview do conteúdo
                    with st.expander("📋 Visualizar conteúdo extraído"):
                        st.text(text_content[:1000] + ("..." if len(text_content) > 1000 else ""))
                        
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
    
    return st.session_state.current_contract

def context_section():
    st.header("2. 🎯 Contexto da Análise")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        contract_type = st.selectbox(
            "Tipo de Contrato",
            ["Prestação de Serviços", "Locação", "Empréstimo", "Compra e Venda", "Trabalho", "Parceria", "Outro"]
        )
        
        industry = st.selectbox(
            "Setor/Área",
            ["Tecnologia", "Saúde", "Educação", "Financeiro", "Imobiliário", "Varejo", "Indústria", "Outro"]
        )
    
    with col2:
        your_role = st.selectbox(
            "Seu Papel",
            ["Contratante", "Contratado", "Prestador", "Cliente", "Fornecedor", "Locador", "Locatário"]
        )
        
        contract_value = st.number_input(
            "Valor do Contrato (R$)",
            min_value=0.0,
            step=1000.0,
            format="%.2f",
            help="Opcional - para cálculos financeiros"
        )
    
    with col3:
        urgency = st.select_slider(
            "Urgência da Análise",
            options=["Baixa", "Média", "Alta", "Crítica"]
        )
        
        priority_areas = st.multiselect(
            "Áreas de Interesse Especial",
            ["Multas e Penalidades", "Confidencialidade", "Prazo e Renovação", 
             "Garantias", "Responsabilidades", "Rescisão", "Jurisdição", "Propriedade Intelectual"]
        )
    
    return {
        "contract_type": contract_type,
        "industry": industry,
        "your_role": your_role,
        "contract_value": contract_value,
        "urgency": urgency,
        "priority_areas": priority_areas
    }

def analysis_results_section(text: str, context: Dict[str, Any]):
    if not text or not text.strip():
        st.warning("Por favor, carregue um contrato para análise.")
        return
    
    # Verificação de limite gratuito
    if not st.session_state.premium and st.session_state.free_runs_left <= 0:
        show_premium_upsell()
        return
    
    # Barra de progresso
    with st.spinner("🔍 CLARA está analisando seu contrato..."):
        progress_bar = st.progress(0)
        
        # Simulação de progresso
        for i in range(100):
            progress_bar.progress(i + 1)
        
        # Análise real
        hits, meta = analyze_contract_text(text, context)
        risk_score = risk_assessment_score(hits)
        negotiation_strategy = generate_negotiation_strategy(hits, context)
    
    # Atualiza limite gratuito
    if not st.session_state.premium:
        st.session_state.free_runs_left -= 1
    
    # Salva análise atual
    st.session_state.current_analysis = {
        "hits": hits,
        "risk_score": risk_score,
        "context": context,
        "timestamp": datetime.now().isoformat()
    }
    
    # Header dos resultados
    st.success("🎉 Análise concluída com sucesso!")
    
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
        resume = summarize_hits(hits)
        st.markdown(f"**Resumo:** {resume['resumo']}")
    
    with col2:
        st.metric("Pontos Críticos", resume['criticos'])
    
    with col3:
        st.metric("Gravidade", resume['gravidade'])
    
    st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
    
    # Medidor de Risco
    st.header("📊 Medidor de Risco do Contrato")
    risk_meter(risk_score)
    
    st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
    
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
            expanded=i < 2
        ):
            col_a, col_b = st.columns([3, 1])
            
            with col_a:
                st.markdown(f"**📝 Explicação:** {hit.get('explanation', '')}")
                
                if hit.get('suggestion'):
                    st.markdown(f"**💡 Sugestão de Negociação:** {hit['suggestion']}")
            
            with col_b:
                if hit.get('evidence'):
                    with st.container():
                        st.markdown("**📄 Trecho Original:**")
                        st.text(hit['evidence'][:500] + ("..." if len(hit['evidence']) > 500 else ""))
    
    # Estratégia de Negociação
    if negotiation_strategy:
        st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
        st.markdown(negotiation_strategy)
    
    # Ferramentas Adicionais
    st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
    st.header("🛠️ Ferramentas Adicionais")
    
    tool_tabs = st.tabs(["Calculadora CET", "Exportar Relatório"])
    
    with tool_tabs[0]:
        cet_calculator_section()
    
    with tool_tabs[1]:
        export_report_section(hits, resume, context, risk_score)

def show_premium_upsell():
    st.warning("""
    🚀 **Você atingiu o limite de análises gratuitas!**
    
    Com o **CLARA Law Premium** você recebe:
    • ✅ Análises ilimitadas
    • 📊 Relatórios detalhados em PDF
    • 📈 Calculadora financeira avançada
    • 🔄 Comparação de versões
    • 🎯 Estratégias de negociação personalizadas
    • 📞 Suporte prioritário
    
    *Entre em contato para saber mais sobre nossos planos Premium.*
    """)

def cet_calculator_section():
    st.subheader("📈 Calculadora de Custo Efetivo Total")
    
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
    
    if st.button("🧮 Calcular CET", use_container_width=True, key="btn_calc_cet"):
        if principal > 0 and installments > 0:
            try:
                cet = compute_cet_quick(principal, monthly_rate/100, installments, total_fees)
                
                st.success(f"**Custo Efetivo Total (CET):** {cet*100:.2f}% ao mês")
                
                # Análise comparativa
                if cet * 100 > 5:
                    st.warning("⚠️ CET acima da média de mercado. Recomendamos negociar melhores condições.")
                elif cet * 100 > 2:
                    st.info("📊 CET dentro da média do mercado.")
                else:
                    st.success("✅ CET em condições favoráveis.")
                    
                # Detalhamento
                monthly_payment = (principal * (monthly_rate/100)) / (1 - (1 + (monthly_rate/100)) ** -installments)
                total_paid = monthly_payment * installments + total_fees
                
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("Parcela Mensal", f"R$ {monthly_payment:,.2f}")
                with col2:
                    st.metric("Total Pago", f"R$ {total_paid:,.2f}")
                    
            except Exception as e:
                st.error(f"Erro no cálculo: {str(e)}")
        else:
            st.error("Por favor, preencha os valores principal e número de parcelas.")

def export_report_section(hits, resume, context, risk_score):
    st.subheader("📄 Gerar Relatório")
    
    # Relatório executivo
    executive_summary = generate_executive_report(hits, resume, context, risk_score)
    
    # E-mail para advogado
    lawyer_email = generate_lawyer_email(resume, hits)
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.download_button(
            "📥 Baixar Relatório Executivo",
            data=executive_summary.encode('utf-8'),
            file_name=f"relatorio_clara_{datetime.now().strftime('%Y%m%d_%H%M')}.txt",
            mime="text/plain",
            use_container_width=True
        )
    
    with col2:
        st.download_button(
            "📧 E-mail para Advogado",
            data=lawyer_email.encode('utf-8'),
            file_name=f"email_advogado_{datetime.now().strftime('%Y%m%d_%H%M')}.txt",
            mime="text/plain",
            use_container_width=True
        )
    
    with col3:
        if st.button("🔄 Nova Análise", use_container_width=True):
            st.session_state.current_contract = None
            st.session_state.current_analysis = None
            st.rerun()

def generate_executive_report(hits, resume, context, risk_score):
    report = f"""
RELATÓRIO DE ANÁLISE - CLARA Law
=================================

INFORMAÇÕES GERAIS
------------------
Data da Análise: {datetime.now().strftime('%d/%m/%Y às %H:%M')}
Tipo de Contrato: {context.get('contract_type', 'Não especificado')}
Setor: {context.get('industry', 'Não especificado')}
Papel do Usuário: {context.get('your_role', 'Não especificado')}
Valor do Contrato: R$ {context.get('contract_value', 0):,.2f}

RESUMO EXECUTIVO
----------------
{resume['resumo']}

SCORE DE RISCO: {risk_score}/100
NÍVEL DE GRAVIDADE: {resume['gravidade']}
PONTOS CRÍTICOS: {resume['criticos']}
TOTAL DE PONTOS ANALISADOS: {resume['total']}

DETALHAMENTO DA ANÁLISE
-----------------------
"""
    
    for i, hit in enumerate(hits, 1):
        report += f"\n{i}. [{hit['severity']}] {hit['title']}\n"
        report += f"   Explicação: {hit.get('explanation', '')}\n"
        if hit.get('suggestion'):
            report += f"   Sugestão: {hit['suggestion']}\n"
        if hit.get('evidence'):
            report += f"   Evidência: {hit['evidence'][:200]}...\n"
        report += "\n"
    
    report += f"""
RECOMENDAÇÕES
-------------
1. Revise cuidadosamente os pontos classificados como 'Alto Risco'
2. Considere negociar as cláusulas problemáticas conforme sugestões
3. Para contratos de alto valor ou complexidade, consulte um advogado
4. Mantenha registro desta análise para referência futura

---
CLARA Law - Inteligência para um mundo mais claro
www.claralaw.com.br | contato@claralaw.com.br

⚠️ AVISO LEGAL: Este relatório foi gerado automaticamente e tem caráter informativo.
Não substitui a análise de um profissional qualificado. Recomendamos consultoria jurídica para decisões importantes.
"""
    
    return report

def generate_lawyer_email(resume, hits):
    critical_points = [h for h in hits if h['severity'] in ['Alto', 'Médio']][:3]
    
    email_content = f"""
Assunto: Solicitação de Análise Jurídica - Contrato

Prezado(a) Advogado(a),

Gostaria de solicitar sua análise profissional sobre o contrato em anexo.

Realizamos uma análise preliminar através da CLARA Law e identificamos os seguintes pontos de atenção:

RESUMO DA ANÁLISE AUTOMÁTICA:
{resume['resumo']}

PRINCIPAIS PONTOS QUE REQUEREM SUA ATENÇÃO:

"""
    
    for i, point in enumerate(critical_points, 1):
        email_content += f"{i}. {point['title']}\n"
        email_content += f"   Nível de Risco: {point['severity']}\n"
        email_content += f"   Contexto: {point.get('explanation', '')}\n"
        if point.get('suggestion'):
            email_content += f"   Sugestão CLARA: {point['suggestion']}\n"
        email_content += "\n"
    
    email_content += f"""
Solicito especialmente sua avaliação sobre:

1. Legalidade e validade das cláusulas problemáticas
2. Sugestões de redação alternativa
3. Riscos jurídicos adicionais não detectados
4. Estratégias de negociação recomendadas
5. Conformidade com a legislação aplicável

Fico à disposição para fornecer quaisquer informações adicionais necessárias.

Atenciosamente,
{st.session_state.profile.get('nome', '[Seu Nome]')}
{st.session_state.profile.get('email', '[Seu E-mail]')}
{st.session_state.profile.get('empresa', '[Sua Empresa]')}
"""
    
    return email_content

# ==================================================
# SIDEBAR
# ==================================================
def render_sidebar():
    st.sidebar.markdown(f"""
    <div style="text-align: center; margin-bottom: 2rem;">
        <div style="font-family: 'Raleway', sans-serif; font-weight: 600; font-size: 1.5rem; color: #0f172a;">
            CLARA Law
        </div>
        <div style="font-size: 0.8rem; color: #D4AF37;">
            Inteligência para um mundo mais claro
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Perfil do usuário
    with st.sidebar.expander("👤 Meu Perfil", expanded=True):
        nome = st.text_input("Nome Completo", value=st.session_state.profile.get("nome", ""))
        email = st.text_input("E-mail", value=st.session_state.profile.get("email", ""))
        empresa = st.text_input("Empresa", value=st.session_state.profile.get("empresa", ""))
        cargo = st.text_input("Cargo", value=st.session_state.profile.get("cargo", ""))
        
        if st.button("💾 Salvar Perfil", use_container_width=True):
            if email and "@" in email:
                st.session_state.profile.update({
                    "nome": nome, 
                    "email": email, 
                    "empresa": empresa, 
                    "cargo": cargo
                })
                st.sidebar.success("Perfil atualizado!")
            else:
                st.sidebar.error("Por favor, insira um e-mail válido.")
    
    # Status da conta
    st.sidebar.markdown("---")
    st.sidebar.subheader("📊 Minha Conta")
    
    if st.session_state.premium:
        st.sidebar.success("💎 Conta Premium")
        st.sidebar.metric("Análises", "Ilimitadas")
    else:
        st.sidebar.info(f"🆓 Conta Gratuita")
        st.sidebar.metric("Análises Restantes", st.session_state.free_runs_left)
        
        if st.sidebar.button("🚀 Fazer Upgrade", use_container_width=True):
            st.sidebar.info("""
            **Planos Premium:**
            - Básico: R$ 29/mês
            - Profissional: R$ 79/mês  
            - Empresarial: R$ 199/mês
            
            *Entre em contato: comercial@claralaw.com.br*
            """)
    
    # Navegação
    st.sidebar.markdown("---")
    st.sidebar.subheader("🧭 Navegação")
    
    if st.sidebar.button("🏠 Página Inicial", use_container_width=True):
        st.session_state.started = False
        st.rerun()
    
    if st.sidebar.button("📋 Meu Histórico", use_container_width=True):
        if st.session_state.analysis_history:
            with st.sidebar.expander("Histórico de Análises"):
                for analysis in st.session_state.analysis_history[-5:]:
                    st.write(f"📅 {analysis['timestamp'][:10]} - {analysis['context']['contract_type']}")
        else:
            st.sidebar.info("Nenhuma análise no histórico")

# ==================================================
# MAIN APPLICATION
# ==================================================
def render_landing_page():
    premium_hero_section()
    features_section()
    social_proof_section()
    
    # Call-to-action final
    st.markdown("---")
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.header("🎯 Pronto para tomar decisões mais seguras?")
        st.markdown("""
        Comece agora sua análise gratuita e experimente o poder da CLARA Law:
        - **2 análises gratuitas** para testar
        - **Resultados em segundos**  
        - **Explicações em linguagem simples**
        - **Sugestões práticas** de negociação
        """)
    
    with col2:
        if st.button("📄 Começar Análise Agora", use_container_width=True, type="primary", size="large"):
            st.session_state.started = True
            st.rerun()
    
    # Footer
    st.markdown("---")
    st.markdown("""
    <div style='text-align: center; color: #666; font-size: 0.9rem;'>
        <p>CLARA Law © 2024 - Inteligência para um mundo mais claro</p>
        <p><em>Este serviço complementa mas não substitui aconselhamento jurídico profissional.</em></p>
    </div>
    """, unsafe_allow_html=True)

def render_analysis_interface():
    st.header("⚖️ Análise de Contrato - CLARA Law")
    
    # Mostra status da conta
    if st.session_state.premium:
        st.success("💎 Conta Premium - Análises Ilimitadas")
    else:
        st.info(f"🆓 Análises gratuitas restantes: {st.session_state.free_runs_left}")
    
    # Fluxo de análise
    contract_text = upload_section()
    
    if contract_text:
        st.markdown("---")
        analysis_context = context_section()
        
        st.markdown("---")
        
        if st.button("🚀 Executar Análise Completa", type="primary", use_container_width=True, size="large"):
            analysis_results_section(contract_text, analysis_context)
        else:
            st.info("💡 Configure o contexto acima e clique em 'Executar Análise Completa'")
    else:
        st.warning("📝 Por favor, carregue um contrato para começar a análise")

def main():
    # Inicialização
    inject_custom_css()
    init_session_state()
    
    # Barra lateral
    render_sidebar()
    
    # Conteúdo principal
    if not st.session_state.started:
        render_landing_page()
    else:
        render_analysis_interface()

if __name__ == "__main__":
    main()
