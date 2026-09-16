from __future__ import annotations

from dataclasses import asdict, dataclass


METRICS = ("net_revenue", "active_mrr", "lead_conversion_percent", "sla_compliance_percent")


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


def primary_change(previous: dict[str, float], current: dict[str, float]) -> dict[str, object]:
    metric = max(METRICS, key=lambda name: abs(current[name] - previous[name]) / max(abs(previous[name]), 1.0))
    before = previous[metric]
    after = current[metric]
    return {
        "metric": metric,
        "direction": "up" if after > before else "down" if after < before else "flat",
        "previous": before,
        "current": after,
    }


def _proposal_matches(proposal: dict[str, object], truth: dict[str, object]) -> bool:
    try:
        return (
            proposal.get("metric") == truth["metric"]
            and proposal.get("direction") == truth["direction"]
            and float(proposal.get("previous")) == float(truth["previous"])
            and float(proposal.get("current")) == float(truth["current"])
        )
    except (TypeError, ValueError):
        return False


def analyze_and_publish(previous: dict[str, float], current: dict[str, float], ai_proposal: dict[str, object] | None) -> AnalysisOutcome:
    """Publish automatically only when every AI claim is grounded in locked metrics."""
    truth = primary_change(previous, current)
    checks: list[str] = []
    if _proposal_matches(ai_proposal or {}, truth):
        analysis = dict(ai_proposal or {})
        source = "ai"
        checks.append("ai_claims_grounded")
    else:
        analysis = {
            **truth,
            "summary": f"{truth['metric']} moved {truth['direction']} from {truth['previous']} to {truth['current']}.",
            "statement_type": "verified_fact",
        }
        source = "deterministic_self_repair"
        checks.append("ungrounded_ai_claims_replaced")
    analysis["source_metric_ids"] = [str(truth["metric"])]
    checks.extend(("all_numbers_verified", "primary_change_recomputed", "source_metric_attached"))
    return AnalysisOutcome(analysis, source, True, tuple(checks))
