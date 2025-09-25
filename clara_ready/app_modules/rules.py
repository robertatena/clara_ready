from dataclasses import dataclass
from typing import List, Dict, Any

@dataclass
class RuleHit:
    title: str
    severity: str  # "Alto", "Médio", "Baixo"
    explanation: str
    suggestion: str = ""
    evidence: str = ""

@dataclass
class ContractRule:
    name: str
    description: str
    sector: str        # "Genérico", "Empréstimos", "Educação", "Plano de saúde", "SaaS/Serviços"
    applies_to: str    # "Contratante", "Contratado", "Ambos"
    keywords_any: List[str]
    keywords_all: List[str] = None
    severity: str = "Médio"
    suggestion: str = ""
    evidence_snippet: bool = True

    def check(self, text: str, ctx: Dict[str, Any]) -> List[RuleHit]:
        t = text.lower()
        if self.sector != "Genérico" and self.sector != ctx.get("setor", "Genérico"):
            return []
        perfil = ctx.get("papel", "Outro")
        if self.applies_to != "Ambos" and self.applies_to != perfil:
            return []
        if self.keywords_all:
            for kw in self.keywords_all:
                if kw.lower() not in t:
                    return []
        if not any(kw.lower() in t for kw in self.keywords_any):
            return []
        evidence = ""
        if self.evidence_snippet:
            for kw in self.keywords_any:
                pos = t.find(kw.lower())
                if pos != -1:
                    start = max(0, pos - 120)
                    end = min(len(text), pos + 200)
                    evidence = text[start:end]
                    break
        return [RuleHit(
            title=self.name,
            severity=self.severity,
            explanation=self.description,
            suggestion=self.suggestion,
            evidence=evidence
        )]

