"""Compatibility surface and wiring helpers for guardrailed RAG workflows."""

from __future__ import annotations

from functools import partial
from typing import Any

from exegesis.application.facades.telemetry import instrument_workflow, set_span_attribute

from ..registry import get_llm_registry
from .chat import (
    DeliverableHooks,
    GuardedAnswerPipeline,
    _guarded_answer,
    _guarded_answer_or_refusal,
    configure_deliverable_hooks,
    run_guarded_chat,
)
from .collaboration import run_research_reconciliation
from .corpus import run_corpus_curation
from .deliverables import (
    generate_comparative_analysis,
    generate_devotional_flow,
    generate_multimedia_digest,
    generate_sermon_prep_outline,
)
from .exports import (
    build_sermon_deliverable,
    build_sermon_prep_package,
    build_transcript_deliverable,
    build_transcript_package,
)
from .guardrail_helpers import GuardrailError, load_passages_for_osis
from .models import (
    CollaborationResponse,
    ComparativeAnalysisResponse,
    CorpusCurationReport,
    DevotionalResponse,
    MultimediaDigestResponse,
    RAGAnswer,
    RAGCitation,
    SermonPrepResponse,
    VerseCopilotResponse,
)
from .refusals import REFUSAL_MESSAGE, REFUSAL_MODEL_NAME, build_guardrail_refusal
from .retrieval import record_used_citation_feedback, search_passages
from .verse import generate_verse_brief
from .types import WorkflowLoggingContext


def _build_deliverable_hooks(logger: WorkflowLoggingContext) -> DeliverableHooks:
    """Bind the workflow logging context into each deliverable helper."""

    return DeliverableHooks(
        generate_sermon_prep_outline=partial(generate_sermon_prep_outline, logger=logger),
        generate_comparative_analysis=partial(generate_comparative_analysis, logger=logger),
        generate_devotional_flow=partial(generate_devotional_flow, logger=logger),
        generate_multimedia_digest=partial(generate_multimedia_digest, logger=logger),
        build_sermon_deliverable=build_sermon_deliverable,
        build_sermon_prep_package=build_sermon_prep_package,
        build_transcript_deliverable=build_transcript_deliverable,
        build_transcript_package=build_transcript_package,
    )


_workflow_logging_context = WorkflowLoggingContext.default()


def _apply_deliverable_hooks(context: WorkflowLoggingContext) -> None:
    configure_deliverable_hooks(_build_deliverable_hooks(context))


def configure_workflow_logging_context(
    context: WorkflowLoggingContext | None = None,
) -> WorkflowLoggingContext:
    """Install a logging callback that all workflow helpers share."""

    global _workflow_logging_context
    effective = context or WorkflowLoggingContext.default()
    _workflow_logging_context = effective
    _apply_deliverable_hooks(effective)
    return effective


def get_workflow_logging_context() -> WorkflowLoggingContext:
    """Return the currently configured workflow logging context."""

    return _workflow_logging_context


def log_workflow_event(event: str, *, workflow: str, **context: Any) -> None:
    """Forward workflow events using the injected context."""

    _workflow_logging_context.log_event(event, workflow=workflow, **context)


_apply_deliverable_hooks(_workflow_logging_context)


__all__ = [
    "CollaborationResponse",
    "ComparativeAnalysisResponse",
    "CorpusCurationReport",
    "DevotionalResponse",
    "GuardedAnswerPipeline",
    "GuardrailError",
    "MultimediaDigestResponse",
    "RAGAnswer",
    "RAGCitation",
    "REFUSAL_MESSAGE",
    "REFUSAL_MODEL_NAME",
    "SermonPrepResponse",
    "VerseCopilotResponse",
    "WorkflowLoggingContext",
    "_guarded_answer",
    "_guarded_answer_or_refusal",
    "build_guardrail_refusal",
    "build_sermon_deliverable",
    "build_sermon_prep_package",
    "build_transcript_deliverable",
    "build_transcript_package",
    "configure_workflow_logging_context",
    "get_llm_registry",
    "generate_comparative_analysis",
    "generate_devotional_flow",
    "generate_multimedia_digest",
    "generate_sermon_prep_outline",
    "generate_verse_brief",
    "get_workflow_logging_context",
    "instrument_workflow",
    "log_workflow_event",
    "load_passages_for_osis",
    "record_used_citation_feedback",
    "run_corpus_curation",
    "run_guarded_chat",
    "run_research_reconciliation",
    "set_span_attribute",
    "search_passages",
]
