import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime, timedelta
import json
import time
import io
import base64
import requests
from typing import Dict, List, Tuple, Optional, Any
import warnings
import calendar
from dateutil.relativedelta import relativedelta
import uuid
import hashlib
import smtplib
from email.mime.text import MimeText
from email.mime.multipart import MimeMultipart
import threading
from collections import defaultdict, Counter
import statistics
import math

warnings.filterwarnings('ignore')

# Configuração da página
st.set_page_config(
    page_title="Clara Ready - Plataforma Completa de Gestão Financeira",
    page_icon="💜",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        'Get Help': 'https://github.com/clara-ready',
        'Report a bug': "https://github.com/clara-ready/issues",
        'About': "### Clara Ready v2.0\nSua plataforma inteligente de gestão financeira pessoal e empresarial."
    }
)

# =============================================
# SISTEMA DE SEGURANÇA E AUTENTICAÇÃO
# =============================================

class SecurityManager:
    def __init__(self):
        self.session_timeout = 3600  # 1 hora
        
    def hash_password(self, password: str) -> str:
        """Hash seguro para senhas"""
        return hashlib.sha256(password.encode()).hexdigest()
    
    def validate_session(self):
        """Valida sessão do usuário"""
        if 'user_authenticated' not in st.session_state:
            st.session_state.user_authenticated = False
        if 'last_activity' not in st.session_state:
            st.session_state.last_activity = time.time()
        
        # Verificar timeout
        if time.time() - st.session_state.last_activity > self.session_timeout:
            st.session_state.user_authenticated = False
            st.warning("Sessão expirada. Por favor, faça login novamente.")
            return False
        
        st.session_state.last_activity = time.time()
        return st.session_state.user_authenticated
    
    def login(self, username: str, password: str) -> bool:
        """Sistema de login simplificado"""
        # Em produção, isso seria conectado a um banco de dados seguro
        valid_users = {
            'admin': self.hash_password('admin123'),
            'usuario': self.hash_password('senha123')
        }
        
        if username in valid_users and valid_users[username] == self.hash_password(password):
            st.session_state.user_authenticated = True
            st.session_state.username = username
            st.session_state.last_activity = time.time()
            return True
        return False

# =============================================
# SISTEMA DE NOTIFICAÇÕES
# =============================================

class NotificationSystem:
    def __init__(self):
        if 'notifications' not in st.session_state:
            st.session_state.notifications = []
    
    def add_notification(self, title: str, message: str, level: str = "info"):
        """Adiciona uma nova notificação"""
        notification = {
            'id': str(uuid.uuid4()),
            'title': title,
            'message': message,
            'level': level,  # info, warning, error, success
            'timestamp': datetime.now(),
            'read': False
        }
        st.session_state.notifications.append(notification)
    
    def get_unread_count(self) -> int:
        """Retorna número de notificações não lidas"""
        return sum(1 for n in st.session_state.notifications if not n['read'])
    
    def mark_all_read(self):
        """Marca todas as notificações como lidas"""
        for notification in st.session_state.notifications:
            notification['read'] = True

# =============================================
# SISTEMA DE RELATÓRIOS AVANÇADOS
# =============================================

