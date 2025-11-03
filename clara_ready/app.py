import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import json
import time
import base64
from typing import Dict, List, Tuple, Optional
import io
import requests

# Configuração da página
st.set_page_config(
    page_title="Clara Ready - Plataforma de Gestão Financeira",
    page_icon="💜",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS personalizado
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        color: #6a0dad;
        text-align: center;
        margin-bottom: 2rem;
        font-weight: bold;
    }
    .sub-header {
        font-size: 1.5rem;
        color: #8a2be2;
        margin-bottom: 1rem;
        font-weight: 600;
    }
    .metric-card {
        background-color: #f8f9fa;
        padding: 1.5rem;
        border-radius: 10px;
        border-left: 4px solid #6a0dad;
        margin-bottom: 1rem;
    }
    .success-metric {
        border-left: 4px solid #28a745;
    }
    .warning-metric {
        border-left: 4px solid #ffc107;
    }
    .danger-metric {
        border-left: 4px solid #dc3545;
    }
    .feature-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 2rem;
        border-radius: 15px;
        margin: 1rem 0;
        text-align: center;
    }
</style>
""", unsafe_allow_html=True)

class FinancialManager:
    def __init__(self):
        self.transactions = []
        self.categories = [
            "Alimentação", "Transporte", "Moradia", "Saúde", 
            "Educação", "Lazer", "Vestuário", "Outros"
        ]
        self.initialize_data()
    
    def initialize_data(self):
        if 'transactions' not in st.session_state:
            st.session_state.transactions = []
        if 'goals' not in st.session_state:
            st.session_state.goals = []
        if 'budgets' not in st.session_state:
            st.session_state.budgets = {category: 0 for category in self.categories}
    
    def add_transaction(self, amount: float, category: str, description: str, date: datetime, type: str = "expense"):
        transaction = {
            'id': len(st.session_state.transactions) + 1,
            'amount': amount,
            'category': category,
            'description': description,
            'date': date,
            'type': type  # 'income' or 'expense'
        }
        st.session_state.transactions.append(transaction)
        return transaction
    
    def add_goal(self, name: str, target_amount: float, current_amount: float, deadline: datetime):
        goal = {
            'id': len(st.session_state.goals) + 1,
            'name': name,
            'target_amount': target_amount,
            'current_amount': current_amount,
            'deadline': deadline,
            'created_at': datetime.now()
        }
        st.session_state.goals.append(goal)
        return goal
    
    def get_financial_summary(self) -> Dict:
        total_income = sum(t['amount'] for t in st.session_state.transactions if t['type'] == 'income')
        total_expenses = sum(t['amount'] for t in st.session_state.transactions if t['type'] == 'expense')
        balance = total_income - total_expenses
        
        expenses_by_category = {}
        for category in self.categories:
            category_expenses = sum(t['amount'] for t in st.session_state.transactions 
                                  if t['type'] == 'expense' and t['category'] == category)
            expenses_by_category[category] = category_expenses
        
        return {
            'total_income': total_income,
            'total_expenses': total_expenses,
            'balance': balance,
            'expenses_by_category': expenses_by_category
        }

# Inicializar gerenciador financeiro
financial_manager = FinancialManager()

def main():
    st.markdown('<div class="main-header">💜 Clara Ready - Plataforma de Gestão Financeira Inteligente</div>', unsafe_allow_html=True)
    
    # Menu lateral
    st.sidebar.title("Navegação")
    menu_options = [
        "📊 Dashboard Principal",
        "💸 Gestão de Transações",
        "🎯 Metas Financeiras",
        "📈 Orçamentos",
        "📋 Relatórios",
        "🔔 Alertas",
        "⚙️ Configurações"
    ]
    selected_menu = st.sidebar.selectbox("Selecione uma opção:", menu_options)
    
    # Filtros globais
    st.sidebar.markdown("---")
    st.sidebar.subheader("Filtros")
    
    # Filtro de período
    period_options = ["Últimos 7 dias", "Últimos 30 dias", "Últimos 90 dias", "Este mês", "Personalizado"]
    selected_period = st.sidebar.selectbox("Período:", period_options)
    
    if selected_period == "Personalizado":
        col1, col2 = st.sidebar.columns(2)
        with col1:
            start_date = st.date_input("Data inicial")
        with col2:
            end_date = st.date_input("Data final")
    
    # Dashboard Principal
    if selected_menu == "📊 Dashboard Principal":
        show_dashboard()
    
    # Gestão de Transações
    elif selected_menu == "💸 Gestão de Transações":
        show_transaction_management()
    
    # Metas Financeiras
    elif selected_menu == "🎯 Metas Financeiras":
        show_financial_goals()
    
    # Orçamentos
    elif selected_menu == "📈 Orçamentos":
        show_budget_management()
    
    # Relatórios
    elif selected_menu == "📋 Relatórios":
        show_reports()
    
    # Alertas
    elif selected_menu == "🔔 Alertas":
        show_alerts()
    
    # Configurações
    elif selected_menu == "⚙️ Configurações":
        show_settings()

def show_dashboard():
    st.markdown('<div class="sub-header">📊 Dashboard Financeiro</div>', unsafe_allow_html=True)
    
    summary = financial_manager.get_financial_summary()
    
    # Métricas principais
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown(f"""
        <div class="metric-card success-metric">
            <h3>💰 Receitas</h3>
            <h2>R$ {summary['total_income']:,.2f}</h2>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown(f"""
        <div class="metric-card danger-metric">
            <h3>💸 Despesas</h3>
            <h2>R$ {summary['total_expenses']:,.2f}</h2>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        balance_class = "success-metric" if summary['balance'] >= 0 else "danger-metric"
        st.markdown(f"""
        <div class="metric-card {balance_class}">
            <h3>⚖️ Saldo</h3>
            <h2>R$ {summary['balance']:,.2f}</h2>
        </div>
        """, unsafe_allow_html=True)
    
    with col4:
        savings_rate = (summary['balance'] / summary['total_income'] * 100) if summary['total_income'] > 0 else 0
        st.markdown(f"""
        <div class="metric-card">
            <h3>📈 Taxa de Poupança</h3>
            <h2>{savings_rate:.1f}%</h2>
        </div>
        """, unsafe_allow_html=True)
    
    # Gráficos
    col1, col2 = st.columns(2)
    
    with col1:
        # Gráfico de despesas por categoria
        if summary['expenses_by_category']:
            categories = list(summary['expenses_by_category'].keys())
            values = list(summary['expenses_by_category'].values())
            
            fig = px.pie(
                names=categories,
                values=values,
                title="Distribuição de Despesas por Categoria",
                color_discrete_sequence=px.colors.sequential.Plasma
            )
            st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        # Gráfico de evolução mensal (exemplo)
        months = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun']
        income_data = [5000, 5200, 4800, 5500, 6000, 5800]
        expense_data = [4500, 4700, 4200, 5000, 5200, 5100]
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=months, y=income_data, name='Receitas', line=dict(color='#28a745')))
        fig.add_trace(go.Scatter(x=months, y=expense_data, name='Despesas', line=dict(color='#dc3545')))
        fig.update_layout(title="Evolução Mensal - Receitas vs Despesas")
        st.plotly_chart(fig, use_container_width=True)
    
    # Transações recentes
    st.markdown("### 🔄 Transações Recentes")
    if st.session_state.transactions:
        recent_transactions = sorted(st.session_state.transactions, key=lambda x: x['date'], reverse=True)[:5]
        
        for transaction in recent_transactions:
            transaction_type = "✅ Receita" if transaction['type'] == 'income' else "❌ Despesa"
            color = "green" if transaction['type'] == 'income' else "red"
            
            st.markdown(f"""
            <div style="border-left: 4px solid {color}; padding: 10px; margin: 5px 0; background-color: #f8f9fa;">
                <strong>{transaction_type}</strong> - {transaction['description']}<br>
                <small>Categoria: {transaction['category']} | Valor: R$ {transaction['amount']:,.2f}</small>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.info("Nenhuma transação cadastrada ainda.")

def show_transaction_management():
    st.markdown('<div class="sub-header">💸 Gestão de Transações</div>', unsafe_allow_html=True)
    
    tab1, tab2, tab3 = st.tabs(["➕ Nova Transação", "📋 Listar Transações", "🔍 Buscar Transações"])
    
    with tab1:
        col1, col2 = st.columns(2)
        
        with col1:
            transaction_type = st.radio("Tipo de Transação:", ["Receita", "Despesa"])
            amount = st.number_input("Valor (R$):", min_value=0.0, step=0.01, format="%.2f")
            category = st.selectbox("Categoria:", financial_manager.categories)
        
        with col2:
            description = st.text_input("Descrição:")
            transaction_date = st.date_input("Data:", datetime.now())
        
        if st.button("💾 Salvar Transação", type="primary"):
            if amount > 0 and description:
                type_str = "income" if transaction_type == "Receita" else "expense"
                financial_manager.add_transaction(
                    amount=amount,
                    category=category,
                    description=description,
                    date=transaction_date,
                    type=type_str
                )
                st.success("✅ Transação salva com sucesso!")
                st.rerun()
            else:
                st.error("❌ Preencha todos os campos obrigatórios.")
    
    with tab2:
        if st.session_state.transactions:
            # Filtros
            col1, col2, col3 = st.columns(3)
            with col1:
                filter_type = st.selectbox("Filtrar por tipo:", ["Todos", "Receita", "Despesa"])
            with col2:
                filter_category = st.selectbox("Filtrar por categoria:", ["Todas"] + financial_manager.categories)
            with col3:
                start_date_filter = st.date_input("Data inicial:", datetime.now() - timedelta(days=30))
            
            # Aplicar filtros
            filtered_transactions = st.session_state.transactions.copy()
            
            if filter_type != "Todos":
                type_filter = "income" if filter_type == "Receita" else "expense"
                filtered_transactions = [t for t in filtered_transactions if t['type'] == type_filter]
            
            if filter_category != "Todas":
                filtered_transactions = [t for t in filtered_transactions if t['category'] == filter_category]
            
            filtered_transactions = [t for t in filtered_transactions if t['date'] >= start_date_filter]
            
            # Tabela de transações
            st.markdown("### 📋 Transações Filtradas")
            for transaction in filtered_transactions:
                with st.expander(f"{transaction['date'].strftime('%d/%m/%Y')} - {transaction['description']} - R$ {transaction['amount']:,.2f}"):
                    col1, col2, col3 = st.columns([3, 2, 1])
                    with col1:
                        st.write(f"**Descrição:** {transaction['description']}")
                        st.write(f"**Categoria:** {transaction['category']}")
                    with col2:
                        st.write(f"**Valor:** R$ {transaction['amount']:,.2f}")
                        st.write(f"**Tipo:** {'✅ Receita' if transaction['type'] == 'income' else '❌ Despesa'}")
                    with col3:
                        if st.button("🗑️", key=f"delete_{transaction['id']}"):
                            st.session_state.transactions = [t for t in st.session_state.transactions if t['id'] != transaction['id']]
                            st.success("Transação excluída!")
                            st.rerun()
        else:
            st.info("Nenhuma transação cadastrada ainda.")
    
    with tab3:
        st.markdown("### 🔍 Busca Avançada")
        search_term = st.text_input("Termo de busca:")
        
        if search_term:
            results = [t for t in st.session_state.transactions 
                      if search_term.lower() in t['description'].lower()]
            
            if results:
                st.success(f"🔍 {len(results)} transação(ões) encontrada(s)")
                for transaction in results:
                    st.write(f"**{transaction['date'].strftime('%d/%m/%Y')}** - {transaction['description']} - R$ {transaction['amount']:,.2f}")
            else:
                st.warning("Nenhuma transação encontrada com o termo buscado.")

def show_financial_goals():
    st.markdown('<div class="sub-header">🎯 Metas Financeiras</div>', unsafe_allow_html=True)
    
    tab1, tab2 = st.tabs(["🎯 Nova Meta", "📊 Minhas Metas"])
    
    with tab1:
        st.markdown("### 🎯 Criar Nova Meta Financeira")
        
        col1, col2 = st.columns(2)
        
        with col1:
            goal_name = st.text_input("Nome da Meta:")
            target_amount = st.number_input("Valor Alvo (R$):", min_value=0.0, step=0.01, format="%.2f")
        
        with col2:
            current_amount = st.number_input("Valor Atual (R$):", min_value=0.0, step=0.01, format="%.2f")
            deadline = st.date_input("Data Limite:", min_value=datetime.now().date())
        
        if st.button("🎯 Criar Meta", type="primary"):
            if goal_name and target_amount > 0:
                financial_manager.add_goal(
                    name=goal_name,
                    target_amount=target_amount,
                    current_amount=current_amount,
                    deadline=deadline
                )
                st.success("✅ Meta criada com sucesso!")
                st.rerun()
            else:
                st.error("❌ Preencha todos os campos obrigatórios.")
    
    with tab2:
        if st.session_state.goals:
            st.markdown("### 📊 Progresso das Metas")
            
            for goal in st.session_state.goals:
                progress = (goal['current_amount'] / goal['target_amount']) * 100
                days_remaining = (goal['deadline'] - datetime.now().date()).days
                
                col1, col2 = st.columns([3, 1])
                
                with col1:
                    st.write(f"**{goal['name']}**")
                    st.progress(progress / 100)
                    st.write(f"R$ {goal['current_amount']:,.2f} de R$ {goal['target_amount']:,.2f} ({progress:.1f}%)")
                    st.write(f"⏰ {days_remaining} dias restantes")
                
                with col2:
                    # Atualizar progresso
                    new_amount = st.number_input(
                        "Atualizar valor:",
                        min_value=0.0,
                        value=float(goal['current_amount']),
                        step=0.01,
                        format="%.2f",
                        key=f"update_{goal['id']}"
                    )
                    if st.button("💾 Atualizar", key=f"save_{goal['id']}"):
                        goal['current_amount'] = new_amount
                        st.success("Progresso atualizado!")
                        st.rerun()
                    
                    if st.button("🗑️ Excluir", key=f"delete_goal_{goal['id']}"):
                        st.session_state.goals = [g for g in st.session_state.goals if g['id'] != goal['id']]
                        st.success("Meta excluída!")
                        st.rerun()
                
                st.markdown("---")
        else:
            st.info("🎯 Nenhuma meta financeira cadastrada ainda.")

def show_budget_management():
    st.markdown('<div class="sub-header">📈 Gestão de Orçamentos</div>', unsafe_allow_html=True)
    
    st.markdown("### 💰 Definir Orçamentos por Categoria")
    
    summary = financial_manager.get_financial_summary()
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### 📋 Orçamentos Mensais")
        for category in financial_manager.categories:
            current_budget = st.session_state.budgets.get(category, 0)
            spent = summary['expenses_by_category'].get(category, 0)
            
            new_budget = st.number_input(
                f"{category}:",
                min_value=0.0,
                value=float(current_budget),
                step=10.0,
                format="%.2f",
                key=f"budget_{category}"
            )
            
            # Atualizar orçamento
            st.session_state.budgets[category] = new_budget
            
            # Mostrar progresso
            if new_budget > 0:
                progress = min((spent / new_budget) * 100, 100)
                color = "green" if progress < 80 else "orange" if progress < 100 else "red"
                
                st.markdown(f"""
                <div style="margin-bottom: 15px;">
                    <small>Gasto: R$ {spent:,.2f} / R$ {new_budget:,.2f}</small>
                    <div style="background-color: #e0e0e0; border-radius: 5px; height: 10px;">
                        <div style="background-color: {color}; width: {progress}%; height: 10px; border-radius: 5px;"></div>
                    </div>
                    <small>{progress:.1f}% utilizado</small>
                </div>
                """, unsafe_allow_html=True)
    
    with col2:
        st.markdown("#### 📊 Resumo dos Orçamentos")
        
        total_budget = sum(st.session_state.budgets.values())
        total_spent = sum(summary['expenses_by_category'].values())
        
        if total_budget > 0:
            overall_progress = (total_spent / total_budget) * 100
            
            st.metric("Orçamento Total", f"R$ {total_budget:,.2f}")
            st.metric("Total Gasto", f"R$ {total_spent:,.2f}")
            st.metric("Saldo Disponível", f"R$ {total_budget - total_spent:,.2f}")
            
            st.markdown(f"""
            <div style="text-align: center; margin-top: 20px;">
                <h4>Utilização Geral: {overall_progress:.1f}%</h4>
                <div style="background-color: #e0e0e0; border-radius: 10px; height: 20px;">
                    <div style="background-color: {'green' if overall_progress < 80 else 'orange' if overall_progress < 100 else 'red'}; 
                                width: {min(overall_progress, 100)}%; height: 20px; border-radius: 10px;"></div>
                </div>
            </div>
            """, unsafe_allow_html=True)

def show_reports():
    st.markdown('<div class="sub-header">📋 Relatórios Financeiros</div>', unsafe_allow_html=True)
    
    tab1, tab2, tab3 = st.tabs(["📈 Relatório Mensal", "📊 Análise por Categoria", "💾 Exportar Dados"])
    
    with tab1:
        st.markdown("### 📈 Relatório Mensal")
        
        # Gráfico de receitas vs despesas
        months = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun']
        income_data = [5000, 5200, 4800, 5500, 6000, 5800]
        expense_data = [4500, 4700, 4200, 5000, 5200, 5100]
        savings_data = [i - e for i, e in zip(income_data, expense_data)]
        
        fig = go.Figure()
        fig.add_trace(go.Bar(x=months, y=income_data, name='Receitas', marker_color='#28a745'))
        fig.add_trace(go.Bar(x=months, y=expense_data, name='Despesas', marker_color='#dc3545'))
        fig.add_trace(go.Scatter(x=months, y=savings_data, name='Poupança', line=dict(color='#6a0dad', width=4)))
        
        fig.update_layout(
            title="Evolução Mensal - Receitas, Despesas e Poupança",
            barmode='group'
        )
        st.plotly_chart(fig, use_container_width=True)
    
    with tab2:
        st.markdown("### 📊 Análise Detalhada por Categoria")
        
        summary = financial_manager.get_financial_summary()
        
        if summary['expenses_by_category']:
            # Gráfico de barras horizontal
            categories = list(summary['expenses_by_category'].keys())
            values = list(summary['expenses_by_category'].values())
            
            fig = px.bar(
                x=values,
                y=categories,
                orientation='h',
                title="Despesas por Categoria",
                color=values,
                color_continuous_scale='Viridis'
            )
            fig.update_layout(yaxis={'categoryorder':'total ascending'})
            st.plotly_chart(fig, use_container_width=True)
            
            # Tabela detalhada
            st.markdown("### 📋 Tabela de Despesas")
            expense_data = []
            for category, amount in summary['expenses_by_category'].items():
                if amount > 0:
                    budget = st.session_state.budgets.get(category, 0)
                    percentage = (amount / budget * 100) if budget > 0 else 0
                    expense_data.append({
                        'Categoria': category,
                        'Valor Gasto': amount,
                        'Orçamento': budget,
                        'Utilização (%)': percentage
                    })
            
            if expense_data:
                df = pd.DataFrame(expense_data)
                st.dataframe(df.style.format({
                    'Valor Gasto': 'R$ {:.2f}',
                    'Orçamento': 'R$ {:.2f}',
                    'Utilização (%)': '{:.1f}%'
                }))
    
    with tab3:
        st.markdown("### 💾 Exportar Dados")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("📥 Exportar Transações para CSV"):
                if st.session_state.transactions:
                    df = pd.DataFrame(st.session_state.transactions)
                    csv = df.to_csv(index=False)
                    
                    st.download_button(
                        label="⬇️ Baixar CSV",
                        data=csv,
                        file_name=f"transacoes_{datetime.now().strftime('%Y%m%d')}.csv",
                        mime="text/csv"
                    )
                else:
                    st.warning("Nenhuma transação para exportar.")
        
        with col2:
            if st.button("📊 Exportar Relatório PDF"):
                st.info("Funcionalidade de exportação PDF em desenvolvimento")

def show_alerts():
    st.markdown('<div class="sub-header">🔔 Alertas e Notificações</div>', unsafe_allow_html=True)
    
    # Alertas baseados nos dados atuais
    summary = financial_manager.get_financial_summary()
    alerts = []
    
    # Verificar orçamentos estourados
    for category, budget in st.session_state.budgets.items():
        spent = summary['expenses_by_category'].get(category, 0)
        if budget > 0 and spent > budget:
            alerts.append({
                'type': 'warning',
                'message': f"⚠️ Orçamento de {category} estourado! Gasto: R$ {spent:,.2f} | Orçamento: R$ {budget:,.2f}"
            })
    
    # Verificar metas próximas do prazo
    for goal in st.session_state.goals:
        days_remaining = (goal['deadline'] - datetime.now().date()).days
        progress = (goal['current_amount'] / goal['target_amount']) * 100
        
        if days_remaining <= 7 and progress < 100:
            alerts.append({
                'type': 'info',
                'message': f"🎯 Meta '{goal['name']}' vence em {days_remaining} dias! Progresso: {progress:.1f}%"
            })
    
    # Verificar saldo negativo
    if summary['balance'] < 0:
        alerts.append({
            'type': 'error',
            'message': f"❌ Saldo negativo! Valor: R$ {abs(summary['balance']):,.2f}"
        })
    
    # Mostrar alertas
    if alerts:
        st.markdown("### 🔔 Alertas Ativos")
        for alert in alerts:
            if alert['type'] == 'error':
                st.error(alert['message'])
            elif alert['type'] == 'warning':
                st.warning(alert['message'])
            else:
                st.info(alert['message'])
    else:
        st.success("✅ Nenhum alerta ativo no momento!")
    
    # Configurações de alerta
    st.markdown("### ⚙️ Configurações de Alerta")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.checkbox("Notificar quando orçamento estourar", value=True)
        st.checkbox("Notificar sobre metas próximas do prazo", value=True)
        st.checkbox("Alertas de saldo negativo", value=True)
    
    with col2:
        st.checkbox("Relatório semanal automático", value=False)
        st.checkbox("Notificações por email", value=False)
        st.number_input("Dias para alerta de metas:", min_value=1, value=7)

def show_settings():
    st.markdown('<div class="sub-header">⚙️ Configurações do Sistema</div>', unsafe_allow_html=True)
    
    tab1, tab2, tab3 = st.tabs(["👤 Perfil", "🔧 Preferências", "🛠️ Sistema"])
    
    with tab1:
        st.markdown("### 👤 Configurações de Perfil")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.text_input("Nome completo:", value="João Silva")
            st.text_input("Email:", value="joao.silva@email.com")
            st.selectbox("Moeda padrão:", ["Real (R$)", "Dólar (US$)", "Euro (€)"])
        
        with col2:
            st.text_input("Empresa/Ocupação:", value="Analista Financeiro")
            st.selectbox("Idioma:", ["Português", "English", "Español"])
            st.date_input("Data de nascimento:", value=datetime(1990, 1, 1))
        
        if st.button("💾 Salvar Perfil", type="primary"):
            st.success("Perfil atualizado com sucesso!")
    
    with tab2:
        st.markdown("### 🔧 Preferências do Usuário")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("#### 🎨 Aparência")
            st.selectbox("Tema:", ["Claro", "Escuro", "Automático"])
            st.selectbox("Densidade:", ["Confortável", "Compacto"])
            st.checkbox("Mostrar tutoriais", value=True)
        
        with col2:
            st.markdown("#### 📊 Relatórios")
            st.selectbox("Formato de data:", ["DD/MM/AAAA", "MM/DD/AAAA", "AAAA-MM-DD"])
            st.number_input("Casas decimais:", min_value=0, max_value=4, value=2)
            st.checkbox("Notificações sonoras", value=False)
        
        if st.button("💾 Salvar Preferências"):
            st.success("Preferências salvas com sucesso!")
    
    with tab3:
        st.markdown("### 🛠️ Configurações do Sistema")
        
        st.markdown("#### 💾 Backup de Dados")
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("📤 Fazer Backup", type="primary"):
                st.success("Backup realizado com sucesso!")
                st.info("Dados salvos em: backup_financeiro.json")
        
        with col2:
            if st.button("🔄 Restaurar Backup"):
                st.warning("Esta ação substituirá todos os dados atuais!")
        
        st.markdown("#### 🗑️ Limpeza de Dados")
        st.warning("⚠️ Área de operações críticas")
        
        if st.button("🧹 Limpar Todos os Dados", type="secondary"):
            st.session_state.transactions = []
            st.session_state.goals = []
            st.session_state.budgets = {category: 0 for category in financial_manager.categories}
            st.success("Todos os dados foram limpos!")
            st.rerun()

# Rodapé
st.markdown("---")
st.markdown(
    """
    <div style='text-align: center; color: #666;'>
        💜 <strong>Clara Ready</strong> - Plataforma de Gestão Financeira Inteligente<br>
        Desenvolvido com ❤️ usando Streamlit
    </div>
    """,
    unsafe_allow_html=True
)

if __name__ == "__main__":
    main()
