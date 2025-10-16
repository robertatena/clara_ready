# app.py — CLARA • Análise de Contratos (v20, single-file)
# Duas páginas (Início + Analisar), UX profissional e leitura robusta (PDF/JPG/PNG/DOCX+OCR)

from __future__ import annotations
import os, io, csv, json, hashlib
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Tuple, List, Optional

import streamlit as st

# ---- módulos locais já existentes no seu projeto ----
from app_modules.pdf_utils import extract_text_from_pdf
from app_modules.analysis import analyze_contract_text, summarize_hits, compute_cet_quick
from app_modules.stripe_utils import init_stripe, create_checkout_session
from app_modules.storage import (
    log_analysis_event, log_subscriber, list_subscribers,
)

# =========================
# Configuração básica
# =========================
APP_TITLE = "CLARA • Análise de Contratos"
VERSION = "v20"

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

# =========================
# Estilos globais (limpos)
# =========================
st.markdown("""
<style>
  .block-container{ padding-top:.8rem }
  .stButton>button{ border-radius:12px; padding:.65rem 1rem; font-weight:600 }
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
def now_iso() -> str:
    return datetime.utcnow().isoformat()

def safe_str(x: Any) -> str:
    try: return str(x)
    except Exception: return ""

def ensure_csv_headers(path: Path, headers: List[str]):
    if not path.exists():
        with path.open("w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(headers)

# =========================
# Pixels (Hotjar/TikTok)
# =========================
def inject_hotjar(hjid: str, hjsv: str="6"):
    if not hjid: return
    st.components.v1.html(f"""
    <script>
    (function(h,o,t,j,a,r){{h.hj=h.hj||function(){{(h.hj.q=h.hj.q||[]).push(arguments)}};h._hjSettings={{hjid:{hjid},hjsv:{hjsv}}};
    a=o.getElementsByTagName('head')[0];r=o.createElement('script');r.async=1;
    r.src=t+h._hjSettings.hjid+j+h._hjSettings.hjsv;a.appendChild(r);}})(window,document,'https://static.hotjar.com/c/hotjar-','.js?sv=');
    </script>
    """, height=0)

def inject_tiktok_pixel(pixel_id: str):
    if not pixel_id: return
    st.components.v1.html(f"""
    <script>
    !function (w, d, t) {{
      w.TiktokAnalyticsObject = t; var ttq = w[t] = w[t] || [];
      ttq.methods = ["page","track","identify","instances","debug","on","off","once","ready","alias","group","enableCookie","disableCookie"];
      ttq.setAndDefer = function(t, e) {{ t[e] = function() {{ t.push([e].concat(Array.prototype.slice.call(arguments,0))) }} }};
      for (var i = 0; i < ttq.methods.length; i++) ttq.setAndDefer(ttq, ttq.methods[i]);
      ttq.load = function(e, n) {{
        var i = "https://analytics.tiktok.com/i18n/pixel/events.js";
        ttq._i = ttq._i || {{}}; ttq._i[e] = []; ttq._i[e]._u = i;
        ttq._t = ttq._t || {{}}; ttq._t[e] = +new Date; ttq._o = ttq._o || {{}};
        var o = document.createElement("script"); o.type = "text/javascript"; o.async = !0; o.src = i + "?sdkid=" + e + "&lib=" + t;
        var a = document.getElementsByTagName("script")[0]; a.parentNode.insertBefore(o, a);
      }};
      ttq.load("{pixel_id}"); ttq.page();
    }}(window, document, 'ttq');
    </script>
    """, height=0)

def ttq_track(event: str, params: Optional[dict] = None):
    if not TIKTOK_PIXEL_ID: return
    try: p = json.dumps(params or {})
    except Exception: p = "{}"
    st.components.v1.html(f"<script>if(window.ttq){{ttq.track('{event}', {p});}}</script>", height=0)

# =========================
# UTM / UA / Referrer (APENAS query_params novos)
# =========================
try:
    from streamlit_js_eval import get_user_agent, get_page_location
except Exception:
    get_user_agent = None; get_page_location = None

def get_utms() -> Dict[str,str]:
    qp = getattr(st, "query_params", {}) or {}
    def pick(k: str) -> str:
        v = qp.get(k, "")
        return v[0] if isinstance(v, list) else (v or "")
    return {k: pick(k) for k in ["utm_source","utm_medium","utm_campaign","utm_content","utm_term"]}

def get_ua_and_referrer() -> Tuple[str,str]:
    ua = ""; ref = ""
    try:
        if get_user_agent: ua = safe_str(get_user_agent())
        if get_page_location:
            loc = get_page_location()
            ref = safe_str(loc.get("href","")) if isinstance(loc, dict) else safe_str(loc)
    except Exception: pass
    return ua, ref

# =========================
# Log de visitas (CSV)
# =========================
VISIT_HEADERS = [
    "ts","session_id","event",
    "utm_source","utm_medium","utm_campaign","utm_content","utm_term",
    "referrer","user_agent",
    "file_name","name","email","phone",
]
ensure_csv_headers(VISITS_CSV, VISIT_HEADERS)

def get_session_id() -> str:
    if "session_id" not in st.session_state:
        st.session_state["session_id"] = hashlib.sha1(os.urandom(24)).hexdigest()
    return safe_str(st.session_state["session_id"])

def log_visit_event(name: str, extra: Optional[Dict[str,str]] = None):
    utm = get_utms(); ua, ref = get_ua_and_referrer()
    row = {
        "ts": now_iso(), "session_id": get_session_id(), "event": name,
        "utm_source": utm.get("utm_source",""), "utm_medium": utm.get("utm_medium",""),
        "utm_campaign": utm.get("utm_campaign",""), "utm_content": utm.get("utm_content",""),
        "utm_term": utm.get("utm_term",""), "referrer": ref, "user_agent": ua,
        "file_name": "", "name": "", "email": "", "phone": "",
    }
    if extra:
        for k in ("file_name","name","email","phone"):
            if k in extra: row[k] = safe_str(extra[k])
    try:
        with VISITS_CSV.open("a", newline="", encoding="utf-8") as f:
            csv.DictWriter(f, fieldnames=VISIT_HEADERS, extrasaction="ignore").writerow(row)
    except Exception as e:
        print(f"[visits.csv] Falha ao gravar visita: {e}")

# =========================
# OCR + Extração robusta
# =========================
_HAS_OCR = True
try:
    import pytesseract  # type: ignore
    from pdf2image import convert_from_bytes  # type: ignore
    from PIL import Image  # type: ignore
except Exception:
    _HAS_OCR = False

try:
    from pypdf import PdfReader  # type: ignore
    _HAS_PYPDF = True
except Exception:
    _HAS_PYPDF = False

def ocr_bytes(data: bytes) -> str:
    if not _HAS_OCR: return ""
    # 1) imagem direta
    try:
        img = Image.open(io.BytesIO(data))
        return pytesseract.image_to_string(img, lang="por+eng")
    except Exception: pass
    # 2) PDF -> imagens
    try:
        pages = convert_from_bytes(data, dpi=300)
        texts = [pytesseract.image_to_string(pg, lang="por+eng") for pg in pages]
        return "\n".join(texts)
    except Exception:
        return ""

def robust_extract_text(data: bytes, filename: Optional[str]=None) -> str:
    # 1) extrator nativo (PDF)
    try:
        txt = extract_text_from_pdf(data) if (filename is None or str(filename).lower().endswith(".pdf")) else ""
        if txt and len(txt.strip()) > 50: return txt
    except Exception: pass
    # 2) pypdf (PDF)
    if _HAS_PYPDF and (filename is None or str(filename).lower().endswith(".pdf")):
        try:
            reader = PdfReader(io.BytesIO(data))
            chunks = []
            for page in reader.pages:
                try: chunks.append(page.extract_text() or "")
                except Exception: pass
            txt = "\n".join(chunks)
            if txt and len(txt.strip()) > 50: return txt
        except Exception: pass
    # 3) arquivo temporário (PDF/DOCX)
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
                import docx2txt  # type: ignore
                txt = docx2txt.process(str(tmp)) or ""
            except Exception: txt = ""
        try: tmp.unlink(missing_ok=True)
        except Exception: pass
        if txt and len(txt.strip()) > 50: return txt
    except Exception: pass
    # 4) OCR
    return ocr_bytes(data)

# =========================
# Pixels + PageView (no load)
# =========================
inject_hotjar(HOTJAR_ID, HOTJAR_SV)
inject_tiktok_pixel(TIKTOK_PIXEL_ID)
log_visit_event("PageView")
ttq_track("PageView", {"value": 1})

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
            # seu init_stripe aceita APENAS 1 argumento
            init_stripe(STRIPE_SECRET_KEY or STRIPE_PUBLIC_KEY)
            if st.button("Assinar CLARA Pro", use_container_width=True):
                url = create_checkout_session(PRICING_PRODUCT_ID)
                if url:
                    st.success("Abrindo checkout…")
                    st.markdown(f"[Ir para o pagamento]({url})")
                    log_visit_event("CheckoutStart"); ttq_track("InitiateCheckout", {"value": 1})
                else:
                    st.error("Não consegui iniciar o checkout agora.")
        except Exception:
            STRIPE_ENABLED = False
            st.warning("Stripe indisponível neste ambiente. Verifique as secrets e o módulo.")
    if not STRIPE_ENABLED:
        st.info("Stripe não configurado ou indisponível neste ambiente.")

    st.divider()
    st.subheader("Admin")
    admin_mode = st.toggle("Exibir painel Admin", value=False)

# =========================
# Cabeçalho + Navegação (duas páginas)
# =========================
st.title(APP_TITLE)
st.caption("Transforme contratos em informação prática — pontos de atenção e CET (quando aplicável).")
nav = st.radio("Navegação", ["Início", "Analisar"], horizontal=True, label_visibility="collapsed")

# =========================
# PÁGINA 1 — Início (landing)
# =========================
if nav == "Início":
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
Milhões assinam documentos legais **sem entender** o que aceitam — colocando **negócios e patrimônio em risco**.
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

    st.markdown("### Como usar\n1) Clique em **Começar agora**  •  2) **Envie** o arquivo  •  3) **Receba** o resumo e os alertas.")
    if st.button("🚀 Começar agora", type="primary"):
        # muda a aba para "Analisar"
        st.session_state["nav_force"] = "Analisar"
        st.rerun()

# =========================
# PÁGINA 2 — Analisar (site em si)
# =========================
if nav == "Analisar" or st.session_state.pop("nav_force", None) == "Analisar":
    st.markdown("### 1) Envie seu contrato")
    st.caption("Formatos: **PDF, JPG, PNG, DOCX**. Para foto/scan, usamos **OCR** automaticamente.")
    uploaded = st.file_uploader("Envie o arquivo (até ~25 MB)",
                                type=["pdf","jpg","jpeg","png","docx"],
                                accept_multiple_files=False)

    if uploaded:
        st.success(f"Arquivo recebido: {uploaded.name}")
        log_visit_event("FileUpload", {"file_name": uploaded.name})
        ttq_track("FileUpload", {"content_type": "contract", "file_name": uploaded.name})

    st.markdown("### 2) Preferências de análise")
    colA, colB, _ = st.columns(3)
    with colA: want_summary = st.checkbox("Resumo amigável", value=True)
    with colB: calc_cet = st.checkbox("Estimar CET (se aplicável)", value=True)

    st.markdown("### 3) Seus dados (para enviarmos o relatório)")
    n1, n2 = st.columns(2)
    with n1:
        user_name  = st.text_input("Nome completo*")
        user_phone = st.text_input("Celular (WhatsApp)*")
    with n2:
        user_email = st.text_input("E-mail*")
        company    = st.text_input("Empresa (opcional)")
    st.caption("Usamos esses dados apenas para enviar seu relatório e contato de suporte.")

    # Form garante clique confiável e validações
    with st.form("form_analisar", clear_on_submit=False):
        submitted = st.form_submit_button("🔎 Analisar agora", type="primary")
        if submitted:
            if not uploaded:
                st.warning("Envie um arquivo antes de analisar."); st.stop()
            if not (user_name and user_email and user_phone):
                st.warning("Preencha **Nome**, **E-mail** e **Celular**."); st.stop()

            with st.status("Lendo e analisando o contrato…", expanded=True) as status:
                status.write("Extraindo texto…")
                data = uploaded.read()
                text = robust_extract_text(data, filename=uploaded.name)

                # Prévia para validar
                if text and len(text.strip()) > 0:
                    preview = (text.strip()[:600] + "…") if len(text.strip()) > 600 else text.strip()
                    with st.expander("Prévia do texto extraído (clique para ver)"):
                        st.text(preview)

                if not text or len(text.strip()) < 50:
                    status.write("Texto curto — aplicando OCR…")
                    text = ocr_bytes(data)

                if not text or len(text.strip()) < 30:
                    st.warning("Não consegui ler o conteúdo. Tente foto mais nítida ou PDF com melhor qualidade.")
                    status.update(label="Leitura falhou", state="error"); st.stop()

                status.write("Rodando análise semântica…")
                try:
                    hits = analyze_contract_text(text)  # sem parâmetro lang
                except Exception as e:
                    st.error(f"Falha na análise: {e}")
                    status.update(label="Análise falhou", state="error"); st.stop()

                summary = summarize_hits(hits) if want_summary else None
                cet_block = None
                if calc_cet:
                    try:
                        cet_block = compute_cet_quick(text)
                    except Exception:
                        cet_block = None

                log_analysis_event(get_session_id(), uploaded.name, len(text))
                log_visit_event("AnalysisCompleted", {"file_name": uploaded.name, "name": user_name, "email": user_email, "phone": user_phone})
                ttq_track("AnalysisCompleted", {"value": 1})
                status.update(label="Análise concluída", state="complete")

            st.markdown("## Resultado da análise")
            if summary:
                st.subheader("Resumo (para humanos)")
                st.write(summary)

            st.subheader("Pontos de atenção")
            st.write(hits)

            if cet_block:
                st.subheader("Estimativa de CET")
                st.write(cet_block)

            st.info("Lembrete: esta ferramenta não substitui aconselhamento jurídico.")

            st.markdown("### Quer receber o PDF do relatório por e-mail?")
            dest = st.text_input("Seu e-mail", key="email_relatorio")
            if st.button("Enviar relatório"):
                if dest and "@" in dest:
                    log_subscriber(dest)
                    log_visit_event("Lead", {"email": dest})
                    st.success("Obrigado! Enviaremos em breve.")
                else:
                    st.warning("Digite um e-mail válido.")

# =========================
# Admin (no sidebar)
# =========================
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

# =========================
# Rodapé / FAQ
# =========================
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
- Você pode bloquear cookies/pixels no seu navegador se preferir.
""")

st.markdown("""
<footer class="clara">
  <small><strong>Disclaimer:</strong> A Clara fornece apoio informativo e <em>não</em> substitui aconselhamento jurídico profissional.</small>
</footer>
""", unsafe_allow_html=True)






