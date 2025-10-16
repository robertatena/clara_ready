# app.py — CLARA • Análise de Contratos (v16)
# "Mobile-first, leitura robusta, medição limpa e duas páginas"
# ----------------------------------------------------------------------------
# Destaques:
# 1) Duas páginas: Landing (Início) e Analisar, com visual profissional
# 2) Extração robusta: pdf_utils -> pypdf -> arquivo temporário -> docx2txt -> OCR
# 3) Métricas: TikTok (PageView/FileUpload/AnalysisCompleted) + Hotjar + CSV visits
# 4) Stripe: init com 1 argumento (compatível), checkout, e fallback seguro
# 5) UX: CTA, validação (nome/email/celular/arquivo), status de progresso, preview do texto
# 6) Admin: funil (PageViews, Uploads, Análises, Leads) + tabela de visitas

from __future__ import annotations

import os
import io
import csv
import json
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Tuple, List, Optional

import streamlit as st

# ---- módulos locais (mantêm sua estrutura) ----
from app_modules.pdf_utils import extract_text_from_pdf
from app_modules.analysis import analyze_contract_text, summarize_hits, compute_cet_quick
from app_modules.stripe_utils import init_stripe, create_checkout_session, verify_checkout_session
from app_modules.storage import (
    init_db,
    log_analysis_event,
    log_subscriber,
    list_subscribers,
    get_subscriber_by_email,
)

# ----------------------------------------------------------------------------
# Configurações
# ----------------------------------------------------------------------------
APP_TITLE = "CLARA • Análise de Contratos"
VERSION = "v16"

st.set_page_config(page_title=APP_TITLE, page_icon="📄", layout="wide")

# Secrets / env
STRIPE_PUBLIC_KEY = st.secrets.get("STRIPE_PUBLIC_KEY", "")
STRIPE_SECRET_KEY = st.secrets.get("STRIPE_SECRET_KEY", "")
PRICING_PRODUCT_ID = st.secrets.get("STRIPE_PRICE_ID", "price_xxx")

TIKTOK_PIXEL_ID = st.secrets.get("TIKTOK_PIXEL_ID", "")  # ex.: TT-XXXXXXX
HOTJAR_ID = st.secrets.get("HOTJAR_ID", "")
HOTJAR_SV = st.secrets.get("HOTJAR_SV", "6")

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)
VISITS_CSV = DATA_DIR / "visits.csv"

# ----------------------------------------------------------------------------
# Estilos globais (limpos e profissionais)
# ----------------------------------------------------------------------------
st.markdown(
    """
<style>
  .block-container { padding-top: 0.8rem; }
  .stButton>button { border-radius: 12px; padding: 0.65rem 1rem; font-weight: 600; }
  .hero{
    padding:32px 22px; border-radius:20px;
    background:linear-gradient(135deg,#f7f7fb 0%, #eef6ff 100%);
    border:1px solid rgba(0,0,0,.06);
    position: relative; overflow:hidden;
  }
  .hero h1{margin:0 0 8px 0; font-size: 2.1rem;}
  .hero p{margin:0; font-size:1.05rem; color:#333}
  .hero .svgwrap{position:absolute; right:-40px; bottom:-40px; opacity:.4}
  .card{
    border:1px solid rgba(0,0,0,.08); border-radius:16px; padding:16px; background:#fff;
    box-shadow: 0 1px 0 rgba(0,0,0,0.02);
  }
  .muted{color:#555}
  footer.clara {margin-top:48px;padding:16px;border-top:1px solid rgba(0,0,0,.06);color:#555}
</style>
""",
    unsafe_allow_html=True,
)

# ----------------------------------------------------------------------------
# Utilidades
# ----------------------------------------------------------------------------
def now_iso() -> str:
    return datetime.utcnow().isoformat()

def ensure_csv_headers(path: Path, headers: List[str]):
    if not path.exists():
        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(headers)

def safe_str(x: Any) -> str:
    try:
        return str(x)
    except Exception:
        return ""

# ----------------------------------------------------------------------------
# Pixels: Hotjar e TikTok
# ----------------------------------------------------------------------------
def inject_hotjar(hjid: str, hjsv: str = "6"):
    if not hjid:
        return
    snippet = f"""
    <script>
      (function(h,o,t,j,a,r){{
          h.hj=h.hj||function(){{(h.hj.q=h.hj.q||[]).push(arguments)}};
          h._hjSettings={{hjid:{hjid},hjsv:{hjsv}}};
          a=o.getElementsByTagName('head')[0];
          r=o.createElement('script');r.async=1;
          r.src=t+h._hjSettings.hjid+j+h._hjSettings.hjsv;
          a.appendChild(r);
      }})(window,document,'https://static.hotjar.com/c/hotjar-','.js?sv=');
    </script>
    """
    st.components.v1.html(snippet, height=0)

