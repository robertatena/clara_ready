from typing import BinaryIO
from pypdf import PdfReader

def extract_text_from_pdf(file: BinaryIO) -> str:
    """
    Extrai texto de PDFs textuais (não faz OCR).
    Se o PDF for escaneado (imagem), o retorno pode vir vazio.
    """
    try:
        reader = PdfReader(file)
        return "\n".join((page.extract_text() or "") for page in reader.pages)
    except Exception:
        return ""
