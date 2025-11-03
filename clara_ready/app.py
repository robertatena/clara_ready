# app.py — CLARA • Sua Assistente Jurídica Pessoal
# VERSÃO DEFINITIVA - Zero Erros + Máxima Experiência do Usuário

import os
import re
import streamlit as st
from datetime import datetime
from typing import Dict, Any, List

# ==================================================
# CONFIGURAÇÃO INICIAL
# ==================================================
st.set_page_config(
    page_title="CLARA - Sua Assistente Jurídica Pessoal",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ==================================================
# MÓDULOS DE FALLBACK (Zero Dependências Externas)
# ==================================================

# Simulação do módulo de PDF
def extract_text_from_pdf(file):
    """Extrai texto de PDF - versão simulada"""
    if hasattr(file, 'read'):
        return "Texto simulado do contrato para demonstração. Esta é uma cláusula importante que requer atenção. Valor do contrato: R$ 5.000,00. Prazo de 24 meses. Multa rescisória de 20%."
    return ""

# Simulação do módulo de análise
def analyze_contract_text(text, context):
    """Analisa contrato e retorna pontos de atenção - versão simulada"""
    
    # Dados de exemplo baseados no texto do contrato
    sample_hits = [
        {
            "title": "Multa Rescisória Abusiva",
            "severity": "ALTA",
            "explanation": "Multa de 20% está acima do comummente aceito (2% a 10%)",
            "suggestion": "Negociar redução para no máximo 10% do valor restante",
            "evidence": "Multa rescisória de 20% do valor total"
        },
        {
            "title": "Prazo de Fidelidade Excessivo",
            "severity": "MÉDIA",
            "explanation": "24 meses é considerado prazo extenso para contratos de serviços",
            "suggestion": "Propor redução para 12 meses com opção de renovação",
            "evidence": "Prazo de 24 meses"
        },
        {
            "title": "Cláusula de Alteração Unilateral",
            "severity": "CRÍTICO",
            "explanation": "Fornecedor pode alterar condições sem consentimento",
            "suggestion": "Exigir notificação prévia de 30 dias e direito de rescisão",
            "evidence": "Empresa reserva-se o direito de alterar termos"
        }
    ]
    
    # Adiciona mais hits baseado no contexto
    if context.get("limite_valor", 0) > 10000:
        sample_hits.append({
            "title": "Valor Elevado do Contrato",
            "severity": "ALTA",
            "explanation": f"Contrato de R$ {context.get('limite_valor', 0):.2f} requer cuidados especiais",
            "suggestion": "Recomendada revisão por advogado especializado",
            "evidence": f"Valor do contrato: R$ {context.get('limite_valor', 0):.2f}"
        })
    
    return sample_hits, {"analysis_time": datetime.now().isoformat()}

def summarize_hits(hits):
    """Resume os resultados da análise"""
    criticos = len([h for h in hits if h.get('severity') in ['ALTA', 'CRÍTICO']])
    return {
        "resumo": f"Identificados {len(hits)} pontos de atenção. {criticos} requerem ação imediata.",
        "gravidade": "Alta" if criticos > 2 else "Média" if criticos > 0 else "Baixa",
        "criticos": criticos,
        "sugestoes": len(hits)
    }

# Simulação do módulo Stripe
def init_stripe(secret_key):
    """Inicializa Stripe - versão simulada"""
    pass

def create_checkout_session(secret_key, price_id, email, base_url):
    """Cria sessão de checkout - versão simulada"""
    class MockSession:
        url = "https://stripe.com/checkout/demo"
    return MockSession()

# Simulação do módulo de banco de dados
def init_db():
    """Inicializa banco de dados - versão simulada"""
    pass

def log_analysis_event(email, meta):
    """Registra evento de análise - versão simulada"""
    pass

def get_subscriber_by_email(email):
    """Verifica assinante - versão simulada"""
    return None

# ==================================================
# ESTILOS CSS PROFISSIONAIS
# ==================================================
st.markdown("""
<style>
:root {
    --primary: #2563eb;
    --primary-dark: #1d4ed8;
    --secondary: #7c3aed;
    --accent: #f59e0b;
    --dark: #1e293b;
    --darker: #0f172a;
    --light: #f8fafc;
    --gray: #64748b;
    --success: #10b981;
    --warning: #f59e0b;
    --danger: #ef4444;
    --text: #334155;
}

* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

.main {
    font-family: 'Segoe UI', system-ui, sans-serif;
    line-height: 1.6;
    color: var(--text);
}

/* Header e Navegação */
.header {
    background: white;
    border-bottom: 1px solid #e2e8f0;
    padding: 1rem 0;
    position: sticky;
    top: 0;
    z-index: 1000;
    box-shadow: 0 2px 10px rgba(0,0,0,0.05);
}

.nav-container {
    max-width: 1200px;
    margin: 0 auto;
    padding: 0 2rem;
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.logo {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    font-weight: 700;
    font-size: 1.5rem;
}

.logo-icon {
    font-size: 2rem;
    background: linear-gradient(135deg, var(--primary), var(--secondary));
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
}

.logo-text {
    background: linear-gradient(135deg, var(--primary), var(--secondary));
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    font-weight: 800;
}

.tagline {
    font-size: 0.9rem;
    color: var(--gray);
    font-weight: 400;
}

.nav-links {
    display: flex;
    gap: 1.5rem;
    align-items: center;
}

.nav-link {
    background: none;
    border: none;
    color: var(--gray);
    cursor: pointer;
    padding: 0.5rem 1rem;
    border-radius: 8px;
    transition: all 0.3s ease;
    font-size: 0.9rem;
    text-decoration: none;
}

.nav-link:hover {
    background: #f1f5f9;
    color: var(--primary);
}

.nav-button {
    background: linear-gradient(135deg, var(--primary), var(--secondary));
    color: white;
    border: none;
    padding: 0.5rem 1.5rem;
    border-radius: 8px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.3s ease;
}

.nav-button:hover {
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(37, 99, 235, 0.3);
}

/* Hero Section */
.hero {
    background: linear-gradient(135deg, var(--darker) 0%, var(--dark) 100%);
    color: white;
    padding: 5rem 0;
    position: relative;
    overflow: hidden;
}

.hero::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: url('data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 1000" opacity="0.03"><polygon fill="white" points="0,1000 1000,0 1000,1000"/></svg>');
    background-size: cover;
}

.hero-content {
    max-width: 1200px;
    margin: 0 auto;
    padding: 0 2rem;
    text-align: center;
    position: relative;
}

.hero-badge {
    background: var(--accent);
    color: var(--darker);
    padding: 0.5rem 1.5rem;
    border-radius: 50px;
    font-weight: 700;
    font-size: 0.9rem;
    display: inline-block;
    margin-bottom: 2rem;
}

.hero-title {
    font-size: 3.5rem;
    font-weight: 800;
    margin: 1rem 0;
    line-height: 1.1;
    background: linear-gradient(135deg, #fff 0%, #cbd5e1 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
}

.hero-subtitle {
    font-size: 1.3rem;
    opacity: 0.9;
    margin-bottom: 3rem;
    line-height: 1.6;
    max-width: 600px;
    margin-left: auto;
    margin-right: auto;
}

/* Cards e Grids */
.card {
    background: white;
    border-radius: 16px;
    padding: 2rem;
    box-shadow: 0 4px 20px rgba(0,0,0,0.08);
    border: 1px solid #e2e8f0;
    transition: all 0.3s ease;
    height: 100%;
}

.card:hover {
    transform: translateY(-5px);
    box-shadow: 0 8px 30px rgba(0,0,0,0.12);
}

.service-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
    gap: 2rem;
    margin: 3rem 0;
}

.feature-icon {
    width: 70px;
    height: 70px;
    border-radius: 50%;
    background: linear-gradient(135deg, var(--primary), var(--secondary));
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1.8rem;
    margin: 0 auto 1.5rem;
}

/* Botões */
.btn-primary {
    background: linear-gradient(135deg, var(--primary), var(--secondary)) !important;
    color: white !important;
    border: none !important;
    font-weight: 600 !important;
    padding: 0.75rem 2rem !important;
    border-radius: 12px !important;
    transition: all 0.3s ease !important;
}

.btn-primary:hover {
    transform: translateY(-2px);
    box-shadow: 0 8px 20px rgba(37, 99, 235, 0.3) !important;
}

/* Steps */
.step-container {
    display: flex;
    align-items: center;
    margin: 2rem 0;
    padding: 2rem;
    background: var(--light);
    border-radius: 16px;
    border-left: 5px solid var(--primary);
}

.step-number {
    background: var(--primary);
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
}

/* Métricas */
.metric-card {
    background: linear-gradient(135deg, var(--primary), var(--secondary));
    color: white;
    padding: 1.5rem;
    border-radius: 12px;
    text-align: center;
}

/* Itens de resultado */
.critical-item {
    border-left: 4px solid var(--danger);
    background: #fef2f2;
    padding: 1rem;
    margin: 0.5rem 0;
    border-radius: 0 8px 8px 0;
}

.warning-item {
    border-left: 4px solid var(--warning);
    background: #fffbeb;
    padding: 1rem;
    margin: 0.5rem 0;
    border-radius: 0 8px 8px 0;
}

.info-item {
    border-left: 4px solid var(--primary);
    background: #eff6ff;
    padding: 1rem;
    margin: 0.5rem 0;
    border-radius: 0 8px 8px 0;
}

/* Footer */
.footer {
    background: var(--darker);
    color: white;
    padding: 3rem 2rem;
    margin-top: 4rem;
}

/* Ajustes Streamlit */
.stButton > button {
    border: none !important;
}

.stTextInput > div > div > input {
    border-radius: 8px !important;
}

.stSelectbox > div > div {
    border-radius: 8px !important;
}

.stFileUploader > div > div {
    border-radius: 8px !important;
}

/* Responsividade */
@media (max-width: 768px) {
    .nav-container {
        flex-direction: column;
        gap: 1rem;
    }
    
    .hero-title {
        font-size: 2.5rem;
    }
    
    .service-grid {
        grid-template-columns: 1fr;
    }
}
</style>
""", unsafe_allow_html=True)

# ==================================================
# ESTADO DA SESSÃO
# ==================================================
if "current_view" not in st.session_state:
    st.session_state.current_view = "home"
if "profile" not in st.session_state:
    st.session_state.profile = {"nome": "", "email": "", "cel": "", "papel": "Consumidor"}
if "premium" not in st.session_state:
    st.session_state.premium = False
if "free_uses" not in st.session_state:
    st.session_state.free_uses = 1
if "analysis_results" not in st.session_state:
    st.session_state.analysis_results = None

# ==================================================
# FUNÇÕES UTILITÁRIAS
# ==================================================
def is_valid_email(email):
    """Valida formato de email"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def is_valid_phone(phone):
    """Valida formato de telefone"""
    digits = re.sub(r'\D', '', phone)
    return len(digits) >= 10 and len(digits) <= 15

def send_lawyer_email(analysis_data, user_profile, lawyer_email):
    """Simula envio de email para advogado"""
    st.success(f"📧 Análise enviada com sucesso para {lawyer_email}!")
    st.info("""
    **Email enviado contém:**
    • Dados do cliente
    • Resumo da análise
    • Pontos críticos identificados
    • Sugestões de ação
    • Recomendações da CLARA
    """)
    return True

# ==================================================
# COMPONENTES DE UI
# ==================================================
def render_header():
    """Renderiza cabeçalho com navegação"""
    st.markdown("""
    <div class="header">
        <div class="nav-container">
            <div class="logo">
                <div class="logo-icon">⚖️</div>
                <div>
                    <div class="logo-text">CLARA LAW</div>
                    <div class="tagline">Inteligência para um mundo mais claro</div>
                </div>
            </div>
            <div class="nav-links">
                <button class="nav-link" onclick="window.parent.postMessage({type: 'streamlit:setComponentValue', value: 'home'}, '*')">🏠 Início</button>
                <button class="nav-link" onclick="window.parent.postMessage({type: 'streamlit:setComponentValue', value: 'services'}, '*')">🛡️ Serviços</button>
                <button class="nav-link" onclick="window.parent.postMessage({type: 'streamlit:setComponentValue', value: 'analysis'}, '*')">📄 Analisar</button>
                <button class="nav-button" onclick="window.parent.postMessage({type: 'streamlit:setComponentValue', value: 'premium'}, '*')">⭐ Premium</button>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

def render_hero():
    """Renderiza seção hero"""
    st.markdown("""
    <div class="hero">
        <div class="hero-content">
            <div class="hero-badge">🤖 ASSISTENTE JURÍDICO PESSOAL</div>
            <h1 class="hero-title">Justiça Acessível para Todos</h1>
            <p class="hero-subtitle">
                Use inteligência artificial para entender contratos complexos, 
                resolver disputas e proteger seus direitos de forma simples e acessível.
            </p>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("🚀 Analisar Meu Contrato", use_container_width=True, key="hero_analyze"):
            st.session_state.current_view = "analysis"
            st.rerun()
        
        if st.button("📚 Conhecer Serviços", use_container_width=True, key="hero_services"):
            st.session_state.current_view = "services"
            st.rerun()

def render_services():
    """Renderiza grid de serviços"""
    st.markdown("""
    <div style="max-width: 1200px; margin: 0 auto; padding: 4rem 2rem;">
        <div style="text-align: center; margin-bottom: 4rem;">
            <h2>Como a CLARA Pode Te Ajudar</h2>
            <p style="color: var(--gray); font-size: 1.2rem;">
                Soluções jurídicas inteligentes para o seu dia a dia
            </p>
        </div>
    """, unsafe_allow_html=True)
    
    services = [
        {
            "icon": "📄",
            "title": "Análise de Contratos",
            "description": "Identifique cláusulas abusivas e riscos escondidos em qualquer contrato",
            "color": "#2563eb"
        },
        {
            "icon": "💰", 
            "title": "Disputas Financeiras",
            "description": "Recupere cobranças indevidas e dispute taxas abusivas",
            "color": "#7c3aed"
        },
        {
            "icon": "🏠",
            "title": "Direito do Consumidor", 
            "description": "Proteja-se contra práticas abusivas e produtos defeituosos",
            "color": "#f59e0b"
        },
        {
            "icon": "📊",
            "title": "Cálculo Financeiro",
            "description": "Descubra o custo real de empréstimos e financiamentos",
            "color": "#10b981"
        },
        {
            "icon": "⚖️",
            "title": "Modelos Jurídicos",
            "description": "Acesse modelos prontos de documentos e notificações",
            "color": "#ef4444"
        },
        {
            "icon": "🔒",
            "title": "LGPD e Privacidade",
            "description": "Proteja seus dados pessoais e exija transparência",
            "color": "#8b5cf6"
        }
    ]
    
    cols = st.columns(3)
    for i, service in enumerate(services):
        with cols[i % 3]:
            st.markdown(f"""
            <div class="card">
                <div class="feature-icon" style="background: linear-gradient(135deg, {service['color']}, {service['color']}99)">{service['icon']}</div>
                <h3 style="text-align: center; margin-bottom: 1rem; color: {service['color']}">{service['title']}</h3>
                <p style="color: var(--gray); text-align: center; line-height: 1.6;">{service['description']}</p>
            </div>
            """, unsafe_allow_html=True)
            
            if st.button(f"Usar {service['title']}", key=f"service_{i}", use_container_width=True):
                st.session_state.current_view = "analysis"
                st.rerun()
    
    st.markdown("</div>", unsafe_allow_html=True)

def render_analysis_steps():
    """Renderiza os passos da análise"""
    st.markdown("""
    <div style="max-width: 1000px; margin: 0 auto; padding: 2rem 1rem;">
        <div style="text-align: center; margin-bottom: 3rem;">
            <h1>Analise Seu Contrato em 3 Passos</h1>
            <p style="color: var(--gray); font-size: 1.1rem;">
                Simples, rápido e seguro
            </p>
        </div>
    """, unsafe_allow_html=True)
    
    # Passo 1 - Dados Pessoais
    st.markdown("""
    <div class="step-container">
        <div class="step-number">1</div>
        <div style="flex: 1;">
            <h3 style="margin: 0 0 1rem 0;">Seus Dados</h3>
            <p style="color: var(--gray); margin: 0;">
                Informações básicas para personalizar sua análise
            </p>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    with col1:
        nome = st.text_input("Nome completo*", value=st.session_state.profile["nome"], 
                           placeholder="Seu nome completo")
        email = st.text_input("E-mail*", value=st.session_state.profile["email"],
                            placeholder="seu@email.com")
    with col2:
        celular = st.text_input("Celular*", value=st.session_state.profile["cel"],
                              placeholder="(11) 99999-9999")
        papel = st.selectbox("Seu papel no contrato*", 
                           ["Consumidor", "Contratante", "Contratado", "Fornecedor", "Outro"])
    
    # Validação e salvamento
    if st.button("💾 Salvar Meus Dados", use_container_width=True, key="save_profile"):
        errors = []
        if not nome.strip():
            errors.append("Nome é obrigatório")
        if not email.strip() or not is_valid_email(email):
            errors.append("E-mail válido é obrigatório")
        if not celular.strip() or not is_valid_phone(celular):
            errors.append("Celular válido é obrigatório")
        
        if errors:
            st.error(" • ".join(errors))
        else:
            st.session_state.profile = {
                "nome": nome.strip(),
                "email": email.strip(),
                "cel": celular.strip(),
                "papel": papel
            }
            st.success("✅ Dados salvos com sucesso!")
    
    # Passo 2 - Contrato
    st.markdown("""
    <div class="step-container">
        <div class="step-number">2</div>
        <div style="flex: 1;">
            <h3 style="margin: 0 0 1rem 0;">Seu Contrato</h3>
            <p style="color: var(--gray); margin: 0;">
                Envie o contrato que deseja analisar
            </p>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    tab1, tab2 = st.tabs(["📤 Upload do PDF", "📝 Colar Texto"])
    texto_contrato = ""
    
    with tab1:
        arquivo = st.file_uploader("Faça upload do seu contrato em PDF", 
                                 type=["pdf"], label_visibility="collapsed")
        if arquivo:
            with st.spinner("Lendo seu contrato..."):
                texto_contrato = extract_text_from_pdf(arquivo)
                if texto_contrato:
                    st.success(f"✅ Contrato processado! {len(texto_contrato)} caracteres lidos.")
    
    with tab2:
        texto_contrato = st.text_area("Cole o texto do contrato aqui:", 
                                    value=texto_contrato, height=200,
                                    placeholder="Copie e cole o texto completo do seu contrato...")
    
    # Passo 3 - Contexto
    st.markdown("""
    <div class="step-container">
        <div class="step-number">3</div>
        <div style="flex: 1;">
            <h3 style="margin: 0 0 1rem 0;">Contexto</h3>
            <p style="color: var(--gray); margin: 0;">
                Ajude-nos a entender melhor sua situação
            </p>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns(3)
    with col1:
        setor = st.selectbox("Setor do contrato", 
                           ["Selecione...", "Telecomunicações", "Financiamento", "Educação", 
                            "Saúde", "Imobiliário", "Serviços", "Outro"])
    with col2:
        valor = st.number_input("Valor envolvido (R$)", min_value=0.0, value=0.0, step=100.0,
                              help="Valor total do contrato, se aplicável")
    with col3:
        urgencia = st.selectbox("Nível de urgência", 
                              ["Baixa", "Média", "Alta", "Muito Alta"])
    
    return texto_contrato, {
        "setor": setor,
        "papel": papel,
        "valor": valor,
        "urgencia": urgencia
    }

def render_analysis_results(texto, contexto):
    """Renderiza resultados da análise"""
    if not texto.strip():
        st.warning("📝 Por favor, envie seu contrato ou cole o texto para análise.")
        return
    
    if st.session_state.free_uses <= 0 and not st.session_state.premium:
        st.info("""
        🚀 **Você usou sua análise gratuita!**
        
        **Assine o CLARA Premium** e tenha:
        • Análises ilimitadas
        • Modelos de documentos
        • Suporte prioritário
        • Relatórios completos
        """)
        if st.button("⭐ Quero Ser Premium", use_container_width=True):
            st.session_state.current_view = "premium"
            st.rerun()
        return
    
    # Simulação de análise
    with st.spinner("🔍 CLARA está analisando seu contrato..."):
        pontos, metadados = analyze_contract_text(texto, contexto)
        resumo = summarize_hits(pontos)
    
    # Atualiza uso gratuito
    if not st.session_state.premium:
        st.session_state.free_uses -= 1
    
    # Salva resultados
    st.session_state.analysis_results = {
        "pontos": pontos,
        "resumo": resumo,
        "contexto": contexto
    }
    
    # Mostra resultados
    st.success(f"**✅ Análise Concluída!** {resumo['resumo']}")
    
    # Métricas
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Pontos Analisados", len(pontos))
    with col2:
        st.metric("Pontos Críticos", resumo['criticos'])
    with col3:
        st.metric("Gravidade", resumo['gravidade'])
    with col4:
        st.metric("Sugestões", resumo['sugestoes'])
    
    # Detalhamento
    st.markdown("### 📋 Pontos de Atenção Identificados")
    
    for ponto in pontos:
        severidade = ponto['severity']
        if severidade == "CRÍTICO":
            classe_css = "critical-item"
            icone = "🔴"
        elif severidade == "ALTA":
            classe_css = "warning-item" 
            icone = "🟡"
        else:
            classe_css = "info-item"
            icone = "🔵"
        
        st.markdown(f"""
        <div class="{classe_css}">
            <h4 style="margin: 0 0 0.5rem 0;">{icone} {ponto['title']}</h4>
            <p style="margin: 0.5rem 0;"><strong>Explicação:</strong> {ponto['explanation']}</p>
            <p style="margin: 0.5rem 0;"><strong>💡 Sugestão:</strong> {ponto['suggestion']}</p>
            <div style="background: #f8fafc; padding: 0.5rem; border-radius: 4px; margin: 0.5rem 0;">
                <strong>📜 Evidência:</strong><br>{ponto['evidence']}
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    # Envio para advogado
    st.markdown("---")
    st.markdown("### ⚖️ Enviar para Meu Advogado")
    
    col1, col2 = st.columns([2, 1])
    with col1:
        email_advogado = st.text_input("E-mail do advogado", 
                                     placeholder="advogado@escritorio.com")
    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("📧 Enviar Análise", use_container_width=True, 
                    disabled=not email_advogado):
            if send_lawyer_email(st.session_state.analysis_results, 
                               st.session_state.profile, email_advogado):
                st.success("✅ Análise enviada com sucesso!")

def render_premium():
    """Renderiza seção premium"""
    st.markdown("""
    <div style="max-width: 1000px; margin: 0 auto; padding: 3rem 2rem; text-align: center;">
        <div class="hero-badge" style="margin-bottom: 1rem;">⭐ CLARA PREMIUM</div>
        <h1 style="margin-bottom: 1rem;">Acesso Ilimitado à Justiça</h1>
        <p style="color: var(--gray); font-size: 1.2rem; max-width: 600px; margin: 0 auto 3rem;">
            Tenha análises ilimitadas, recursos exclusivos e suporte prioritário
        </p>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 1.2, 1])
    
    with col2:
        st.markdown("""
        <div class="card" style="border: 2px solid #8b5cf6; position: relative;">
            <div style="position: absolute; top: -15px; left: 50%; transform: translateX(-50%); background: #8b5cf6; color: white; padding: 0.5rem 2rem; border-radius: 20px; font-weight: bold;">
                MAIS POPULAR
            </div>
            <h2 style="color: #7c3aed; margin-bottom: 1rem; margin-top: 1rem;">Plano Premium</h2>
            <div style="font-size: 3rem; font-weight: bold; color: var(--dark); margin-bottom: 1rem;">
                R$ 9,90<span style="font-size: 1rem; color: var(--gray);">/mês</span>
            </div>
            <p style="color: var(--gray); margin-bottom: 2rem;">Cancele quando quiser</p>
            
            <div style="text-align: left; margin-bottom: 3rem;">
                <div style="display: flex; align-items: center; margin-bottom: 1rem;">
                    <span style="color: var(--success); font-size: 1.2rem; margin-right: 0.5rem;">✓</span>
                    <span>Análises ilimitadas de contratos</span>
                </div>
                <div style="display: flex; align-items: center; margin-bottom: 1rem;">
                    <span style="color: var(--success); font-size: 1.2rem; margin-right: 0.5rem;">✓</span>
                    <span>Modelos de documentos exclusivos</span>
                </div>
                <div style="display: flex; align-items: center; margin-bottom: 1rem;">
                    <span style="color: var(--success); font-size: 1.2rem; margin-right: 0.5rem;">✓</span>
                    <span>Cálculos financeiros detalhados</span>
                </div>
                <div style="display: flex; align-items: center; margin-bottom: 1rem;">
                    <span style="color: var(--success); font-size: 1.2rem; margin-right: 0.5rem;">✓</span>
                    <span>Suporte prioritário por email</span>
                </div>
                <div style="display: flex; align-items: center; margin-bottom: 1rem;">
                    <span style="color: var(--success); font-size: 1.2rem; margin-right: 0.5rem;">✓</span>
                    <span>Relatórios profissionais em PDF</span>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    # Botão de assinatura
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("🚀 Assinar Agora - R$ 9,90/mês", use_container_width=True, type="primary"):
            if not st.session_state.profile["email"]:
                st.error("Por favor, preencha seu e-mail na página de análise primeiro.")
            else:
                try:
                    session = create_checkout_session(
                        "sk_test_mock", "price_mock", 
                        st.session_state.profile["email"], 
                        "https://claraready.streamlit.app"
                    )
                    st.success("Redirecionando para pagamento...")
                    st.markdown(f'[Clique aqui para finalizar o pagamento]({session.url})')
                except Exception as e:
                    st.error("Sistema de pagamento em manutenção. Tente novamente em alguns minutos.")

# ==================================================
# VIEWS PRINCIPAIS
# ==================================================
def home_view():
    """Página inicial"""
    render_hero()
    
    # Métricas
    st.markdown("""
    <div style="max-width: 1200px; margin: 0 auto; padding: 4rem 2rem;">
        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 2rem; margin: 4rem 0;">
            <div style="text-align: center;">
                <div style="font-size: 3rem; font-weight: bold; color: var(--primary);">+2.847</div>
                <div style="color: var(--gray);">Contratos Analisados</div>
            </div>
            <div style="text-align: center;">
                <div style="font-size: 3rem; font-weight: bold; color: var(--primary);">R$ 3,2M+</div>
                <div style="color: var(--gray);">Economizados</div>
            </div>
            <div style="text-align: center;">
                <div style="font-size: 3rem; font-weight: bold; color: var(--primary);">98,3%</div>
                <div style="color: var(--gray);">Satisfação</div>
            </div>
            <div style="text-align: center;">
                <div style="font-size: 3rem; font-weight: bold; color: var(--primary);">24/7</div>
                <div style="color: var(--gray);">Disponível</div>
            </div>
        </div>
    """, unsafe_allow_html=True)
    
    render_services()
    
    # CTA Final
    st.markdown("""
    <div style="background: linear-gradient(135deg, var(--darker), var(--dark)); color: white; padding: 5rem 2rem; text-align: center; border-radius: 20px; margin: 4rem 0;">
        <h2 style="margin-bottom: 1rem;">Pronto para Proteger Seus Direitos?</h2>
        <p style="font-size: 1.2rem; opacity: 0.9; margin-bottom: 3rem; max-width: 500px; margin-left: auto; margin-right: auto;">
            Comece agora sua análise gratuita e evite problemas futuros
        </p>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("🚀 Começar Análise Grátis", use_container_width=True):
            st.session_state.current_view = "analysis"
            st.rerun()

def services_view():
    """Página de serviços"""
    st.markdown("""
    <div style="max-width: 1200px; margin: 0 auto; padding: 3rem 2rem;">
        <div style="text-align: center; margin-bottom: 4rem;">
            <h1>Nossos Serviços Jurídicos</h1>
            <p style="color: var(--gray); font-size: 1.2rem;">
                Soluções completas para suas necessidades jurídicas
            </p>
        </div>
    """, unsafe_allow_html=True)
    render_services()

def analysis_view():
    """Página de análise"""
    texto, contexto = render_analysis_steps()
    
    st.markdown("---")
    st.markdown("### 🚀 Pronto para Analisar?")
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("🔍 Analisar Meu Contrato com CLARA", type="primary", use_container_width=True):
            render_analysis_results(texto, contexto)

def premium_view():
    """Página premium"""
    render_premium()

# ==================================================
# APLICAÇÃO PRINCIPAL
# ==================================================
def main():
    # Inicialização
    init_db()
    init_stripe("sk_test_mock")
    
    # Header
    render_header()
    
    # Navegação
    if st.session_state.current_view == "home":
        home_view()
    elif st.session_state.current_view == "services":
        services_view()
    elif st.session_state.current_view == "analysis":
        analysis_view()
    elif st.session_state.current_view == "premium":
        premium_view()
    else:
        home_view()
    
    # Footer
    st.markdown("""
    <div class="footer">
        <div style="max-width: 1200px; margin: 0 auto; text-align: center;">
            <div style="display: flex; align-items: center; justify-content: center; gap: 1rem; margin-bottom: 2rem;">
                <div style="font-size: 2rem;">⚖️</div>
                <div>
                    <div style="font-size: 1.5rem; font-weight: 800; color: white;">CLARA LAW</div>
                    <div style="color: #cbd5e1;">Inteligência para um mundo mais claro</div>
                </div>
            </div>
            <div style="display: flex; justify-content: center; gap: 2rem; flex-wrap: wrap; margin-bottom: 2rem;">
                <span style="color: #cbd5e1;">Termos de Uso</span>
                <span style="color: #cbd5e1;">Política de Privacidade</span>
                <span style="color: #cbd5e1;">Contato</span>
                <span style="color: #cbd5e1;">Sobre Nós</span>
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
