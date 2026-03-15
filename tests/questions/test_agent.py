from __future__ import annotations

from pydantic_ai import ModelResponse, ToolCallPart
from pydantic_ai.models.function import FunctionModel

from src.questions.schemas import SourceChunk
from src.questions.service import QAAgentDeps, qa_agent


def _make_source_chunk(*, citation: str | None = "ORO.FC.101(a)") -> SourceChunk:
    return SourceChunk(
        chunk_id="00000000-0000-0000-0000-000000000001",
        text="Crew composition requirements text.",
        citation=citation,
        section_path="Part-ORO > Subpart FC > ORO.FC.101",
        heading="Crew composition",
        document_title="Regulation (EU) 965/2012",
        jurisdiction="easa",
        doc_type="regulation",
        distance=0.01,
    )


async def test_agent_prepare_tools_without_history_or_citations() -> None:
    tool_names_seen: list[set[str]] = []

    async def function(_, info):
        tool_names_seen.append({tool.name for tool in info.function_tools})
        output_tool = info.output_tools[0].name
        return ModelResponse(
            parts=[ToolCallPart(tool_name=output_tool, args={"answer": "A", "citations": []})]
        )

    deps = QAAgentDeps(
        question="What are crew requirements?",
        conversation_context=None,
        source_chunks=[_make_source_chunk(citation=None)],
    )
    with qa_agent.override(model=FunctionModel(function=function)):
        result = await qa_agent.run("What are crew requirements?", deps=deps, model="test")

    assert result.output.answer == "A"
    assert tool_names_seen == [{"list_retrieved_sources"}]


async def test_agent_prepare_tools_with_history_and_citations() -> None:
    tool_names_seen: list[set[str]] = []
    instructions_seen: list[str | None] = []

    async def function(_, info):
        tool_names_seen.append({tool.name for tool in info.function_tools})
        instructions_seen.append(info.instructions)
        output_tool = info.output_tools[0].name
        return ModelResponse(
            parts=[ToolCallPart(tool_name=output_tool, args={"answer": "A", "citations": []})]
        )

    deps = QAAgentDeps(
        question="What kinds are there?",
        conversation_context="Turn 1 question: What is an apple?",
        source_chunks=[_make_source_chunk(citation="ORO.FC.101(a)")],
    )
    with qa_agent.override(model=FunctionModel(function=function)):
        await qa_agent.run("What kinds are there?", deps=deps, model="test")

    assert tool_names_seen == [
        {"list_retrieved_sources", "get_source_by_citation", "get_conversation_history"}
    ]
    assert instructions_seen and instructions_seen[0] is not None
    assert "Available citation labels: ORO.FC.101(a)" in instructions_seen[0]
    assert "Conversation history" in instructions_seen[0]


async def test_agent_output_validator_normalizes_answer_and_citations() -> None:
    async def function(_, info):
        output_tool = info.output_tools[0].name
        return ModelResponse(
            parts=[
                ToolCallPart(
                    tool_name=output_tool,
                    args={
                        "answer": "  ",
                        "citations": ["NOT.A.CITATION", "ORO.FC.101(a)", "ORO.FC.101(a)"],
                    },
                )
            ]
        )

    deps = QAAgentDeps(
        question="What are crew requirements?",
        conversation_context=None,
        source_chunks=[_make_source_chunk(citation="ORO.FC.101(a)")],
    )
    with qa_agent.override(model=FunctionModel(function=function)):
        result = await qa_agent.run("What are crew requirements?", deps=deps, model="test")

    assert result.output.answer == "The retrieved context is insufficient to answer this question."
    assert result.output.citations == ["ORO.FC.101(a)"]


async def test_agent_output_validator_forces_empty_citations_when_unavailable() -> None:
    async def function(_, info):
        output_tool = info.output_tools[0].name
        return ModelResponse(
            parts=[ToolCallPart(tool_name=output_tool, args={"answer": "A", "citations": ["ANY"]})]
        )

    deps = QAAgentDeps(
        question="Unknown topic?",
        conversation_context=None,
        source_chunks=[],
    )
    with qa_agent.override(model=FunctionModel(function=function)):
        result = await qa_agent.run("Unknown topic?", deps=deps, model="test")

    assert result.output.answer == "A"
    assert result.output.citations == []
