from __future__ import annotations

import hashlib
from dataclasses import dataclass

from src.documents.constants import MAX_CHUNK_TOKENS, TARGET_CHUNK_TOKENS, TOKEN_MULTIPLIER
from src.documents.odt_parser import ODTParser, ParsedSection


@dataclass
class Chunk:
    chunk_index: int
    section_path: str | None
    citation: str | None
    heading: str | None
    text: str
    token_count: int
    checksum: str


class DocumentChunker:
    """Split parsed sections into chunks respecting token limits."""

    def chunk_sections(self, sections: list[ParsedSection]) -> list[Chunk]:
        chunks: list[Chunk] = []

        for section in sections:
            full_text = "\n".join(section.content)
            if not full_text.strip():
                continue

            token_count = self._estimate_tokens(full_text)
            citation = ODTParser.extract_citation(section.heading) if section.heading else None

            if token_count <= MAX_CHUNK_TOKENS:
                chunks.append(
                    Chunk(
                        chunk_index=len(chunks),
                        section_path=section.section_path or None,
                        citation=citation,
                        heading=section.heading or None,
                        text=full_text,
                        token_count=token_count,
                        checksum=self._checksum(full_text),
                    )
                )
            else:
                # Split by paragraph boundaries targeting TARGET_CHUNK_TOKENS
                sub_chunks = self._split_paragraphs(
                    paragraphs=section.content,
                    section_path=section.section_path,
                    citation=citation,
                    heading=section.heading,
                    start_index=len(chunks),
                )
                chunks.extend(sub_chunks)

        return chunks

    def _split_paragraphs(
        self,
        paragraphs: list[str],
        section_path: str,
        citation: str | None,
        heading: str | None,
        start_index: int,
    ) -> list[Chunk]:
        chunks: list[Chunk] = []
        current_paragraphs: list[str] = []
        current_tokens = 0

        for para in paragraphs:
            para_tokens = self._estimate_tokens(para)

            if current_tokens + para_tokens > TARGET_CHUNK_TOKENS and current_paragraphs:
                text = "\n".join(current_paragraphs)
                chunks.append(
                    Chunk(
                        chunk_index=start_index + len(chunks),
                        section_path=section_path or None,
                        citation=citation,
                        heading=heading or None,
                        text=text,
                        token_count=self._estimate_tokens(text),
                        checksum=self._checksum(text),
                    )
                )
                current_paragraphs = []
                current_tokens = 0

            current_paragraphs.append(para)
            current_tokens += para_tokens

        # Flush remaining
        if current_paragraphs:
            text = "\n".join(current_paragraphs)
            chunks.append(
                Chunk(
                    chunk_index=start_index + len(chunks),
                    section_path=section_path or None,
                    citation=citation,
                    heading=heading or None,
                    text=text,
                    token_count=self._estimate_tokens(text),
                    checksum=self._checksum(text),
                )
            )

        return chunks

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        return int(len(text.split()) * TOKEN_MULTIPLIER)

    @staticmethod
    def _checksum(text: str) -> str:
        normalized = " ".join(text.split())
        return hashlib.sha256(normalized.encode()).hexdigest()
