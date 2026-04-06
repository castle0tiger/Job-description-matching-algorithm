import pdfplumber
import io


def extract_text_from_pdf(file_bytes: bytes) -> str:
    """PDF 바이트 데이터에서 텍스트를 추출합니다."""
    text_parts = []
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)
    return "\n".join(text_parts)
