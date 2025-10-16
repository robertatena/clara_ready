# app.py — CLARA • Análise de Contratos (v24, single-file, formulário confiável)
from __future__ import annotations
import os, io, csv, json, hashlib, inspect, urllib.parse
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Tuple, List, Optional
import streamlit as st

# ---- módulos locais do seu projeto ----
from app_modules.pdf_utils import extract_text_from_pdf
from app_modules.analysis import analyze_contract_text, summarize_hits, compute_cet_quick
from app_modules.stripe_utils import init_stripe, create_checkout_session
from app_modules.storage import log_analysis_event, log_subscriber, list_subscribers

# =========================
# Config & estilos
# =========================
APP_TITLE = "CLARA • Análise de Contratos"
VERSION = "v24"
st.set_page_config(page_title=APP_TITLE, page_icon="📄", layout="wide")

# Secrets
STRIPE_PUBLIC_KEY = st.secrets.get("STRIPE_PUBLIC_KEY", "")
STRIPE_SECRET_KEY = st.secrets.get("STRIPE_SECRET_KEY", "")
PRICING_PRODUCT_ID = st.secrets.get("STRIPE_PRICE_ID", "price_xxx")
TIKTOK_PIXEL_ID = st.secrets.get("TIKTOK_PIXEL_ID", "")
HOTJAR_ID = st.secrets.get("HOTJAR_ID", "")
HOTJAR_SV = st.secrets.get("HOTJAR_SV", "6")

DATA_DIR = Path("data"); DATA_DIR.mkdir(exist_ok=True)
VISITS_CSV = DATA_DIR / "visits.csv"

st.markdown("""
<style>
  .block-container{ padding-top:.8rem }
  .stButton>button{ border-radius:12px; padding:.7rem 1rem; font-weight:700 }
  .hero{padding:32px 22px;border-radius:20px;background:linear-gradient(135deg,#f7f7fb,#eef6ff);border:1px solid rgba(0,0,0,.06)}
  .hero h1{margin:0 0 8px 0; font-size:2.1rem}
  .hero p{margin:0; font-size:1.05rem; color:#333}
  .cards{ display:grid; gap:16px; grid-template-columns: repeat(3, minmax(0,1fr)); margin-top: 8px }
  @media (max-width:980px){ .cards{ grid-template-columns: 1fr } }
  .card{ background:#fff; border:1px solid #e5e7eb; border-radius:16px; padding:16px; box-shadow: 0 1px 0 rgba(0,0,0,.02) }
  footer.clara{ margin-top:48px; padding:16px; border-top:1px solid #e5e7eb; color:#555 }
</style>
""", unsafe_allow_html=True)

# =========================
# Utilidades
# =========================
def now_iso() -> str: return datetime.utcnow().isoformat()
def safe_str(x: Any) -> str:
    try: return str(x)
    except Exception: return ""

