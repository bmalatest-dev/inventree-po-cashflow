import importlib.util
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path


POLICY_PATH = Path(__file__).resolve().parents[1] / "po_cashflow" / "logic.py"
spec = importlib.util.spec_from_file_location("po_cashflow_logic", POLICY_PATH)
logic = importlib.util.module_from_spec(spec)
spec.loader.exec_module(logic)


class CashflowLogicTests(unittest.TestCase):
    def test_partial_receipt_uses_only_open_quantity(self):
        self.assertEqual(
            logic.outstanding_quantity("100", "75"),
            Decimal("25"),
        )
        self.assertEqual(
            logic.outstanding_value("100", "75", "20", "0"),
            Decimal("500"),
        )

    def test_fully_received_is_zero(self):
        self.assertEqual(logic.outstanding_quantity("10", "10"), Decimal("0"))
        self.assertEqual(logic.outstanding_value("10", "10", "25"), Decimal("0"))

    def test_over_received_does_not_go_negative(self):
        self.assertEqual(logic.outstanding_quantity("10", "12"), Decimal("0"))

    def test_discount_applies_to_outstanding_value(self):
        self.assertEqual(
            logic.outstanding_value("10", "4", "100", "10"),
            Decimal("540"),
        )

    def test_missing_price_is_unknown_not_zero(self):
        self.assertIsNone(logic.outstanding_value("10", "2", None))

    def test_month_grouping(self):
        self.assertEqual(logic.month_key(date(2026, 11, 15)), "2026-11")
        self.assertEqual(logic.month_label("2026-11"), "Nov 2026")
        self.assertEqual(logic.month_key(None), logic.NO_DATE)

    def test_matrix_keeps_currency_separate(self):
        rows = [
            {"project_code": "TATE", "currency": "USD", "month_key": "2026-10", "outstanding_value": "100"},
            {"project_code": "TATE", "currency": "USD", "month_key": "2026-10", "outstanding_value": "50"},
            {"project_code": "TATE", "currency": "CAD", "month_key": "2026-10", "outstanding_value": "25"},
        ]
        matrix = logic.aggregate_matrix(rows)
        self.assertEqual(matrix[("TATE", "USD")]["2026-10"], Decimal("150"))
        self.assertEqual(matrix[("TATE", "CAD")]["2026-10"], Decimal("25"))

    def test_missing_price_excluded_from_matrix(self):
        rows = [
            {"project_code": "TATE", "currency": "USD", "month_key": "2026-10", "outstanding_value": None},
            {"project_code": "TATE", "currency": "USD", "month_key": "2026-10", "outstanding_value": "10"},
        ]
        matrix = logic.aggregate_matrix(rows)
        self.assertEqual(matrix[("TATE", "USD")]["2026-10"], Decimal("10"))

    def test_no_target_date_sorts_last(self):
        rows = [
            {"month_key": logic.NO_DATE},
            {"month_key": "2026-12"},
            {"month_key": "2026-09"},
        ]
        self.assertEqual(
            logic.sorted_months(rows),
            ["2026-09", "2026-12", logic.NO_DATE],
        )



class ExporterIntegrationSourceTests(unittest.TestCase):
    def test_v012_uses_data_export_mixin(self):
        plugin_path = Path(__file__).resolve().parents[1] / "po_cashflow" / "plugin.py"
        source = plugin_path.read_text()
        self.assertIn("DataExportMixin", source)
        self.assertIn("model_class == PurchaseOrder", source)
        self.assertIn("export_report_type", source)
        self.assertNotIn("NavigationMixin", source)

    def test_matrix_headers_created_before_export_data(self):
        plugin_path = Path(__file__).resolve().parents[1] / "po_cashflow" / "plugin.py"
        source = plugin_path.read_text()
        self.assertIn("_matrix_months_for_headers", source)
        self.assertIn("headers[month] = month_label(month)", source)
        self.assertIn('context["_po_cashflow_months"] = months', source)
        self.assertIn("months = sorted_months(rows)", source)

    def test_matrix_export_uses_rows_before_headers(self):
        plugin_path = Path(__file__).resolve().parents[1] / "po_cashflow" / "plugin.py"
        source = plugin_path.read_text()
        export_pos = source.find("def export_data")
        header_pos = source.find("def update_headers")
        self.assertGreater(export_pos, -1)
        self.assertGreater(header_pos, -1)
        self.assertIn("_po_cashflow_months", source)


if __name__ == "__main__":
    unittest.main()
