import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from streamlit_lottie import st_lottie
import json
import requests
from datetime import datetime
import io
import base64

# Configuração da página
st.set_page_config(
    page_title="Clara Ready - Dashboard Analytics",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS personalizado
st.markdown("""
<style>
    .main-header {
        font-size: 3rem;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 1.5rem;
        border-radius: 10px;
        border-left: 5px solid #1f77b4;
    }
    .sidebar .sidebar-content {
        background-color: #f8f9fa;
    }
</style>
""", unsafe_allow_html=True)

# Função para carregar animações Lottie
def load_lottie_url(url: str):
    try:
        r = requests.get(url)
        if r.status_code != 200:
            return None
        return r.json()
    except:
        return None

# Função para carregar Lottie local
def load_lottie_file(filepath: str):
    try:
        with open(filepath, "r") as f:
            return json.load(f)
    except:
        return None

# Header principal
st.markdown('<h1 class="main-header">📊 Clara Ready Analytics</h1>', unsafe_allow_html=True)

# Sidebar
with st.sidebar:
    st.title("🔧 Configurações")
    
    # Upload de arquivo
    uploaded_file = st.file_uploader("📁 Upload de arquivo", type=['csv', 'xlsx', 'txt'])
    
    # Filtros
    st.subheader("🎯 Filtros")
    date_range = st.date_input(
        "Período",
        value=(datetime.now().replace(day=1), datetime.now()),
        key="date_range"
    )
    
    categories = st.multiselect(
        "Categorias",
        ["Marketing", "Vendas", "TI", "RH", "Financeiro"],
        default=["Marketing", "Vendas"]
    )
    
    # Configurações
    st.subheader("⚙️ Configurações")
    theme = st.selectbox("Tema", ["Claro", "Escuro"])
    auto_refresh = st.checkbox("Atualização automática")

# Conteúdo principal em abas
tab1, tab2, tab3, tab4 = st.tabs(["📈 Dashboard", "📊 Análises", "📁 Dados", "ℹ️ Sobre"])

with tab1:
    st.header("Visão Geral")
    
    # Métricas principais
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown('<div class="metric-card">', unsafe_allow_html=True)
        st.metric("Receita Total", "R$ 125.000", "+15%")
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col2:
        st.markdown('<div class="metric-card">', unsafe_allow_html=True)
        st.metric("Novos Clientes", "45", "+8%")
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col3:
        st.markdown('<div class="metric-card">', unsafe_allow_html=True)
        st.metric("Taxa de Conversão", "3.2%", "+0.5%")
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col4:
        st.markdown('<div class="metric-card">', unsafe_allow_html=True)
        st.metric("Satisfação", "4.5/5", "+0.2")
        st.markdown('</div>', unsafe_allow_html=True)
    
    # Gráficos
    col1, col2 = st.columns(2)
    
    with col1:
        # Gráfico de linha - Receita ao longo do tempo
        st.subheader("Receita Mensal")
        revenue_data = pd.DataFrame({
            'Mês': ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun'],
            'Receita': [85000, 92000, 105000, 112000, 118000, 125000]
        })
        
        fig_line = px.line(
            revenue_data,
            x='Mês',
            y='Receita',
            title='Evolução da Receita',
            markers=True
        )
        fig_line.update_layout(height=400)
        st.plotly_chart(fig_line, use_container_width=True)
    
    with col2:
        # Gráfico de pizza - Distribuição por categoria
        st.subheader("Distribuição por Categoria")
        category_data = pd.DataFrame({
            'Categoria': ['Marketing', 'Vendas', 'TI', 'RH', 'Financeiro'],
            'Valor': [35000, 45000, 15000, 12000, 18000]
        })
        
        fig_pie = px.pie(
            category_data,
            values='Valor',
            names='Categoria',
            title='Distribuição de Orçamento'
        )
        fig_pie.update_layout(height=400)
        st.plotly_chart(fig_pie, use_container_width=True)
    
    # Gráfico de barras
    st.subheader("Desempenho por Região")
    region_data = pd.DataFrame({
        'Região': ['Norte', 'Nordeste', 'Centro-Oeste', 'Sudeste', 'Sul'],
        'Vendas': [28000, 32000, 19000, 35000, 31000],
        'Meta': [25000, 30000, 18000, 32000, 29000]
    })
    
    fig_bar = go.Figure()
    fig_bar.add_trace(go.Bar(
        name='Vendas Reais',
        x=region_data['Região'],
        y=region_data['Vendas'],
        marker_color='#1f77b4'
    ))
    fig_bar.add_trace(go.Bar(
        name='Meta',
        x=region_data['Região'],
        y=region_data['Meta'],
        marker_color='#ff7f0e'
    ))
    fig_bar.update_layout(
        title='Vendas vs Meta por Região',
        barmode='group',
        height=400
    )
    st.plotly_chart(fig_bar, use_container_width=True)

with tab2:
    st.header("Análises Detalhadas")
    
    # Análise de tendências
    st.subheader("Análise de Tendências")
    
    # Dados de exemplo para análise
    trend_data = pd.DataFrame({
        'Data': pd.date_range('2024-01-01', periods=180, freq='D'),
        'Valor': np.random.randn(180).cumsum() + 100
    })
    
    fig_trend = px.line(
        trend_data,
        x='Data',
        y='Valor',
        title='Tendência Temporal - 6 Meses'
    )
    st.plotly_chart(fig_trend, use_container_width=True)
    
    # Análise comparativa
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Comparativo Trimestral")
        quarterly_data = pd.DataFrame({
            'Trimestre': ['Q1', 'Q2', 'Q3', 'Q4'],
            '2023': [85000, 92000, 88000, 95000],
            '2024': [105000, 112000, 118000, 125000]
        })
        
        fig_quarter = px.bar(
            quarterly_data,
            x='Trimestre',
            y=['2023', '2024'],
            title='Comparativo Anual',
            barmode='group'
        )
        st.plotly_chart(fig_quarter, use_container_width=True)
    
    with col2:
        st.subheader("Indicadores de Performance")
        kpi_data = pd.DataFrame({
            'KPI': ['ROI', 'CAC', 'LTV', 'Churn Rate'],
            'Valor': [3.2, 150, 450, 2.1],
            'Meta': [2.8, 180, 400, 2.5]
        })
        
        fig_kpi = px.scatter(
            kpi_data,
            x='KPI',
            y='Valor',
            size='Valor',
            color='KPI',
            title='Indicadores Chave'
        )
        st.plotly_chart(fig_kpi, use_container_width=True)

with tab3:
    st.header("Gerenciamento de Dados")
    
    # Upload e visualização de dados
    if uploaded_file is not None:
        try:
            if uploaded_file.type == "text/csv":
                df = pd.read_csv(uploaded_file)
            elif uploaded_file.type in ["application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", 
                                      "application/vnd.ms-excel"]:
                df = pd.read_excel(uploaded_file)
            else:
                df = pd.read_csv(uploaded_file, delimiter='\t')
            
            st.success(f"Arquivo carregado com sucesso! Shape: {df.shape}")
            
            # Visualização dos dados
            st.subheader("Visualização dos Dados")
            st.dataframe(df.head(10), use_container_width=True)
            
            # Estatísticas descritivas
            st.subheader("Estatísticas Descritivas")
            st.dataframe(df.describe(), use_container_width=True)
            
            # Download dos dados processados
            csv = df.to_csv(index=False)
            b64 = base64.b64encode(csv.encode()).decode()
            href = f'<a href="data:file/csv;base64,{b64}" download="dados_processados.csv">📥 Download CSV Processado</a>'
            st.markdown(href, unsafe_allow_html=True)
            
        except Exception as e:
            st.error(f"Erro ao processar arquivo: {str(e)}")
    else:
        st.info("📁 Faça upload de um arquivo CSV ou Excel para começar a análise")
        
        # Dados de exemplo
        st.subheader("Dados de Exemplo")
        sample_data = pd.DataFrame({
            'ID': range(1, 11),
            'Produto': [f'Produto {i}' for i in range(1, 11)],
            'Categoria': ['A', 'B', 'A', 'C', 'B', 'A', 'C', 'B', 'A', 'C'],
            'Preço': [100, 150, 200, 120, 180, 90, 220, 130, 170, 140],
            'Vendas': [45, 32, 28, 51, 39, 47, 23, 41, 36, 44]
        })
        st.dataframe(sample_data, use_container_width=True)

with tab4:
    st.header("Sobre o Clara Ready")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.markdown("""
        ### 📊 Sobre esta Aplicação
        
        **Clara Ready** é uma plataforma de analytics desenvolvida para fornecer 
        insights valiosos sobre o desempenho do seu negócio.
        
        ### 🚀 Funcionalidades
        
        - **Dashboard Interativo**: Visualizações em tempo real
        - **Análises Avançadas**: Tendências e comparativos
        - **Gerenciamento de Dados**: Upload e processamento de arquivos
        - **Relatórios Personalizáveis**: Filtros e configurações flexíveis
        
        ### 🛠 Tecnologias Utilizadas
        
        - **Streamlit**: Framework para aplicações web em Python
        - **Plotly**: Visualizações interativas
        - **Pandas**: Processamento de dados
        - **Lottie**: Animações e ilustrações
        """)
    
    with col2:
        # Animação Lottie
        lottie_animation = load_lottie_url("https://assets5.lottiefiles.com/packages/lf20_vybwn7df.json")
        if lottie_animation:
            st_lottie(lottie_animation, height=300, key="about")
        else:
            st.info("🎨 Ilustração interativa")

# Footer
st.markdown("---")
st.markdown(
    "<div style='text-align: center; color: #666;'>"
    "Desenvolvido com ❤️ usando Streamlit • Clara Ready Analytics v1.0"
    "</div>",
    unsafe_allow_html=True
)

# Import necessário no final para evitar conflitos
import numpy as np

