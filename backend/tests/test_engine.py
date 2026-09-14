import asyncio
from uuid import uuid4

import pytest

from app.connectors.handlers import execute_step
from app.engine.graph import OPS_INTAKE_GRAPH, WorkflowGraph


def test_ops_intake_graph_valid():
    graph = WorkflowGraph.model_validate(OPS_INTAKE_GRAPH)
    ordered = graph.ordered_from_entry()
    assert [s.key for s in ordered] == ["ingest", "validate", "approve", "export", "notify"]


@pytest.mark.asyncio
async def test_validate_fixture_rows():
    rows = [
        {"name": "A", "email": "a@test.com", "company": "Acme"},
        {"name": "B", "email": "bad", "company": "X"},
    ]
    result = await execute_step(
        "data.validate",
        {"required_fields": ["email", "name", "company"], "normalize_email": True},
        {"ingest": {"rows": rows}},
        run_id=uuid4(),
    )
    assert result.output["valid_count"] == 1
    assert result.output["invalid_count"] == 1


@pytest.mark.asyncio
async def test_ingest_fixture_flag():
    result = await execute_step(
        "csv.ingest",
        {"source_field": "rows"},
        {"run_input": {"use_fixture": True}},
        run_id=uuid4(),
    )
    assert result.output["count"] >= 4


@pytest.mark.asyncio
async def test_human_approve_pauses():
    result = await execute_step(
        "human.approve",
        {"title": "Approve"},
        {"validate": {"summary": "ok", "valid_count": 2, "invalid_count": 1, "valid_rows": [], "invalid_rows": []}},
        run_id=uuid4(),
    )
    assert result.needs_approval is True
