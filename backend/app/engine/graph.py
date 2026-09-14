from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class StepDef(BaseModel):
    key: str
    type: str
    name: str | None = None
    config: dict[str, Any] = Field(default_factory=dict)
    max_attempts: int = 3
    next: str | None = None
    on_reject: str | None = None


class WorkflowGraph(BaseModel):
    entry: str
    steps: list[StepDef]

    def step_map(self) -> dict[str, StepDef]:
        return {s.key: s for s in self.steps}

    def ordered_from_entry(self) -> list[StepDef]:
        smap = self.step_map()
        if self.entry not in smap:
            raise ValueError(f"entry step '{self.entry}' not found")
        ordered: list[StepDef] = []
        seen: set[str] = set()
        current: str | None = self.entry
        while current:
            if current in seen:
                break
            if current not in smap:
                raise ValueError(f"step '{current}' not found")
            step = smap[current]
            ordered.append(step)
            seen.add(current)
            current = step.next
        return ordered


OPS_INTAKE_GRAPH: dict[str, Any] = {
    "entry": "ingest",
    "steps": [
        {
            "key": "ingest",
            "type": "csv.ingest",
            "name": "Ingest rows",
            "config": {"source_field": "rows"},
            "max_attempts": 2,
            "next": "validate",
        },
        {
            "key": "validate",
            "type": "data.validate",
            "name": "Validate & normalize",
            "config": {
                "required_fields": ["email", "name", "company"],
                "normalize_email": True,
            },
            "max_attempts": 2,
            "next": "approve",
        },
        {
            "key": "approve",
            "type": "human.approve",
            "name": "Human approval",
            "config": {
                "title": "Approve ops intake batch",
            },
            "max_attempts": 1,
            "next": "export",
            "on_reject": None,
        },
        {
            "key": "export",
            "type": "csv.export",
            "name": "Export CSV",
            "config": {},
            "max_attempts": 3,
            "next": "notify",
        },
        {
            "key": "notify",
            "type": "slack.notify",
            "name": "Notify Slack",
            "config": {
                "message_template": "Relay ops intake completed: {valid_count} valid rows, export ready.",
            },
            "max_attempts": 3,
            "next": None,
        },
    ],
}
