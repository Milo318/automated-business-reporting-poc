from __future__ import annotations

from dataclasses import asdict, dataclass
import math


METRICS = (
    "net_revenue",
    "active_mrr",
    "lead_conversion_percent",
    "sla_compliance_percent",
)


@dataclass(frozen=True)
class AnalysisOutcome:
    analysis: dict[str, object]
    source: str
    approved_for_publication: bool
    checks: tuple[str, ...]
    manual_approval_required: bool = False

    def to_dict(self) -> dict[str, object]:
        result = asdict(self)
        result["checks"] = list(self.checks)
        return result


def primary_change(
    previous: dict[str, float], current: dict[str, float]
) -> dict[str, object]:
    for snapshot in (previous, current):
        if not isinstance(snapshot, dict):
            raise ValueError("Metrics must be an object")
        for name in METRICS:
            value = snapshot.get(name)
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
            ):
                raise ValueError(f"Metric {name} must be a finite number")
    metric = max(
        METRICS,
        key=lambda name: (
            abs(current[name] - previous[name]) / max(abs(previous[name]), 1.0)
        ),
    )
    before = previous[metric]
    after = current[metric]
    return {
        "metric": metric,
        "direction": "up" if after > before else "down" if after < before else "flat",
        "previous": before,
        "current": after,
    }


def _proposal_matches(proposal: dict[str, object], truth: dict[str, object]) -> bool:
    if not isinstance(proposal, dict):
        return False
    try:
        return (
            not isinstance(proposal.get("previous"), bool)
            and not isinstance(proposal.get("current"), bool)
            and proposal.get("metric") == truth["metric"]
            and proposal.get("direction") == truth["direction"]
            and float(proposal.get("previous")) == float(truth["previous"])
            and float(proposal.get("current")) == float(truth["current"])
            and proposal.get("summary") == verified_summary(truth)
            and proposal.get("statement_type") == "verified_fact"
        )
    except (TypeError, ValueError):
        return False


def verified_summary(change: dict[str, object]) -> str:
    return f"{change['metric']} moved {change['direction']} from {change['previous']} to {change['current']}."


def analyze_and_publish(
    previous: dict[str, float],
    current: dict[str, float],
    ai_proposal: dict[str, object] | None,
) -> AnalysisOutcome:
    """Publish automatically only when every AI claim is grounded in locked metrics."""
    truth = primary_change(previous, current)
    checks: list[str] = []
    if _proposal_matches(ai_proposal or {}, truth):
        analysis = {
            **truth,
            "summary": verified_summary(truth),
            "statement_type": "verified_fact",
        }
        source = "ai"
        checks.append("ai_claims_grounded")
    else:
        analysis = {
            **truth,
            "summary": verified_summary(truth),
            "statement_type": "verified_fact",
        }
        source = "deterministic_self_repair"
        checks.append("ungrounded_ai_claims_replaced")
    analysis["source_metric_ids"] = [str(truth["metric"])]
    checks.extend(
        ("all_numbers_verified", "primary_change_recomputed", "source_metric_attached")
    )
    return AnalysisOutcome(analysis, source, True, tuple(checks))
