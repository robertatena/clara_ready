# app.py — CLARA • Análise de Contratos (v15)
# "Mobile‑first, medição certa e observabilidade de visitas"
# ----------------------------------------------------------------------------
# O QUE MUDOU NESTA VERSÃO
# 1) Medição: TikTok Pixel (pageview + eventos FileUpload/AnalysisCompleted) e Hotjar fix
# 2) UX mobile: botões grandes, contraste, mensagens claras, barra de progresso
# 3) OCR automático: imagem/PDF escaneado vira texto (pytesseract/pdf2image), sem pedir "copiar e colar"
# 4) UTM/referrer e log de visitas: grava em CSV (visits.csv) com session_id, horários,
#    utm_source/medium/campaign/content, referrer, user_agent (via streamlit_js_eval se disponível)
# 5) Mini‑dashboard de funil: PageViews, Uploads, Análises e Leads no Admin
# 6) Mantém Stripe checkout/verify, compute_cet_quick, summarize_hits, logs de análise e assinantes
# ----------------------------------------------------------------------------

from __future__ import annotations

import os
import io
import re
import csv
import json
import time
import uuid
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Tuple, Set, List, Optional

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
# Configs
# ----------------------------------------------------------------------------
APP_TITLE = "CLARA • Análise de Contratos"
VERSION = "v15"

st.set_page_config(page_title=APP_TITLE, page_icon="📄", layout="wide")

# Secrets / env
STRIPE_PUBLIC_KEY = st.secrets.get("STRIPE_PUBLIC_KEY", "")
STRIPE_SECRET_KEY = st.secrets.get("STRIPE_SECRET_KEY", "")
PRICING_PRODUCT_ID = st.secrets.get("STRIPE_PRICE_ID", "price_xxx")

TIKTOK_PIXEL_ID = st.secrets.get("TIKTOK_PIXEL_ID", "")  # ex.: TT-XXXXXXX
HOTJAR_ID = st.secrets.get("HOTJAR_ID", "6519667")
HOTJAR_SV = st.secrets.get("HOTJAR_SV", "6")

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)
VISITS_CSV = DATA_DIR / "visits.csv"

# ----------------------------------------------------------------------------
# Utilidades gerais
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
# Injeções: Hotjar e TikTok Pixel (sem aparecer na tela)
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
# Captura de UTM/referrer/UA (sem depender do servidor)
# ----------------------------------------------------------------------------
# - UTMs: via st.query_params
# - Referrer/UserAgent: tenta via streamlit_js_eval; se não houver, registra vazio

try:
    from streamlit_js_eval import get_user_agent, get_page_location
except Exception:
    get_user_agent = None
    get_page_location = None


def get_utms() -> Dict[str, str]:
    qp = getattr(st, "query_params", None)
    # Compatibilidade com versões antigas do Streamlit
    if qp is None:
        try:
            qp = st.experimental_get_query_params()
        except Exception:
            qp = {}
    # query_params pode ser Mapping -> valores lista
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
    "ts",
    "session_id",
    "event",
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_content",
    "utm_term",
    "referrer",
    "user_agent",
    "file_name",
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
            writer = csv.DictWriter(f, fieldnames=VISIT_HEADERS)
            writer.writerow(row)
    except Exception as e:
        # streamlit não tem st.debug; usamos print silencioso para logs de servidor
        print(f"[visits.csv] Falha ao gravar visita: {e}")


# ----------------------------------------------------------------------------
# OCR automático (fallback)
# ----------------------------------------------------------------------------
# Tenta importar dependências. Se não existirem, o app continua sem OCR.

_HAS_OCR = True
try:
    import pytesseract  # type: ignore
    from pdf2image import convert_from_bytes  # type: ignore
    from PIL import Image  # type: ignore
except Exception:
    _HAS_OCR = False


def ocr_bytes(data: bytes) -> str:
    if not _HAS_OCR:
        return ""
    # 1) Tenta abrir como imagem direta (JPG/PNG)
    try:
        img = Image.open(io.BytesIO(data))
        return pytesseract.image_to_string(img, lang="por+eng")
    except Exception:
        pass
    # 2) Caso seja PDF → converter páginas e extrair
    try:
        pages = convert_from_bytes(data, dpi=300)
        texts: List[str] = []
        for pg in pages:
            texts.append(pytesseract.image_to_string(pg, lang="por+eng"))
        return "\n".join(texts)
    except Exception:
        return ""