class AdvancedReporting:
    def __init__(self, finance_manager):
        self.finance_manager = finance_manager
    
    def generate_comprehensive_report(self, start_date: datetime, end_date: datetime) -> Dict:
        """Gera relatório financeiro completo"""
        transactions = self._get_transactions_in_period(start_date, end_date)
        
        report = {
            'period': f"{start_date.strftime('%d/%m/%Y')} - {end_date.strftime('%d/%m/%Y')}",
            'summary': self._generate_summary(transactions),
            'category_analysis': self._analyze_categories(transactions),
            'cash_flow_analysis': self._analyze_cash_flow(transactions),
            'financial_health': self._assess_financial_health(transactions),
            'recommendations': self._generate_recommendations(transactions)
        }
        
        return report
    
    def _get_transactions_in_period(self, start_date: datetime, end_date: datetime) -> List:
        """Filtra transações por período"""
        return [
            t for t in st.session_state.transactions
            if start_date <= t['date'] <= end_date
        ]
    
    def _generate_summary(self, transactions: List) -> Dict:
        """Gera resumo financeiro"""
        income = sum(t['amount'] for t in transactions if t['type'] == 'Receita')
        expenses = sum(t['amount'] for t in transactions if t['type'] == 'Despesa')
        savings = income - expenses
        savings_rate = (savings / income * 100) if income > 0 else 0
        
        return {
            'total_income': income,
            'total_expenses': expenses,
            'net_savings': savings,
            'savings_rate': savings_rate,
            'transaction_count': len(transactions),
            'average_transaction': income / len(transactions) if transactions else 0
        }
    
    def _analyze_categories(self, transactions: List) -> Dict:
        """Analisa gastos por categoria"""
        expense_transactions = [t for t in transactions if t['type'] == 'Despesa']
        category_totals = {}
        
        for transaction in expense_transactions:
            category = transaction['category']
            amount = transaction['amount']
            category_totals[category] = category_totals.get(category, 0) + amount
        
        total_expenses = sum(category_totals.values())
        category_percentages = {
            category: (amount / total_expenses * 100) if total_expenses > 0 else 0
            for category, amount in category_totals.items()
        }
        
        return {
            'category_totals': category_totals,
            'category_percentages': category_percentages,
            'top_categories': sorted(category_totals.items(), key=lambda x: x[1], reverse=True)[:5]
        }
    
    def _analyze_cash_flow(self, transactions: List) -> Dict:
        """Analisa fluxo de caixa"""
        daily_flow = defaultdict(float)
        
        for transaction in transactions:
            date_key = transaction['date'].strftime('%Y-%m-%d')
            amount = transaction['amount']
            if transaction['type'] == 'Receita':
                daily_flow[date_key] += amount
            else:
                daily_flow[date_key] -= amount
        
        return {
            'daily_cash_flow': dict(daily_flow),
            'positive_days': sum(1 for flow in daily_flow.values() if flow > 0),
            'negative_days': sum(1 for flow in daily_flow.values() if flow < 0),
            'average_daily_flow': statistics.mean(daily_flow.values()) if daily_flow else 0
        }
    
    def _assess_financial_health(self, transactions: List) -> Dict:
        """Avalia saúde financeira"""
        summary = self._generate_summary(transactions)
        category_analysis = self._analyze_categories(transactions)
        
        # Métricas de saúde financeira
        savings_rate_score = min(summary['savings_rate'] / 20 * 100, 100)  # Meta: 20%
        expense_diversity = len(category_analysis['category_totals']) / 8 * 100  # Meta: 8 categorias
        consistency_score = self._calculate_consistency_score(transactions)
        
        overall_score = (savings_rate_score + expense_diversity + consistency_score) / 3
        
        return {
            'overall_score': overall_score,
            'savings_rate_score': savings_rate_score,
            'expense_diversity_score': expense_diversity,
            'consistency_score': consistency_score,
            'grade': self._get_grade(overall_score)
        }
    
    def _calculate_consistency_score(self, transactions: List) -> float:
        """Calcula score de consistência financeira"""
        if len(transactions) < 10:
            return 50.0  # Score base para poucas transações
        
        # Analisar consistência de receitas
        income_transactions = [t for t in transactions if t['type'] == 'Receita']
        if len(income_transactions) > 1:
            income_amounts = [t['amount'] for t in income_transactions]
            income_std = statistics.stdev(income_amounts)
            income_mean = statistics.mean(income_amounts)
            income_cv = (income_std / income_mean * 100) if income_mean > 0 else 100
            income_consistency = max(0, 100 - income_cv)
        else:
            income_consistency = 50
        
        return income_consistency
    
    def _get_grade(self, score: float) -> str:
        """Converte score em nota"""
        if score >= 90: return "A+"
        elif score >= 80: return "A"
        elif score >= 70: return "B"
        elif score >= 60: return "C"
        elif score >= 50: return "D"
        else: return "F"
    
    def _generate_recommendations(self, transactions: List) -> List[str]:
        """Gera recomendações personalizadas"""
        recommendations = []
        summary = self._generate_summary(transactions)
        category_analysis = self._analyze_categories(transactions)
        financial_health = self._assess_financial_health(transactions)
        
        # Recomendações baseadas em savings rate
        if summary['savings_rate'] < 10:
            recommendations.append("💡 **Aumente sua taxa de economia**: Tente economizar pelo menos 20% da sua renda")
        elif summary['savings_rate'] > 30:
            recommendations.append("✅ **Excelente taxa de economia**: Considere investir o excedente")
        
        # Recomendações baseadas em diversidade de gastos
        if len(category_analysis['category_totals']) < 5:
            recommendations.append("📊 **Diversifique seus gastos**: Suas despesas estão concentradas em poucas categorias")
        
        # Recomendações baseadas em saúde financeira
        if financial_health['overall_score'] < 60:
            recommendations.append("⚕️ **Melhore sua saúde financeira**: Foque em consistência e diversificação")
        
        # Recomendações específicas por categoria
        for category, percentage in category_analysis['category_percentages'].items():
            if percentage > 40:
                recommendations.append(f"🎯 **Reduza gastos com {category}**: Está consumindo {percentage:.1f}% do seu orçamento")
        
        return recommendations

# =============================================
# SISTEMA DE INVESTIMENTOS
# =============================================

class InvestmentManager:
    def __init__(self):
        if 'investments' not in st.session_state:
            st.session_state.investments = []
        if 'investment_goals' not in st.session_state:
            st.session_state.investment_goals = []
    
    def add_investment(self, name: str, type: str, amount: float, 
                      expected_return: float, risk_level: str, date: datetime):
        """Adiciona um novo investimento"""
        investment = {
            'id': str(uuid.uuid4()),
            'name': name,
            'type': type,
            'amount': amount,
            'current_value': amount,
            'expected_return': expected_return,
            'risk_level': risk_level,
            'date_added': date,
            'last_updated': datetime.now()
        }
        st.session_state.investments.append(investment)
    
    def update_investment_value(self, investment_id: str, new_value: float):
        """Atualiza valor do investimento"""
        for investment in st.session_state.investments:
            if investment['id'] == investment_id:
                investment['current_value'] = new_value
                investment['last_updated'] = datetime.now()
                break
    
    def get_portfolio_summary(self) -> Dict:
        """Retorna resumo da carteira de investimentos"""
        if not st.session_state.investments:
            return {}
        
        total_invested = sum(inv['amount'] for inv in st.session_state.investments)
        total_current = sum(inv['current_value'] for inv in st.session_state.investments)
        total_return = total_current - total_invested
        total_return_percentage = (total_return / total_invested * 100) if total_invested > 0 else 0
        
        # Análise por tipo
        type_analysis = {}
        for investment in st.session_state.investments:
            inv_type = investment['type']
            if inv_type not in type_analysis:
                type_analysis[inv_type] = {
                    'total_invested': 0,
                    'total_current': 0,
                    'count': 0
                }
            type_analysis[inv_type]['total_invested'] += investment['amount']
            type_analysis[inv_type]['total_current'] += investment['current_value']
            type_analysis[inv_type]['count'] += 1
        
        # Análise por risco
        risk_analysis = {}
        for investment in st.session_state.investments:
            risk = investment['risk_level']
            if risk not in risk_analysis:
                risk_analysis[risk] = {
                    'total_invested': 0,
                    'total_current': 0,
                    'count': 0
                }
            risk_analysis[risk]['total_invested'] += investment['amount']
            risk_analysis[risk]['total_current'] += investment['current_value']
            risk_analysis[risk]['count'] += 1
        
        return {
            'total_invested': total_invested,
            'total_current_value': total_current,
            'total_return': total_return,
            'total_return_percentage': total_return_percentage,
            'type_analysis': type_analysis,
            'risk_analysis': risk_analysis,
            'investment_count': len(st.session_state.investments)
        }

