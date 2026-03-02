from __future__ import annotations

import re
from dataclasses import dataclass, field
from io import BytesIO
from unittest.mock import patch

from defusedxml.expatreader import DefusedExpatParser
from odf.namespaces import OFFICENS, TEXTNS
from odf.opendocument import load
from odf.teletype import extractText


@dataclass
class ParsedSection:
    heading: str
    heading_level: int
    content: list[str] = field(default_factory=list)
    section_path: str = ""


class ODTParser:
    """Parse an ODT file into structured sections with headings and paragraphs."""

    # Patterns for aviation-law citations
    _CITATION_RE = re.compile(
        r"(?:"
        r"\b(?:Article|Art\.?)\s+\d+"  # Article 5, Art. 5
        r"|\b[A-Z]{2,6}\.[A-Z]{2,4}\.\d+(?:\([a-z0-9]+\))*"  # ORO.FC.105(a)
        r"|\b\d+\.\d+(?:\.\d+)+"  # 3.2.1
        r")"
    )

    def __init__(self, file_bytes: bytes) -> None:
        # odfpy uses defusedxml internally, which blocks the standard
        # Manifest.dtd external entity reference present in all real ODT files.
        # Temporarily allow it during loading — the DTD is never fetched,
        # it's just a declaration in META-INF/manifest.xml.
        _original_init = DefusedExpatParser.__init__

        def _permissive_init(self_parser: object, *args: object, **kwargs: object) -> None:
            kwargs["forbid_external"] = False
            _original_init(self_parser, *args, **kwargs)

        with patch.object(DefusedExpatParser, "__init__", _permissive_init):
            self._doc = load(BytesIO(file_bytes))

    # Element types that are containers — we recurse into them but don't
    # extract text from them directly.  Headings and paragraphs nested at
    # any depth (e.g. inside text:list > text:list-item, text:section,
    # table:table-cell) are picked up by the recursive walk.
    _H_QNAME = (TEXTNS, "h")
    _P_QNAME = (TEXTNS, "p")

    def _get_text_body(self) -> object:
        """Find the office:text element that holds the actual document content.

        odfpy's ``doc.text`` is unreliable — for some ODT files it returns an
        empty Text node instead of the ``office:text`` element.  Fall back to
        searching ``doc.body`` children when that happens.
        """
        # Fast path: doc.text has content
        if getattr(self._doc.text, "childNodes", None):
            return self._doc.text

        # Fallback: find <office:text> under <office:body>
        body = getattr(self._doc, "body", None)
        if body:
            for child in getattr(body, "childNodes", []):
                if getattr(child, "qname", None) == (OFFICENS, "text"):
                    return child

        # Last resort
        return self._doc.text

    def parse(self) -> list[ParsedSection]:
        sections: list[ParsedSection] = []
        heading_stack: list[tuple[int, str]] = []
        current_section: ParsedSection | None = None
        text_body = self._get_text_body()

        def walk(node: object) -> None:
            nonlocal current_section

            tag = getattr(node, "qname", None)

            if tag == self._H_QNAME:
                level = int(node.getAttribute("outlinelevel") or 1)
                text = self._extract_text(node)
                if not text.strip():
                    return
                self._update_heading_stack(heading_stack, level, text.strip())
                section_path = self._build_section_path(heading_stack)
                current_section = ParsedSection(
                    heading=text.strip(),
                    heading_level=level,
                    section_path=section_path,
                )
                sections.append(current_section)
                return  # don't recurse into heading children

            if tag == self._P_QNAME:
                text = self._extract_text(node)
                if not text.strip():
                    return
                if current_section is None:
                    current_section = ParsedSection(
                        heading="",
                        heading_level=0,
                        section_path="",
                    )
                    sections.append(current_section)
                current_section.content.append(text.strip())
                return  # don't recurse into paragraph children

            # Container element — recurse into children
            for child in getattr(node, "childNodes", []):
                walk(child)

        walk(text_body)
        return sections

    @staticmethod
    def _extract_text(element: object) -> str:
        raw = extractText(element)
        # Normalize whitespace within the line
        return " ".join(raw.split())

    @staticmethod
    def _update_heading_stack(stack: list[tuple[int, str]], level: int, text: str) -> None:
        # Pop headings at same or deeper level
        while stack and stack[-1][0] >= level:
            stack.pop()
        stack.append((level, text))

    @staticmethod
    def _build_section_path(stack: list[tuple[int, str]]) -> str:
        return " > ".join(text for _, text in stack)

    @staticmethod
    def extract_citation(heading: str) -> str | None:
        match = ODTParser._CITATION_RE.search(heading)
        return match.group(0) if match else None
