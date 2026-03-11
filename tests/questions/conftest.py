import uuid

import pytest
from pydantic_ai import models
from pydantic_ai.models.test import TestModel

from src.questions.service import qa_agent

# Block real model requests globally — any accidental call to a real LLM will fail.
models.ALLOW_MODEL_REQUESTS = False


@pytest.fixture
def override_qa_agent():
    """Override the QA agent with TestModel for all tests that need it."""
    with qa_agent.override(model=TestModel()):
        yield


def make_mock_chunks(n: int = 2) -> list[dict]:
    """Create fake search result chunks for testing."""
    return [
        {
            "chunk_id": str(uuid.uuid4()),
            "text": f"Chunk {i} text about aviation regulation.",
            "citation": f"ORO.FC.{100 + i}(a)",
            "section_path": f"Part-ORO > Subpart FC > ORO.FC.{100 + i}",
            "heading": f"Heading {i}",
            "document_title": "Regulation (EU) 965/2012",
            "jurisdiction": "easa",
            "doc_type": "regulation",
            "distance": 0.1 * i,
        }
        for i in range(1, n + 1)
    ]
