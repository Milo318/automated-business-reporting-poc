import csv
import json
from pathlib import Path
import shutil
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from business_reporting.autonomy import analyze_and_publish, primary_change
from business_reporting.metrics import calculate_metrics
from business_reporting.cli import main

DATA = Path(__file__).parents[1] / "data/mock"
PREVIOUS = {
    "net_revenue": 100.0,
    "active_mrr": 50.0,
    "lead_conversion_percent": 10.0,
    "sla_compliance_percent": 90.0,
}
CURRENT = {**PREVIOUS, "net_revenue": 110.0}


def change_csv(root, filename, change):
    path = root / filename
    with path.open() as stream:
        reader = csv.DictReader(stream)
        fields, rows = reader.fieldnames, list(reader)
    change(rows)
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


class ContractTests(unittest.TestCase):
    def test_invented_narrative_cannot_pass_with_correct_numbers(self):
        proposal = {
            **primary_change(PREVIOUS, CURRENT),
            "summary": "Revenue is 999999 EUR after gaining 500 customers.",
            "statement_type": "verified_fact",
        }
        outcome = analyze_and_publish(PREVIOUS, CURRENT, proposal)
        self.assertTrue(outcome.approved_for_publication)
        self.assertEqual(outcome.source, "deterministic_self_repair")
        self.assertEqual(
            outcome.analysis["summary"], "net_revenue moved up from 100.0 to 110.0."
        )

    def test_missing_or_malformed_model_output_uses_safe_summary(self):
        for proposal in [None, [], "invalid", {"metric": "net_revenue"}]:
            with self.subTest(proposal=proposal):
                self.assertEqual(
                    analyze_and_publish(PREVIOUS, CURRENT, proposal).source,
                    "deterministic_self_repair",
                )

    def test_extra_model_claims_are_not_published(self):
        proposal = {
            **primary_change(PREVIOUS, CURRENT),
            "summary": "net_revenue moved up from 100.0 to 110.0.",
            "statement_type": "verified_fact",
            "cause": "invented customer growth",
        }
        result = analyze_and_publish(PREVIOUS, CURRENT, proposal)
        self.assertNotIn("cause", result.analysis)
        self.assertEqual(result.source, "ai")

    def test_nonfinite_metrics_are_rejected(self):
        for value in [float("nan"), float("inf"), True, "100"]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                primary_change(PREVIOUS, {**CURRENT, "net_revenue": value})

    def test_bad_financial_and_cohort_data_are_rejected(self):
        cases = [
            ("payments.csv", "amount_eur", "NaN"),
            ("payments.csv", "amount_eur", "-100"),
            ("payments.csv", "type", "unknown"),
            ("customers.csv", "mrr_eur", "-10"),
            ("leads.csv", "qualified", "false"),
            ("tickets.csv", "resolved_at", "2020-01-01T00:00:00"),
            ("tickets.csv", "sla_hours", "-1"),
        ]
        for filename, field, value in cases:
            with (
                self.subTest(filename=filename, field=field, value=value),
                TemporaryDirectory() as temporary,
            ):
                root = Path(temporary)
                shutil.copytree(DATA, root, dirs_exist_ok=True)
                change_csv(root, filename, lambda rows: rows[0].update({field: value}))
                with self.assertRaises(ValueError):
                    calculate_metrics(root)

    def test_duplicate_payment_is_not_double_counted(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            shutil.copytree(DATA, root, dirs_exist_ok=True)
            change_csv(root, "payments.csv", lambda rows: rows.append(rows[0]))
            with self.assertRaises(ValueError):
                calculate_metrics(root)

    def test_outage_still_produces_verified_cli_report(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            args = [
                "report",
                "--data",
                str(DATA),
                "--previous",
                str(DATA / "previous_metrics.json"),
                "--output",
                str(root / "report.html"),
                "--metrics",
                str(root / "metrics.json"),
                "--ai",
            ]
            with (
                patch.object(sys, "argv", args),
                patch(
                    "business_reporting.cli.propose_analysis", side_effect=TimeoutError
                ),
            ):
                main()
            result = json.loads((root / "metrics.json").read_text())
            self.assertEqual(result["analysis"]["source"], "deterministic_self_repair")
            self.assertTrue(result["reconciliation"]["reconciled"])


class ReportInputContractTests(unittest.TestCase):
    def test_empty_table_still_requires_correct_columns(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            shutil.copytree(DATA, root, dirs_exist_ok=True)
            (root / "payments.csv").write_text("unexpected,column\n")
            with self.assertRaises(ValueError):
                calculate_metrics(root)

    def test_external_inputs_are_not_labeled_fictional(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            shutil.copytree(DATA, root / "inputs")
            args = [
                "report",
                "--data",
                str(root / "inputs"),
                "--output",
                str(root / "report.html"),
                "--metrics",
                str(root / "metrics.json"),
            ]
            with patch.object(sys, "argv", args):
                main()
            self.assertFalse(
                json.loads((root / "metrics.json").read_text())["synthetic_data"]
            )
            self.assertNotIn("fictional", (root / "report.html").read_text())
