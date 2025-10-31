import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import requests
from datetime import datetime, timedelta
import json
from io import BytesIO
import base64

# ==================================================
# CONFIGURAÇÃO DA PÁGINA E IDENTIDADE VISUAL DA CLARA
# ==================================================

st.set_page_config(
    page_title="Clara Ready - Plataforma de Gestão Financeira",
    page_icon="💜",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS personalizado com identidade da Clara
st.markdown("""
<style>
    .main-header {
        font-size: 3rem;
        color: #8A2BE2;
        text-align: center;
        margin-bottom: 1rem;
        font-weight: bold;
    }
    .clara-subtitle {
        font-size: 1.5rem;
        color: #6A0DAD;
        text-align: center;
        margin-bottom: 2rem;
    }
    .clara-card {
        background: linear-gradient(135deg, #8A2BE2, #6A0DAD);
        color: white;
        padding: 1.5rem;
        border-radius: 15px;
        margin: 1rem 0;
    }
    .metric-card {
        background-color: #f8f9fa;
        padding: 1.5rem;
        border-radius: 10px;
        border-left: 5px solid #8A2BE2;
        margin: 0.5rem 0;
    }
    .sidebar .sidebar-content {
        background-color: #f0f2f6;
    }
    .clara-purple {
        color: #8A2BE2;
    }
    .feature-icon {
        font-size: 2rem;
        margin-bottom: 1rem;
    }
</style>
""", unsafe_allow_html=True)

# ==================================================
# CABEÇALHO E APRESENTAÇÃO DA CLARA
# ==================================================

col1, col2, col3 = st.columns([1, 2, 1])
with col2:
    st.markdown('<h1 class="main-header">💜 Clara Ready</h1>', unsafe_allow_html=True)
    st.markdown('<p class="clara-subtitle">Sua Plataforma Inteligente de Gestão Financeira</p>', unsafe_allow_html=True)

# O que é a Clara Ready
with st.expander("🔍 **O que é a Clara Ready?**", expanded=True):
    st.markdown("""
    **Clara Ready** é uma plataforma completa de gestão financeira desenvolvida para:
    
    💰 **Controlar suas finanças** de forma simples e intuitiva  
    📈 **Analisar desempenho** com dashboards em tempo real  
    🔮 **Projetar cenários** com simulações precisas  
    📊 **Tomar decisões estratégicas** baseadas em dados  
    🎯 **Otimizar resultados** com insights inteligentes
    
    *"Clara como suas finanças devem estar"* 💜
    """)

# ==================================================
# FUNÇÕES PRINCIPAIS DO SISTEMA
# ==================================================

@st.cache_data
def carregar_dados_exemplo():
    """Carrega dados de exemplo para demonstração"""
    np.random.seed(42)
    
    # Dados de receita mensal
    meses = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dec']
    receita = np.random.normal(100000, 20000, 12).cumsum() + 500000
    
    # Dados de categorias
    categorias = ['Produtos Digitais', 'Consultoria', 'Assinaturas', 'Serviços', 'Suporte']
    valores_categorias = np.random.randint(20000, 100000, 5)
    
    # Dados de desempenho temporal
    datas = pd.date_range('2024-01-01', periods=180, freq='D')
    tendencia = np.random.randn(180).cumsum() + 100
    
    return {
        'meses': meses,
        'receita': receita,
        'categorias': categorias,
        'valores_categorias': valores_categorias,
        'datas': datas,
        'tendencia': tendencia
    }

def calcular_metricas_financeiras(receita_bruta, custos_diretos, despesas_operacionais):
    """Calcula métricas financeiras básicas"""
    lucro_bruto = receita_bruta - custos_diretos
    lucro_liquido = lucro_bruto - despesas_operacionais
    margem_bruta = (lucro_bruto / receita_bruta) * 100 if receita_bruta > 0 else 0
    margem_liquida = (lucro_liquido / receita_bruta) * 100 if receita_bruta > 0 else 0
    
    return {
        'lucro_bruto': lucro_bruto,
        'lucro_liquido': lucro_liquido,
        'margem_bruta': margem_bruta,
        'margem_liquida': margem_liquida
    }

def simular_investimento(capital_inicial, aporte_mensal, tempo_anos, taxa_anual):
    """Simula investimento em renda fixa"""
    meses = tempo_anos * 12
    taxa_mensal = (1 + taxa_anual/100) ** (1/12) - 1
    
    montante = capital_inicial * (1 + taxa_mensal) ** meses
    for i in range(meses):
        montante += aporte_mensal * (1 + taxa_mensal) ** (meses - i - 1)
    
    total_investido = capital_inicial + (aporte_mensal * meses)
    juros_obtidos = montante - total_investido
    
    return {
        'montante': montante,
        'total_investido': total_investido,
        'juros_obtidos': juros_obtidos,
        'rentabilidade': (juros_obtidos / total_investido) * 100
    }

# ==================================================
# SIDEBAR - NAVEGAÇÃO
# ==================================================

with st.sidebar:
    st.image("https://via.placeholder.com/150x50/8A2BE2/FFFFFF?text=CLARA+READY", width=150)
    st.markdown("---")
    
    st.markdown("### 📊 Navegação")
    pagina = st.radio(
        "Selecione a página:",
        [
            "🏠 Dashboard Principal",
            "💰 Análise de Rentabilidade", 
            "📈 Projeções Financeiras",
            "💼 Simulações de Investimento",
            "📋 Relatórios Personalizados",
            "⚙️ Configurações"
        ]
    )
    
    st.markdown("---")
    st.markdown("### 🎯 Métricas Rápidas")
    st.metric("Saldo Disponível", "R$ 125.430")
    st.metric("Receita do Mês", "R$ 85.240")
    st.metric("Despesas", "R$ 42.180")
    
    st.markdown("---")
    st.info("💡 **Dica Clara:** Monitore seu fluxo de caixa diariamente!")

# ==================================================
# PÁGINA: DASHBOARD PRINCIPAL
# ==================================================

if pagina == "🏠 Dashboard Principal":
    st.header("🏠 Dashboard Principal - Visão Clara")
    
    # Carregar dados
    dados = carregar_dados_exemplo()
    
    # Métricas principais em tempo real
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown('<div class="metric-card">', unsafe_allow_html=True)
        st.metric(
            label="💳 Receita Total",
            value="R$ 1.254.300",
            delta="12.5%",
            delta_color="normal"
        )
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col2:
        st.markdown('<div class="metric-card">', unsafe_allow_html=True)
        st.metric(
            label="📈 Lucro Líquido", 
            value="R$ 352.180",
            delta="8.3%",
            delta_color="normal"
        )
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col3:
        st.markdown('<div class="metric-card">', unsafe_allow_html=True)
        st.metric(
            label="🎯 ROI",
            value="28.7%",
            delta="3.2%",
            delta_color="normal"
        )
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col4:
        st.markdown('<div class="metric-card">', unsafe_allow_html=True)
        st.metric(
            label="👥 Clientes Ativos",
            value="154",
            delta="5.2%",
            delta_color="normal"
        )
        st.markdown('</div>', unsafe_allow_html=True)
    
    # Gráficos principais
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📈 Evolução da Receita Mensal")
        
        revenue_data = pd.DataFrame({
            'Mês': dados['meses'],
            'Receita': dados['receita']
        })
        
        fig_line = px.line(
            revenue_data,
            x='Mês',
            y='Receita',
            title='',
            markers=True,
            line_shape='spline'
        )
        fig_line.update_layout(
            height=400,
            showlegend=False,
            plot_bgcolor='rgba(0,0,0,0)',
            yaxis_title="Receita (R$)"
        )
        fig_line.update_traces(line=dict(color='#8A2BE2', width=3))
        st.plotly_chart(fig_line, use_container_width=True)
    
    with col2:
        st.subheader("🍰 Distribuição por Categoria")
        
        category_data = pd.DataFrame({
            'Categoria': dados['categorias'],
            'Valor': dados['valores_categorias']
        })
        
        fig_pie = px.pie(
            category_data,
            values='Valor',
            names='Categoria',
            title='',
            color_discrete_sequence=px.colors.sequential.Viridis
        )
        fig_pie.update_layout(height=400)
        st.plotly_chart(fig_pie, use_container_width=True)
    
    # Tabela de desempenho detalhada
    st.subheader("📊 Desempenho por Segmento")
    
    performance_data = pd.DataFrame({
        'Segmento': ['Varejo Digital', 'Corporate', 'E-commerce', 'Serviços Premium', 'Consultoria'],
        'Receita (R$)': [285000, 335000, 230000, 215000, 189300],
        'Crescimento (%)': [15.2, 8.7, 25.4, 12.1, 18.3],
        'Meta Atingida (%)': [95, 88, 110, 92, 105],
        'Lucratividade (%)': [22.5, 18.3, 28.7, 32.1, 35.4]
    })
    
    st.dataframe(
        performance_data.style.format({
            'Receita (R$)': 'R$ {:,.0f}',
            'Crescimento (%)': '{:.1f}%',
            'Meta Atingida (%)': '{:.0f}%',
            'Lucratividade (%)': '{:.1f}%'
        }),
        use_container_width=True
    )
    
    # Alertas e insights
    st.subheader("🔔 Insights da Clara")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown('<div class="clara-card">', unsafe_allow_html=True)
        st.markdown("### 💡")
        st.markdown("**Oportunidade:** Seu segmento de Consultoria tem a maior lucratividade (35.4%)")
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col2:
        st.markdown('<div class="clara-card">', unsafe_allow_html=True)
        st.markdown("### ⚠️")
        st.markdown("**Atenção:** Segmento Corporate está abaixo da meta (88%)")
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col3:
        st.markdown('<div class="clara-card">', unsafe_allow_html=True)
        st.markdown("### 🎯")
        st.markdown("**Meta:** E-commerce superou expectativas (110% da meta)")
        st.markdown('</div>', unsafe_allow_html=True)

# ==================================================
# PÁGINA: ANÁLISE DE RENTABILIDADE
# ==================================================

elif pagina == "💰 Análise de Rentabilidade":
    st.header("💰 Análise de Rentabilidade Detalhada")
    
    tab1, tab2, tab3 = st.tabs(["📊 Métricas Principais", "📈 Análise de Margens", "🎯 Ponto de Equilíbrio"])
    
    with tab1:
        st.subheader("Indicadores de Rentabilidade")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### 💰 Entradas")
            receita_bruta = st.number_input("Receita Bruta (R$):", value=1250000, step=50000, key="rb1")
            custos_diretos = st.number_input("Custos Diretos (R$):", value=650000, step=50000, key="cd1")
            despesas_operacionais = st.number_input("Despesas Operacionais (R$):", value=250000, step=10000, key="do1")
            
            # Cálculos
            metricas = calcular_metricas_financeiras(receita_bruta, custos_diretos, despesas_operacionais)
        
        with col2:
            st.markdown("### 📈 Resultados")
            
            st.markdown('<div class="metric-card">', unsafe_allow_html=True)
            st.metric("💸 Lucro Bruto", f"R$ {metricas['lucro_bruto']:,.0f}")
            st.markdown('</div>', unsafe_allow_html=True)
            
            st.markdown('<div class="metric-card">', unsafe_allow_html=True)
            st.metric("💰 Lucro Líquido", f"R$ {metricas['lucro_liquido']:,.0f}")
            st.markdown('</div>', unsafe_allow_html=True)
            
            st.markdown('<div class="metric-card">', unsafe_allow_html=True)
            st.metric("📊 Margem Bruta", f"{metricas['margem_bruta']:.1f}%")
            st.markdown('</div>', unsafe_allow_html=True)
            
            st.markdown('<div class="metric-card">', unsafe_allow_html=True)
            st.metric("🎯 Margem Líquida", f"{metricas['margem_liquida']:.1f}%")
            st.markdown('</div>', unsafe_allow_html=True)
    
    with tab2:
        st.subheader("📈 Análise de Margens por Segmento")
        
        # Dados para análise de margens
        segmentos = ['Varejo Digital', 'Corporate', 'E-commerce', 'Serviços Premium', 'Consultoria']
        margens_brutas = [25.3, 22.1, 30.5, 35.2, 42.8]
        margens_liquidas = [18.5, 15.3, 25.7, 28.1, 35.4]
        
        fig_margens = go.Figure()
        
        fig_margens.add_trace(go.Bar(
            name='Margem Bruta',
            x=segmentos,
            y=margens_brutas,
            marker_color='#8A2BE2'
        ))
        
        fig_margens.add_trace(go.Bar(
            name='Margem Líquida',
            x=segmentos,
            y=margens_liquidas,
            marker_color='#6A0DAD'
        ))
        
        fig_margens.update_layout(
            title="Comparativo de Margens por Segmento",
            barmode='group',
            height=500,
            showlegend=True
        )
        
        st.plotly_chart(fig_margens, use_container_width=True)
        
        # Análise comparativa
        st.subheader("📋 Análise Comparativa")
        analise_data = pd.DataFrame({
            'Segmento': segmentos,
            'Margem Bruta (%)': margens_brutas,
            'Margem Líquida (%)': margens_liquidas,
            'Eficiência (%)': [margens_liquidas[i]/margens_brutas[i]*100 for i in range(len(segmentos))]
        })
        
        st.dataframe(analise_data.style.format({
            'Margem Bruta (%)': '{:.1f}%',
            'Margem Líquida (%)': '{:.1f}%',
            'Eficiência (%)': '{:.1f}%'
        }), use_container_width=True)
    
    with tab3:
        st.subheader("🎯 Análise de Ponto de Equilíbrio")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### 📊 Dados de Entrada")
            custos_fixos = st.number_input("Custos Fixos Mensais (R$):", value=185000, step=10000, key="cf1")
            preco_medio = st.number_input("Preço Médio por Unidade (R$):", value=150, step=10, key="pm1")
            custo_variavel_unitario = st.number_input("Custo Variável Unitário (R$):", value=65, step=5, key="cvu1")
            unidades_vendidas = st.number_input("Unidades Vendidas (Mês):", value=2500, step=100, key="uv1")
        
        with col2:
            st.markdown("### 📈 Resultados")
            
            margem_contribuicao = preco_medio - custo_variavel_unitario
            ponto_equilibrio = custos_fixos / margem_contribuicao if margem_contribuicao > 0 else 0
            margem_seguranca = ((unidades_vendidas - ponto_equilibrio) / unidades_vendidas) * 100 if unidades_vendidas > 0 else 0
            
            st.markdown('<div class="metric-card">', unsafe_allow_html=True)
            st.metric("💰 Margem de Contribuição", f"R$ {margem_contribuicao:.2f}")
            st.markdown('</div>', unsafe_allow_html=True)
            
            st.markdown('<div class="metric-card">', unsafe_allow_html=True)
            st.metric("🎯 Ponto de Equilíbrio", f"{ponto_equilibrio:.0f} unidades")
            st.markdown('</div>', unsafe_allow_html=True)
            
            st.markdown('<div class="metric-card">', unsafe_allow_html=True)
            st.metric("🛡️ Margem de Segurança", f"{margem_seguranca:.1f}%")
            st.markdown('</div>', unsafe_allow_html=True)
            
            # Análise de viabilidade
            if margem_seguranca > 20:
                st.success("✅ **Excelente!** Margem de segurança acima de 20%")
            elif margem_seguranca > 10:
                st.warning("⚠️ **Atenção!** Margem de segurança entre 10-20%")
            else:
                st.error("❌ **Crítico!** Margem de segurança abaixo de 10%")

# ==================================================
# PÁGINA: PROJEÇÕES FINANCEIRAS
# ==================================================

elif pagina == "📈 Projeções Financeiras":
    st.header("🔮 Projeções Financeiras - Planejamento Estratégico")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📊 Parâmetros de Projeção")
        
        receita_atual = st.number_input("Receita Atual (R$):", value=1250000, step=50000, key="ra1")
        taxa_crescimento = st.slider("Taxa de Crescimento Anual (%):", 0.0, 50.0, 15.0, 0.5, key="tc1")
        anos_projecao = st.slider("Anos de Projeção:", 1, 10, 5, key="ap1")
    
    with col2:
        st.subheader("🎯 Otimização de Margens")
        
        margem_atual = st.number_input("Margem Líquida Atual (%):", value=12.5, step=0.5, key="ma1")
        melhoria_margem = st.slider("Melhoria Anual da Margem (%):", 0.0, 5.0, 1.2, 0.1, key="mm1")
        inflacao_esperada = st.slider("Inflação Esperada (% ao ano):", 0.0, 15.0, 4.5, 0.1, key="ie1")
    
    # Calcular projeções
    anos = list(range(1, anos_projecao + 1))
    receitas = []
    lucros = []
    receitas_reais = []
    
    receita_projetada = receita_atual
    margem_projetada = margem_atual
    
    for ano in anos:
        receita_nominal = receita_projetada
        lucro_nominal = receita_nominal * (margem_projetada / 100)
        
        # Ajuste pela inflação
        receita_real = receita_nominal / ((1 + inflacao_esperada/100) ** (ano-1))
        
        receitas.append(receita_nominal)
        lucros.append(lucro_nominal)
        receitas_reais.append(receita_real)
        
        receita_projetada *= (1 + taxa_crescimento / 100)
        margem_projetada += melhoria_margem
    
    # Criar DataFrame para projeções
    proj_data = pd.DataFrame({
        'Ano': anos,
        'Receita_Nominal': receitas,
        'Receita_Real': receitas_reais,
        'Lucro_Projetado': lucros,
        'Margem_Projetada': [margem_atual + (melhoria_margem * i) for i in range(anos_projecao)]
    })
    
    # Gráfico de projeção
    st.subheader("📈 Projeção de Receita e Lucro")
    
    fig_proj = go.Figure()
    
    fig_proj.add_trace(go.Scatter(
        x=proj_data['Ano'], 
        y=proj_data['Receita_Nominal'],
        mode='lines+markers',
        name='Receita Nominal',
        line=dict(color='#8A2BE2', width=3)
    ))
    
    fig_proj.add_trace(go.Scatter(
        x=proj_data['Ano'], 
        y=proj_data['Receita_Real'],
        mode='lines+markers',
        name='Receita Real (ajustada)',
        line=dict(color='#6A0DAD', width=3, dash='dash')
    ))
    
    fig_proj.add_trace(go.Scatter(
        x=proj_data['Ano'], 
        y=proj_data['Lucro_Projetado'],
        mode='lines+markers',
        name='Lucro Projetado',
        line=dict(color='#00CC96', width=3)
    ))
    
    fig_proj.update_layout(
        title='Projeção Financeira - Próximos Anos',
        xaxis_title='Ano',
        yaxis_title='Valor (R$)',
        height=500,
        showlegend=True
    )
    
    st.plotly_chart(fig_proj, use_container_width=True)
    
    # Tabela de projeções detalhada
    st.subheader("📋 Tabela de Projeções Detalhada")
    
    proj_data_display = proj_data.copy()
    proj_data_display['Receita_Nominal'] = proj_data_display['Receita_Nominal'].apply(lambda x: f"R$ {x:,.0f}")
    proj_data_display['Receita_Real'] = proj_data_display['Receita_Real'].apply(lambda x: f"R$ {x:,.0f}")
    proj_data_display['Lucro_Projetado'] = proj_data_display['Lucro_Projetado'].apply(lambda x: f"R$ {x:,.0f}")
    proj_data_display['Margem_Projetada'] = proj_data_display['Margem_Projetada'].apply(lambda x: f"{x:.1f}%")
    
    st.dataframe(proj_data_display, use_container_width=True)
    
    # Análise de cenários
    st.subheader("🔄 Análise de Cenários")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("### 📈 Cenário Otimista")
        st.metric("Receita 5 anos", "R$ 2.8M", "124%")
        st.metric("Lucro Acumulado", "R$ 450K", "28% margem")
    
    with col2:
        st.markdown("### 📊 Cenário Realista")
        st.metric("Receita 5 anos", "R$ 2.1M", "68%")
        st.metric("Lucro Acumulado", "R$ 320K", "22% margem")
    
    with col3:
        st.markdown("### 📉 Cenário Conservador")
        st.metric("Receita 5 anos", "R$ 1.6M", "28%")
        st.metric("Lucro Acumulado", "R$ 240K", "18% margem")

# ==================================================
# PÁGINA: SIMULAÇÕES DE INVESTIMENTO
# ==================================================

elif pagina == "💼 Simulações de Investimento":
    st.header("💼 Simulações de Investimento - Clara Invest")
    
    tab1, tab2, tab3, tab4 = st.tabs(["💰 Renda Fixa", "📈 Ações", "🏠 Fundos Imobiliários", "🔗 Carteira Recomendada"])
    
    with tab1:
        st.subheader("💰 Renda Fixa - CDB/Tesouro Direto")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### 📊 Parâmetros do Investimento")
            capital_inicial = st.number_input("Capital Inicial (R$):", value=25000, step=1000, key="ci1")
            aporte_mensal = st.number_input("Aporte Mensal (R$):", value=2000, step=100, key="am1")
            tempo_anos = st.slider("Tempo de Investimento (anos):", 1, 30, 10, key="ti1")
            taxa_anual = st.slider("Taxa Anual (% a.a.):", 0.1, 20.0, 11.5, 0.1, key="ta1")
        
        with col2:
            st.markdown("### 📈 Resultados da Simulação")
            
            resultado = simular_investimento(capital_inicial, aporte_mensal, tempo_anos, taxa_anual)
            
            st.markdown('<div class="clara-card">', unsafe_allow_html=True)
            st.metric("🏦 Montante Final", f"R$ {resultado['montante']:,.2f}")
            st.markdown('</div>', unsafe_allow_html=True)
            
            st.markdown('<div class="metric-card">', unsafe_allow_html=True)
            st.metric("💵 Total Investido", f"R$ {resultado['total_investido']:,.0f}")
            st.markdown('</div>', unsafe_allow_html=True)
            
            st.markdown('<div class="metric-card">', unsafe_allow_html=True)
            st.metric("🎯 Juros Obtidos", f"R$ {resultado['juros_obtidos']:,.2f}")
            st.markdown('</div>', unsafe_allow_html=True)
            
            st.markdown('<div class="metric-card">', unsafe_allow_html=True)
            st.metric("📊 Rentabilidade Total", f"{resultado['rentabilidade']:.1f}%")
            st.markdown('</div>', unsafe_allow_html=True)
        
        # Gráfico de evolução
        st.subheader("📊 Evolução do Patrimônio")
        
        # Simular evolução ano a ano
        anos_evolucao = list(range(1, tempo_anos + 1))
        patrimonio = []
        
        for ano in anos_evolucao:
            sim_ano = simular_investimento(capital_inicial, aporte_mensal, ano, taxa_anual)
            patrimonio.append(sim_ano['montante'])
        
        fig_evolucao = px.line(
            x=anos_evolucao,
            y=patrimonio,
            title=f"Evolução do Patrimônio - {tempo_anos} anos",
            labels={'x': 'Ano', 'y': 'Patrimônio (R$)'}
        )
        fig_evolucao.update_traces(line=dict(color='#8A2BE2', width=3))
        fig_evolucao.update_layout(height=400)
        
        st.plotly_chart(fig_evolucao, use_container_width=True)
    
    with tab2:
        st.subheader("📈 Renda Variável - Ações")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### 💹 Parâmetros do Investimento")
            preco_acao = st.number_input("Preço por Ação (R$):", value=85.50, step=1.0, key="pa1")
            qtd_acoes = st.number_input("Quantidade de Ações:", value=500, step=10, key="qa1")
            dividend_yield = st.slider("Dividend Yield Anual (%):", 0.1, 15.0, 6.5, 0.1, key="dy1")
            valorizacao_anual = st.slider("Valorização Anual Esperada (%):", -5.0, 30.0, 14.2, 0.5, key="va1")
            tempo_investimento = st.slider("Tempo de Investimento (anos):", 1, 30, 8, key="ti2")
        
        with col2:
            st.markdown("### 💰 Resultados da Simulação")
            
            # Cálculos
            investimento_inicial = preco_acao * qtd_acoes
            valor_final_acoes = investimento_inicial * (1 + valorizacao_anual/100) ** tempo_investimento
            dividendos_anuais = investimento_inicial * (dividend_yield/100)
            
            # Calcular dividendos compostos
            total_dividendos = 0
            for ano in range(1, tempo_investimento + 1):
                dividendos_ano = dividendos_anuais * (1 + valorizacao_anual/100) ** (ano - 1)
                total_dividendos += dividendos_ano
            
            retorno_total = valor_final_acoes + total_dividendos
            lucro_total = retorno_total - investimento_inicial
            rentabilidade_total = (lucro_total / investimento_inicial) * 100
            
            st.markdown('<div class="clara-card">', unsafe_allow_html=True)
            st.metric("💎 Valor Final das Ações", f"R$ {valor_final_acoes:,.2f}")
            st.markdown('</div>', unsafe_allow_html=True)
            
            st.markdown('<div class="metric-card">', unsafe_allow_html=True)
            st.metric("💰 Total em Dividendos", f"R$ {total_dividendos:,.2f}")
            st.markdown('</div>', unsafe_allow_html=True)
            
            st.markdown('<div class="metric-card">', unsafe_allow_html=True)
            st.metric("🎯 Retorno Total", f"R$ {retorno_total:,.2f}")
            st.markdown('</div>', unsafe_allow_html=True)
            
            st.markdown('<div class="metric-card">', unsafe_allow_html=True)
            st.metric("📈 Rentabilidade Total", f"{rentabilidade_total:.1f}%")
            st.markdown('</div>', unsafe_allow_html=True)
    
    with tab3:
        st.subheader("🏠 Fundos Imobiliários - FIIs")
        
        st.info("""
        **💡 Sobre Fundos Imobiliários:**
        - Rendimentos mensais via dividendos
        - Diversificação em diferentes tipos de imóveis
        - Liquidez diária na bolsa
        - Isenção de IR para pessoas físicas (até R$ 20k/mês)
        """)
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### 🏢 Parâmetros do Investimento")
            valor_cota = st.number_input("Valor da Cota (R$):", value=98.75, step=1.0, key="vc1")
            cotas_adquiridas = st.number_input("Quantidade de Cotas:", value=300, step=10, key="qc1")
            dy_mensal = st.slider("Dividend Yield Mensal (%):", 0.1, 2.0, 0.65, 0.05, key="dym1")
            valorizacao_anual_fii = st.slider("Valorização Anual da Cota (%):", -5.0, 20.0, 8.5, 0.5, key="vaf1")
            tempo_investimento_fii = st.slider("Tempo de Investimento (anos):", 1, 30, 7, key="tif1")
        
        with col2:
            st.markdown("### 💰 Projeção de Resultados")
            
            # Cálculos FII
            investimento_inicial_fii = valor_cota * cotas_adquiridas
            valor_final_cotas = investimento_inicial_fii * (1 + valorizacao_anual_fii/100) ** tempo_investimento_fii
            
            # Dividendos mensais
            dividendos_mensais = investimento_inicial_fii * (dy_mensal/100)
            total_meses = tempo_investimento_fii * 12