# =============================================
# SISTEMA DE METAS AVANÇADAS
# =============================================

class AdvancedGoalManager:
    def __init__(self, finance_manager):
        self.finance_manager = finance_manager
    
    def calculate_goal_progress(self, goal: Dict) -> Dict:
        """Calcula progresso detalhado da meta"""
        target_amount = goal['target_amount']
        current_amount = goal['current_amount']
        deadline = goal['deadline']
        created_at = goal['created_at']
        
        # Progresso atual
        current_progress = (current_amount / target_amount * 100) if target_amount > 0 else 0
        
        # Progresso esperado baseado no tempo
        total_days = (deadline - created_at.date()).days
        days_passed = (datetime.now().date() - created_at.date()).days
        expected_progress = (days_passed / total_days * 100) if total_days > 0 else 0
        
        # Quantia necessária por mês
        remaining_amount = target_amount - current_amount
        months_remaining = max(1, (deadline - datetime.now().date()).days // 30)
        monthly_savings_needed = remaining_amount / months_remaining
        
        # Status da meta
        if current_progress >= 100:
            status = "Concluída"
        elif current_progress >= expected_progress:
            status = "No Prazo"
        else:
            status = "Atrasada"
        
        return {
            'current_progress': current_progress,
            'expected_progress': expected_progress,
            'remaining_amount': remaining_amount,
            'monthly_savings_needed': monthly_savings_needed,
            'status': status,
            'days_remaining': (deadline - datetime.now().date()).days,
            'on_track': current_progress >= expected_progress
        }

# =============================================
# GERENCIADOR FINANCEIRO PRINCIPAL (EXPANDIDO)
# =============================================

class FinancialManager:
    def __init__(self):
        self.categories = {
            'Receitas': ['Salário', 'Freelance', 'Investimentos', 'Aluguel', 'Bônus', 'Dividendos', 'Outros'],
            'Despesas': ['Moradia', 'Alimentação', 'Transporte', 'Saúde', 'Educação', 
                        'Lazer', 'Vestuário', 'Serviços', 'Impostos', 'Seguros', 'Outros']
        }
        
        # Inicializar session states
        self._initialize_session_states()
        
        # Subsistemas
        self.security = SecurityManager()
        self.notifications = NotificationSystem()
        self.reporting = AdvancedReporting(self)
        self.investments = InvestmentManager()
        self.goal_manager = AdvancedGoalManager(self)
    
    def _initialize_session_states(self):
        """Inicializa todos os session states necessários"""
        defaults = {
            'transactions': [],
            'financial_goals': [],
            'budgets': {},
            'recurring_transactions': [],
            'financial_plans': [],
            'user_preferences': {
                'currency': 'BRL',
                'savings_target': 20,
                'notifications': True,
                'theme': 'light'
            }
        }
        
        for key, value in defaults.items():
            if key not in st.session_state:
                st.session_state[key] = value
    
    def add_transaction(self, amount: float, category: str, description: str, 
                       transaction_type: str, date: datetime, recurring: bool = False,
                       recurring_frequency: str = None) -> Dict:
        """Adiciona uma nova transação financeira com suporte a recorrência"""
        transaction = {
            'id': str(uuid.uuid4()),
            'amount': amount,
            'category': category,
            'description': description,
            'type': transaction_type,
            'date': date,
            'created_at': datetime.now(),
            'recurring': recurring,
            'recurring_frequency': recurring_frequency
        }
        
        st.session_state.transactions.append(transaction)
        
        # Adicionar notificação
        self.notifications.add_notification(
            "Nova Transação",
            f"{transaction_type} de R$ {amount:,.2f} em {category}",
            "info"
        )
        
        return transaction
    
    def add_recurring_transaction(self, amount: float, category: str, description: str,
                                transaction_type: str, start_date: datetime, 
                                frequency: str, end_date: datetime = None):
        """Adiciona transação recorrente"""
        recurring_transaction = {
            'id': str(uuid.uuid4()),
            'amount': amount,
            'category': category,
            'description': description,
            'type': transaction_type,
            'start_date': start_date,
            'frequency': frequency,  # daily, weekly, monthly, yearly
            'end_date': end_date,
            'created_at': datetime.now()
        }
        
        st.session_state.recurring_transactions.append(recurring_transaction)
        
        # Gerar transações baseadas na recorrência
        self._generate_recurring_transactions()
    
    def _generate_recurring_transactions(self):
        """Gera transações baseadas nas regras de recorrência"""
        today = datetime.now().date()
        
        for recurring in st.session_state.recurring_transactions:
            last_generated = recurring.get('last_generated')
            
            if not last_generated or self._should_generate_transaction(recurring, last_generated, today):
                # Criar nova transação
                new_transaction = {
                    'id': str(uuid.uuid4()),
                    'amount': recurring['amount'],
                    'category': recurring['category'],
                    'description': recurring['description'],
                    'type': recurring['type'],
                    'date': datetime.now(),
                    'created_at': datetime.now(),
                    'recurring': True,
                    'recurring_id': recurring['id']
                }
                
                st.session_state.transactions.append(new_transaction)
                recurring['last_generated'] = today
    
    def _should_generate_transaction(self, recurring: Dict, last_generated: datetime, today: datetime) -> bool:
        """Verifica se deve gerar nova transação baseada na frequência"""
        frequency = recurring['frequency']
        
        if frequency == 'daily':
            return today > last_generated
        elif frequency == 'weekly':
            return (today - last_generated).days >= 7
        elif frequency == 'monthly':
            return today.month != last_generated.month or today.year != last_generated.year
        elif frequency == 'yearly':
            return today.year != last_generated.year
        
        return False
    
    def get_balance(self) -> float:
        """Calcula o saldo total"""
        income = sum(t['amount'] for t in st.session_state.transactions if t['type'] == 'Receita')
        expenses = sum(t['amount'] for t in st.session_state.transactions if t['type'] == 'Despesa')
        return income - expenses
    
    def get_monthly_summary(self, year: int = None, month: int = None) -> Dict:
        """Retorna resumo mensal detalhado"""
        if year is None:
            year = datetime.now().year
        if month is None:
            month = datetime.now().month
        
        monthly_transactions = [
            t for t in st.session_state.transactions
            if t['date'].year == year and t['date'].month == month
        ]
        
        income = sum(t['amount'] for t in monthly_transactions if t['type'] == 'Receita')
        expenses = sum(t['amount'] for t in monthly_transactions if t['type'] == 'Despesa')
        savings = income - expenses
        savings_rate = (savings / income * 100) if income > 0 else 0
        
        # Análise por categoria
        expense_by_category = {}
        for transaction in monthly_transactions:
            if transaction['type'] == 'Despesa':
                category = transaction['category']
                expense_by_category[category] = expense_by_category.get(category, 0) + transaction['amount']
        
        # Comparação com mês anterior
        prev_month = month - 1 if month > 1 else 12
        prev_year = year if month > 1 else year - 1
        prev_summary = self.get_monthly_summary(prev_year, prev_month)
        
        return {
            'income': income,
            'expenses': expenses,
            'savings': savings,
            'savings_rate': savings_rate,
            'transaction_count': len(monthly_transactions),
            'expense_by_category': expense_by_category,
            'comparison': {
                'income_change': income - prev_summary['income'],
                'expense_change': expenses - prev_summary['expenses'],
                'savings_change': savings - prev_summary['savings']
            }
        }
    
    def get_yearly_summary(self, year: int = None) -> Dict:
        """Retorna resumo anual"""
        if year is None:
            year = datetime.now().year
        
        yearly_data = {}
        for month in range(1, 13):
            yearly_data[month] = self.get_monthly_summary(year, month)
        
        total_income = sum(data['income'] for data in yearly_data.values())
        total_expenses = sum(data['expenses'] for data in yearly_data.values())
        total_savings = total_income - total_expenses
        
        return {
            'yearly_data': yearly_data,
            'total_income': total_income,
            'total_expenses': total_expenses,
            'total_savings': total_savings,
            'average_savings_rate': (total_savings / total_income * 100) if total_income > 0 else 0,
            'best_month': max(yearly_data.items(), key=lambda x: x[1]['savings']),
            'worst_month': min(yearly_data.items(), key=lambda x: x[1]['savings'])
        }
    
    def set_budget(self, category: str, amount: float, period: str = 'monthly'):
        """Define orçamento para uma categoria"""
        st.session_state.budgets[category] = {
            'amount': amount,
            'period': period,
            'set_at': datetime.now()
        }
    
    def get_budget_status(self) -> Dict:
        """Retorna status detalhado dos orçamentos"""
        current_month = datetime.now().month
        current_year = datetime.now().year
        
        budget_status = {}
        for category, budget in st.session_state.budgets.items():
            spent = sum(
                t['amount'] for t in st.session_state.transactions 
                if t['category'] == category and t['type'] == 'Despesa'
                and t['date'].month == current_month and t['date'].year == current_year
            )
            
            budget_amount = budget['amount']
            remaining = budget_amount - spent
            percentage = (spent / budget_amount * 100) if budget_amount > 0 else 0
            
            budget_status[category] = {
                'budget': budget_amount,
                'spent': spent,
                'remaining': remaining,
                'percentage': percentage,
                'status': 'within_budget' if percentage <= 100 else 'over_budget',
                'over_amount': max(0, spent - budget_amount)
            }
        
        return budget_status
    
    def add_financial_goal(self, goal: str, target_amount: float, deadline: datetime,
                          priority: str = 'medium', category: str = 'Outros'):
        """Adiciona uma meta financeira detalhada"""
        goal_data = {
            'id': str(uuid.uuid4()),
            'goal': goal,
            'target_amount': target_amount,
            'current_amount': 0,
            'deadline': deadline,
            'priority': priority,  # low, medium, high
            'category': category,
            'created_at': datetime.now(),
            'completed': False,
            'milestones': []
        }
        st.session_state.financial_goals.append(goal_data)
        return goal_data
    
    def add_milestone_to_goal(self, goal_id: str, milestone: str, target_amount: float):
        """Adiciona marco a uma meta"""
        for goal in st.session_state.financial_goals:
            if goal['id'] == goal_id:
                milestone_data = {
                    'id': str(uuid.uuid4()),
                    'milestone': milestone,
                    'target_amount': target_amount,
                    'completed': False
                }
                goal['milestones'].append(milestone_data)
                break
    
    def update_goal_progress(self, goal_id: str, amount: float):
        """Atualiza progresso da meta"""
        for goal in st.session_state.financial_goals:
            if goal['id'] == goal_id:
                goal['current_amount'] += amount
                
                # Verificar se completou a meta
                if goal['current_amount'] >= goal['target_amount']:
                    goal['completed'] = True
                    goal['completed_at'] = datetime.now()
                    
                    self.notifications.add_notification(
                        "🎉 Meta Concluída!",
                        f"Parabéns! Você alcançou a meta: {goal['goal']}",
                        "success"
                    )
                
                break

# =============================================
# COMPONENTES DE UI AVANÇADOS
# =============================================

class AdvancedUIComponents:
    @staticmethod
    def create_financial_card(title: str, value: Any, change: Any = None, 
                            change_label: str = "", icon: str = "💰"):
        """Cria card financeiro avançado"""
        col1, col2 = st.columns([3, 1])
        
        with col1:
            st.metric(
                label=title,
                value=value,
                delta=change,
                delta_color="normal" if change is None else ("inverse" if change < 0 else "normal")
            )
        
        with col2:
            st.write(f"<div style='font-size: 2rem; text-align: center;'>{icon}</div>", 
                    unsafe_allow_html=True)
        
        if change_label:
            st.caption(change_label)
    
    @staticmethod
    def create_progress_dashboard(finance_manager):
        """Cria dashboard de progresso completo"""
        st.markdown("### 📊 Dashboard de Progresso")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            balance = finance_manager.get_balance()
            AdvancedUIComponents.create_financial_card(
                "Saldo Total", 
                f"R$ {balance:,.2f}", 
                icon="💼"
            )
        
        with col2:
            monthly = finance_manager.get_monthly_summary()
            AdvancedUIComponents.create_financial_card(
                "Economias do Mês", 
                f"R$ {monthly['savings']:,.2f}",
                monthly['comparison']['savings_change'],
                icon="📈"
            )
        
        with col3:
            budget_status = finance_manager.get_budget_status()
            within_budget = sum(1 for status in budget_status.values() 
                              if status['status'] == 'within_budget')
            total_budgets = len(budget_status)
            budget_percentage = (within_budget / total_budgets * 100) if total_budgets > 0 else 0
            
            AdvancedUIComponents.create_financial_card(
                "Orçamentos no Verde",
                f"{budget_percentage:.1f}%",
                icon="✅"
            )
        
        with col4:
            goals = [g for g in st.session_state.financial_goals if not g['completed']]
            if goals:
                completed_goals = sum(1 for g in goals if g['completed'])
                goals_percentage = (completed_goals / len(goals) * 100)
                AdvancedUIComponents.create_financial_card(
                    "Metas em Progresso",
                    f"{goals_percentage:.1f}%",
                    icon="🎯"
                )
            else:
                AdvancedUIComponents.create_financial_card(
                    "Metas",
                    "0%",
                    icon="🎯"
                )

# =============================================
# APLICAÇÃO PRINCIPAL
# =============================================

def main():
    # Inicializar gerenciador financeiro
    finance_manager = FinancialManager()
    
    # Verificar autenticação
    if not finance_manager.security.validate_session():
        show_login_page(finance_manager.security)
        return
    
    # CSS personalizado avançado
    st.markdown("""
    <style>
        .main-header {
            font-size: 3.5rem;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            text-align: center;
            margin-bottom: 1rem;
            font-weight: bold;
        }
        .metric-card {
            background: white;
            border-radius: 15px;
            padding: 1.5rem;
            margin-bottom: 1rem;
            border-left: 5px solid #6A0DAD;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            transition: transform 0.2s;
        }
        .metric-card:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 12px rgba(0, 0, 0, 0.15);
        }
        .positive {
            color: #00C851;
            font-weight: bold;
        }
        .negative {
            color: #ff4444;
            font-weight: bold;
        }
        .notification-badge {
            background-color: #ff4444;
            color: white;
            border-radius: 50%;
            padding: 2px 6px;
            font-size: 0.8rem;
            margin-left: 5px;
        }
    </style>
    """, unsafe_allow_html=True)
    
    # Header principal
    st.markdown('<div class="main-header">💜 Clara Ready</div>', unsafe_allow_html=True)
    st.markdown('<p style="text-align: center; font-size: 1.3rem; color: #666;">Sua plataforma inteligente de gestão financeira pessoal e empresarial</p>', unsafe_allow_html=True)
    
    # Barra superior com notificações
    show_top_navigation(finance_manager)
    
    # Sidebar principal
    with st.sidebar:
        show_sidebar(finance_manager)
    
    # Conteúdo principal baseado na seleção do menu
    menu_option = st.session_state.get('selected_menu', '📊 Dashboard Principal')
    
    if menu_option == "📊 Dashboard Principal":
        show_advanced_dashboard(finance_manager)
    elif menu_option == "💸 Gestão de Transações":
        show_transaction_management(finance_manager)
    elif menu_option == "📈 Análises Detalhadas":
        show_detailed_analysis(finance_manager)
    elif menu_option == "🎯 Metas Financeiras":
        show_advanced_goals(finance_manager)
    elif menu_option == "💰 Orçamentos":
        show_budget_management(finance_manager)
    elif menu_option == "📊 Relatórios":
        show_reports(finance_manager)
    elif menu_option == "💼 Investimentos":
        show_investments(finance_manager)
    elif menu_option == "🔮 Previsões":
        show_advanced_forecasts(finance_manager)
    elif menu_option == "⚙️ Configurações":
        show_advanced_settings(finance_manager)

def show_login_page(security_manager):
    """Página de login"""
    st.markdown("""
    <style>
        .login-container {
            max-width: 400px;
            margin: 100px auto;
            padding: 2rem;
            border-radius: 15px;
            box-shadow: 0 10px 25px rgba(0,0,0,0.1);
            background: white;
        }
    </style>
    """, unsafe_allow_html=True)
    
    st.markdown('<div class="login-container">', unsafe_allow_html=True)
    
    st.markdown('<h2 style="text-align: center; color: #6A0DAD;">🔐 Login</h2>', unsafe_allow_html=True)
    
    with st.form("login_form"):
        username = st.text_input("👤 Usuário")
        password = st.text_input("🔒 Senha", type="password")
        
        if st.form_submit_button("🚀 Entrar"):
            if security_manager.login(username, password):
                st.success("✅ Login realizado com sucesso!")
                st.rerun()
            else:
                st.error("❌ Usuário ou senha incorretos")
    
    st.markdown("""
    <div style="text-align: center; margin-top: 2rem;">
        <p><strong>Credenciais de demonstração:</strong></p>
        <p>👤 Usuário: <code>admin</code></p>
        <p>🔒 Senha: <code>admin123</code></p>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown('</div>', unsafe_allow_html=True)

def show_top_navigation(finance_manager):
    """Barra de navegação superior"""
    col1, col2, col3, col4 = st.columns([3, 1, 1, 1])
    
    with col1:
        st.write(f"👋 Bem-vindo(a), **{st.session_state.get('username', 'Usuário')}**!")
    
    with col2:
        # Notificações
        unread_count = finance_manager.notifications.get_unread_count()
        notification_text = "🔔 Notificações"
        if unread_count > 0:
            notification_text += f" <span class='notification-badge'>{unread_count}</span>"
        
        if st.button(notification_text, use_container_width=True):
            show_notifications(finance_manager.notifications)
    
    with col3:
        # Saldo rápido
        balance = finance_manager.get_balance()
        balance_color = "positive" if balance >= 0 else "negative"
        st.markdown(f"**Saldo:** <span class='{balance_color}'>R$ {balance:,.2f}</span>", 
                   unsafe_allow_html=True)
    
    with col4:
        if st.button("🚪 Sair", use_container_width=True):
            st.session_state.user_authenticated = False
            st.rerun()

def show_sidebar(finance_manager):
    """Sidebar principal"""
    st.image("https://img.icons8.com/color/96/000000/money-bag.png", width=80)
    st.markdown("## Navegação")
    
    menu_options = [
        "📊 Dashboard Principal",
        "💸 Gestão de Transações", 
        "📈 Análises Detalhadas",
        "🎯 Metas Financeiras",
        "💰 Orçamentos",
        "📊 Relatórios",
        "💼 Investimentos",
        "🔮 Previsões",
        "⚙️ Configurações"
    ]
    
    selected_menu = st.radio("Selecione uma opção:", menu_options, key="selected_menu")
    
    st.markdown("---")
    st.markdown("### 📈 Resumo Rápido")
    
    # Mostrar métricas rápidas
    balance = finance_manager.get_balance()
    monthly_summary = finance_manager.get_monthly_summary()
    
    st.metric("Saldo Atual", f"R$ {balance:,.2f}")
    st.metric("Economias do Mês", f"R$ {monthly_summary['savings']:,.2f}")
    st.metric("Taxa de Economia", f"{monthly_summary['savings_rate']:.1f}%")
    
    # Alertas rápidos
    st.markdown("---")
    st.markdown("### ⚡ Alertas")
    show_quick_alerts(finance_manager)

def show_quick_alerts(finance_manager):
    """Mostra alertas rápidos na sidebar"""
    budget_status = finance_manager.get_budget_status()
    
    # Verificar orçamentos estourados
    over_budget_categories = [
        category for category, status in budget_status.items()
        if status['status'] == 'over_budget'
    ]
    
    if over_budget_categories:
        st.warning(f"🚨 {len(over_budget_categories)} orçamento(s) estourado(s)")
    
    # Verificar metas próximas do prazo
    current_goals = [g for g in st.session_state.financial_goals if not g['completed']]
    urgent_goals = [
        g for g in current_goals
        if (g['deadline'] - datetime.now().date()).days <= 30
    ]
    
    if urgent_goals:
        st.error(f"⏰ {len(urgent_goals)} meta(s) próxima(s) do prazo")

# =============================================
# PÁGINAS PRINCIPAIS (IMPLEMENTAÇÕES DETALHADAS)
# =============================================

def show_advanced_dashboard(finance_manager):
    """Dashboard principal avançado"""
    st.markdown("## 📊 Dashboard Financeiro Completo")
    
    # Métricas principais
    AdvancedUIComponents.create_progress_dashboard(finance_manager)
    
    # Gráficos e visualizações
    col1, col2 = st.columns(2)
    
    with col1:
        show_income_expense_trend(finance_manager)
        show_category_breakdown(finance_manager)
    
    with col2:
        show_budget_compliance(finance_manager)
        show_goals_overview(finance_manager)
    
    # Insights inteligentes
    st.markdown("## 💡 Insights Financeiros")
    show_ai_insights(finance_manager)
    
    # Transações recentes
    st.markdown("## 🔄 Transações Recentes")
    show_enhanced_recent_transactions(finance_manager)

def show_transaction_management(finance_manager):
    """Gestão completa de transações"""
    st.markdown("## 💸 Gestão de Transações")
    
    tab1, tab2, tab3, tab4 = st.tabs(["➕ Nova Transação", "📋 Todas Transações", "🔄 Recorrentes", "📁 Importar/Exportar"])
    
    with tab1:
        show_advanced_transaction_form(finance_manager)
    
    with tab2:
        show_transaction_list(finance_manager)
    
    with tab3:
        show_recurring_transactions(finance_manager)
    
    with tab4:
        show_import_export(finance_manager)

def show_detailed_analysis(finance_manager):
    """Análises financeiras detalhadas"""
    st.markdown("## 📈 Análises Financeiras Detalhadas")
    
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📊 Visão Geral", "📋 Análise por Categoria", "📅 Tendências", 
        "🔍 Análise Comparativa", "📐 Métricas Avançadas"
    ])
    
    with tab1:
        show_comprehensive_overview(finance_manager)
    
    with tab2:
        show_detailed_category_analysis(finance_manager)
    
    with tab3:
        show_trend_analysis_advanced(finance_manager)
    
    with tab4:
        show_comparative_analysis(finance_manager)
    
    with tab5:
        show_advanced_metrics(finance_manager)

def show_advanced_goals(finance_manager):
    """Sistema avançado de metas"""
    st.markdown("## 🎯 Metas Financeiras Avançadas")
    
    col1, col2 = st.columns([2, 1])
    
    with col2:
        show_goal_creation_form(finance_manager)
    
    with col1:
        show_goals_dashboard(finance_manager)

def show_budget_management(finance_manager):
    """Gestão de orçamentos"""
    st.markdown("## 💰 Gestão de Orçamentos")
    
    col1, col2 = st.columns(2)
    
    with col1:
        show_budget_setup(finance_manager)
    
    with col2:
        show_budget_analysis(finance_manager)

def show_reports(finance_manager):
    """Sistema de relatórios"""
    st.markdown("## 📊 Relatórios Financeiros")
    
    period = st.selectbox("Período do Relatório:", 
                         ["Últimos 30 dias", "Últimos 3 meses", "Últimos 6 meses", "Este ano", "Personalizado"])
    
    if st.button("📄 Gerar Relatório Completo"):
        report = finance_manager.reporting.generate_comprehensive_report(
            datetime.now() - timedelta(days=30), 
            datetime.now()
        )
        show_financial_report(report)

def show_investments(finance_manager):
    """Gestão de investimentos"""
    st.markdown("## 💼 Carteira de Investimentos")
    
    tab1, tab2, tab3 = st.tabs(["📊 Minha Carteira", "➕ Novo Investimento", "📈 Análise de Performance"])
    
    with tab1:
        show_investment_portfolio(finance_manager)
    
    with tab2:
        show_investment_form(finance_manager)
    
    with tab3:
        show_investment_analysis(finance_manager)

def show_advanced_forecasts(finance_manager):
    """Previsões avançadas"""
    st.markdown("## 🔮 Previsões Financeiras")
    
    col1, col2 = st.columns(2)
    
    with col1:
        show_income_forecast_advanced(finance_manager)
    
    with col2:
        show_expense_forecast_advanced(finance_manager)
    
    st.markdown("### 🎯 Projeção de Metas")
    show_goal_forecasts(finance_manager)

def show_advanced_settings(finance_manager):
    """Configurações avançadas"""
    st.markdown("## ⚙️ Configurações Avançadas")
    
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "👤 Perfil", "🔔 Notificações", "💾 Dados", "🎨 Aparência", "🔒 Segurança"
    ])
    
    with tab1:
        show_profile_settings(finance_manager)
    
    with tab2:
        show_notification_settings(finance_manager)
    
    with tab3:
        show_data_management(finance_manager)
    
    with tab4:
        show_appearance_settings(finance_manager)
    
    with tab5:
        show_security_settings(finance_manager)

# =============================================
# FUNÇÕES DE VISUALIZAÇÃO DETALHADAS
# =============================================

def show_income_expense_trend(finance_manager):
    """Mostra tendência de receitas vs despesas"""
    st.markdown("### 📈 Tendência Receitas vs Despesas")
    
    # Implementar gráfico de tendências
    # ... (código para gerar gráfico)
    
    st.plotly_chart(create_income_expense_trend_chart(finance_manager), use_container_width=True)

def show_category_breakdown(finance_manager):
    """Mostra breakdown por categoria"""
    st.markdown("### 🎯 Distribuição por Categoria")
    
    # Implementar gráfico de categorias
    # ... (código para gerar gráfico)
    
    st.plotly_chart(create_category_breakdown_chart(finance_manager), use_container_width=True)

def show_budget_compliance(finance_manager):
    """Mostra conformidade com orçamentos"""
    st.markdown("### ✅ Conformidade com Orçamentos")
    
    budget_status = finance_manager.get_budget_status()
    
    if budget_status:
        categories = list(budget_status.keys())
        percentages = [status['percentage'] for status in budget_status.values()]
        
        fig = go.Figure(data=[
            go.Bar(name='% Utilizado', x=categories, y=percentages,
                  marker_color=['green' if p <= 100 else 'red' for p in percentages])
        ])
        
        fig.add_hline(y=100, line_dash="dash", line_color="red", 
                     annotation_text="Limite do Orçamento")
        
        fig.update_layout(
            title="Utilização dos Orçamentos por Categoria",
            yaxis_title="Percentual Utilizado (%)",
            height=400
        )
        
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("ℹ️ Nenhum orçamento definido ainda.")

def show_goals_overview(finance_manager):
    """Visão geral das metas"""
    st.markdown("### 🎯 Visão Geral das Metas")
    
    goals = st.session_state.financial_goals
    
    if goals:
        for goal in goals[:3]:  # Mostrar apenas 3 metas
            progress_info = finance_manager.goal_manager.calculate_goal_progress(goal)
            
            col1, col2 = st.columns([3, 1])
            
            with col1:
                st.write(f"**{goal['goal']}**")
                st.progress(progress_info['current_progress'] / 100)
                
            with col2:
                st.metric(
                    "Progresso", 
                    f"{progress_info['current_progress']:.1f}%",
                    f"{progress_info['status']}"
                )
            
            st.caption(f"R$ {goal['current_amount']:,.2f} de R$ {goal['target_amount']:,.2f} • {progress_info['days_remaining']} dias restantes")
            st.divider()
    else:
        st.info("🎯 Você ainda não tem metas financeiras. Crie sua primeira meta!")

def show_ai_insights(finance_manager):
    """Insights inteligentes baseados em IA"""
    monthly_summary = finance_manager.get_monthly_summary()
    budget_status = finance_manager.get_budget_status()
    
    insights = []
    
    # Análise de savings rate
    if monthly_summary['savings_rate'] >= 25:
        insights.append("💰 **Excelente!** Sua taxa de economia está acima de 25% - continue assim!")
    elif monthly_summary['savings_rate'] <= 5:
        insights.append("⚠️ **Atenção!** Sua taxa de economia está muito baixa. Considere reduzir despesas.")
    
    # Análise de orçamentos
    over_budget_count = sum(1 for status in budget_status.values() 
                           if status['status'] == 'over_budget')
    if over_budget_count > 0:
        insights.append(f"🎯 **Otimização necessária:** {over_budget_count} categoria(s) está(ão) acima do orçamento")
    
    # Análise de consistência
    if len(st.session_state.transactions) < 10:
        insights.append("📊 **Dica:** Registre mais transações para obter análises mais precisas")
    
    # Mostrar insights
    for insight in insights:
        st.write(f"- {insight}")

def show_enhanced_recent_transactions(finance_manager):
    """Transações recentes com mais detalhes"""
    transactions = sorted(
        st.session_state.transactions, 
        key=lambda x: x['date'], 
        reverse=True
    )[:15]
    
    if not transactions:
        st.info("💸 Nenhuma transação registrada ainda. Adicione sua primeira transação!")
        return
    
    for transaction in transactions:
        amount_color = "positive" if transaction['type'] == 'Receita' else "negative"
        amount_prefix = "+" if transaction['type'] == 'Receita' else "-"
        recurring_icon = " 🔄" if transaction.get('recurring', False) else ""
        
        col1, col2, col3, col4 = st.columns([4, 2, 1, 1])
        
        with col1:
            st.write(f"**{transaction['description']}**{recurring_icon}")
            st.caption(f"{transaction['category']} • {transaction['date'].strftime('%d/%m/%Y')}")
        
        with col2:
            st.write("")
        
        with col3:
            st.markdown(f"<span class='{amount_color}'>{amount_prefix}R$ {transaction['amount']:,.2f}</span>", 
                       unsafe_allow_html=True)
        
        with col4:
            if st.button("🗑️", key=f"delete_{transaction['id']}"):
                # Implementar deleção
                pass
        
        st.divider()

# =============================================
# FUNÇÕES AUXILIARES PARA GRÁFICOS
# =============================================

def create_income_expense_trend_chart(finance_manager):
    """Cria gráfico de tendência de receitas vs despesas"""
    # Implementação do gráfico
    fig = go.Figure()
    
    # Adicionar dados de exemplo (substituir por dados reais)
    dates = pd.date_range(start='2024-01-01', end='2024-12-01', freq='M')
    income = [5000, 5200, 4800, 5500, 6000, 5800, 6200, 6500, 6300, 6700, 7000, 7200]
    expenses = [4500, 4700, 4600, 4800, 5200, 5100, 5300, 5500, 5400, 5600, 5800, 6000]
    
    fig.add_trace(go.Scatter(x=dates, y=income, name='Receitas', line=dict(color='green')))
    fig.add_trace(go.Scatter(x=dates, y=expenses, name='Despesas', line=dict(color='red')))
    
    fig.update_layout(
        title="Tendência de Receitas vs Despesas",
        xaxis_title="Mês",
        yaxis_title="Valor (R$)",
        height=400
    )
    
    return fig

def create_category_breakdown_chart(finance_manager):
    """Cria gráfico de distribuição por categoria"""
    monthly_summary = finance_manager.get_monthly_summary()
    expense_by_category = monthly_summary['expense_by_category']
    
    if expense_by_category:
        fig = px.pie(
            values=list(expense_by_category.values()),
            names=list(expense_by_category.keys()),
            title="Distribuição de Despesas por Categoria"
        )
        fig.update_layout(height=400)
    else:
        # Gráfico de exemplo quando não há dados
        fig = px.pie(
            values=[100],
            names=['Sem Dados'],
            title="Distribuição de Despesas por Categoria"
        )
        fig.update_layout(height=400)
    
    return fig

# =============================================
# OUTRAS FUNÇÕES DE VISUALIZAÇÃO
# =============================================

def show_notifications(notification_system):
    """Mostra painel de notificações"""
    st.markdown("## 🔔 Notificações")
    
    if not notification_system.notifications:
        st.info("📭 Nenhuma notificação no momento.")
        return
    
    unread_notifications = [n for n in notification_system.notifications if not n['read']]
    read_notifications = [n for n in notification_system.notifications if n['read']]
    
    if unread_notifications:
        st.markdown("### 📨 Não Lidas")
        for notification in unread_notifications:
            show_notification_card(notification, notification_system)
    
    if read_notifications:
        st.markdown("### 📭 Lidas")
        for notification in read_notifications:
            show_notification_card(notification, notification_system)
    
    if st.button("✅ Marcar Todas como Lidas"):
        notification_system.mark_all_read()
        st.rerun()

def show_notification_card(notification, notification_system):
    """Mostra card de notificação individual"""
    col1, col2 = st.columns([4, 1])
    
    with col1:
        st.write(f"**{notification['title']}**")
        st.write(notification['message'])
        st.caption(notification['timestamp'].strftime('%d/%m/%Y %H:%M'))
    
    with col2:
        if not notification['read']:
            if st.button("👁️", key=f"read_{notification['id']}"):
                notification['read'] = True
                st.rerun()

# =============================================
# IMPLEMENTAÇÕES DAS OUTRAS PÁGINAS
# =============================================

def show_advanced_transaction_form(finance_manager):
    """Formulário avançado para transações"""
    with st.form("advanced_transaction_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            transaction_type = st.radio("Tipo de Transação:", ["Receita", "Despesa"], horizontal=True)
            amount = st.number_input("Valor (R$):", min_value=0.0, step=0.01, format="%.2f")
            date = st.date_input("Data:", datetime.now())
            category_options = (finance_manager.categories['Receitas'] 
                              if transaction_type == 'Receita' 
                              else finance_manager.categories['Despesas'])
            category = st.selectbox("Categoria:", category_options)
        
        with col2:
            description = st.text_input("Descrição:")
            tags = st.multiselect("Tags:", ["Essencial", "Opcional", "Investimento", "Lazer"])
            recurring = st.checkbox("Transação Recorrente")
            
            if recurring:
                frequency = st.selectbox("Frequência:", ["Mensal", "Semanal", "Quinzenal", "Anual"])
                end_date = st.date_input("Data Final (opcional):", 
                                       datetime.now() + timedelta(days=365))
        
        notes = st.text_area("Observações (opcional):")
        
        submitted = st.form_submit_button("💾 Salvar Transação")
        
        if submitted:
            if amount > 0 and description:
                transaction = finance_manager.add_transaction(
                    amount=amount,
                    category=category,
                    description=description,
                    transaction_type=transaction_type,
                    date=datetime.combine(date, datetime.min.time()),
                    recurring=recurring,
                    recurring_frequency=frequency if recurring else None
                )
                
                st.success("✅ Transação adicionada com sucesso!")
                
                # Mostrar resumo
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Saldo Atual", f"R$ {finance_manager.get_balance():,.2f}")
                with col2:
                    st.metric("Total de Transações", len(st.session_state.transactions))
                with col3:
                    monthly = finance_manager.get_monthly_summary()
                    st.metric("Economias do Mês", f"R$ {monthly['savings']:,.2f}")
            else:
                st.error("❌ Por favor, preencha todos os campos obrigatórios.")

# ... (implementações das outras funções continuariam aqui)

# =============================================
# EXECUÇÃO PRINCIPAL
# =============================================

if __name__ == "__main__":
    main()
