from io import BytesIO

from odf.opendocument import OpenDocumentText
from odf.text import H, List, ListItem, P


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


def create_test_odt_with_lists(
    sections: list[tuple[str, int, list[str], list[str]]],
) -> bytes:
    """Build an ODT where paragraphs are nested inside text:list elements.

    Args:
        sections: list of (heading_text, heading_level, [direct_paragraphs], [list_items])

    Returns:
        ODT file bytes.
    """
    doc = OpenDocumentText()

    for heading_text, level, paragraphs, list_items in sections:
        if heading_text:
            h = H(outlinelevel=str(level), text=heading_text)
            doc.text.addElement(h)
        for para_text in paragraphs:
            doc.text.addElement(P(text=para_text))
        if list_items:
            lst = List()
            for item_text in list_items:
                li = ListItem()
                li.addElement(P(text=item_text))
                lst.addElement(li)
            doc.text.addElement(lst)

    buf = BytesIO()
    doc.save(buf)
    return buf.getvalue()
