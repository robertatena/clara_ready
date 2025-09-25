# app_modules/pdf_utils.py
from typing import BinaryIO
from pypdf import PdfReader
import re

def normalize_contract_text(t: str) -> str:
    """
    Recompõe parágrafos de PDFs 'picotados':
    - remove hifenização no fim de linha
    - preserva parágrafos (duas quebras)
    - troca quebras únicas por espaço
    - colapsa múltiplos espaços
    """
    if not t:
        return ""
    t = t.replace("\r", "")
    # junta palavras quebradas por hífen no fim da linha
    t = re.sub(r"-\s*\n\s*", "", t)
    # preserva parágrafos: marca \n\n com marcador temporário
    t = re.sub(r"\n{2,}", "<<<PARA>>>", t)
    # qualquer \n restante vira espaço
    t = re.sub(r"\n+", " ", t)
    # restaura parágrafos
    t = t.replace("<<<PARA>>>", "\n\n")
    # normaliza espaços
    t = re.sub(r"[ \t]+", " ", t).strip()
    return t

def extract_text_from_pdf(file: BinaryIO) -> str:
    """Extrai texto de PDFs textuais e já normaliza para leitura."""
    try:
        reader = PdfReader(file)
        raw = "\n".join((page.extract_text() or "") for page in reader.pages)
        return normalize_contract_text(raw)
    except Exception:
        return ""

