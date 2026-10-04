"""Post-decision refinement: confusion-pair resolve + optional consistency."""
from __future__ import annotations

from .confusion_pairs import resolve_confusion


def refine_prediction(
    clause_text: str,
    predicted_label: str | None,
    candidate_labels: list[str] | None = None,
) -> dict:
    """Apply confusion-pair resolution; return updated label + metadata."""
    resolved, reason = resolve_confusion(
        clause_text,
        predicted_label,
        candidates=candidate_labels,
    )
    return {
        "predicted_label": resolved,
        "confusion_resolved": reason is not None,
        "confusion_reason": reason,
        "pre_resolve_label": predicted_label,
    }