VISIT_HEADERS = [
    "ts","session_id","event",
    "utm_source","utm_medium","utm_campaign","utm_content","utm_term",
    "referrer","user_agent","file_name","name","email","phone",
]
def ensure_csv_headers(path: Path, headers: List[str]):
    if not path.exists():
        with path.open("w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(headers)
ensure_csv_headers(VISITS_CSV, VISIT_HEADERS)

# Pixels (opcional – seguros; não quebram se faltarem secrets)
def inject_hotjar(hjid: str, hjsv: str="6"):
    if not hjid: return
    st.components.v1.html(f"""
    <script>(function(h,o,t,j,a,r){{h.hj=h.hj||function(){{(h.hj.q=h.hj.q||[]).push(arguments)}};h._hjSettings={{hjid:{hjid},hjsv:{hjsv}}};
    a=o.getElementsByTagName('head')[0];r=o.createElement('script');r.async=1;
    r.src=t+h._hjSettings.hjid+j+h._hjSettings.hjsv;a.appendChild(r);}})(window,document,'https://static.hotjar.com/c/hotjar-','.js?sv=');</script>
    """, height=0)
def inject_tiktok_pixel(pixel_id: str):
    if not pixel_id: return
    st.components.v1.html(f"""
    <script>!function (w, d, t) {{
      w.TiktokAnalyticsObject = t; var ttq = w[t] = w[t] || [];
      ttq.methods = ["page","track","identify","instances","debug","on","off","once","ready","alias","group","enableCookie","disableCookie"];
      ttq.setAndDefer = function(t, e) {{ t[e] = function() {{ t.push([e].concat(Array.prototype.slice.call(arguments,0))) }} }};
      for (var i = 0; i < ttq.methods.length; i++) ttq.setAndDefer(ttq, ttq.methods[i]);
      ttq.load = function(e, n) {{ var i = "https://analytics.tiktok.com/i18n/pixel/events.js";
        ttq._i = ttq._i || {{}}; ttq._i[e] = []; ttq._i[e]._u = i; ttq._t = ttq._t || {{}}; ttq._o = ttq._o || {{}};
        var o = d.createElement("script"); o.type = "text/javascript"; o.async = !0; o.src = i + "?sdkid=" + e + "&lib=" + t;
        var a = d.getElementsByTagName("script")[0]; a.parentNode.insertBefore(o, a); }};
      ttq.load("{pixel_id}"); ttq.page(); }}(window, document, 'ttq');</script>
    """, height=0)
def ttq_track(event: str, params: Optional[dict]=None):
    if not TIKTOK_PIXEL_ID: return
    try: p = json.dumps(params or {})
    except Exception: p = "{}"
    st.components.v1.html(f"<script>if(window.ttq){{ttq.track('{event}', {p});}}</script>", height=0)

# UTM/UA/Referrer (API nova)
try:
    from streamlit_js_eval import get_user_agent, get_page_location
except Exception:
    get_user_agent = None; get_page_location = None
def get_utms() -> Dict[str,str]:
    qp = getattr(st, "query_params", {}) or {}
    def pick(k):
        v = qp.get(k, "")
        return v[0] if isinstance(v, list) else (v or "")
    return {k: pick(k) for k in ["utm_source","utm_medium","utm_campaign","utm_content","utm_term"]}
def get_ua_and_referrer() -> Tuple[str,str]:
    ua=""; ref=""
    try:
        if get_user_agent: ua = safe_str(get_user_agent())
        if get_page_location:
            loc = get_page_location()
            ref = safe_str(loc.get("href","")) if isinstance(loc, dict) else safe_str(loc)
    except Exception: pass
    return ua, ref
def get_session_id() -> str:
    if "session_id" not in st.session_state:
        st.session_state["session_id"] = hashlib.sha1(os.urandom(24)).hexdigest()
    return safe_str(st.session_state["session_id"])
def log_visit_event(name: str, extra: Optional[Dict[str,str]]=None):
    utm = get_utms(); ua, ref = get_ua_and_referrer()
    row = {"ts": now_iso(), "session_id": get_session_id(), "event": name,
           "utm_source": utm.get("utm_source",""), "utm_medium": utm.get("utm_medium",""),
           "utm_campaign": utm.get("utm_campaign",""), "utm_content": utm.get("utm_content",""),
           "utm_term": utm.get("utm_term",""), "referrer": ref, "user_agent": ua,
           "file_name": "", "name": "", "email": "", "phone": ""}
    if extra:
        for k in ("file_name","name","email","phone"):
            if k in extra: row[k] = safe_str(extra[k])
    try:
        with VISITS_CSV.open("a", newline="", encoding="utf-8") as f:
            csv.DictWriter(f, fieldnames=VISIT_HEADERS, extrasaction="ignore").writerow(row)
    except Exception as e:
        print(f"[visits.csv] Falha ao gravar visita: {e}")

# OCR & extração
_HAS_OCR = True
try:
    import pytesseract
    from pdf2image import convert_from_bytes
    from PIL import Image
except Exception:
    _HAS_OCR = False
try:
    from pypdf import PdfReader
    _HAS_PYPDF = True
except Exception:
    _HAS_PYPDF = False
def ocr_bytes(data: bytes) -> str:
    if not _HAS_OCR: return ""
    try:
        img = Image.open(io.BytesIO(data))
        return pytesseract.image_to_string(img, lang="por+eng")
    except Exception: pass
    try:
        pages = convert_from_bytes(data, dpi=300)
        return "\n".join([pytesseract.image_to_string(pg, lang="por+eng") for pg in pages])
    except Exception: return ""
def robust_extract_text(data: bytes, filename: Optional[str]=None) -> str:
    try:
        txt = extract_text_from_pdf(data) if (filename is None or str(filename).lower().endswith(".pdf")) else ""
        if txt and len(txt.strip()) > 50: return txt
    except Exception: pass
    if _HAS_PYPDF and (filename is None or str(filename).lower().endswith(".pdf")):
        try:
            reader = PdfReader(io.BytesIO(data))
            txt = "\n".join([(p.extract_text() or "") for p in reader.pages])
            if txt and len(txt.strip()) > 50: return txt
        except Exception: pass
    try:
        suffix = Path(filename).suffix if filename else ".pdf"
        tmp = DATA_DIR / f"_tmp_upload{suffix}"
        tmp.write_bytes(data)
        txt = ""
        if tmp.suffix.lower() == ".pdf":
            try: txt = extract_text_from_pdf(str(tmp))
            except Exception: txt = ""
        if (not txt or len(txt.strip()) <= 50) and tmp.suffix.lower() == ".docx":
            try:
                import docx2txt
                txt = docx2txt.process(str(tmp)) or ""
            except Exception: txt = ""
        try: tmp.unlink(missing_ok=True)
        except Exception: pass
        if txt and len(txt.strip()) > 50: return txt
    except Exception: pass
    return ocr_bytes(data)

# Compat: analyze_contract_text pode pedir ctx
def run_analysis_with_ctx(text: str, ctx: dict):
    try:
        sig = inspect.signature(analyze_contract_text)
        params = list(sig.parameters.keys())
        if len(params) >= 2:
            try: return analyze_contract_text(text, ctx)        # posicional
            except TypeError: return analyze_contract_text(text, ctx=ctx)  # nomeado
        elif "ctx" in params:
            return analyze_contract_text(text, ctx=ctx)
        else:
            return analyze_contract_text(text)
    except TypeError:
        return analyze_contract_text(text)

# =========================
# Pixels + PV
# =========================
inject_hotjar(HOTJAR_ID, HOTJAR_SV)
inject_tiktok_pixel(TIKTOK_PIXEL_ID)
log_visit_event("PageView"); ttq_track("PageView", {"value":1})

# =========================
# Sidebar (Stripe + Admin)
# =========================
with st.sidebar:
    st.header("Plano & Ajuda")
    st.write("Precisa de suporte? Fale com a gente pelo WhatsApp.")
    st.divider()
    st.subheader("Assinatura")
    STRIPE_ENABLED = bool(PRICING_PRODUCT_ID and (STRIPE_SECRET_KEY or STRIPE_PUBLIC_KEY))
    if STRIPE_ENABLED:
        try:
            init_stripe(STRIPE_SECRET_KEY or STRIPE_PUBLIC_KEY)  # apenas 1 argumento
            if st.button("Assinar CLARA Pro", use_container_width=True):
                url = create_checkout_session(PRICING_PRODUCT_ID)
                if url:
                    st.success("Abrindo checkout…")
                    st.markdown(f"[Ir para o pagamento]({url})")
                    log_visit_event("CheckoutStart"); ttq_track("InitiateCheckout", {"value":1})
                else:
                    st.error("Não consegui iniciar o checkout agora.")
        except Exception:
            STRIPE_ENABLED = False
            st.warning("Stripe indisponível neste ambiente.")
    if not STRIPE_ENABLED:
        st.info("Stripe não configurado ou indisponível.")
    st.divider()
    st.subheader("Admin")
    admin_mode = st.toggle("Exibir painel Admin", value=False)

# =========================
# Abas (duas páginas)
# =========================
st.title(APP_TITLE)
st.caption("Transforme contratos em informação prática — pontos de atenção e CET (quando aplicável).")
tab_inicio, tab_analisar = st.tabs(["🏠 Início", "📄 Analisar"])

# ---------- Início
with tab_inicio:
    st.markdown("""
<div class="hero">
  <h1>Clara — análise inteligente de contratos</h1>
  <p>Envie um PDF, foto ou DOCX e receba um resumo claro com pontos de atenção. Para contratos de crédito,
  estimamos o CET quando fizer sentido.</p>
</div>
""", unsafe_allow_html=True)
    st.markdown("""
**A frase “Eu li e concordo com os termos e condições” virou símbolo de uma crise silenciosa no Brasil.**
Empresários frequentemente **negligenciam a leitura profunda** e se expõem a **vulnerabilidades evitáveis**.
Milhões assinam documentos **sem entender** o que aceitam — colocando **negócios e patrimônio em risco**.
A **Clara** nasceu para reduzir esse risco: transformar contratos em **informação compreensível**, com os alertas certos, antes da decisão.
""")
    st.markdown("""
### O que a Clara resolve
<div class="cards">
  <div class="card"><strong>Leitura rápida</strong><br/>Lê PDF, foto (OCR) e DOCX. Destaca cláusulas sensíveis.</div>
  <div class="card"><strong>Transparência</strong><br/>Mostra os <em>trechos</em> que embasam cada alerta, em linguagem simples.</div>
  <div class="card"><strong>CET em segundos</strong><br/>Para contratos de crédito, estimamos rapidamente o CET, quando aplicável.</div>
</div>
""", unsafe_allow_html=True)

# ---------- Analisar (tudo dentro de UM formulário)
with tab_analisar:
    st.markdown("### Faça upload, preencha seus dados e clique em **Analisar agora**")

    with st.form("form_clara_v24", clear_on_submit=False):
        # 1) Upload
        uploaded = st.file_uploader("Arquivo (PDF, JPG, PNG, DOCX) — até ~25 MB",
                                    type=["pdf","jpg","jpeg","png","docx"],
                                    accept_multiple_files=False,
                                    key="upload_file")
        if uploaded:
            st.success(f"Arquivo recebido: {uploaded.name}")

        # 2) Preferências
        cA, cB, _ = st.columns(3)
        with cA: want_summary = st.checkbox("Resumo amigável", value=True, key="pref_sum")
        with cB: calc_cet = st.checkbox("Estimar CET (se aplicável)", value=True, key="pref_cet")

        # 3) Contexto
        col1, col2 = st.columns(2)
        with col1:
            setor = st.selectbox("Setor do contrato*", 
                                 ["Serviços","Tecnologia","Imobiliário","Saúde","Educação","Construção","Financeiro","Varejo","Outro"],
                                 index=0, key="setor")
            papel = st.selectbox("Seu papel no contrato*", 
                                 ["Sou CONTRATANTE (quem contrata/compra)","Sou CONTRATADO (prestador/fornecedor)"],
                                 index=0, key="papel")
        with col2:
            user_name  = st.text_input("Nome completo*", key="u_name")
            user_email = st.text_input("E-mail*", key="u_email")
            user_phone = st.text_input("Celular (WhatsApp)*", key="u_phone")
            company    = st.text_input("Empresa (opcional)", key="u_company")

        # Placeholder para mensagens de validação/resultados do submit
        feedback = st.empty()

        submitted = st.form_submit_button("🔎 Analisar agora", type="primary")
        if submitted:
            errors = []
            if not uploaded: errors.append("Envie um arquivo.")
            if not user_name: errors.append("Informe seu nome.")
            if not user_email or "@" not in user_email: errors.append("E-mail inválido.")
            if not user_phone: errors.append("Informe seu WhatsApp.")
            if errors:
                feedback.error(" • ".join(errors))

            if not errors:
                # métrica
                log_visit_event("FileUpload", {"file_name": uploaded.name})
                ttq_track("FileUpload", {"content_type":"contract","file_name":uploaded.name})

                # leitura dos bytes de forma segura no Streamlit
                data = uploaded.getvalue()

                text_was_ocr = False
                with st.status("Lendo e analisando o contrato…", expanded=True) as status:
                    status.write("Extraindo texto…")
                    text = robust_extract_text(data, filename=uploaded.name)
                    if not text or len(text.strip()) < 50:
                        status.write("Texto curto — aplicando OCR…")
                        text = ocr_bytes(data); text_was_ocr = bool(text)

                    if not text or len(text.strip()) < 30:
                        feedback.warning("Não consegui ler o conteúdo. Tente uma foto mais nítida ou um PDF com melhor qualidade.")
                        status.update(label="Leitura falhou", state="error")
                    else:
                        # contexto para a análise
                        ctx = {
                            "sector": setor,
                            "role": "contratante" if "CONTRATANTE" in papel else "contratado",
                            "user": {"name": user_name, "email": user_email, "phone": user_phone, "company": company},
                            "preferences": {"want_summary": want_summary, "calc_cet": calc_cet, "language": "pt-BR"},
                            "filename": uploaded.name,
                        }
                        text = f"[Contexto: setor={setor}; papel={ctx['role']}; nome={user_name}; empresa={company}]\n\n" + text

                        status.write("Rodando análise semântica…")
                        try:
                            hits = run_analysis_with_ctx(text, ctx)   # <— compatível com ctx
                        except Exception as e:
                            feedback.error(f"Falha na análise: {e}")
                            status.update(label="Análise falhou", state="error")
                            hits = None

                        if hits is not None:
                            summary = summarize_hits(hits) if want_summary else None
                            cet_block = None
                            if calc_cet:
                                try: cet_block = compute_cet_quick(text)
                                except Exception: cet_block = None

                            log_analysis_event(get_session_id(), uploaded.name, len(text))
                            log_visit_event("AnalysisCompleted", {
                                "file_name": uploaded.name, "name": user_name, "email": user_email, "phone": user_phone
                            })
                            ttq_track("AnalysisCompleted", {"value":1})
                            status.update(label="Análise concluída", state="complete")

                            # 🎉 celebração
                            st.balloons()

                            # Resultado
                            st.markdown("## Resultado da análise")
                            if summary:
                                st.subheader("Resumo (para humanos)")
                                st.write(summary)

                            st.subheader("Pontos de atenção")
                            st.write(hits)

                            if cet_block:
                                st.subheader("Estimativa de CET")
                                st.write(cet_block)

                            # Sugestões
                            sugestoes = []
                            if text_was_ocr:
                                sugestoes.append("Envie um **PDF nativo** ou foto em **alta resolução** (300 DPI) para melhorar a leitura.")
                            if calc_cet and (not cet_block):
                                sugestoes.append("Para estimar o **CET**, inclua **valor**, **parcelas**, **taxas/encargos** e **datas**.")
                            if isinstance(hits, (list, tuple)) and len(hits) < 3:
                                sugestoes.append("Poucos pontos detectados; considere **detalhar obrigações, prazos e penalidades**.")
                            if len(text) < 1200:
                                sugestoes.append("O texto está curto; contratos mais completos geram análises melhores.")
                            if sugestoes:
                                st.subheader("Como este contrato pode ficar ainda melhor")
                                st.markdown("\n".join([f"- {s}" for s in sugestoes]))

                            st.info("Lembrete: esta ferramenta não substitui aconselhamento jurídico.")

                            # Relatório
                            relatorio_md = f"""# Relatório CLARA – Análise de Contrato

**Data:** {now_iso()}
**Arquivo:** {uploaded.name}
**Setor:** {setor}
**Papel:** {papel}
**Nome:** {user_name}  •  **E-mail:** {user_email}  •  **WhatsApp:** {user_phone}

---

## Resumo
{summary or "_(Resumo não solicitado.)_"}

## Pontos de atenção
{safe_str(hits)}

## Estimativa de CET
{safe_str(cet_block) if cet_block else "_(Não aplicável ou não calculado.)_"}
"""
                            st.download_button(
                                "⬇️ Baixar relatório (.md)",
                                data=relatorio_md.encode("utf-8"),
                                file_name=f"Relatorio_CLARA_{Path(uploaded.name).stem}.md",
                                mime="text/markdown",
                                use_container_width=True
                            )
                            mailto_body = urllib.parse.quote(relatorio_md)
                            mailto_subj = urllib.parse.quote(f"Relatório CLARA – {uploaded.name}")
                            st.markdown(f"[✉️ Enviar ao advogado (abrir e-mail)](mailto:?subject={mailto_subj}&body={mailto_body})")
                            st.caption("Dica: você também pode baixar o arquivo e anexar ao e-mail.")

# ---------- Admin (sidebar)
if 'admin_mode' in locals() and admin_mode:
    st.header("Painel Admin")
    pv = up = ac = ld = 0
    try:
        with VISITS_CSV.open("r", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        for r in rows:
            ev = r.get("event","")
            if ev == "PageView": pv += 1
            elif ev == "FileUpload": up += 1
            elif ev == "AnalysisCompleted": ac += 1
            elif ev == "Lead": ld += 1
        m1,m2,m3,m4 = st.columns(4)
        m1.metric("PageViews", pv); m2.metric("Uploads", up); m3.metric("Análises", ac); m4.metric("Leads", ld)
        st.subheader("Visitas recentes")
        st.dataframe(rows[-200:] if len(rows) > 200 else rows, use_container_width=True)
    except Exception as e:
        st.write("Não consegui abrir o visits.csv."); st.write(e)

# ---------- Rodapé / FAQ
with st.expander("Como funciona a leitura de documentos?"):
    st.markdown("""
- Se o PDF tiver **texto** embutido, extraímos diretamente.
- Se for uma **foto** ou **scan**, usamos **OCR** automaticamente.
- Para **.docx**, quando possível, extraímos o texto diretamente.
- Depois, rodamos análise semântica para destacar **pontos de atenção** e, se aplicável, **CET**.
""")
with st.expander("Privacidade"):
    st.markdown("""
- Seu arquivo é processado para análise e não é compartilhado.
- Registramos apenas **métricas de uso** (PageView, Upload, Análise) com identificador de sessão anônimo.
""")
st.markdown("""
<footer class="clara">
  <small><strong>Disclaimer:</strong> A Clara fornece apoio informativo e <em>não</em> substitui aconselhamento jurídico profissional.</small>
</footer>
""", unsafe_allow_html=True)