RULES: List[ContractRule] = [
    # GENÉRICAS
    ContractRule(
        name="Multas desproporcionais",
        description="Penalidades elevadas, sem teto, podem ser desproporcionais. Preste atenção no percentual/valor, gatilhos e prazo de correção.",
        sector="Genérico", applies_to="Ambos",
        keywords_any=["multa", "penalidad", "penalty", "cláusula penal"],
        severity="Alto",
        suggestion="Negocie teto (ex.: 10% do valor do contrato) e período de correção (ex.: 5 dias úteis)."
    ),
    ContractRule(
        name="Renovação automática sem aviso claro",
        description="Renovações tácitas exigem comunicação prévia e canal simples de cancelamento.",
        sector="Genérico", applies_to="Ambos",
        keywords_any=["renovação automática", "renovacao automatica", "renovação tácita", "tácita"],
        severity="Médio",
        suggestion="Peça aviso com 30 dias de antecedência e e-mail/canal claro para cancelar."
    ),
    ContractRule(
        name="Foro exclusivo desfavorável",
        description="Foro muito distante encarece a defesa. Negocie foro no domicílio do contratante/consumidor.",
        sector="Genérico", applies_to="Contratante",
        keywords_any=["foro", "comarca", "juízo", "juizo"],
        severity="Médio",
        suggestion="Foro do domicílio do contratante ou mediação prévia."
    ),
    ContractRule(
        name="Arbitragem obrigatória sem opção",
        description="Arbitragem obrigatória pode ser cara; sem opção judicial, o consumidor perde alternativas.",
        sector="Genérico", applies_to="Contratante",
        keywords_any=["arbitragem", "câmara arbitral", "camera arbitral"],
        severity="Médio",
        suggestion="Prever opção judicial e custeio equilibrado das taxas."
    ),
    ContractRule(
        name="Cessão/transferência sem consentimento",
        description="Cessão ampla do contrato sem consentimento traz riscos com terceiros.",
        sector="Genérico", applies_to="Contratante",
        keywords_any=["cessão", "cessao", "transferência", "transferencia", "cessionário"],
        severity="Médio",
        suggestion="Exigir consentimento prévio por escrito."
    ),
    ContractRule(
        name="Exclusividade rígida",
        description="Exclusividade impede contratar outros fornecedores e pode ter multa de saída.",
        sector="Genérico", applies_to="Contratante",
        keywords_any=["exclusividade", "exclusivo"],
        severity="Médio",
        suggestion="Restringir escopo/tempo e evitar multa excessiva."
    ),
    ContractRule(
        name="Limitação de responsabilidade excessiva",
        description="Limitações muito restritivas podem inviabilizar reparação justa.",
        sector="Genérico", applies_to="Contratante",
        keywords_any=["isento de responsabilidade", "não se responsabiliza", "limitação de responsabilidade", "limitacao de responsabilidade"],
        severity="Alto",
        suggestion="Exceções para dolo/culpa grave e limite razoável (ex.: 100% do contrato)."
    ),
    ContractRule(
        name="Propriedade intelectual ampla/perpétua",
        description="Cessões amplas e perpétuas podem transferir indevidamente criações/dados.",
        sector="Genérico", applies_to="Contratante",
        keywords_any=["propriedade intelectual", "direitos autorais", "cessão perpétua", "licença perpétua"],
        severity="Médio",
        suggestion="Finalidade/escopo/prazo restritos; considerar licença não exclusiva."
    ),
    ContractRule(
        name="Não-solicitação/Não-competição desequilibrada",
        description="Restrições extensas de prazo/território podem inviabilizar negócios.",
        sector="Genérico", applies_to="Ambos",
        keywords_any=["não solicitação", "nao solicitacao", "não competição", "nao competicao", "non-compete", "non solicit"],
        severity="Médio",
        suggestion="Limitar a 12–24 meses e escopo claro."
    ),
    ContractRule(
        name="Rescisão unilateral sem justa causa clara",
        description="Rescisão a qualquer tempo sem critérios gera insegurança.",
        sector="Genérico", applies_to="Contratante",
        keywords_any=["rescisão", "rescisao", "denúncia", "denuncia", "unilateral"],
        severity="Médio",
        suggestion="Aviso prévio + hipóteses objetivas; proporcionalidade de pagamentos."
    ),
    ContractRule(
        name="Confidencialidade sem LGPD/terceiros",
        description="Cláusula de sigilo sem LGPD e sem regra para subcontratados pode expor dados.",
        sector="Genérico", applies_to="Ambos",
        keywords_any=["confidencial", "sigilo", "lgpd", "dados pessoais", "dado pessoal"],
        severity="Alto",
        suggestion="Bases legais, DPA e obrigações a terceiros/subprocessadores."
    ),

    # SaaS/Serviços
    ContractRule(
        name="SLA ausente ou vago",
        description="Sem SLA não há garantia de disponibilidade/tempo de resposta.",
        sector="SaaS/Serviços", applies_to="Contratante",
        keywords_any=["sla", "nível de serviço", "nivel de servico", "disponibilidade", "uptime"],
        severity="Médio",
        suggestion="Uptime (ex.: 99,5%), tempos de resposta e créditos/multas."
    ),
    ContractRule(
        name="Lock-in com multa de saída",
        description="Períodos mínimos longos + multa dificultam troca de fornecedor.",
        sector="SaaS/Serviços", applies_to="Contratante",
        keywords_any=["período mínimo", "periodo minimo", "fidelidade", "multa de cancelamento"],
        severity="Médio",
        suggestion="Ofertar mensal/anual e multa proporcional e razoável."
    ),

    # Empréstimos
    ContractRule(
        name="Juros/CET acima do divulgado",
        description="Divergência entre taxa divulgada e efetiva indica custo total maior.",
        sector="Empréstimos", applies_to="Contratante",
        keywords_any=["juros", "cet", "custo efetivo total", "taxa"],
        severity="Alto",
        suggestion="Planilha CET completa e comparação independente."
    ),
    ContractRule(
        name="Vencimento antecipado amplo",
        description="Gatilhos genéricos aumentam risco de execução.",
        sector="Empréstimos", applies_to="Contratante",
        keywords_any=["vencimento antecipado", "antecipação de vencimento", "vencimento imediato"],
        severity="Alto",
        suggestion="Hipóteses objetivas + prazo de cura (ex.: 5 dias úteis)."
    ),
    ContractRule(
        name="Garantias sem liberação",
        description="Sem regra de baixa após quitação, o gravame pode persistir.",
        sector="Empréstimos", applies_to="Contratante",
        keywords_any=["garantia", "aval", "alienação fiduciária", "alienacao fiduciaria", "hipoteca"],
        severity="Médio",
        suggestion="Liberação automática na quitação e custos de baixa pelo credor."
    ),

    # Educação
    ContractRule(
        name="Reajuste sem índice claro",
        description="Reajuste exige índice oficial e fórmula transparente.",
        sector="Educação", applies_to="Ambos",
        keywords_any=["reajuste", "índice", "indice", "ipca", "igpm"],
        severity="Médio",
        suggestion="Fixar índice (IPCA/IGP-M), periodicidade e aviso."
    ),
    ContractRule(
        name="Cobrança por inadimplência desproporcional",
        description="Encargos por atraso acima do razoável oneram o contratante.",
        sector="Educação", applies_to="Contratante",
        keywords_any=["mora", "multa por atraso", "juros de mora", "correção", "correcao"],
        severity="Médio",
        suggestion="Multa 2% + juros 1% a.m. + correção legal (parâmetros usuais)."
    ),

    # Plano de saúde
    ContractRule(
        name="Carências e exclusões extensas",
        description="Carências longas e exclusões importantes comprometem a cobertura.",
        sector="Plano de saúde", applies_to="Contratante",
        keywords_any=["carência", "carencia", "exclusão", "exclusoes", "cobertura"],
        severity="Médio",
        suggestion="Comparar prazos máximos e garantir coberturas essenciais."
    ),
    ContractRule(
        name="Reembolso/rede credenciada pouco claros",
        description="Sem regras claras, reembolso pode ser baixo ou demorado.",
        sector="Plano de saúde", applies_to="Contratante",
        keywords_any=["reembolso", "rede credenciada", "credenciada"],
        severity="Médio",
        suggestion="Definir percentuais, prazos e canais de atendimento."
    ),

    # LGPD/Dados
    ContractRule(
        name="Compartilhamento com terceiros sem base legal",
        description="Compartilhar dados com terceiros sem base legal/contratos adequados viola a LGPD.",
        sector="Genérico", applies_to="Ambos",
        keywords_any=["terceiro", "subprocessador", "subcontratado", "compartilhamento de dados"],
        severity="Alto",
        suggestion="Base legal, DPA/adição contratual e auditoria de terceiros."
    ),
    ContractRule(
        name="Retenção de dados indefinida",
        description="Guardar dados por prazo indefinido aumenta riscos.",
        sector="Genérico", applies_to="Ambos",
        keywords_any=["retenção de dados", "retencao de dados", "prazo de guarda", "armazenamento"],
        severity="Médio",
        suggestion="Definir prazos por finalidade e regras de eliminação/anonimização."
    ),
]
