from __future__ import annotations

import csv
from dataclasses import asdict, dataclass
from datetime import datetime, date
from decimal import Decimal, InvalidOperation
from pathlib import Path


@dataclass(frozen=True)
class Metrics:
    gross_revenue: Decimal
    refunds: Decimal
    net_revenue: Decimal
    ledger_sum: Decimal
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
        result.pop("ledger_sum")
        for key in ("gross_revenue", "refunds", "net_revenue", "active_mrr"):
            result[key] = f"{result[key]:.2f}"
        return result


def read_csv(path: Path) -> list[dict[str, str]]:
    schemas = {
        "payments.csv": {"payment_id", "date", "type", "amount_eur", "customer_id"},
        "customers.csv": {"customer_id", "status", "mrr_eur", "started_in_period"},
        "leads.csv": {"lead_id", "qualified", "status"},
        "tickets.csv": {"ticket_id", "opened_at", "resolved_at", "sla_hours"},
    }
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or len(set(reader.fieldnames)) != len(
            reader.fieldnames
        ):
            raise ValueError(f"Missing or duplicate columns in {path.name}")
        if not schemas[path.name] <= set(reader.fieldnames):
            raise ValueError(f"Missing required columns in {path.name}")
        rows = list(reader)
    if any(None in row or any(value is None for value in row.values()) for row in rows):
        raise ValueError(f"Malformed row in {path.name}")
    return rows


def money(value: str) -> Decimal:
    try:
        result = Decimal(value)
    except (InvalidOperation, TypeError) as exc:
        raise ValueError("Invalid monetary value") from exc
    if (
        not result.is_finite()
        or abs(result) > Decimal("1e15")
        or result != result.quantize(Decimal("0.01"))
    ):
        raise ValueError("Money must be finite with at most two decimal places")
    return result


def validate_rows(rows, required, identifier):
    seen = set()
    for row in rows:
        if (
            not required <= row.keys()
            or not row[identifier].strip()
            or row[identifier] in seen
        ):
            raise ValueError(f"Missing fields or duplicate {identifier}")
        seen.add(row[identifier])


def calculate_metrics(data_dir: Path) -> Metrics:
    payments = read_csv(data_dir / "payments.csv")
    customers = read_csv(data_dir / "customers.csv")
    leads = read_csv(data_dir / "leads.csv")
    tickets = read_csv(data_dir / "tickets.csv")
    validate_rows(
        payments,
        {"payment_id", "date", "type", "amount_eur", "customer_id"},
        "payment_id",
    )
    validate_rows(
        customers,
        {"customer_id", "status", "mrr_eur", "started_in_period"},
        "customer_id",
    )
    validate_rows(leads, {"lead_id", "qualified", "status"}, "lead_id")
    validate_rows(
        tickets, {"ticket_id", "opened_at", "resolved_at", "sla_hours"}, "ticket_id"
    )
    for row in payments:
        value = money(row["amount_eur"])
        date.fromisoformat(row["date"])
        if (
            row["type"] not in {"payment", "refund"}
            or (row["type"] == "payment" and value < 0)
            or (row["type"] == "refund" and value > 0)
        ):
            raise ValueError("Payments must be positive and refunds negative")
    for row in customers:
        if (
            row["status"] not in {"active", "churned", "inactive"}
            or row["started_in_period"] not in {"true", "false"}
            or money(row["mrr_eur"]) < 0
        ):
            raise ValueError("Invalid customer status or MRR")
    for row in leads:
        if row["qualified"] not in {"true", "false"} or row["status"] not in {
            "won",
            "lost",
            "open",
        }:
            raise ValueError("Invalid lead status")
        if row["status"] == "won" and row["qualified"] != "true":
            raise ValueError("Won leads must belong to the qualified cohort")
    gross = sum(
        (money(row["amount_eur"]) for row in payments if row["type"] == "payment"),
        Decimal("0"),
    )
    refunds = sum(
        (abs(money(row["amount_eur"])) for row in payments if row["type"] == "refund"),
        Decimal("0"),
    )
    active_mrr = sum(
        (money(row["mrr_eur"]) for row in customers if row["status"] == "active"),
        Decimal("0"),
    )
    qualified = sum(row["qualified"] == "true" for row in leads)
    won = sum(row["status"] == "won" for row in leads)
    resolved = [row for row in tickets if row["resolved_at"]]
    within_sla = 0
    for row in tickets:
        opened = datetime.fromisoformat(row["opened_at"])
        hours = money(row["sla_hours"])
        if hours <= 0:
            raise ValueError("SLA hours must be positive")
        if not row["resolved_at"]:
            continue
        closed = datetime.fromisoformat(row["resolved_at"])
        if (opened.tzinfo is None) != (closed.tzinfo is None) or closed < opened:
            raise ValueError("Ticket timestamps are inconsistent")
        within_sla += (closed - opened).total_seconds() / 3600 <= float(hours)
    return Metrics(
        gross_revenue=gross,
        refunds=refunds,
        net_revenue=gross - refunds,
        ledger_sum=sum((money(row["amount_eur"]) for row in payments), Decimal("0")),
        active_mrr=active_mrr,
        new_customers=sum(row["started_in_period"] == "true" for row in customers),
        churned_customers=sum(row["status"] == "churned" for row in customers),
        qualified_leads=qualified,
        won_leads=won,
        lead_conversion_percent=round(won / qualified * 100, 2) if qualified else 0,
        tickets_total=len(tickets),
        tickets_resolved=len(resolved),
        tickets_within_sla=within_sla,
        sla_compliance_percent=round(within_sla / len(resolved) * 100, 2)
        if resolved
        else 0,
    )


def reconciliation(metrics: Metrics) -> dict[str, object]:
    difference = metrics.net_revenue - metrics.ledger_sum
    return {
        "ledger_sum_eur": f"{metrics.ledger_sum:.2f}",
        "reported_net_revenue_eur": f"{metrics.net_revenue:.2f}",
        "difference_eur": f"{difference:.2f}",
        "reconciled": difference == 0,
    }