# ----------------------------------------------------------------------------
# UI/Estilos (contraste e legibilidade no mobile)
# ----------------------------------------------------------------------------

CSS_STYLE = """
<style>
  .block-container { padding-top: 0.6rem; }
  div[data-testid="stFileUploader"] {
    border: 1px solid rgba(0,0,0,0.12);
    border-radius: 12px; padding: 12px; background: rgba(0,0,0,0.02);
  }
  .muted { color: #666; font-size: 0.9rem; }
  .caption { color: #444; font-size: 0.82rem; }
  .ok-badge { display:inline-block; padding: 4px 8px; border-radius: 999px; background: #e6f4ea; }
  .warn-badge { display:inline-block; padding: 4px 8px; border-radius: 999px; background: #fff7e6; }
  .error-badge { display:inline-block; padding: 4px 8px; border-radius: 999px; background: #fdecea; }
  .cta { font-weight: 600; }
</style>
"""

st.markdown(CSS_STYLE, unsafe_allow_html=True)


# ----------------------------------------------------------------------------
# Layout topo com navegação simples
# ----------------------------------------------------------------------------

st.title(APP_TITLE)

# Navegação (Início / Analisar) — traz de volta a página inicial explicativa
DEFAULT_TAB = st.session_state.get("__tab__", "Início")
nav = st.radio("", ["Início", "Analisar"], index=0 if DEFAULT_TAB=="Início" else 1, horizontal=True)
st.session_state["__tab__"] = nav

