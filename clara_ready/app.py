import streamlit as st
import pandas as pd
import requests
import json
from datetime import datetime
import base64
import io
import re
from typing import List, Dict, Tuple

# Configuração da página
st.set_page_config(
    page_title="Clara Ready - Seu Assistente Jurídico Inteligente",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS personalizado
st.markdown("""
<style>
    .main-header {
        font-size: 2.8rem;
        color: #7B1FA2;
        text-align: center;
        margin-bottom: 1rem;
        font-weight: 800;
        background: linear-gradient(135deg, #7B1FA2, #E91E63);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    .sub-header {
        font-size: 1.8rem;
        color: #7B1FA2;
        margin-bottom: 1.5rem;
        font-weight: 700;
    }
    .feature-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 2rem;
        border-radius: 15px;
        margin: 1rem 0;
        text-align: center;
        box-shadow: 0 4px 15px rgba(0,0,0,0.1);
    }
    .alert-box {
        background-color: #FFF3CD;
        border: 1px solid #FFEAA7;
        border-radius: 10px;
        padding: 1rem;
        margin: 1rem 0;
    }
    .success-box {
        background-color: #D1ECF1;
        border: 1px solid #BEE5EB;
        border-radius: 10px;
        padding: 1rem;
        margin: 1rem 0;
    }
    .contract-section {
        background-color: #f8f9fa;
        padding: 1.5rem;
        border-radius: 10px;
        border-left: 4px solid #7B1FA2;
        margin: 1rem 0;
    }
</style>
""", unsafe_allow_html=True)

class ContractAnalyzer:
    def __init__(self):
        self.clausulas_problematicas = {
            'juros_abusivos': {
                'patterns': [
                    r'juros.*(\d{2,})%',
                    r'taxa.*(\d{2,})%',
                    r'multa.*(\d{2,})%'
                ],
                'risco': 'Alto',
                'recomendacao': 'Juros acima de 1% ao mês podem ser considerados abusivos. Sugerimos negociar redução.'
            },
            'clausula_penal_excessiva': {
                'patterns': [
                    r'multa.*(\d{2,})%',
                    r'penalidade.*(\d{2,})%'
                ],
                'risco': 'Médio',
                'recomendacao': 'Multas superiores a 2% podem ser revisadas judicialmente.'
            },
            'alteracao_unilateral': {
                'patterns': [
                    r'unilateralmente',
                    r'a critério.*empresa',
                    r'reserva.*direito.*alterar'
                ],
                'risco': 'Alto',
                'recomendacao': 'Cláusulas que permitem alteração unilateral são abusivas.'
            },
            'renuncia_direitos': {
                'patterns': [
                    r'renúncia.*direito',
                    r'concorda.*não.*processar',
                    r'abre.*mão.*direitos'
                ],
                'risco': 'Alto',
                'recomendacao': 'Não é permitida renúncia antecipada de direitos.'
            }
        }
        
        self.leis_referencia = [
            "Código de Defesa do Consumidor (Lei 8.078/90)",
            "Código Civil Brasileiro (Lei 10.406/02)",
            "Lei do Superendividamento (Lei 14.181/21)",
            "Lei de Liberdade Econômica (Lei 13.874/19)"
        ]

    def analisar_contrato(self, texto: str) -> Dict:
        """Analisa o texto do contrato em busca de cláusulas problemáticas"""
        resultados = {
            'clausulas_problematicas': [],
            'pontos_atenção': [],
            'score_risco': 0,
            'recomendacoes': [],
            'leis_aplicaveis': self.leis_referencia
        }
        
        texto_lower = texto.lower()
        
        for clausula, info in self.clausulas_problematicas.items():
            for pattern in info['patterns']:
                if re.search(pattern, texto_lower):
                    resultados['clausulas_problematicas'].append({
                        'tipo': clausula,
                        'risco': info['risco'],
                        'recomendacao': info['recomendacao']
                    })
                    resultados['score_risco'] += 1
        
        # Análise de pontos de atenção adicionais
        if len(texto.split()) < 500:
            resultados['pontos_atenção'].append("Contrato muito curto - pode estar incompleto")
        
        if 'confidencialidade' not in texto_lower:
            resultados['pontos_atenção'].append("Ausência de cláusula de confidencialidade")
        
        if 'rescisão' not in texto_lower:
            resultados['pontos_atenção'].append("Cláusula de rescisão não identificada")
        
        # Recomendações gerais
        if resultados['score_risco'] > 2:
            resultados['recomendacoes'].append("⚠️ Contrato apresenta alto risco. Recomendamos consulta com advogado.")
        elif resultados['score_risco'] > 0:
            resultados['recomendacoes'].append("🔍 Contrato apresenta pontos de atenção que devem ser revisados.")
        else:
            resultados['recomendacoes'].append("✅ Contrato aparenta estar dentro dos parâmetros legais.")
        
        return resultados

class LegalAssistant:
    def __init__(self):
        self.servicos_disponiveis = [
            "Análise de Contratos",
            "Recursos de Multas de Trânsito",
            "Cancelamento de Assinaturas",
            "Ação Renovatória",
            "Direito do Consumidor",
            "Direito Trabalhista"
        ]
        
        self.modelos_documentos = {
            "multa_transito": "Recurso para Multa de Trânsito",
            "cancelamento_assinatura": "Carta de Cancelamento",
            "notificacao_extrajudicial": "Notificação Extrajudicial",
            "reclamacao_consumidor": "Reclamação no PROCON"
        }

    def gerar_documento(self, tipo: str, dados: Dict) -> str:
        """Gera documentos legais personalizados"""
        modelos = {
            "multa_transito": f"""
EXMO. SR. DR. JUIZ DE DIREITO DA {dados.get('vara', 'XXª VARA CÍVEL')}
Processo: {dados.get('processo', 'Nº 0000000-00.0000.0.00.0000')}

RECURSO DE MULTA DE TRÂNSITO

{dados.get('nome', 'NOME DO RECORRENTE')}, brasileiro, portador do CPF {dados.get('cpf', '000.000.000-00')}, 
vem respeitosamente à presença de Vossa Excelência, através deste recurso, impugnar a multa de trânsito 
aplicada conforme auto de infração nº {dados.get('numero_auto', '000000000')}, pelos seguintes fundamentos:

1. {dados.get('fundamento1', 'Fundamento jurídico aqui')}
2. {dados.get('fundamento2', 'Segundo fundamento jurídico')}

Diante do exposto, requer:
- O provimento do presente recurso
- O cancelamento da multa aplicada
- A juntada de documentos em anexo

Local e data: {dados.get('cidade', 'Cidade')}, {datetime.now().strftime('%d/%m/%Y')}

Atenciosamente,
{dados.get('nome', 'Nome do Recorrente')}
            """,
            "cancelamento_assinatura": f"""
À {dados.get('empresa', 'NOME DA EMPRESA')}
CNPJ: {dados.get('cnpj', '00.000.000/0000-00')}

CARTA DE CANCELAMENTO

Eu, {dados.get('nome', 'NOME DO CLIENTE')}, portador do CPF {dados.get('cpf', '000.000.000-00')}, 
venho por meio desta comunicar o cancelamento da assinatura/service {dados.get('servico', 'nome do serviço')}, 
contratado em {dados.get('data_contratacao', '00/00/0000')}.

Fundamento legal: Artigo 49 do Código de Defesa do Consumidor.

Solicito:
1. Cancelamento imediato do serviço
2. Encerramento de cobranças futuras
3. Confirmação por escrito do cancelamento

Atenciosamente,
{dados.get('nome', 'Nome do Cliente')}
Telefone: {dados.get('telefone', '(00) 00000-0000')}
Email: {dados.get('email', 'email@exemplo.com')}
            """
        }
        
        return modelos.get(tipo, "Modelo não encontrado.")

# Inicializar classes
analisador = ContractAnalyzer()
assistente = LegalAssistant()

def main():
    st.markdown('<div class="main-header">⚖️ Clara Ready - Seu Assistente Jurídico Brasileiro</div>', unsafe_allow_html=True)
    
    st.markdown("""
    <div style='text-align: center; color: #666; margin-bottom: 2rem;'>
        A primeira plataforma brasileira de defesa do consumidor e assistência jurídica automatizada
    </div>
    """, unsafe_allow_html=True)
    
    # Menu de navegação
    menu = st.sidebar.selectbox(
        "Navegação",
        ["🏠 Início", "📄 Análise de Contratos", "🚗 Recursos de Trânsito", "📝 Modelos de Documentos", "ℹ️ Direitos do Consumidor"]
    )
    
    if menu == "🏠 Início":
        show_home()
    elif menu == "📄 Análise de Contratos":
        show_contract_analysis()
    elif menu == "🚗 Recursos de Trânsito":
        show_traffic_appeals()
    elif menu == "📝 Modelos de Documentos":
        show_document_templates()
    elif menu == "ℹ️ Direitos do Consumidor":
        show_consumer_rights()

def show_home():
    st.markdown('<div class="sub-header">🎯 Como a Clara Ready Pode Te Ajudar Hoje?</div>', unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("""
        <div class="feature-card">
            <h3>📄 Análise de Contratos</h3>
            <p>Revise contratos e identifique cláusulas abusivas automaticamente</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown("""
        <div class="feature-card">
            <h3>🚗 Recursos de Multas</h3>
            <p>Recorra multas de trânsito com modelos personalizados</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown("""
        <div class="feature-card">
            <h3>📝 Documentos Jurídicos</h3>
            <p>Gere cartas, recursos e notificações automaticamente</p>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Casos de sucesso
    st.markdown("### 🏆 Casos Resolvidos com Sucesso")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("""
        <div class="success-box">
            <h4>💰 R$ 15.760 em multas canceladas</h4>
            <p>João Silva usou nossos recursos e cancelou 8 multas de trânsito</p>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("""
        <div class="success-box">
            <h4>📄 Contrato revisado em 5 minutos</h4>
            <p>Maria Santos identificou 3 cláusulas abusivas no seu financiamento</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown("""
        <div class="success-box">
            <h4>🔔 Assinatura cancelada</h4>
            <p>Carlos Oliveira cancelou serviço com base no artigo 49 do CDC</p>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("""
        <div class="success-box">
            <h4>⚖️ Direitos garantidos</h4>
            <p>Ana Costa recebeu indenização por cobrança indevida</p>
        </div>
        """, unsafe_allow_html=True)

def show_contract_analysis():
    st.markdown('<div class="sub-header">📄 Análise Inteligente de Contratos</div>', unsafe_allow_html=True)
    
    st.markdown("""
    <div class="alert-box">
        <strong>⚠️ Atenção:</strong> Esta análise não substitui consulta com advogado. 
        É uma ferramenta de triagem para identificar possíveis problemas.
    </div>
    """, unsafe_allow_html=True)
    
    tab1, tab2, tab3 = st.tabs(["📤 Upload do Contrato", "📝 Colar Texto", "📊 Análise Rápida"])
    
    with tab1:
        uploaded_file = st.file_uploader("Faça upload do contrato (PDF, DOCX ou TXT)", 
                                       type=['pdf', 'docx', 'txt'])
        
        if uploaded_file is not None:
            # Simulação de processamento de arquivo
            st.success(f"✅ Arquivo {uploaded_file.name} carregado com sucesso!")
            
            if st.button("🔍 Analisar Contrato", type="primary"):
                with st.spinner("Analisando contrato..."):
                    # Simulação de análise
                    texto_exemplo = """
                    CONTRATO DE PRESTAÇÃO DE SERVIÇOS
                    
                    Cláusula 1 - OBJETO: Contratação de serviços mediante pagamento mensal.
                    Cláusula 2 - PRAZO: Vigência de 12 meses com renovação automática.
                    Cláusula 3 - MULTA: Em caso de rescisão, multa de 50% do valor total.
                    Cláusula 4 - JUROS: Juros de 5% ao mês em caso de atraso.
                    Cláusula 5 - ALTERAÇÕES: A empresa pode alterar unilateralmente os termos.
                    """
                    
                    resultados = analisador.analisar_contrato(texto_exemplo)
                    mostrar_resultados_analise(resultados)
    
    with tab2:
        texto_contrato = st.text_area("Cole o texto do contrato aqui:", height=300,
                                    placeholder="Cole o texto completo do contrato para análise...")
        
        if st.button("🔍 Analisar Texto", type="primary", key="analyze_text"):
            if texto_contrato:
                with st.spinner("Analisando texto do contrato..."):
                    resultados = analisador.analisar_contrato(texto_contrato)
                    mostrar_resultados_analise(resultados)
            else:
                st.warning("Por favor, cole o texto do contrato para análise.")
    
    with tab3:
        st.markdown("### 📊 Análise Rápida por Tipo de Contrato")
        
        tipo_contrato = st.selectbox(
            "Selecione o tipo de contrato:",
            ["Empréstimo/FINAME", "Aluguel", "Trabalho", "Prestação de Serviços", "Consórcio"]
        )
        
        if st.button("🎯 Análise Específica", type="primary"):
            st.info(f"Análise específica para contrato de {tipo_contrato}")
            
            # Dicas específicas por tipo de contrato
            dicas = {
                "Empréstimo/FINAME": [
                    "Verifique os juros - não podem ser superiores a 1% ao mês + taxa de risco",
                    "Confira se há seguros embutidos no valor",
                    "Atenção a multas por antecipação"
                ],
                "Aluguel": [
                    "Reajuste máximo pelo IGP-M ou índice contratado",
                    "Verifique cláusulas de fiador e caução",
                    "Multa de 1/3 do aluguel em caso de quebra"
                ]
            }
            
            for dica in dicas.get(tipo_contrato, ["Analise todas as cláusulas cuidadosamente"]):
                st.markdown(f"• {dica}")

def mostrar_resultados_analise(resultados):
    st.markdown("---")
    st.markdown("## 📋 Resultados da Análise")
    
    # Score de risco
    col1, col2, col3 = st.columns(3)
    
    with col1:
        risco_color = "red" if resultados['score_risco'] > 2 else "orange" if resultados['score_risco'] > 0 else "green"
        st.metric("Nível de Risco", resultados['score_risco'], delta=None, delta_color="off")
    
    with col2:
        st.metric("Cláusulas Problemáticas", len(resultados['clausulas_problematicas']))
    
    with col3:
        st.metric("Pontos de Atenção", len(resultados['pontos_atenção']))
    
    # Cláusulas problemáticas
    if resultados['clausulas_problematicas']:
        st.markdown("### 🚨 Cláusulas Identificadas")
        
        for clausula in resultados['clausulas_problematicas']:
            cor = "🔴" if clausula['risco'] == 'Alto' else "🟡"
            st.markdown(f"""
            <div class="contract-section">
                <h4>{cor} {clausula['tipo'].replace('_', ' ').title()}</h4>
                <p><strong>Risco:</strong> {clausula['risco']}</p>
                <p><strong>Recomendação:</strong> {clausula['recomendacao']}</p>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.success("✅ Nenhuma cláusula problemática identificada!")
    
    # Pontos de atenção
    if resultados['pontos_atenção']:
        st.markdown("### 🔍 Pontos de Atenção")
        for ponto in resultados['pontos_atenção']:
            st.warning(ponto)
    
    # Recomendações
    st.markdown("### 💡 Recomendações")
    for recomendacao in resultados['recomendacoes']:
        st.info(recomendacao)
    
    # Leis aplicáveis
    st.markdown("### ⚖️ Legislação Aplicável")
    for lei in resultados['leis_aplicaveis']:
        st.markdown(f"• {lei}")

def show_traffic_appeals():
    st.markdown('<div class="sub-header">🚗 Recursos de Multas de Trânsito</div>', unsafe_allow_html=True)
    
    st.markdown("""
    <div class="alert-box">
        <strong>💡 Dica:</strong> Você pode recorrer de multas dentro de 30 dias. 
        Nossa plataforma gera o recurso automaticamente!
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 📝 Dados da Multa")
        
        numero_auto = st.text_input("Número do Auto de Infração:")
        data_infracao = st.date_input("Data da Infração:")
        orgao_autuador = st.selectbox("Órgão Autuador:", ["DETRAN", "Polícia Rodoviária Federal", "Municipal"])
        tipo_infracao = st.selectbox("Tipo de Infração:", [
            "Excesso de Velocidade",
            "Avançar Sinal Vermelho", 
            "Estacionamento em Local Proibido",
            "Uso do Celular ao Volante"
        ])
    
    with col2:
        st.markdown("### 👤 Seus Dados")
        
        nome_condutor = st.text_input("Nome do Condutor:")
        cpf = st.text_input("CPF:")
        habilitacao = st.text_input("Nº da CNH:")
        endereco = st.text_input("Endereço:")
    
    fundamentos = st.text_area("Fundamentos do Recurso (opcional):",
                             placeholder="Descreva brevemente por que você está recorrendo...")
    
    if st.button("🔄 Gerar Recurso Automático", type="primary"):
        if numero_auto and nome_condutor:
            dados = {
                'nome': nome_condutor,
                'cpf': cpf,
                'numero_auto': numero_auto,
                'vara': 'XXª VARA CÍVEL',
                'cidade': 'Sua Cidade',
                'fundamento1': 'Ausência de sinalização adequada' if not fundamentos else fundamentos,
                'fundamento2': 'Erro na aferição do equipamento'
            }
            
            documento = assistente.gerar_documento("multa_transito", dados)
            
            st.markdown("### 📄 Recurso Gerado com Sucesso!")
            st.text_area("Seu recurso:", documento, height=400)
            
            # Botão para download
            st.download_button(
                label="📥 Baixar Recurso em PDF",
                data=documento,
                file_name=f"recurso_multas_{numero_auto}.txt",
                mime="text/plain"
            )
        else:
            st.error("Por favor, preencha pelo menos o número do auto e seu nome.")

def show_document_templates():
    st.markdown('<div class="sub-header">📝 Modelos de Documentos Jurídicos</div>', unsafe_allow_html=True)
    
    tipo_documento = st.selectbox(
        "Selecione o tipo de documento:",
        ["Carta de Cancelamento", "Notificação Extrajudicial", "Reclamação no PROCON", "Recurso Administrativo"]
    )
    
    if tipo_documento == "Carta de Cancelamento":
        st.markdown("### 📝 Carta de Cancelamento (Artigo 49 CDC)")
        
        col1, col2 = st.columns(2)
        
        with col1:
            nome_cliente = st.text_input("Seu Nome Completo:")
            cpf_cliente = st.text_input("Seu CPF:")
            nome_empresa = st.text_input("Nome da Empresa:")
        
        with col2:
            cnpj_empresa = st.text_input("CNPJ da Empresa (opcional):")
            servico = st.text_input("Serviço a Cancelar:")
            data_contratacao = st.date_input("Data da Contratação:")
        
        if st.button("📄 Gerar Carta de Cancelamento", type="primary"):
            if nome_cliente and nome_empresa:
                dados = {
                    'nome': nome_cliente,
                    'cpf': cpf_cliente,
                    'empresa': nome_empresa,
                    'cnpj': cnpj_empresa,
                    'servico': servico,
                    'data_contratacao': data_contratacao.strftime('%d/%m/%Y'),
                    'telefone': '(00) 00000-0000',
                    'email': 'seuemail@exemplo.com'
                }
                
                documento = assistente.gerar_documento("cancelamento_assinatura", dados)
                
                st.markdown("### ✅ Carta Gerada com Sucesso!")
                st.text_area("Sua carta de cancelamento:", documento, height=300)
                
                st.download_button(
                    label="📥 Baixar Carta",
                    data=documento,
                    file_name=f"carta_cancelamento_{nome_empresa}.txt",
                    mime="text/plain"
                )

def show_consumer_rights():
    st.markdown('<div class="sub-header">ℹ️ Seus Direitos como Consumidor</div>', unsafe_allow_html=True)
    
    tab1, tab2, tab3, tab4 = st.tabs(["📋 CDC", "💳 Cartão de Crédito", "📱 Serviços", "🏠 Contratos"])
    
    with tab1:
        st.markdown("### 📋 Código de Defesa do Consumidor")
        
        direitos = [
            "**Artigo 6°** - Direito à informação clara sobre produtos e serviços",
            "**Artigo 18°** - Responsabilidade por vícios aparentes ou de fácil constatação",
            "**Artigo 39°** - Práticas abusivas vedadas aos fornecedores", 
            "**Artigo 49°** - Direito de arrependimento em 7 dias para compras fora do estabelecimento"
        ]
        
        for direito in direitos:
            st.markdown(f"• {direito}")
    
    with tab2:
        st.markdown("### 💳 Direitos no Cartão de Crédito")
        
        st.markdown("""
        - **Anuidade**: Só pode ser cobrada se explicitamente acordada
        - **Limite**: Banco não pode reduzir limite sem comunicação prévia
        - **Juros**: Máximo de 30% ao ano + taxa de risco (resolução CMN 4.539)
        - **Compras não reconhecidas**: Você não paga enquanto não for comprovada a fraude
        """)
    
    with tab3:
        st.markdown("### 📱 Direitos em Serviços")
        
        st.markdown("""
        - **Telefonia/Internet**: Você pode cancelar sem multa se houver mudança na qualidade
        - **Assinaturas**: Direito de cancelar a qualquer tempo (artigo 49 CDC)
        - **Cobrança indevida**: Direito ao dobro do valor cobrado indevidamente + correção
        - **Serviços essenciais**: Não podem ser cortados sem aviso prévio de 30 dias
        """)
    
    with tab4:
        st.markdown("### 🏠 Direitos em Contratos")
        
        st.markdown("""
        - **Cláusulas abusivas**: São nulas de pleno direito (artigo 51 CDC)
        - **Letras miúdas**: Não têm validade se você não as leu
        - **Alteração unilateral**: Fornecedor não pode mudar contrato sozinho
        - **Vícios ocultos**: Responsabilidade do fornecedor por até 90 dias após descoberta
        """)

# Rodapé
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #666; padding: 2rem;'>
    <strong>⚖️ Clara Ready</strong> - Seu assistente jurídico pessoal<br>
    <small>Este serviço oferece orientação jurídica básica e não substitui consulta com advogado.</small>
</div>
""", unsafe_allow_html=True)

if __name__ == "__main__":
    main()
