from __future__ import annotations

import re
from dataclasses import dataclass, field
from io import BytesIO

from odf.namespaces import TEXTNS
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
        self._doc = load(BytesIO(file_bytes))

    def parse(self) -> list[ParsedSection]:
        sections: list[ParsedSection] = []
        heading_stack: list[tuple[int, str]] = []
        current_section: ParsedSection | None = None

        for element in self._doc.text.childNodes:
            tag = element.qname

            if tag == H.qname:
                level = int(element.getAttribute("outlinelevel") or 1)
                text = self._extract_text(element)
                if not text.strip():
                    continue

                self._update_heading_stack(heading_stack, level, text.strip())
                section_path = self._build_section_path(heading_stack)

                current_section = ParsedSection(
                    heading=text.strip(),
                    heading_level=level,
                    section_path=section_path,
                )
                sections.append(current_section)

            elif tag == P.qname:
                text = self._extract_text(element)
                if not text.strip():
                    continue

                if current_section is None:
                    # Paragraphs before any heading go into a preamble section
                    current_section = ParsedSection(
                        heading="",
                        heading_level=0,
                        section_path="",
                    )
                    sections.append(current_section)

                current_section.content.append(text.strip())

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
