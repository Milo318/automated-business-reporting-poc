from __future__ import annotations

import argparse
import json
from pathlib import Path

from .ai import propose_analysis
from .autonomy import METRICS, analyze_and_publish, primary_change
from .metrics import calculate_metrics, reconciliation
from .report import render_report


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build a reconciled HTML KPI report from operational data."
    )
    parser.add_argument("--data", type=Path, default=Path("data/mock"))
    parser.add_argument("--output", type=Path, default=Path("output/report.html"))
    parser.add_argument("--metrics", type=Path, default=Path("output/metrics.json"))
    parser.add_argument(
        "--previous", type=Path, default=Path("data/mock/previous_metrics.json")
    )
    parser.add_argument(
        "--ai",
        action="store_true",
        help="Add an AI-written narrative based only on calculated KPIs",
    )
    args = parser.parse_args()
    metrics = calculate_metrics(args.data)
    if not reconciliation(metrics)["reconciled"]:
        raise ValueError("Ledger reconciliation failed; report was not published")
    analysis = None
    summary = None
    if args.ai:
        previous = json.loads(args.previous.read_text(encoding="utf-8"))
        current = {name: float(metrics.to_dict()[name]) for name in METRICS}
        change = primary_change(previous, current)
        try:
            proposal = propose_analysis(change)
        except (OSError, ValueError, RuntimeError, KeyError, TypeError):
            proposal = None
        outcome = analyze_and_publish(previous, current, proposal)
        analysis = outcome.to_dict()
        summary = str(outcome.analysis["summary"])
    synthetic_data = (
        args.data.resolve() == (Path(__file__).parents[2] / "data/mock").resolve()
    )
    render_report(metrics, args.output, summary, synthetic_data=synthetic_data)
    result = {
        "synthetic_data": synthetic_data,
        "metrics": metrics.to_dict(),
        "reconciliation": reconciliation(metrics),
    }
    if analysis:
        result["analysis"] = analysis
    args.metrics.parent.mkdir(parents=True, exist_ok=True)
    args.metrics.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
