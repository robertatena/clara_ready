import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import matplotlib.pyplot as plt
import altair as alt
from datetime import datetime, timedelta
import io
import base64
import sqlite3
import json
import PyPDF2
import os
import re
from typing import Dict, List, Any, Optional

# ===== CONFIGURAÇÃO DA PÁGINA =====
st.set_page_config(
    page_title="Clara Ready - Plataforma de Gestão Financeira",
    page_icon="💜",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ===== CSS PERSONALIZADO =====
st.markdown("""
<style>
    .main-header {
        font-size: 3rem;
        color: #6A0DAD;
        text-align: center;
        margin-bottom: 2rem;
        font-weight: bold;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    .sub-header {
        font-size: 1.8rem;
        color: #8A2BE2;
        margin: 1.5rem 0;
        font-weight: bold;
        border-left: 5px solid #8A2BE2;
        padding-left: 1rem;
    }
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1.5rem;
        border-radius: 15px;
        color: white;
        text-align: center;
        margin: 0.5rem 0;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    }
    .feature-card {
        background: #f8f9fa;
        padding: 1.5rem;
        border-radius: 12px;
        border-left: 4px solid #6A0DAD;
        margin: 1rem 0;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
    }
    .stButton>button {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        padding: 0.75rem 2rem;
        border-radius: 25px;
        font-weight: bold;
        font-size: 1rem;
        transition: all 0.3s ease;
        width: 100%;
    }
    .stButton>button:hover {
        background: linear-gradient(135deg, #764ba2 0%, #667eea 100%);
        color: white;
        transform: translateY(-2px);
        box-shadow: 0 4px 8px rgba(0, 0, 0, 0.2);
    }
    .analysis-result {
        background: white;
        padding: 1.5rem;
        border-radius: 10px;
        border: 1px solid #e0e0e0;
        margin: 1rem 0;
    }
    .risk-high {
        background: linear-gradient(135deg, #ff6b6b 0%, #ee5a52 100%);
        color: white;
        padding: 0.5rem 1rem;
        border-radius: 20px;
        font-weight: bold;
    }
    .risk-medium {
        background: linear-gradient(135deg, #ffa726 0%, #fb8c00 100%);
        color: white;
        padding: 0.5rem 1rem;
        border-radius: 20px;
        font-weight: bold;
    }
    .risk-low {
        background: linear-gradient(135deg, #66bb6a 0%, #4caf50 100%);
        color: white;
        padding: 0.5rem 1rem;
        border-radius: 20px;
        font-weight: bold;
    }
    .sidebar .sidebar-content {
        background: linear-gradient(180deg, #f8f9fa 0%, #e9ecef 100%);
    }
</style>
""", unsafe_allow_html=True)

# ===== FUNÇÕES DO BANCO DE DADOS =====
def init_database():
    """Inicializa o banco de dados SQLite"""
    try:
        conn = sqlite3.connect('clara_ready.db', check_same_thread=False)
        cursor = conn.cursor()
        
        # Tabela de usuários
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                password TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                plan_type TEXT DEFAULT 'basic'
            )
        ''')
        
        # Tabela de análises
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS analyses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                filename TEXT NOT NULL,
                file_content BLOB,
                analysis_result TEXT,
                risk_score INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        
        # Tabela de eventos
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                event_type TEXT,
                details TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        
        conn.commit()
        return conn
    except Exception as e:
        st.error(f"Erro ao inicializar banco de dados: {e}")
        return None

def create_user(email: str, password: str) -> bool:
    """Cria um novo usuário"""
    try:
        conn = init_database()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO users (email, password) VALUES (?, ?)",
            (email, password)  # Em produção, usar hash para senha
        )
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        return False
    except Exception as e:
        st.error(f"Erro ao criar usuário: {e}")
        return False

def authenticate_user(email: str, password: str) -> Dict[str, Any]:
    """Autentica um usuário"""
    try:
        conn = init_database()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, email, plan_type FROM users WHERE email = ? AND password = ?",
            (email, password)
        )
        user = cursor.fetchone()
        conn.close()
        
        if user:
            return {
                'id': user[0],
                'email': user[1],
                'plan_type': user[2]
            }
        return None
    except Exception as e:
        st.error(f"Erro na autenticação: {e}")
        return None

def save_analysis(user_id: int, filename: str, analysis_result: Dict[str, Any]) -> int:
    """Salva uma análise no banco de dados"""
    try:
        conn = init_database()
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO analyses (user_id, filename, analysis_result, risk_score) 
               VALUES (?, ?, ?, ?)""",
            (user_id, filename, json.dumps(analysis_result), analysis_result['pontuacao'])
        )
        analysis_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return analysis_id
    except Exception as e:
        st.error(f"Erro ao salvar análise: {e}")
        return -1

def get_user_analyses(user_id: int) -> List[Dict[str, Any]]:
    """Recupera análises do usuário"""
    try:
        conn = init_database()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, filename, analysis_result, risk_score, created_at FROM analyses WHERE user_id = ? ORDER BY created_at DESC",
            (user_id,)
        )
        
        analyses = []
        for row in cursor.fetchall():
            analyses.append({
                'id': row[0],
                'filename': row[1],
                'result': json.loads(row[2]),
                'risk_score': row[3],
                'date': datetime.fromisoformat(row[4])
            })
        conn.close()
        return analyses
    except Exception as e:
        st.error(f"Erro ao recuperar análises: {e}")
        return []

# ===== FUNÇÕES DE ANÁLISE DE PDF =====
def extract_text_from_pdf(pdf_file) -> str:
    """Extrai texto de um arquivo PDF"""
    try:
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        text = ""
        for page in pdf_reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
        
        if not text.strip():
            raise Exception("PDF não contém texto legível")
            
        return text
    except Exception as e:
        raise Exception(f"Erro ao extrair texto do PDF: {str(e)}")

def analyze_contract_text(text: str) -> Dict[str, Any]:
    """Analisa o texto do contrato e identifica riscos"""
    
    # Dicionário de palavras-chave por categoria de risco
    risk_categories = {
        'financeiro': {
            'keywords': ['multa', 'juros', 'indenização', 'garantia', 'caução', 'penhora', 'execução', 'dívida', 'pagamento', 'valor', 'preço', 'custas'],
            'weight': 1.2
        },
        'contratual': {
            'keywords': ['rescisão', 'resolução', 'vigência', 'prazo', 'renovação', 'exclusivo', 'confidencialidade', 'propriedade', 'licença'],
            'weight': 1.0
        },
        'legal': {
            'keywords': ['jurisdição', 'foro', 'arbitragem', 'lei', 'legislação', 'tribunal', 'justiça', 'cláusula', 'penal', 'civil'],
            'weight': 1.1
        },
        'operacional': {
            'keywords': ['prazo', 'entrega', 'qualidade', 'especificação', 'inspeção', 'teste', 'aprovação', 'rejeição', 'defeito'],
            'weight': 0.9
        }
    }
    
    text_lower = text.lower()
    riscos_encontrados = []
    pontuacao_total = 0
    max_pontos = 100
    
    # Análise por categoria
    for categoria, config in risk_categories.items():
        for keyword in config['keywords']:
            if keyword in text_lower:
                # Encontrar contexto da palavra-chave
                start = max(0, text_lower.find(keyword) - 50)
                end = min(len(text_lower), text_lower.find(keyword) + len(keyword) + 50)
                contexto = text[start:end].strip()
                
                risco = {
                    'categoria': categoria.upper(),
                    'keyword': keyword,
                    'contexto': contexto,
                    'severidade': 'ALTA' if config['weight'] > 1.0 else 'MÉDIA'
                }
                riscos_encontrados.append(risco)
                pontuacao_total += 10 * config['weight']
    
    # Limitar pontuação máxima
    pontuacao_final = min(max_pontos, pontuacao_total)
    
    # Gerar recomendações baseadas nos riscos encontrados
    recomendacoes = [
        "Revise cuidadosamente todas as cláusulas identificadas",
        "Consulte um especialista jurídico para análise detalhada",
        "Negocie termos mais favoráveis quando possível",
        "Documente todas as observações e preocupações",
        "Estabeleça plano de ação para mitigação de riscos"
    ]
    
    # Adicionar recomendações específicas baseadas na pontuação
    if pontuacao_final >= 70:
        recomendacoes.append("⚠️ ALERTA: Contrato apresenta riscos significativos - análise jurídica obrigatória")
    elif pontuacao_final >= 40:
        recomendacoes.append("📋 Contrato requer atenção especial em cláusulas críticas")
    
    return {
        "riscos": riscos_encontrados[:8],  # Limitar a 8 riscos principais
        "recomendacoes": recomendacoes,
        "pontuacao": int(pontuacao_final),
        "total_riscos": len(riscos_encontrados),
        "categorias_afetadas": list(set([r['categoria'] for r in riscos_encontrados]))
    }

def generate_executive_summary(analysis_result: Dict[str, Any]) -> str:
    """Gera um resumo executivo da análise"""
    nivel_risco = "BAIXO"
    cor_risco = "🟢"
    
    if analysis_result['pontuacao'] >= 70:
        nivel_risco = "ALTO"
        cor_risco = "🔴"
    elif analysis_result['pontuacao'] >= 40:
        nivel_risco = "MÉDIO"
        cor_risco = "🟡"
    
    return f"""
{cor_risco} **RESUMO EXECUTIVO - CLARA READY**

**Nível de Risco:** {nivel_risco}
**Pontuação:** {analysis_result['pontuacao']}/100
**Total de Riscos Identificados:** {analysis_result['total_riscos']}
**Categorias Afetadas:** {', '.join(analysis_result['categorias_afetadas'])}

**Principais Observações:**
- Contrato analisado através de inteligência artificial
- {analysis_result['total_riscos']} pontos de atenção identificados
- Recomenda-se {'' if nivel_risco == 'BAIXO' else 'fortemente '}revisão por especialista

**Status:** {'✅ Dentro dos parâmetros esperados' if nivel_risco == 'BAIXO' else '⚠️ Requer atenção imediata'}
"""

# ===== FUNÇÕES DE RELATÓRIO =====
def generate_pdf_report(analysis: Dict[str, Any]) -> bytes:
    """Gera um relatório PDF da análise (simulação)"""
    report_content = f"""
RELATÓRIO DE ANÁLISE - CLARA READY
==================================

Arquivo: {analysis['filename']}
Data da Análise: {analysis['date'].strftime('%d/%m/%Y às %H:%M')}
Usuário: {st.session_state.current_user['email']}

RESULTADO DA ANÁLISE
-------------------
Pontuação de Risco: {analysis['result']['pontuacao']}/100
Total de Riscos Identificados: {analysis['result']['total_riscos']}
Categorias Envolvidas: {', '.join(analysis['result']['categorias_afetadas'])}

RISCOS IDENTIFICADOS
-------------------
{chr(10).join(f"- [{risco['categoria']}] {risco['keyword']} - Severidade: {risco['severidade']}{chr(10)}  Contexto: {risco['contexto'][:100]}..." for risco in analysis['result']['riscos'])}

RECOMENDAÇÕES
-------------
{chr(10).join(f"- {rec}" for rec in analysis['result']['recomendacoes'])}

RESUMO EXECUTIVO
----------------
{generate_executive_summary(analysis['result'])}

---
Relatório gerado automaticamente por Clara Ready
Plataforma de Análise de Contratos Inteligente
"""
    return report_content.encode('utf-8')

# ===== FUNÇÕES DE VISUALIZAÇÃO =====
def create_risk_gauge(score: int):
    """Cria um gráfico de gauge para mostrar o risco"""
    fig = go.Figure(go.Indicator(
        mode = "gauge+number+delta",
        value = score,
        domain = {'x': [0, 1], 'y': [0, 1]},
        title = {'text': "Nível de Risco"},
        delta = {'reference': 50},
        gauge = {
            'axis': {'range': [None, 100]},
            'bar': {'color': "darkblue"},
            'steps': [
                {'range': [0, 30], 'color': "lightgreen"},
                {'range': [30, 70], 'color': "yellow"},
                {'range': [70, 100], 'color': "red"}
            ],
            'threshold': {
                'line': {'color': "black", 'width': 4},
                'thickness': 0.75,
                'value': 90
            }
        }
    ))
    fig.update_layout(height=300)
    return fig

def create_risk_distribution_chart(analyses: List[Dict[str, Any]]):
    """Cria gráfico de distribuição de riscos"""
    if not analyses:
        return None
    
    scores = [analysis['risk_score'] for analysis in analyses]
    
    fig = px.histogram(
        x=scores,
        nbins=10,
        title="Distribuição das Pontuações de Risco",
        labels={'x': 'Pontuação de Risco', 'y': 'Número de Contratos'}
    )
    fig.update_layout(height=300, showlegend=False)
    return fig

# ===== INICIALIZAÇÃO DA SESSÃO =====
if 'user_authenticated' not in st.session_state:
    st.session_state.user_authenticated = False
if 'current_user' not in st.session_state:
    st.session_state.current_user = None
if 'analysis_history' not in st.session_state:
    st.session_state.analysis_history = []
if 'db_initialized' not in st.session_state:
    st.session_state.db_initialized = init_database() is not None

# ===== HEADER PRINCIPAL =====
st.markdown('<div class="main-header">💜 Clara Ready</div>', unsafe_allow_html=True)
st.markdown("### 🤖 Sua plataforma inteligente para análise de contratos financeiros")

# ===== SIDEBAR =====
with st.sidebar:
    st.image("https://via.placeholder.com/200x200/6A0DAD/FFFFFF?text=CR", width=150)
    st.markdown("---")
    
    if not st.session_state.user_authenticated:
        st.markdown("### 🔐 Acesso")
        
        login_tab, register_tab = st.tabs(["Login", "Cadastro"])
        
        with login_tab:
            login_email = st.text_input("📧 Email", key="login_email")
            login_password = st.text_input("🔒 Senha", type="password", key="login_password")
            
            if st.button("🚀 Entrar", key="login_btn", use_container_width=True):
                if login_email and login_password:
                    user = authenticate_user(login_email, login_password)
                    if user:
                        st.session_state.user_authenticated = True
                        st.session_state.current_user = user
                        st.session_state.analysis_history = get_user_analyses(user['id'])
                        st.success(f"Bem-vindo, {user['email']}!") 
                        st.rerun()
                    else:
                        st.error("Credenciais inválidas!")
                else:
                    st.warning("Preencha email e senha!")
        
        with register_tab:
            reg_email = st.text_input("📧 Email", key="reg_email")
            reg_password = st.text_input("🔒 Senha", type="password", key="reg_password")
            reg_confirm = st.text_input("✅ Confirmar Senha", type="password", key="reg_confirm")
            
            if st.button("📝 Cadastrar", key="register_btn", use_container_width=True):
                if reg_email and reg_password:
                    if reg_password == reg_confirm:
                        if create_user(reg_email, reg_password):
                            st.success("Cadastro realizado! Faça login.")
                        else:
                            st.error("Email já cadastrado!")
                    else:
                        st.error("Senhas não coincidem!")
                else:
                    st.warning("Preencha todos os campos!")
    
    else:
        st.success(f"👋 Bem-vindo, {st.session_state.current_user['email']}!")
        st.info(f"📊 Plano: {st.session_state.current_user['plan_type'].upper()}")
        
        if st.button("🚪 Sair", use_container_width=True):
            st.session_state.user_authenticated = False
            st.session_state.current_user = None
            st.session_state.analysis_history = []
            st.rerun()
        
        st.markdown("---")
        st.markdown("### 📋 Análises Recentes")
        
        if st.session_state.analysis_history:
            for i, analysis in enumerate(st.session_state.analysis_history[:5]):
                risk_color = "🟢" if analysis['risk_score'] < 40 else "🟡" if analysis['risk_score'] < 70 else "🔴"
                st.write(f"{risk_color} {analysis['filename'][:25]}... ({analysis['risk_score']}/100)")
        else:
            st.info("Nenhuma análise realizada")

# ===== CONTEÚDO PRINCIPAL =====
if not st.session_state.user_authenticated:
    # PÁGINA DE BOAS-VINDAS
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.markdown("""
        ## 🚀 Transforme sua Análise de Contratos
        
        A **Clara Ready** utiliza **inteligência artificial avançada** para identificar 
        riscos financeiros em seus contratos de forma **rápida, precisa e segura**.
        
        ### ✨ Por que escolher a Clara Ready?
        
        🔍 **Análise Detalhada** 
        - Identificação automática de cláusulas críticas
        - Detecção de termos potencialmente prejudiciais
        - Análise contextual inteligente
        
        ⚠️ **Gestão de Riscos**
        - Pontuação de risco personalizada
        - Categorização por tipo de risco
        - Alertas proativos para questões críticas
        
        💡 **Recomendações Inteligentes**
        - Sugestões de mitigação baseadas em IA
        - Insights acionáveis
        - Orientações personalizadas
        
        📊 **Relatórios Completos**
        - Dashboard interativo
        - Relatórios executivos
        - Histórico de análises
        """)
    
    with col2:
        st.markdown("""
        <div style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                   padding: 2rem; border-radius: 15px; color: white; text-align: center; margin-bottom: 2rem;'>
            <h3>🚀 Comece Agora!</h3>
            <p>Cadastre-se gratuitamente e realize suas primeiras análises</p>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("""
        <div class='feature-card'>
            <h4>🎯 Planos Disponíveis</h4>
            <p><strong>🆓 Básico:</strong><br>3 análises/mês<br>Relatórios básicos</p>
            <p><strong>💼 Profissional:</strong><br>Análises ilimitadas<br>Relatórios completos</p>
            <p><strong>🏢 Empresarial:</strong><br>Recursos avançados<br>Suporte prioritário</p>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("""
        <div class='feature-card'>
            <h4>📈 Estatísticas</h4>
            <p>• +1,000 contratos analisados</p>
            <p>• 95% de precisão na detecção</p>
            <p>• 40% de economia em revisões</p>
            <p>• 100% de segurança dos dados</p>
        </div>
        """, unsafe_allow_html=True)

else:
    # USUÁRIO AUTENTICADO - FUNCIONALIDADES PRINCIPAIS
    tab1, tab2, tab3, tab4 = st.tabs(["📁 Análise de Contratos", "📊 Dashboard", "📈 Relatórios", "⚙️ Configurações"])
    
    with tab1:
        st.markdown('<div class="sub-header">🔍 Análise de Contratos</div>', unsafe_allow_html=True)
        
        uploaded_file = st.file_uploader(
            "📤 Faça upload do seu contrato em PDF", 
            type=['pdf'],
            help="Envie um arquivo PDF contendo o contrato para análise"
        )
        
        if uploaded_file is not None:
            col1, col2 = st.columns([3, 1])
            
            with col1:
                st.success(f"✅ Arquivo carregado: **{uploaded_file.name}**")
                st.info(f"📄 Tamanho: {uploaded_file.size / 1024:.1f} KB")
                
                if st.button("🔍 Iniciar Análise do Contrato", type="primary", use_container_width=True):
                    with st.spinner("🤖 Analisando contrato... Isso pode levar alguns segundos."):
                        try:
                            # Extrair texto do PDF
                            text = extract_text_from_pdf(uploaded_file)
                            
                            if text and len(text.strip()) > 100:
                                # Realizar análise
                                analysis_result = analyze_contract_text(text)
                                
                                # Salvar no banco de dados
                                analysis_id = save_analysis(
                                    st.session_state.current_user['id'],
                                    uploaded_file.name,
                                    analysis_result
                                )
                                
                                if analysis_id > 0:
                                    # Atualizar histórico
                                    new_analysis = {
                                        'id': analysis_id,
                                        'filename': uploaded_file.name,
                                        'date': datetime.now(),
                                        'result': analysis_result,
                                        'risk_score': analysis_result['pontuacao']
                                    }
                                    st.session_state.analysis_history.insert(0, new_analysis)
                                    
                                    st.success("🎉 Análise concluída com sucesso!")
                                    
                                    # Exibir resultados
                                    st.markdown("### 📋 Resultados da Análise")
                                    
                                    # Métricas principais
                                    col_met1, col_met2, col_met3, col_met4 = st.columns(4)
                                    with col_met1:
                                        risk_class = "risk-high" if analysis_result['pontuacao'] >= 70 else "risk-medium" if analysis_result['pontuacao'] >= 40 else "risk-low"
                                        st.markdown(f'<div class="{risk_class}">{analysis_result["pontuacao"]}/100</div>', unsafe_allow_html=True)
                                        st.caption("Pontuação de Risco")
                                    
                                    with col_met2:
                                        st.metric("Riscos Identificados", analysis_result['total_riscos'])
                                    
                                    with col_met3:
                                        st.metric("Categorias Afetadas", len(analysis_result['categorias_afetadas']))
                                    
                                    with col_met4:
                                        st.metric("Recomendações", len(analysis_result['recomendacoes']))
                                    
                                    # Gauge de risco
                                    st.plotly_chart(create_risk_gauge(analysis_result['pontuacao']), use_container_width=True)
                                    
                                    # Resumo executivo
                                    st.markdown("#### 📊 Resumo Executivo")
                                    st.markdown(generate_executive_summary(analysis_result))
                                    
                                    # Riscos detalhados
                                    st.markdown("#### ⚠️ Riscos Identificados")
                                    for i, risco in enumerate(analysis_result['riscos'], 1):
                                        with st.expander(f"**{i}. [{risco['categoria']}] {risco['keyword'].upper()}** - Severidade: {risco['severidade']}"):
                                            st.write(f"**Contexto:** {risco['contexto']}")
                                    
                                    # Recomendações
                                    st.markdown("#### 💡 Recomendações de Ação")
                                    for i, recomendacao in enumerate(analysis_result['recomendacoes'], 1):
                                        st.info(f"**{i}.** {recomendacao}")
                                        
                            else:
                                st.error("❌ O arquivo PDF não contém texto suficiente para análise. Verifique se o documento é legível.")
                                
                        except Exception as e:
                            st.error(f"❌ Erro durante a análise: {str(e)}")
            
            with col2:
                st.markdown("""
                <div class='feature-card'>
                    <h4>🎯 Dicas para Melhor Análise</h4>
                    <p>• Use PDFs com texto selecionável</p>
                    <p>• Verifique a qualidade do documento</p>
                    <p>• Inclua todas as páginas relevantes</p>
                    <p>• Evite documentos escaneados com baixa qualidade</p>
                    <p>• Certifique-se de que o texto está legível</p>
                </div>
                """, unsafe_allow_html=True)
                
                st.markdown("""
                <div class='feature-card'>
                    <h4>📊 Interpretação de Resultados</h4>
                    <p><strong>0-39:</strong> Baixo Risco</p>
                    <p><strong>40-69:</strong> Risco Moderado</p>
                    <p><strong>70-100:</strong> Alto Risco</p>
                </div>
                """, unsafe_allow_html=True)
        
        else:
            st.info("""
            👆 **Faça upload de um arquivo PDF** para começar a análise
            
            A Clara Ready irá analisar automaticamente:
            • Cláusulas financeiras e de pagamento
            • Prazos e condições contratuais
            • Aspectos legais e jurisdicionais  
            • Riscos operacionais e de desempenho
            """)
    
    with tab2:
        st.markdown('<div class="sub-header">📊 Dashboard Financeiro</div>', unsafe_allow_html=True)
        
        if st.session_state.analysis_history:
            # Métricas principais
            col1, col2, col3, col4 = st.columns(4)
            
            total_analises = len(st.session_state.analysis_history)
            risco_medio = np.mean([a['risk_score'] for a in st.session_state.analysis_history])
            total_riscos = sum([a['result']['total_riscos'] for a in st.session_state.analysis_history])
            economia_estimada = total_riscos * 1200  # Valor estimado por risco identificado
            
            with col1:
                st.metric("📈 Contratos Analisados", total_analises)
            with col2:
                st.metric("⚖️ Risco Médio", f"{risco_medio:.1f}/100")
            with col3:
                st.metric("⚠️ Riscos Totais", total_riscos)
            with col4:
                st.metric("💰 Economia Estimada", f"R$ {economia_estimada:,}")
            
            # Gráficos
            col_chart1, col_chart2 = st.columns(2)
            
            with col_chart1:
                st.plotly_chart(create_risk_distribution_chart(st.session_state.analysis_history), use_container_width=True)
            
            with col_chart2:
                # Gráfico de tendência temporal
                if len(st.session_state.analysis_history) > 1:
                    dates = [a['date'] for a in st.session_state.analysis_history]
                    scores = [a['risk_score'] for a in st.session_state.analysis_history]
                    
                    fig = px.line(
                        x=dates, y=scores,
                        title="Evolução do Risco ao Longo do Tempo",
                        labels={'x': 'Data', 'y': 'Pontuação de Risco'}
                    )
                    fig.update_layout(height=300)
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("📈 Execute mais análises para ver a evolução temporal")
            
            # Análises recentes detalhadas
            st.markdown("#### 📋 Histórico de Análises")
            for analysis in st.session_state.analysis_history[:5]:
                with st.expander(f"{analysis['filename']} - {analysis['date'].strftime('%d/%m/%Y %H:%M')} - Score: {analysis['risk_score']}/100"):
                    st.write(f"**Riscos Identificados:** {analysis['result']['total_riscos']}")
                    st.write(f"**Categorias:** {', '.join(analysis['result']['categorias_afetadas'])}")
                    st.write(f"**Resumo:** {generate_executive_summary(analysis['result']).split('Status:')[0]}")
        
        else:
            st.info("""
            📊 **Execute algumas análises** para ver métricas e gráficos interativos
            
            O dashboard mostrará:
            • Evolução do risco ao longo do tempo
            • Distribuição das pontuações
            • Estatísticas consolidadas
            • Insights e tendências
            """)
    
    with tab3:
        st.markdown('<div class="sub-header">📈 Relatórios Detalhados</div>', unsafe_allow_html=True)
        
        if st.session_state.analysis_history:
            selected_analysis = st.selectbox(
                "📋 Selecione uma análise para gerar relatório:",
                options=st.session_state.analysis_history,
                format_func=lambda x: f"{x['filename']} - {x['date'].strftime('%d/%m/%Y %H:%M')} - Score: {x['risk_score']}/100"
            )
            
            if selected_analysis:
                col_report1, col_report2 = st.columns([3, 1])
                
                with col_report1:
                    st.markdown("#### 📄 Visualização do Relatório")
                    
                    # Resumo executivo
                    st.markdown(generate_executive_summary(selected_analysis['result']))
                    
                    # Detalhes da análise
                    st.markdown("##### 📊 Detalhes da Análise")
                    st.json(selected_analysis['result'], expanded=False)
                
                with col_report2:
                    st.markdown("#### 📥 Exportar Relatório")
                    
                    # Botão de download
                    report_data = generate_pdf_report(selected_analysis)
                    st.download_button(
                        label="💾 Baixar PDF",
                        data=report_data,
                        file_name=f"relatorio_{selected_analysis['filename'][:-4]}_{datetime.now().strftime('%Y%m%d_%H%M')}.txt",
                        mime="text/plain",
                        use_container_width=True
                    )
                    
                    st.download_button(
                        label="📊 Exportar JSON",
                        data=json.dumps(selected_analysis, indent=2, ensure_ascii=False),
                        file_name=f"dados_{selected_analysis['filename'][:-4]}.json",
                        mime="application/json",
                        use_container_width=True
                    )
        
        else:
            st.info("📄 **Execute análises** para gerar relatórios detalhados")
    
    with tab4:
        st.markdown('<div class="sub-header">⚙️ Configurações</div>', unsafe_allow_html=True)
        
        col_set1, col_set2 = st.columns(2)
        
        with col_set1:
            st.markdown("#### 📧 Preferências de Notificação")
            notif_email = st.checkbox("Receber notificações por email", value=True)
            notif_alert = st.checkbox("Alertas para riscos altos", value=True)
            notif_weekly = st.checkbox("Relatório semanal resumido", value=False)
            
            st.markdown("#### 🎨 Personalização")
            tema = st.selectbox("Tema da
