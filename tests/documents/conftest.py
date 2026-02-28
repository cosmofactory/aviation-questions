from io import BytesIO

from odf.opendocument import OpenDocumentText
from odf.text import H, P


def create_test_odt(sections: list[tuple[str, int, list[str]]]) -> bytes:
    """Build a minimal ODT file in memory.

    Args:
        sections: list of (heading_text, heading_level, [paragraph_texts])

    Returns:
        ODT file bytes.
    """
    doc = OpenDocumentText()

    for heading_text, level, paragraphs in sections:
        if heading_text:
            h = H(outlinelevel=str(level), text=heading_text)
            doc.text.addElement(h)
        for para_text in paragraphs:
            p = P(text=para_text)
            doc.text.addElement(p)

    buf = BytesIO()
    doc.save(buf)
    return buf.getvalue()