def inject_tiktok_pixel(pixel_id: str):
    if not pixel_id:
        return
    pixel = f"""
    <!-- TikTok Pixel -->
    <script>
    !function (w, d, t) {{
      w.TiktokAnalyticsObject = t; var ttq = w[t] = w[t] || [];
      ttq.methods = ["page","track","identify","instances","debug","on","off","once","ready","alias","group","enableCookie","disableCookie"];
      ttq.setAndDefer = function(t, e) {{ t[e] = function() {{ t.push([e].concat(Array.prototype.slice.call(arguments,0))) }} }};
      for (var i = 0; i < ttq.methods.length; i++) ttq.setAndDefer(ttq, ttq.methods[i]);
      ttq.instance = function(t) {{ var e = ttq._i[t] || []; return e.push = ttq.push, e }};
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
    """
    st.components.v1.html(pixel, height=0)

def ttq_track(event: str, params: Optional[dict] = None):
    if not TIKTOK_PIXEL_ID:
        return
    params = params or {}
    try:
        params_json = json.dumps(params)
    except Exception:
        params_json = "{}"
    script = f"""
    <script>
      if (window.ttq) {{ ttq.track("{event}", {params_json}); }}
    </script>
    """
    st.components.v1.html(script, height=0)

# ----------------------------------------------------------------------------
# UTMs, referrer e user agent
# ----------------------------------------------------------------------------
try:
    from streamlit_js_eval import get_user_agent, get_page_location
except Exception:
    get_user_agent = None
    get_page_location = None

def get_utms() -> Dict[str, str]:
    # Streamlit novo: st.query_params; legado: experimental_get_query_params
    qp = getattr(st, "query_params", None)
    if qp is None:
        try:
            qp = st.experimental_get_query_params()
        except Exception:
            qp = {}
    def pick(name: str) -> str:
        v = qp.get(name)
        if isinstance(v, list):
            return v[0]
        return v or ""
    return {
        "utm_source": pick("utm_source"),
        "utm_medium": pick("utm_medium"),
        "utm_campaign": pick("utm_campaign"),
        "utm_content": pick("utm_content"),
        "utm_term": pick("utm_term"),
    }

def get_ua_and_referrer() -> Tuple[str, str]:
    ua, ref = "", ""
    try:
        if get_user_agent:
            ua = get_user_agent()
        if get_page_location:
            loc = get_page_location()
            if isinstance(loc, dict):
                ref = safe_str(loc.get("href", ""))
            else:
                ref = safe_str(loc)
    except Exception:
        pass
    return ua, ref

# ----------------------------------------------------------------------------
# Log de visitas (CSV simples)
# ----------------------------------------------------------------------------
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

