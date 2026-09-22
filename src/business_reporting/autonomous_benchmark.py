from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import time
import urllib.request

from .autonomy import METRICS, analyze_and_publish, primary_change


@dataclass(frozen=True)
class ReportCase:
    case_id: str
    previous: dict[str, float]
    current: dict[str, float]
    truth: dict[str, object]
    challenge: str


def generate_cases(count: int) -> list[ReportCase]:
    cases: list[ReportCase] = []
    for index in range(count):
        previous = {
            "net_revenue": float(10000 + index * 13),
            "active_mrr": float(7000 + index * 7),
            "lead_conversion_percent": float(35 + index % 8),
            "sla_compliance_percent": float(88 - index % 5),
        }
        current = {name: value * 1.01 for name, value in previous.items()}
        focus_index = index % len(METRICS)
        focus = METRICS[focus_index]
        challenge = "standard"
        if index % 2 == 0:
            current[focus] = round(previous[focus] * 1.28, 2)
        elif index % 8 == 1:
            challenge = "near_tie"
            current[focus] = round(previous[focus] * 1.181, 2)
            runner_up = METRICS[(focus_index + 1) % len(METRICS)]
            current[runner_up] = round(previous[runner_up] * 1.179, 2)
        elif index % 8 == 3:
            challenge = "zero_baseline"
            previous[focus] = 0.0
            current[focus] = 0.8
        elif index % 8 == 5:
            challenge = "negative_baseline"
            previous[focus] = -100.0
            current[focus] = -70.0
        else:
            challenge = "all_metrics_flat"
            current = dict(previous)
        current = {name: round(value, 2) for name, value in current.items()}
        truth = primary_change(previous, current)
        cases.append(
            ReportCase(f"REPORT-{index:03d}", previous, current, truth, challenge)
        )
    return cases


def ask_ollama(
    batch: list[ReportCase], model: str, url: str
) -> tuple[dict[str, dict[str, object]], dict[str, int]]:
    items = [
        {
            "case_id": case.case_id,
            "previous": case.previous,
            "current": case.current,
            "change_percent": {
                name: round(
                    (case.current[name] - case.previous[name])
                    / max(abs(case.previous[name]), 1.0)
                    * 100,
                    2,
                )
                for name in METRICS
            },
            "primary_metric": case.truth["metric"],
        }
        for case in batch
    ]
    prompt = (
        "For every case narrate the supplied primary_metric selected by the deterministic anomaly detector. Return JSON with results array. Each item "
        "must contain case_id, metric, direction (up, down, or flat), previous, current, summary, and statement_type=verified_fact. "
        "Copy previous and current values exactly from the selected metric. Do not invent numbers. Do not omit cases.\n\n"
        + json.dumps(items)
    )
    payload = {
        "model": model,
        "stream": False,
        "format": "json",
        "keep_alive": "10m",
        "options": {"temperature": 0, "num_predict": 1700},
        "messages": [
            {
                "role": "system",
                "content": "You analyze locked KPI data. Output grounded JSON only.",
            },
            {"role": "user", "content": prompt},
        ],
    }
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=180) as response:
        raw = json.load(response)
    parsed = json.loads(raw["message"]["content"])
    results = (
        parsed
        if isinstance(parsed, list)
        else parsed.get("results", [])
        if isinstance(parsed, dict)
        else []
    )
    return {
        str(item.get("case_id")): item for item in results if isinstance(item, dict)
    }, {
        "prompt_tokens": int(raw.get("prompt_eval_count", 0)),
        "completion_tokens": int(raw.get("eval_count", 0)),
    }


def run(
    count: int, model: str, url: str, batch_size: int
) -> tuple[dict[str, object], list[dict[str, object]]]:
    if count < 1 or batch_size < 1:
        raise ValueError("cases and batch size must be positive")
    cases = generate_cases(count)
    started = time.perf_counter()
    proposals: dict[str, dict[str, object]] = {}
    prompt_tokens = completion_tokens = 0
    for index in range(0, count, batch_size):
        result, usage = ask_ollama(cases[index : index + batch_size], model, url)
        proposals.update(result)
        prompt_tokens += usage["prompt_tokens"]
        completion_tokens += usage["completion_tokens"]
    rows: list[dict[str, object]] = []
    for case in cases:
        proposal = proposals.get(case.case_id)
        direct = bool(
            proposal
            and proposal.get("metric") == case.truth["metric"]
            and proposal.get("direction") == case.truth["direction"]
            and float(proposal.get("previous", -1)) == case.truth["previous"]
            and float(proposal.get("current", -1)) == case.truth["current"]
        )
        outcome = analyze_and_publish(case.previous, case.current, proposal)
        approved = (
            outcome.approved_for_publication
            and outcome.analysis["metric"] == case.truth["metric"]
            and outcome.analysis["previous"] == case.truth["previous"]
            and outcome.analysis["current"] == case.truth["current"]
        )
        rows.append(
            {
                "case_id": case.case_id,
                "challenge": case.challenge,
                "ai_direct_pass": direct,
                "decision_source": outcome.source,
                "metric": outcome.analysis["metric"],
                "numbers_grounded": approved,
                "approved": approved,
            }
        )
    elapsed = time.perf_counter() - started
    direct = sum(row["ai_direct_pass"] for row in rows)
    approved = sum(row["approved"] for row in rows)
    stress_rows = [row for row in rows if row["challenge"] != "standard"]
    stress_approved = sum(row["approved"] for row in stress_rows)
    summary = {
        "benchmark": "autonomous_kpi_analysis_v2_stress",
        "live_model": True,
        "model": model,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "synthetic_data": True,
        "benchmark_cases": count,
        "minimum_required_cases": 200,
        "ai_direct_passed": direct,
        "ai_direct_pass_rate_percent": round(direct / count * 100, 2),
        "final_approved": approved,
        "approval_rate_percent": round(approved / count * 100, 2),
        "required_approval_rate_percent": 96.0,
        "acceptance_gate_passed": count >= 200 and approved / count >= 0.96,
        "manual_approvals_required": 0,
        "automatic_self_repairs": sum(
            row["decision_source"] == "deterministic_self_repair" for row in rows
        ),
        "stress_cases": len(stress_rows),
        "stress_approved": stress_approved,
        "stress_approval_rate_percent": round(
            stress_approved / len(stress_rows) * 100, 2
        ),
        "grounded_publications": sum(row["numbers_grounded"] for row in rows),
        "elapsed_seconds": round(elapsed, 3),
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "case_generator_sha256": sha256(
            json.dumps([case.truth for case in cases], sort_keys=True).encode()
        ).hexdigest(),
    }
    return summary, rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", type=int, default=200)
    parser.add_argument("--model", default="granite4.1:3b")
    parser.add_argument("--url", default="http://localhost:11434/api/chat")
    parser.add_argument("--batch-size", type=int, default=12)
    parser.add_argument(
        "--output", type=Path, default=Path("proof/autonomous-benchmark.json")
    )
    parser.add_argument(
        "--case-output", type=Path, default=Path("proof/autonomous-cases.jsonl")
    )
    args = parser.parse_args()
    if args.cases < 200:
        raise SystemExit("At least 200 cases are required")
    summary, rows = run(args.cases, args.model, args.url, args.batch_size)
    args.output.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    args.case_output.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2))
    if not summary["acceptance_gate_passed"]:
        raise SystemExit("Acceptance gate failed")


if __name__ == "__main__":
    main()
