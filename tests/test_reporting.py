from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from business_reporting.metrics import calculate_metrics, reconciliation
from business_reporting.report import render_report


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


if __name__ == "__main__":
    unittest.main()