def log_visit_event(name: str, extra: Optional[Dict[str, str]] = None):
    extra = extra or {}
    utms = get_utms()
    ua, ref = get_ua_and_referrer()
    row = {
        "ts": now_iso(),
        "session_id": get_session_id(),
        "event": name,
        "utm_source": utms.get("utm_source", ""),
        "utm_medium": utms.get("utm_medium", ""),
        "utm_campaign": utms.get("utm_campaign", ""),
        "utm_content": utms.get("utm_content", ""),
        "utm_term": utms.get("utm_term", ""),
        "referrer": ref,
        "user_agent": ua,
    }
    row.update({k: safe_str(v) for k, v in extra.items() if k not in row})
    try:
        with VISITS_CSV.open("a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=VISIT_HEADERS, extrasaction="ignore")
            writer.writerow(row)
    except Exception as e:
        print(f"[visits.csv] Falha ao gravar visita: {e}")

# ----------------------------------------------------------------------------
# OCR e extração robusta
# ----------------------------------------------------------------------------
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
    if not _HAS_OCR:
        return ""
    # 1) Tenta imagem direta
    try:
        img = Image.open(io.BytesIO(data))
        return pytesseract.image_to_string(img, lang="por+eng")
    except Exception:
        pass
    # 2) PDF -> imagens
    try:
        pages = convert_from_bytes(data, dpi=300)
        texts: List[str] = []
        for pg in pages:
            texts.append(pytesseract.image_to_string(pg, lang="por+eng"))
        return "\n".join(texts)
    except Exception:
        return ""

def robust_extract_text(data: bytes, filename: Optional[str] = None) -> str:
    # 1) extractor nativo (PDF)
    try:
        txt = extract_text_from_pdf(data) if (filename is None or str(filename).lower().endswith(".pdf")) else ""
        if txt and len(txt.strip()) > 50:
            return txt
    except Exception:
        pass
    # 2) pypdf (PDF)
    if _HAS_PYPDF and (filename is None or str(filename).lower().endswith(".pdf")):
        try:
            reader = PdfReader(io.BytesIO(data))
            chunks: List[str] = []
            for page in reader.pages:
                try:
                    chunks.append(page.extract_text() or "")
                except Exception:
                    pass
            txt = "\n".join(chunks)
            if txt and len(txt.strip()) > 50:
                return txt
        except Exception:
            pass
    # 3) temp file: PDF ou DOCX
    try:
        DATA_DIR.mkdir(exist_ok=True)
        suffix = Path(filename).suffix if filename else ".pdf"
        tmp = DATA_DIR / f"_tmp_upload{suffix}"
        tmp.write_bytes(data)
        txt = ""
        if tmp.suffix.lower() == ".pdf":
            try:
                txt = extract_text_from_pdf(str(tmp))
            except Exception:
                txt = ""
        if (not txt or len(txt.strip()) <= 50) and tmp.suffix.lower() == ".docx":
            try:
                import docx2txt  # type: ignore
                txt = docx2txt.process(str(tmp)) or ""
            except Exception:
                txt = ""
        try:
            tmp.unlink(missing_ok=True)
        except Exception:
            pass
        if txt and len(txt.strip()) > 50:
            return txt
    except Exception:
        pass
    # 4) OCR
    return ocr_bytes(data)

# ----------------------------------------------------------------------------
# Hotjar/TikTok + PageView
# ----------------------------------------------------------------------------
inject_hotjar(HOTJAR_ID, HOTJAR_SV)
inject_tiktok_pixel(TIKTOK_PIXEL_ID)
log_visit_event("PageView")
ttq_track("PageView", {"value": 1})

# ----------------------------------------------------------------------------
# Cabeçalho + navegação
# ----------------------------------------------------------------------------
st.title(APP_TITLE)
st.caption("Transforme contratos em informação prática — com pontos de atenção e CET (quando aplicável).")
DEFAULT_TAB = st.session_state.get("__tab__", "Início")
nav = st.radio(
    "Navegação", ["Início", "Analisar"],
    index=0 if DEFAULT_TAB == "Início" else 1,
    horizontal=True, label_visibility="collapsed"
)
st.session_state["__tab__"] = nav

# ----------------------------------------------------------------------------
# Sidebar (Plano/Stripe, Ajuda, Admin)
# ----------------------------------------------------------------------------
with st.sidebar:
    st.header("Plano & Ajuda")
    st.write("Precisa de suporte? Fale com a gente pelo WhatsApp.")

    st.divider()
    st.subheader("Assinatura")
    STRIPE_ENABLED = bool(PRICING_PRODUCT_ID and (STRIPE_SECRET_KEY or STRIPE_PUBLIC_KEY))
    if STRIPE_ENABLED:
        try:
            # Seu módulo aceita 1 argumento (secret se existir; senão public)
            init_stripe(STRIPE_SECRET_KEY or STRIPE_PUBLIC_KEY)
            if st.button("Assinar CLARA Pro", use_container_width=True):
                session_url = create_checkout_session(PRICING_PRODUCT_ID)
                if session_url:
                    st.success("Abrindo checkout…")
                    st.markdown(f"[Ir para o pagamento]({session_url})")
                    log_visit_event("CheckoutStart")
                    ttq_track("InitiateCheckout", {"value": 1})
                else:
                    st.error("Não consegui iniciar o checkout agora. Tente novamente em instantes.")
        except Exception:
            STRIPE_ENABLED = False
            st.warning("Stripe indisponível neste ambiente. Verifique as secrets e o módulo.")
    if not STRIPE_ENABLED:
        st.info("Stripe não configurado ou indisponível neste ambiente.")

    st.divider()
    st.subheader("Admin")
    admin_mode = st.toggle("Exibir painel Admin", value=False)

# ----------------------------------------------------------------------------
# Página: Início (Landing)
# ----------------------------------------------------------------------------
if nav == "Início":
    st.markdown(
        """
<div class="hero">
  <h1>Clara — análise inteligente de contratos</h1>
  <p>Envie um PDF, foto ou DOCX e receba um resumo claro com pontos de atenção. Para contratos de crédito,
  estimamos o CET quando fizer sentido.</p>
  <div class="svgwrap">
    <svg width="220" height="220" viewBox="0 0 200 200" fill="none" xmlns="http://www.w3.org/2000/svg">
      <circle cx="140" cy="140" r="60" stroke="#2E6BFF" stroke-opacity="0.25" stroke-width="6"/>
      <rect x="10" y="40" width="110" height="70" rx="10" stroke="#2E6BFF" stroke-opacity="0.25" stroke-width="6" />
      <path d="M25 55 h80 M25 75 h80 M25 95 h50" stroke="#2E6BFF" stroke-opacity="0.3" stroke-width="6" stroke-linecap="round"/>
    </svg>
  </div>
</div>
""",
        unsafe_allow_html=True,
    )

    st.markdown(
        """
**A frase “Eu li e concordo com os termos e condições” virou símbolo de uma crise silenciosa no Brasil.**
Empresários frequentemente **negligenciam a leitura profunda** dos contratos que assinam e isso os expõe a **vulnerabilidades evitáveis**.
Milhões de brasileiros firmam documentos legais **sem entender completamente** o que estão aceitando — colocando **negócios e patrimônio em risco desnecessário**.
A **Clara** nasceu para reduzir esse risco: transformar contratos em **informação compreensível**, com os alertas certos, antes da decisão.
"""
    )

    st.markdown("### O que a Clara resolve")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown('<div class="card"><strong>Leitura rápida</strong><br/>Lê PDF, foto (OCR) e DOCX. Destaca cláusulas sensíveis.</div>', unsafe_allow_html=True)
    with c2:
        st.markdown('<div class="card"><strong>Transparência</strong><br/>Mostra os <em>trechos</em> que embasam cada alerta, em linguagem simples.</div>', unsafe_allow_html=True)
    with c3:
        st.markdown('<div class="card"><strong>CET em segundos</strong><br/>Para contratos de crédito, estimamos rapidamente o CET, quando aplicável.</div>', unsafe_allow_html=True)

    st.markdown("### Como usar")
    st.markdown("1) Clique em **Começar agora**  •  2) **Envie** o arquivo (PDF/JPG/PNG/DOCX)  •  3) **Receba** o resumo e os alertas.")
    if st.button("🚀 Começar agora", type="primary"):
        st.session_state["__tab__"] = "Analisar"
        st.rerun()

# ----------------------------------------------------------------------------
# Página: Analisar
# ----------------------------------------------------------------------------
if nav == "Analisar":
    st.markdown("### 1) Envie seu contrato")
    st.caption("Formatos: **PDF, JPG, PNG, DOCX**. Se for foto/scan, a Clara usa **OCR** automaticamente.")
    uploaded = st.file_uploader(
        "Envie o arquivo (até ~25 MB)",
        type=["pdf", "jpg", "jpeg", "png", "docx"],
        accept_multiple_files=False
    )

    if uploaded is not None:
        st.success(f"Arquivo recebido: {uploaded.name}")
        log_visit_event("FileUpload", {"file_name": uploaded.name})
        ttq_track("FileUpload", {"content_type": "contract", "file_name": uploaded.name})

        st.markdown("### 2) Preferências de análise")
        cA, cB, cC = st.columns(3)
        with cA:
            want_summary = st.checkbox("Resumo amigável", value=True)
        with cB:
            calc_cet = st.checkbox("Estimar CET (se aplicável)", value=True)
        with cC:
            st.write("")  # espaçador

        st.markdown("### 3) Seus dados (para enviarmos o relatório)")
        n1, n2 = st.columns(2)
        with n1:
            user_name = st.text_input("Nome completo*")
            user_phone = st.text_input("Celular (WhatsApp)*")
        with n2:
            user_email = st.text_input("E-mail*")
            company = st.text_input("Empresa (opcional)")
        st.caption("Usamos esses dados apenas para enviar seu relatório e contato de suporte.")

        # Botão com validação
        can_analyze = bool(user_name and user_email and user_phone and uploaded is not None)
        analyze_clicked = st.button("🔎 Analisar agora", type="primary", disabled=not can_analyze)

        if analyze_clicked:
            with st.status("Lendo e analisando o contrato…", expanded=True) as status:
                status.write("Extraindo texto…")
                data = uploaded.read()
                text = robust_extract_text(data, filename=uploaded.name)

                # Preview curto do texto extraído (qualidade)
                if text and len(text.strip()) > 0:
                    preview = (text.strip()[:600] + "…") if len(text.strip()) > 600 else text.strip()
                    with st.expander("Prévia do texto extraído (clique para ver)"):
                        st.markdown(f"<div class='card'><pre style='white-space:pre-wrap'>{preview}</pre></div>", unsafe_allow_html=True)

                # OCR fallback agressivo se ainda curto
                if not text or len(text.strip()) < 50:
                    if _HAS_OCR:
                        status.write("Arquivo parece imagem/scan. Rodando OCR…")
                        text = ocr_bytes(data)
                    else:
                        status.write("OCR indisponível no ambiente.")

                if not text or len(text.strip()) < 30:
                    st.warning("Não consegui ler o conteúdo. Tente uma foto mais nítida ou um PDF com melhor qualidade.")
                    status.update(label="Leitura falhou", state="error")
                else:
                    status.write("Rodando análise semântica…")
                    try:
                        hits = analyze_contract_text(text)
                    except Exception as e:
                        st.error(f"Falha na análise: {e}")
                        status.update(label="Análise falhou", state="error")
                        hits = None

                    if hits is not None:
                        status.write("Gerando resumo…")
                        summary = summarize_hits(hits) if want_summary else None

                        cet_block = None
                        if calc_cet:
                            try:
                                cet_block = compute_cet_quick(text)
                            except Exception:
                                cet_block = None

                        # Logs de análise
                        log_analysis_event(get_session_id(), uploaded.name, len(text))
                        log_visit_event("AnalysisCompleted", {
                            "file_name": uploaded.name, "name": user_name, "email": user_email, "phone": user_phone
                        })
                        ttq_track("AnalysisCompleted", {"value": 1})

                        status.update(label="Análise concluída", state="complete")

                        # Resultados
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
                        email = st.text_input("Seu e-mail")
                        if st.button("Enviar relatório"):
                            if email and "@" in email:
                                log_subscriber(email)
                                log_visit_event("Lead", {"email": email})
                                st.success("Obrigado! Enviaremos em breve.")
                            else:
                                st.warning("Digite um e-mail válido.")
    else:
        st.info("Dica: se você não tiver o PDF, pode tirar uma **foto nítida** do contrato e enviar em JPG/PNG.")

# ----------------------------------------------------------------------------
# Admin
# ----------------------------------------------------------------------------
if admin_mode:
    st.header("Painel Admin")

    pv = up = ac = ld = 0
    try:
        with VISITS_CSV.open("r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        for r in rows:
            ev = r.get("event", "")
            if ev == "PageView": pv += 1
            elif ev == "FileUpload": up += 1
            elif ev == "AnalysisCompleted": ac += 1
            elif ev == "Lead": ld += 1
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("PageViews", pv)
        m2.metric("Uploads", up)
        m3.metric("Análises", ac)
        m4.metric("Leads", ld)

        st.subheader("Visitas recentes")
        st.dataframe(rows[-200:] if len(rows) > 200 else rows, use_container_width=True)
    except Exception as e:
        st.write("Não consegui abrir o visits.csv ainda.")
        st.write(e)

    st.divider()
    st.subheader("Assinantes (Stripe/Newsletter)")
    try:
        subs = list_subscribers()
        if subs:
            st.dataframe(subs, use_container_width=True)
        else:
            st.caption("Nenhum assinante listado.")
    except Exception:
        st.caption("list_subscribers() indisponível neste ambiente.")

# ----------------------------------------------------------------------------
# Rodapé
# ----------------------------------------------------------------------------
with st.expander("Como funciona a leitura de documentos?"):
    st.markdown(
        """
- Se o PDF tiver **texto** embutido, extraímos diretamente.
- Se for uma **foto** ou **scan**, usamos **OCR** para converter imagem em texto automaticamente.
- Para **.docx**, quando possível, extraímos o texto diretamente.
- Depois, rodamos uma análise semântica que destaca **pontos de atenção** e, se aplicável, estimamos **CET**.
"""
    )

with st.expander("Privacidade"):
    st.markdown(
        """
- Seu arquivo é processado para análise e não é compartilhado.
- Registramos apenas **métricas de uso** (PageView, Upload, Análise) com identificador de sessão anônimo.
- Você pode bloquear cookies/pixels no seu navegador se preferir.
"""
    )

st.markdown(
    """
<footer class="clara">
  <small><strong>Disclaimer:</strong> A Clara fornece apoio informativo e <em>não</em> substitui aconselhamento jurídico profissional.</small>
</footer>
""",
    unsafe_allow_html=True,
)



