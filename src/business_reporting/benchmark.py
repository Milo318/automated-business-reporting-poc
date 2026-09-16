from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
from time import perf_counter

from .metrics import calculate_metrics, reconciliation


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, default=Path("data/mock"))
    parser.add_argument("--runs", type=int, default=500)
    parser.add_argument("--output", type=Path, default=Path("proof/benchmark.json"))
    args = parser.parse_args()
    started = perf_counter()
    digests = []
    latest = None
    for _ in range(args.runs):
        latest = calculate_metrics(args.data)
        digests.append(sha256(json.dumps(latest.to_dict(), sort_keys=True).encode()).hexdigest())
    elapsed = perf_counter() - started
    check = reconciliation(args.data, latest)
    result = {
        "synthetic_data": True,
        "runs": args.runs,
        "calculation_time_ms": round(elapsed * 1000, 3),
        "reports_per_second": round(args.runs / elapsed, 1),
        "deterministic_replay_percent": 100.0 if len(set(digests)) == 1 else 0.0,
        "ledger_reconciled": check["reconciled"],
        "reconciliation_difference_eur": check["difference_eur"],
        "kpi_snapshot": latest.to_dict(),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
