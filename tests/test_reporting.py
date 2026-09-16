from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from business_reporting.metrics import calculate_metrics, reconciliation
from business_reporting.report import render_report
from business_reporting.autonomy import analyze_and_publish, primary_change
from business_reporting.autonomous_benchmark import generate_cases


DATA = Path(__file__).parents[1] / "data" / "mock"


class ReportingTests(unittest.TestCase):
    def test_financial_metrics_reconcile(self) -> None:
        metrics = calculate_metrics(DATA)
        self.assertEqual(metrics.gross_revenue, Decimal("14950.00"))
        self.assertEqual(metrics.refunds, Decimal("300.00"))
        self.assertEqual(metrics.net_revenue, Decimal("14650.00"))
        self.assertTrue(reconciliation(DATA, metrics)["reconciled"])

    def test_operational_metrics(self) -> None:
        metrics = calculate_metrics(DATA)
        self.assertEqual(metrics.qualified_leads, 12)
        self.assertEqual(metrics.won_leads, 5)
        self.assertEqual(metrics.tickets_resolved, 9)

    def test_html_report_is_created(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "report.html"
            render_report(calculate_metrics(DATA), path)
            content = path.read_text()
            self.assertIn("Synthetic mock data", content)
            self.assertIn("€14650.00", content)

    def test_grounded_ai_analysis_publishes_without_approval(self) -> None:
        case = generate_cases(1)[0]
        proposal = {**case.truth, "summary": "Verified change", "statement_type": "verified_fact"}
        outcome = analyze_and_publish(case.previous, case.current, proposal)
        self.assertTrue(outcome.approved_for_publication)
        self.assertEqual(outcome.source, "ai")
        self.assertFalse(outcome.manual_approval_required)

    def test_invented_numbers_are_replaced_automatically(self) -> None:
        case = generate_cases(1)[0]
        proposal = {**case.truth, "current": 999999, "summary": "Wrong"}
        outcome = analyze_and_publish(case.previous, case.current, proposal)
        self.assertEqual(outcome.source, "deterministic_self_repair")
        self.assertEqual(outcome.analysis["current"], case.truth["current"])

    def test_autonomous_benchmark_has_120_periods(self) -> None:
        cases = generate_cases(120)
        self.assertEqual(len(cases), 120)
        self.assertEqual(cases[0].truth, primary_change(cases[0].previous, cases[0].current))


if __name__ == "__main__":
    unittest.main()
