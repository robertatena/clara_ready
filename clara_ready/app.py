CLARA LAW — DoNotPay-style (Brasil)
Single-file Streamlit app focused on:
- Contract analysis (kept from your structure)
- High-volume consumer flows: cancelar assinatura, cobrança indevida, renegociação/CET, aéreo (ANAC), telecom/utilities (Anatel/agências locais)
- Auto documents (.txt) for Procon/Consumidor.gov and providers
- Savings metric in R$ per case and accumulated
- Premium Stripe hooks (kept)
This file avoids JS comments and weird unicode dashes.
"""
import os, io, re, csv
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Tuple, Set, List

import streamlit as st

# Local modules (same API as your project)
from app_modules.pdf_utils import extract_text_from_pdf
from app_modules.analysis import analyze_contract_text, summarize_hits, compute_cet_quick
from app_modules.stripe_utils import init_stripe, create_checkout_session, verify_checkout_session
from app_modules.storage import init_db, log_analysis_event, log_subscriber, list_subscribers, get_subscriber_by_email

APP_TITLE = "CLARA LAW"
VERSION = "v16.1 (DoNotPay-BR)"
st.set_page_config(page_title=APP_TITLE, page_icon="📄", layout="wide")

# Config
STRIPE_PUBLIC_KEY = st.secrets.get("STRIPE_PUBLIC_KEY", os.getenv("STRIPE_PUBLIC_KEY", ""))
STRIPE_SECRET_KEY = st.secrets.get("STRIPE_SECRET_KEY", os.getenv("STRIPE_SECRET_KEY", ""))
STRIPE_PRICE_ID   = st.secrets.get("STRIPE_PRICE_ID",   os.getenv("STRIPE_PRICE_ID", ""))
BASE_URL          = st.secrets.get("BASE_URL",          os.getenv("BASE_URL", "https://claraready.streamlit.app"))
MONTHLY_PRICE_TEXT = "R$ 9,90/mês"

VISITS_CSV  = Path("/tmp/visitas.csv")
CONSULT_CSV = Path("/tmp/consultas.csv")

st.markdown("""
<style>
:root{ --text:#0f172a; --muted:#475569; --line:#e5e7eb; --bg:#ffffff; --gold:#D4AF37; --sky:#A8D8F0; }
.wrap{ max-width:1140px; margin:0 auto; padding:0 24px; }
.title{ font-size:clamp(32px,6vw,56px); font-weight:800; line-height:1.06; }
.subtitle{ color:#475569; font-size:18px; line-height:1.7; max-width:900px; }
.card{ background:#fff; border:1px solid var(--line); border-radius:16px; padding:18px; }
.soft{ font-size:13px; color:#64748b; }
</style>
""", unsafe_allow_html=True)

# State
if "profile" not in st.session_state: st.session_state.profile = {"nome":"", "email":"", "cel":"", "papel":"Contratante"}
if "premium" not in st.session_state: st.session_state.premium = False
if "free_runs_left" not in st.session_state: st.session_state.free_runs_left = 1
if "savings_total" not in st.session_state: st.session_state.savings_total = 0.0

EMAIL_RE = re.compile(r"^[^\\s@]+@[^\\s@]+\\.[^\\s@]+$")
PHONE_RE = re.compile(r"^\\+?\\d{10,15}$")

def is_valid_email(v: str) -> bool: return bool(EMAIL_RE.match((v or '').strip()))
def is_valid_phone(v: str) -> bool:
    digits = re.sub(r"\\D","", v or "")
    return bool(PHONE_RE.match(digits))

def _parse_admin_emails() -> Set[str]:
    raw = st.secrets.get("admin_emails", os.getenv("ADMIN_EMAILS",""))
    if isinstance(raw, list): return {str(x).strip().lower() for x in raw if str(x).strip()}
    if isinstance(raw, str): return {e.strip().lower() for e in raw.split(",") if e.strip()}
    return set()

ADMIN_EMAILS = _parse_admin_emails()
def current_email() -> str: return (st.session_state.profile.get("email") or "").strip().lower()

def is_premium() -> bool:
    if st.session_state.premium: return True
    email = current_email()
    if not email: return False
    try:
        if get_subscriber_by_email(email):
            st.session_state.premium = True
            return True
    except Exception: pass
    return False

def stripe_diagnostics() -> Tuple[bool, str]:
    miss = []
    if not STRIPE_PUBLIC_KEY: miss.append("STRIPE_PUBLIC_KEY")
    if not STRIPE_SECRET_KEY: miss.append("STRIPE_SECRET_KEY")
    if not STRIPE_PRICE_ID:   miss.append("STRIPE_PRICE_ID")
    if miss: return False, "Configure os segredos: " + ", ".join(miss) + "."
    if STRIPE_PRICE_ID.startswith("prod_"): return False, "Use price_... (não prod_...)."
    if not STRIPE_PRICE_ID.startswith("price_"): return False, "STRIPE_PRICE_ID deve começar com price_..."
    return True, ""

def _ensure_csv(path: Path, header: List[str]):
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(header)

def log_visit(email: str):
    if not (email or "").strip(): return
    _ensure_csv(VISITS_CSV, ["ts_utc","email"])
    with VISITS_CSV.open("a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow([datetime.utcnow().isoformat(), email.strip().lower()])

def log_consultation(payload: Dict[str, Any]):
    _ensure_csv(CONSULT_CSV, ["ts_utc","nome","email","cel","papel","setor","valor_max","texto_len"])
    row = [
        datetime.utcnow().isoformat(),
        st.session_state.profile.get("nome",""),
        st.session_state.profile.get("email",""),
        st.session_state.profile.get("cel",""),
        st.session_state.profile.get("papel",""),
        payload.get("setor",""),
        payload.get("valor_max",""),
        payload.get("texto_len",""),
    ]
    with CONSULT_CSV.open("a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow(row)

@st.cache_resource(show_spinner="Preparando serviços...")
def _boot() -> Tuple[bool, str]:
    try:
        if not STRIPE_SECRET_KEY: return False, "Faltando STRIPE_SECRET_KEY."
        init_stripe(STRIPE_SECRET_KEY)
        init_db()
        return True, ""
    except Exception as e:
        return False, f"Falha ao iniciar serviços: {e}"

ok_boot, boot_msg = _boot()
if not ok_boot:
    st.error(boot_msg); st.stop()

def sidebar_profile():
    st.sidebar.header("Seus dados (opcional)")
    nome  = st.sidebar.text_input("Nome",  value=st.session_state.profile.get("nome",""))
    email = st.sidebar.text_input("E-mail",value=st.session_state.profile.get("email",""))
    cel   = st.sidebar.text_input("Celular",value=st.session_state.profile.get("cel",""))
    papel = st.sidebar.selectbox("Perfil", ["Contratante","Contratado","Outro"],
             index=["Contratante","Contratado","Outro"].index(st.session_state.profile.get("papel","Contratante")))
    if st.sidebar.button("Salvar"):
        errs = []
        if email and not is_valid_email(email): errs.append("E-mail inválido.")
        if cel and not is_valid_phone(cel): errs.append("Celular inválido (somente números, com DDD).")
        if errs: st.sidebar.error(" • ".join(errs))
        else:
            st.session_state.profile = {"nome":nome.strip(),"email":email.strip(),"cel":cel.strip(),"papel":papel}
            try: log_visit(email.strip())
            except Exception: pass
            try:
                if current_email() and get_subscriber_by_email(current_email()):
                    st.session_state.premium = True
            except Exception: pass
            st.sidebar.success("Dados salvos!")

    st.sidebar.markdown("---")
    st.sidebar.caption("© Clara Law 2025")

def premium_card():
    st.markdown("#### Plano Premium")
    st.caption(f"{MONTHLY_PRICE_TEXT} - análises ilimitadas - histórico - suporte prioritário")
    okS, msgS = stripe_diagnostics()
    email = current_email()
    if not email:
        st.info("Salve seu e-mail na barra lateral para assinar. A análise gratuita continua liberada.")
        return
    if st.button("Assinar Premium agora", use_container_width=True):
        if not okS:
            st.error(msgS)
        else:
            try:
                sess = create_checkout_session(
                    price_id=STRIPE_PRICE_ID,
                    customer_email=email,
                    success_url=f"{BASE_URL}?success=true&session_id={{CHECKOUT_SESSION_ID}}",
                    cancel_url=f"{BASE_URL}?canceled=true",
                )
                if sess.get("url"):
                    st.link_button("Abrir checkout seguro", sess["url"], use_container_width=True)
                else:
                    st.error(sess.get("error","Stripe indisponível."))
            except Exception as e:
                st.error(f"Stripe indisponível. Detalhe: {e}")

def handle_checkout_result():
    qs = st.query_params
    if qs.get("success") == "true" and qs.get("session_id"):
        sid = qs["session_id"]
        try:
            ok, payload = verify_checkout_session(sid)
        except Exception as e:
            st.error(f"Não foi possível confirmar o pagamento: {e}")
            ok, payload = False, {}
        if ok:
            try:
                log_subscriber(
                    email=current_email(),
                    name=st.session_state.profile.get("nome",""),
                    stripe_customer_id=(payload.get("customer") or (payload.get("subscription") or {}).get("customer") or ""),
                )
            except Exception: pass
            st.session_state.premium = True
            st.success("Pagamento confirmado! Premium liberado.")
        else:
            st.warning("Não conseguimos confirmar essa sessão. Tente novamente.")
        try: st.query_params.clear()
        except Exception: pass

def hero():
    st.markdown('<div class="wrap">', unsafe_allow_html=True)
    st.markdown('<div class="title">Inteligência para um <span style="color:#A8D8F0">mundo mais claro</span>.</div>', unsafe_allow_html=True)
    st.markdown('<div class="subtitle">Dinheiro que escapa -> a Clara recupera ou evita. Documentos confusos -> a Clara traduz e orienta. Você entende, decide e economiza.</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

# ---- Contract analysis ----
def tab_analise():
    st.subheader("Análise de contrato")
    f = st.file_uploader("PDF do contrato", type=["pdf"])
    raw = ""
    if f:
        with st.spinner("Lendo PDF..."):
            raw = extract_text_from_pdf(f)
    raw = st.text_area("Ou cole o texto do contrato", value=raw or "", height=240)

    c1,c2,c3 = st.columns(3)
    setor = c1.selectbox("Setor", ["Genérico","SaaS/Serviços","Empréstimos","Educação","Plano de saúde"])
    papel = c2.selectbox("Perfil", ["Contratante","Contratado","Outro"])
    valor = c3.number_input("Valor máximo (opcional)", min_value=0.0, step=100.0)

    if st.button("Analisar agora", use_container_width=True):
        if not raw.strip():
            st.warning("Envie ou cole um contrato para analisar.")
            return

        if not is_premium() and st.session_state.free_runs_left <= 0:
            st.info("Você usou sua análise gratuita. Assine o Premium para continuar.")
            return

        with st.spinner("Analisando..."):
            hits, meta = analyze_contract_text(raw, {"setor":setor,"papel":papel,"limite_valor":valor})

        if not is_premium():
            st.session_state.free_runs_left -= 1

        log_analysis_event(email=current_email(), meta={"setor":setor,"papel":papel,"len":len(raw)})
        log_consultation({"setor":setor, "valor_max":valor, "texto_len":len(raw)})

        resume = summarize_hits(hits)
        st.success("Resumo: " + resume["resumo"])
        st.write("Gravidade: **{}** | Pontos críticos: **{}** | Itens: {}".format(resume["gravidade"], resume["criticos"], len(hits)))

        for h in hits:
            with st.expander("{} • {}".format(h["severity"], h["title"]), expanded=False):
                st.write(h.get("explanation",""))
                if h.get("suggestion"):
                    st.markdown("**Como negociar:** " + h["suggestion"])
                if h.get("evidence"):
                    st.text_area("Trecho do contrato (referência)", value=h["evidence"][:800], height=160)

        # Report
        buff = io.StringIO()
        buff.write("{} {}\n".format(APP_TITLE, VERSION))
        buff.write("Usuário: {} <{}> • Papel: {}\n".format(st.session_state.profile.get("nome",""), current_email() or "sem e-mail", papel))
        buff.write("Setor: {} | Valor máx.: {}\n\n".format(setor, valor))
        buff.write("Resumo: {} (Gravidade: {})\n\n".format(resume["resumo"], resume["gravidade"]))
        buff.write("Pontos de atenção:\n")
        for h in hits:
            buff.write("- [{}] {} — {}\n".format(h["severity"], h["title"], h.get("explanation","")))
            if h.get("suggestion"):
                buff.write("  Como negociar: {}\n".format(h["suggestion"]))
        st.download_button("Baixar relatório (.txt)", data=buff.getvalue(), file_name="relatorio_clara.txt", mime="text/plain")

        # CET quick calc
        with st.expander("Calculadora de CET (opcional)", expanded=False):
            P   = st.number_input("Valor principal (R$)", min_value=0.0, step=100.0, key="cet_p")
            i_m = st.number_input("Juros mensais (%)", min_value=0.0, step=0.1, key="cet_i")
            n   = st.number_input("Parcelas (n)", min_value=1, step=1, key="cet_n")
            fee = st.number_input("Taxas fixas totais (R$)", min_value=0.0, step=10.0, key="cet_fee")
            if st.button("Calcular CET", key="btn_calc_cet"):
                cet = compute_cet_quick(P, i_m/100.0, int(n), fee)
                st.success("CET aproximado: {:.2f}% ao mês".format(cet*100.0))

# ---- Flow utils ----
def _tpl_email(assunto: str, corpo: str) -> str:
    nome = st.session_state.profile.get("nome") or "—"
    return "Assunto: {}\n\n{}\n\nAtenciosamente,\n{}".format(assunto, corpo, nome)

def _add_savings(estimativa_rs: float):
    try:
        st.session_state.savings_total = float(st.session_state.savings_total) + float(estimativa_rs or 0.0)
    except Exception:
        pass

def _download_btn(label: str, txt: str, fname: str):
    st.download_button(label, data=txt.encode("utf-8"), file_name=fname, mime="text/plain")

# ---- Flows ----
def flow_cancelamento():
    st.markdown("#### Cancelar assinatura/serviço")
    prest = st.text_input("Prestadora/serviço (ex.: streaming, telefonia)")
    contrato = st.text_input("Contrato/código (opcional)")
    prazo = st.number_input("Prazo desejado para cancelamento (dias corridos)", min_value=1, value=7)
    estimativa = st.number_input("Quanto você economiza por mês ao cancelar? (R$)", min_value=0.0, step=10.0)

    corpo = (
        "Prezados(as),\n\n"
        "Solicito o CANCELAMENTO do serviço/assinatura {p} vinculado ao contrato/código {c}.\n"
        "Peço confirmação por e-mail e a data exata do encerramento, sem multas indevidas, observando o CDC (art. 6 e 39).\n\n"
        "Prazo solicitado: {d} dias corridos.\n"
    ).format(p="({})".format(prest) if prest else "", c=(contrato or "—"), d=prazo)
    email_txt = _tpl_email("Cancelamento de assinatura/serviço — solicitação", corpo)
    _download_btn("Baixar solicitação (.txt)", email_txt, "cancelamento_assinatura.txt")

    if st.button("Registrar economia estimada"):
        _add_savings(estimativa)
        st.success("Economia acumulada: R$ {:.2f}".format(st.session_state.savings_total))

def flow_cobranca_indevida():
    st.markdown("#### Contestação de cobrança indevida")
    empresa = st.text_input("Banco/empresa")
    valor = st.number_input("Valor cobrado indevidamente (R$)", min_value=0.0, step=10.0)
    protocolo = st.text_input("Protocolo do contato (se houver)")
    estimativa = st.number_input("Valor que espera recuperar (R$)", min_value=0.0, step=10.0)

    corpo = (
        "Prezados(as),\n\n"
        "Contesto a cobrança indevida identificada junto à {e}. "
        "Solicito o estorno do valor de R$ {v:.2f} e esclarecimentos.\n"
        "Protocolo (se houver): {p}\n\n"
        "Caso não haja solução em prazo razoável, seguirei com registro no Consumidor.gov/Procon.\n"
    ).format(e=(empresa or "sua empresa"), v=valor, p=(protocolo or "—"))
    email_txt = _tpl_email("Contestação de cobrança indevida — pedido de estorno", corpo)
    _download_btn("Baixar contestação (.txt)", email_txt, "cobranca_indevida.txt")

    if st.button("Registrar recuperação estimada"):
        _add_savings(estimativa)
        st.success("Economia acumulada: R$ {:.2f}".format(st.session_state.savings_total))

def flow_renegociacao():
    st.markdown("#### Renegociação de dívida / Juros")
    empresa = st.text_input("Instituição/empresa")
    desconto = st.slider("Meta de desconto (%)", 5, 60, 20)
    parcelas = st.number_input("Parcelas desejadas", min_value=1, value=6)
    motivo = st.selectbox("Motivo", ["Renda reduzida","Cobrança irregular","Fidelização/Concorrência","Outros"])
    estimativa = st.number_input("Economia mensal prevista após renegociação (R$)", min_value=0.0, step=10.0)

    corpo = (
        "Prezados(as),\n\n"
        "Busco renegociação da fatura/pendência junto à {e}.\n"
        "Proponho: desconto de {d}% e parcelamento em {p}x. Motivo: {m}.\n"
        "Solicito retorno com contraproposta e detalhamento do CET para decisão transparente.\n"
    ).format(e=(empresa or "sua empresa"), d=desconto, p=parcelas, m=motivo)
    email_txt = _tpl_email("Renegociação de fatura — proposta inicial", corpo)
    _download_btn("Baixar proposta (.txt)", email_txt, "renegociacao.txt")

    with st.expander("Calculadora rápida de CET", expanded=False):
        P   = st.number_input("Valor principal (R$)", min_value=0.0, step=100.0, key="cet2_p")
        i_m = st.number_input("Juros mensais (%)", min_value=0.0, step=0.1, key="cet2_i")
        n   = st.number_input("Parcelas (n)", min_value=1, step=1, key="cet2_n")
        fee = st.number_input("Taxas fixas totais (R$)", min_value=0.0, step=10.0, key="cet2_fee")
        if st.button("Calcular CET", key="btn_calc_cet2"):
            cet = compute_cet_quick(P, i_m/100.0, int(n), fee)
            st.success("CET aproximado: {:.2f}% ao mês".format(cet*100.0))

    if st.button("Registrar economia estimada (renegociação)"):
        _add_savings(estimativa)
        st.success("Economia acumulada: R$ {:.2f}".format(st.session_state.savings_total))

def flow_aereo():
    st.markdown("#### Transporte aéreo (ANAC)")
    cia = st.text_input("Companhia aérea")
    problema = st.selectbox("Problema", ["Atraso", "Cancelamento", "Extravio/Dano de bagagem", "Overbooking"])
    voo = st.text_input("Número do voo (opcional)")
    estimativa = st.number_input("Estimativa de reembolso/indenização (R$)", min_value=0.0, step=10.0)

    corpo = (
        "Prezados(as),\n\n"
        "Registro reclamação sobre {prob} com a companhia {cia}. Voo: {voo}.\n"
        "Solicito providências e compensação de acordo com as regras da ANAC.\n"
    ).format(prob=problema, cia=(cia or "sua companhia"), voo=(voo or "—"))
    email_txt = _tpl_email("Reclamação — transporte aéreo (ANAC)", corpo)
    _download_btn("Baixar reclamação (.txt)", email_txt, "anac_reclamacao.txt")

    if st.button("Registrar valor estimado (aéreo)"):
        _add_savings(estimativa)
        st.success("Economia acumulada: R$ {:.2f}".format(st.session_state.savings_total))

def flow_telecom_util():
    st.markdown("#### Telecom (Anatel) e Energia/Água (agências locais)")
    setor = st.selectbox("Setor", ["Telefonia/Internet (Anatel)", "Energia", "Água/Saneamento"])
    empresa = st.text_input("Empresa/operadora")
    descricao = st.text_area("Descreva o problema brevemente")
    estimativa = st.number_input("Estimativa de crédito/estorno (R$)", min_value=0.0, step=10.0)

    corpo = (
        "Prezados(as),\n\n"
        "Relato problema em {setor} junto à {emp}. Descrição: {desc}.\n"
        "Solicito solução e, quando aplicável, estorno/compensação. Em caso de não resolução, seguirei para Anatel/Procon.\n"
    ).format(setor=setor, emp=(empresa or "sua empresa"), desc=(descricao or "—"))
    email_txt = _tpl_email("Reclamação — serviços essenciais", corpo)
    _download_btn("Baixar reclamação (.txt)", email_txt, "servicos_essenciais.txt")

    if st.button("Registrar economia estimada (serviços)"):
        _add_savings(estimativa)
        st.success("Economia acumulada: R$ {:.2f}".format(st.session_state.savings_total))

def flows_section():
    st.subheader("Casos campeões (rápidos)")
    st.caption("Perguntas simples, upload opcional, documento pronto. Medimos a economia recuperada.")

    t1, t2, t3 = st.tabs(["Assinaturas", "Cobrança/Juros", "Aéreo/Serviços"])
    with t1: flow_cancelamento()
    with t2:
        col1, col2 = st.columns(2)
        with col1: flow_cobranca_indevida()
        with col2: flow_renegociacao()
    with t3:
        col3, col4 = st.columns(2)
        with col3: flow_aereo()
        with col4: flow_telecom_util()

    st.info("Economia/recuperação acumulada: R$ {:.2f}".format(st.session_state.savings_total))

def main():
    hero()
    sidebar_profile()
    handle_checkout_result()

    tabs = st.tabs(["Análise de Contrato", "Casos Campeões", "Premium/Admin"])
    with tabs[0]: tab_analise()
    with tabs[1]: flows_section()
    with tabs[2]: premium_card()

    st.markdown("---")
    st.markdown('<div class="soft">A Clara orienta com linguagem simples e não substitui a atuação profissional de advogados(as).</div>', unsafe_allow_html=True)

if __name__ == "__main__":
    main()
