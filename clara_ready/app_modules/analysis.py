from typing import List, Dict, Any, Tuple
from .rules import RULES

def analyze_contract_text(text: str, ctx: Dict[str, Any]) -> Tuple[List[Dict[str,Any]], Dict[str,Any]]:
    hits: List[Dict[str,Any]] = []
    for rule in RULES:
        for h in rule.check(text, ctx):
            hits.append({
                "title": h.title, "severity": h.severity, "explanation": h.explanation,
                "suggestion": h.suggestion, "evidence": h.evidence
            })
    return hits, {"length": len(text)}

def summarize_hits(hits: List[Dict[str,Any]]) -> Dict[str,Any]:
    if not hits:
        return {"resumo": "Nenhum ponto crítico encontrado.", "gravidade": "Baixa", "criticos": 0}
    criticos = sum(1 for h in hits if h["severity"] == "Alto")
    grav = "Alta" if criticos >= 3 else ("Média" if criticos >= 1 else "Baixa")
    return {"resumo": "Foram encontrados pontos que exigem atenção.", "gravidade": grav, "criticos": criticos}

def compute_cet_quick(P: float, i: float, n: int, fee: float) -> float:
    if P <= 0 or n <= 0: return 0.0
    parcela = (P/n) if i == 0 else P * (i * (1 + i) ** n) / ((1 + i) ** n - 1)
    parcela_aj = parcela + (fee / max(1, n))
    x = i if i > 0 else 0.02
    for _ in range(20):
        vp = sum(parcela_aj / ((1 + x) ** k) for k in range(1, n+1)) - P
        d  = sum(-k * parcela_aj / ((1 + x) ** (k+1)) for k in range(1, n+1))
        x = max(0.0, x - vp / d if d != 0 else x)
    return x
