"""Shared DTOs for the guardrailed RAG workflows."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from exegesis.application.facades.telemetry import log_workflow_event as _telemetry_log_workflow_event


class WorkflowLogCallback(Protocol):
    """Signature required for workflow log callbacks."""

    def __call__(self, event: str, *, workflow: str, **context: Any) -> None:
        ...


def _default_workflow_log_callback(event: str, *, workflow: str, **context: Any) -> None:
    """Forward events to the application telemetry facade."""

    _telemetry_log_workflow_event(event, workflow=workflow, **context)


@dataclass(frozen=True)
class WorkflowLoggingContext:
    """Encapsulate a workflow logging callback for explicit injection."""

    callback: WorkflowLogCallback = _default_workflow_log_callback

    def log_event(self, event: str, *, workflow: str, **context: Any) -> None:
        """Emit a workflow event via the configured callback."""

        self.callback(event, workflow=workflow, **context)

    @classmethod
    def default(cls) -> "WorkflowLoggingContext":
        """Return the shared default logging context."""

        return _DEFAULT_WORKFLOW_LOGGING_CONTEXT


_DEFAULT_WORKFLOW_LOGGING_CONTEXT = WorkflowLoggingContext()
