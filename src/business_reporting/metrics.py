from __future__ import annotations

import csv
from dataclasses import asdict, dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path


@dataclass(frozen=True)
class Metrics:
    gross_revenue: Decimal
    refunds: Decimal
    net_revenue: Decimal
    active_mrr: Decimal
    new_customers: int
    churned_customers: int
    qualified_leads: int
    won_leads: int
    lead_conversion_percent: float
    tickets_total: int
    tickets_resolved: int
    tickets_within_sla: int
    sla_compliance_percent: float

    def to_dict(self) -> dict[str, object]:
        result = asdict(self)
        for key in ("gross_revenue", "refunds", "net_revenue", "active_mrr"):
            result[key] = f"{result[key]:.2f}"
        return result


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def calculate_metrics(data_dir: Path) -> Metrics:
    payments = read_csv(data_dir / "payments.csv")
    customers = read_csv(data_dir / "customers.csv")
    leads = read_csv(data_dir / "leads.csv")
    tickets = read_csv(data_dir / "tickets.csv")
    gross = sum((Decimal(row["amount_eur"]) for row in payments if row["type"] == "payment"), Decimal("0"))
    refunds = sum((abs(Decimal(row["amount_eur"])) for row in payments if row["type"] == "refund"), Decimal("0"))
    active_mrr = sum((Decimal(row["mrr_eur"]) for row in customers if row["status"] == "active"), Decimal("0"))
    qualified = sum(row["qualified"] == "true" for row in leads)
    won = sum(row["status"] == "won" for row in leads)
    resolved = [row for row in tickets if row["resolved_at"]]
    within_sla = 0
    for row in resolved:
        opened = datetime.fromisoformat(row["opened_at"])
        closed = datetime.fromisoformat(row["resolved_at"])
        within_sla += (closed - opened).total_seconds() / 3600 <= float(row["sla_hours"])
    return Metrics(
        gross_revenue=gross,
        refunds=refunds,
        net_revenue=gross - refunds,
        active_mrr=active_mrr,
        new_customers=sum(row["started_in_period"] == "true" for row in customers),
        churned_customers=sum(row["status"] == "churned" for row in customers),
        qualified_leads=qualified,
        won_leads=won,
        lead_conversion_percent=round(won / qualified * 100, 2) if qualified else 0,
        tickets_total=len(tickets),
        tickets_resolved=len(resolved),
        tickets_within_sla=within_sla,
        sla_compliance_percent=round(within_sla / len(resolved) * 100, 2) if resolved else 0,
    )


def reconciliation(data_dir: Path, metrics: Metrics) -> dict[str, object]:
    payments = read_csv(data_dir / "payments.csv")
    ledger_sum = sum((Decimal(row["amount_eur"]) for row in payments), Decimal("0"))
    difference = metrics.net_revenue - ledger_sum
    return {"ledger_sum_eur": f"{ledger_sum:.2f}", "reported_net_revenue_eur": f"{metrics.net_revenue:.2f}", "difference_eur": f"{difference:.2f}", "reconciled": difference == 0}
