from __future__ import annotations

import argparse
import json
from pathlib import Path

from .ai import generate_executive_summary
from .metrics import calculate_metrics, reconciliation
from .report import render_report


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a reconciled HTML KPI report from operational data.")
    parser.add_argument("--data", type=Path, default=Path("data/mock"))
    parser.add_argument("--output", type=Path, default=Path("output/report.html"))
    parser.add_argument("--metrics", type=Path, default=Path("output/metrics.json"))
    parser.add_argument("--ai", action="store_true", help="Add an AI-written narrative based only on calculated KPIs")
    args = parser.parse_args()
    metrics = calculate_metrics(args.data)
    summary = generate_executive_summary(metrics.to_dict()) if args.ai else None
    render_report(metrics, args.output, summary)
    result = {"synthetic_data": True, "metrics": metrics.to_dict(), "reconciliation": reconciliation(args.data, metrics)}
    args.metrics.parent.mkdir(parents=True, exist_ok=True)
    args.metrics.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