if nav == "Início":
    # Hero profissional com copy clara sobre o problema que a Clara resolve
    st.markdown(
        """
        <style>
            .hero{padding:28px 22px;border-radius:16px;background:linear-gradient(135deg,#f7f7fb,#eef6ff);border:1px solid rgba(0,0,0,.06);}
            .hero h1{margin:0 0 8px 0; font-size: 2.0rem;}
            .hero p{margin:0; font-size:1.02rem; color:#333}
            .card{border:1px solid rgba(0,0,0,.08);border-radius:14px;padding:14px;background:#fff}
        </style>
        <div class=\"hero\">
            <h1>Clara — análise inteligente de contratos</h1>
            <p>Envie um PDF ou foto e receba, em segundos, um resumo claro com pontos de atenção e, quando fizer sentido, a estimativa de CET.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Copy solicitada — crise silenciosa
    st.markdown(
        """
        **A frase “Eu li e concordo com os termos e condições” virou símbolo de uma crise silenciosa no Brasil.**
        Empresários frequentemente **negligenciam a leitura profunda** dos contratos que assinam e isso os expõe a **vulnerabilidades evitáveis**.
        Milhões de brasileiros firmam documentos legais **sem entender completamente** o que estão aceitando — colocando **negócios e patrimônio em risco desnecessário**.
        A **Clara** nasceu para reduzir esse risco: transformar contratos em **informação compreensível**, com os alertas certos, antes da decisão.
        """
    )

    st.markdown("### O que a Clara resolve")
    colh1, colh2, colh3 = st.columns(3)
    with colh1:
        st.markdown("""
        <div class=\"card\"><strong>Leitura rápida</strong><br/>Extrai o texto do PDF ou foto (OCR automático) e identifica cláusulas sensíveis.</div>
        """, unsafe_allow_html=True)
    with colh2:
        st.markdown("""
        <div class=\"card\"><strong>Transparência</strong><br/>Mostra os <em>trechos</em> que embasam cada ponto de atenção em linguagem simples.</div>
        """, unsafe_allow_html=True)
    with colh3:
        st.markdown("""
        <div class=\"card\"><strong>CET em segundos</strong><br/>Para contratos de crédito, estimamos rapidamente o CET quando aplicável.</div>
        """, unsafe_allow_html=True)

    st.markdown("### Como usar")
    st.markdown("1) Clique em **Começar agora**  •  2) **Envie** o contrato (PDF/JPG/PNG)  •  3) **Receba** o resumo e os alertas.")

    if st.button("🚀 Começar agora", type="primary"):
        st.session_state["__tab__"] = "Analisar"
        st.experimental_rerun()

# Injeta medições no início

inject_hotjar(HOTJAR_ID, HOTJAR_SV)
inject_tiktok_pixel(TIKTOK_PIXEL_ID)

# Loga pageview imediatamente
log_visit_event("PageView")

# Também registra PageView no TikTok
ttq_track("PageView", {"value": 1})


# ----------------------------------------------------------------------------
# Sidebar: Plano/Stripe, Ajuda e Admin
# ----------------------------------------------------------------------------

with st.sidebar:
    st.header("Plano & Ajuda")
    st.write("Se precisar de ajuda, fale com a gente pelo WhatsApp.")

    st.divider()
    st.subheader("Assinatura")

    # Inicialização segura do Stripe (não quebra a aplicação se faltar secret ou a assinatura mudar)
    STRIPE_ENABLED = bool(PRICING_PRODUCT_ID and (STRIPE_SECRET_KEY or STRIPE_PUBLIC_KEY))
    if STRIPE_ENABLED:
        try:
            # Tenta assinatura antiga (1 arg) primeiro — evita TypeError:
            try:
                init_stripe(STRIPE_SECRET_KEY or STRIPE_PUBLIC_KEY)
            except TypeError:
                # Fallback para assinatura nova (2 args):
                init_stripe(STRIPE_PUBLIC_KEY, STRIPE_SECRET_KEY)

            if st.button("Assinar CLARA Pro", use_container_width=True):
                session_url = create_checkout_session(PRICING_PRODUCT_ID)
                if session_url:
                    st.success("Abrindo checkout…")
                    st.markdown(f"[Ir para o pagamento]({session_url})")
                    log_visit_event("CheckoutStart")
                    ttq_track("InitiateCheckout", {"value": 1})
                else:
                    st.error("Não consegui iniciar o checkout agora. Tente novamente em instantes.")
        except Exception as e:
            STRIPE_ENABLED = False
            st.warning("Stripe indisponível neste ambiente. Verifique as secrets e o módulo stripe_utils.")
    if not STRIPE_ENABLED:
        st.info("Stripe não configurado ou indisponível neste ambiente.")

    st.divider()
    st.subheader("Admin")
    admin_mode = st.toggle("Exibir painel Admin", value=False)


# ----------------------------------------------------------------------------
# Área principal — Fluxo de análise
# ----------------------------------------------------------------------------

# Navegação temporariamente unificada para evitar erro de indentação durante ajustes
SHOW_ANALYSIS = True

st.markdown("### 1) Envie seu contrato")
st.markdown("**Formatos aceitos:** PDF, JPG, PNG. Se for foto/scan, eu leio com OCR automaticamente.")

uploaded = st.file_uploader("Envie o arquivo (até ~25 MB)", type=["pdf","jpg","jpeg","png"], accept_multiple_files=False)

if uploaded is not None:
    # Confirmação visual do arquivo
    st.success(f"Arquivo recebido: {uploaded.name}")
    log_visit_event("FileUpload", {"file_name": uploaded.name})
    ttq_track("FileUpload", {"content_type": "contract", "file_name": uploaded.name})

    # Configurações rápidas
    st.markdown("### 2) Preferências de análise")
    colA, colB, colC = st.columns(3)
    with colA:
        lang_pt = st.checkbox("Análise em Português", value=True)
    with colB:
        want_summary = st.checkbox("Resumo amigável", value=True)
    with colC:
        calc_cet = st.checkbox("Estimar CET (se aplicável)", value=True)

    if st.button("🔎 Analisar agora", type="primary"):
        with st.status("Lendo e analisando o contrato…", expanded=True) as status:
            status.write("Extraindo texto…")
            data = uploaded.read()

            # 1) Extrai texto do PDF (ou retorna vazio se imagem)
            text = ""
            try:
                text = extract_text_from_pdf(data)
            except Exception:
                text = ""

            # 2) Se texto curto → tenta OCR
            if not text or len(text.strip()) < 30:
                if _HAS_OCR:
                    status.write("Arquivo parece imagem/scan. Rodando OCR…")
                    text = ocr_bytes(data)
                else:
                    status.write("Não consegui ler texto do arquivo (OCR indisponível neste ambiente).")

            if not text or len(text.strip()) < 30:
                st.warning("Não consegui ler o conteúdo. Tente uma foto mais nítida ou um PDF com melhor qualidade.")
                status.update(label="Leitura falhou", state="error")
            else:
                status.write("Rodando análise semântica…")
                try:
                    hits = analyze_contract_text(text, lang="pt" if lang_pt else "en")
                except Exception as e:
                    st.error(f"Falha na análise: {e}")
                    status.update(label="Análise falhou", state="error")
                    hits = None

                if hits is not None:
                    status.write("Gerando resumo…")
                    summary = summarize_hits(hits, lang="pt" if lang_pt else "en") if want_summary else None

                    cet_block = None
                    if calc_cet:
                        try:
                            cet_block = compute_cet_quick(text)
                        except Exception:
                            cet_block = None

                    # Loga evento de análise concluída
                    log_analysis_event(get_session_id(), uploaded.name, len(text))
                    log_visit_event("AnalysisCompleted", {"file_name": uploaded.name})
                    ttq_track("AnalysisCompleted", {"value": 1})

                    status.update(label="Análise concluída", state="complete")

                    # Apresentação de resultados
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

                    st.markdown("### Quer receber o PDF do relatório por e‑mail?")
                    email = st.text_input("Seu e‑mail")
                    if st.button("Enviar relatório"):
                        if email and "@" in email:
                            log_subscriber(email)
                            log_visit_event("Lead", {"email": email})
                            st.success("Obrigado! Enviaremos em breve.")
                        else:
                            st.warning("Digite um e‑mail válido.")

else:
    st.info("Dica: se você não tiver o PDF, pode tirar uma **foto nítida** do contrato e enviar em JPG/PNG.")


# ----------------------------------------------------------------------------
# Admin / Observabilidade
# ----------------------------------------------------------------------------

if admin_mode:
    st.header("Painel Admin")

    # Contadores simples do funil
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
        st.metric("PageViews", pv)
        st.metric("Uploads", up)
        st.metric("Análises", ac)
        st.metric("Leads", ld)

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
# Rodapé / FAQ curto
# ----------------------------------------------------------------------------
with st.expander("Como funciona a leitura de documentos?"):
    st.markdown(
        """
        - Se o PDF tiver **texto** embutido, extraímos diretamente.
        - Se for uma **foto** ou **scan**, usamos OCR para converter imagem em texto automaticamente.
        - Depois, rodamos uma análise semântica que destaca **pontos de atenção** e, se aplicável, estimamos **CET**.
        """
    )

with st.expander("Privacidade"):
    st.markdown(
        """
        - Seu arquivo é processado para análise e não é compartilhado.
        - Registramos apenas **métricas de uso** (PageView, Upload, Análise) com identificador de sessão anônimo para
          melhorar a experiência e medir conversões. Você pode bloquear cookies/pixels no seu navegador se preferir.
        """
    )


# ----------------------------------------------------------------------------
# Notas técnicas e compatibilidade
# ----------------------------------------------------------------------------
# - Caso pytesseract/pdf2image não estejam instalados, o OCR é silenciosamente desativado e exibimos uma
#   mensagem amigável. Para ativar, instale: `pytesseract`, `pdf2image`, `poppler` (sistema) e `Pillow`.
# - Para Stripe: defina STRIPE_PUBLIC_KEY, STRIPE_SECRET_KEY e STRIPE_PRICE_ID em st.secrets.
# - Para TikTok Pixel: defina TIKTOK_PIXEL_ID em st.secrets. Hotjar usa HOTJAR_ID/HOTJAR_SV.
# - O CSV de visitas é gravado em ./data/visits.csv.
# - Este arquivo preserva as assinaturas das funções importadas de app_modules/* para manter compatibilidade.
#
# Fim do app.py v15





