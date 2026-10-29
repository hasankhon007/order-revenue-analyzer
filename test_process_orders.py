#!/usr/bin/env python3
"""
Unit tests for process_orders.py
"""

from decimal import Decimal
import io
from pathlib import Path
import tempfile
import unittest

from process_orders import (
    format_currency,
    parse_created_at_to_month,
    print_report,
    process_orders,
    validate_and_parse_row,
)


class TestOrderRevenueAnalyzer(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def _create_csv(self, filename: str, content: str) -> Path:
        file_path = self.temp_path / filename
        file_path.write_text(content, encoding="utf-8")
        return file_path

    def test_parse_created_at_to_month(self):
        # ISO formats
        self.assertEqual(parse_created_at_to_month("2024-05-18T14:30:00Z"), "2024-05")
        self.assertEqual(parse_created_at_to_month("2024-05-18 14:30:00"), "2024-05")
        self.assertEqual(parse_created_at_to_month("2024-05-18"), "2024-05")
        self.assertEqual(parse_created_at_to_month("2024-05-18T14:30:00+02:00"), "2024-05")

        # Alternate formats
        self.assertEqual(parse_created_at_to_month("2024/05/18"), "2024-05")
        self.assertEqual(parse_created_at_to_month("2024/05/18 10:00:00"), "2024-05")

        # Invalid formats
        with self.assertRaises(ValueError):
            parse_created_at_to_month("invalid-date")
        with self.assertRaises(ValueError):
            parse_created_at_to_month("")
        with self.assertRaises(ValueError):
            parse_created_at_to_month("   ")

    def test_validate_and_parse_row_valid(self):
        row = {
            "order_id": "ORD-1",
            "customer_id": "CUST-A",
            "amount": "150.25",
            "created_at": "2024-01-15T12:00:00Z"
        }
        parsed, invalid = validate_and_parse_row(row, row_number=2)
        self.assertIsNone(invalid)
        self.assertIsNotNone(parsed)
        cid, month, amt = parsed
        self.assertEqual(cid, "CUST-A")
        self.assertEqual(month, "2024-01")
        self.assertEqual(amt, Decimal("150.25"))

    def test_validate_and_parse_row_invalid_cases(self):
        # Empty order_id
        _, inv = validate_and_parse_row(
            {"order_id": "", "customer_id": "CUST-A", "amount": "10", "created_at": "2024-01-01"}, 2
        )
        self.assertIsNotNone(inv)
        self.assertIn("order_id", inv.reason)

        # Empty customer_id
        _, inv = validate_and_parse_row(
            {"order_id": "O1", "customer_id": "  ", "amount": "10", "created_at": "2024-01-01"}, 3
        )
        self.assertIsNotNone(inv)
        self.assertIn("customer_id", inv.reason)

        # Non-numeric amount
        _, inv = validate_and_parse_row(
            {"order_id": "O1", "customer_id": "CUST-A", "amount": "abc", "created_at": "2024-01-01"}, 4
        )
        self.assertIsNotNone(inv)
        self.assertIn("numeric", inv.reason)

        # Negative amount
        _, inv = validate_and_parse_row(
            {"order_id": "O1", "customer_id": "CUST-A", "amount": "-15.00", "created_at": "2024-01-01"}, 5
        )
        self.assertIsNotNone(inv)
        self.assertIn("greater than 0", inv.reason)

        # Zero amount
        _, inv = validate_and_parse_row(
            {"order_id": "O1", "customer_id": "CUST-A", "amount": "0.00", "created_at": "2024-01-01"}, 6
        )
        self.assertIsNotNone(inv)
        self.assertIn("greater than 0", inv.reason)

        # Invalid date
        _, inv = validate_and_parse_row(
            {"order_id": "O1", "customer_id": "CUST-A", "amount": "25.00", "created_at": "not-a-date"}, 7
        )
        self.assertIsNotNone(inv)
        self.assertIn("created_at", inv.reason)

        # Missing column in row dict
        _, inv = validate_and_parse_row(
            {"order_id": "O1", "customer_id": "CUST-A", "amount": "25.00"}, 8
        )
        self.assertIsNotNone(inv)
        self.assertIn("Missing required field", inv.reason)

    def test_process_orders_aggregation_and_sorting(self):
        csv_data = """order_id,customer_id,amount,created_at
ORD-1,CUST-A,100.00,2024-01-05
ORD-2,CUST-B,500.00,2024-01-10
ORD-3,CUST-A,50.00,2024-01-20
ORD-4,CUST-A,300.00,2024-02-01
ORD-5,CUST-B,150.00,2024-02-15
ORD-6,BAD-ROW,-20.00,2024-01-10
ORD-7,,50.00,2024-01-10
"""
        csv_file = self._create_csv("test_orders.csv", csv_data)
        records, invalid_rows, total = process_orders(csv_file, descending=True)

        self.assertEqual(total, 7)
        self.assertEqual(len(invalid_rows), 2)
        self.assertEqual(len(records), 4)

        # Check records sorted descending:
        # CUST-B (2024-01): 500.00
        # CUST-A (2024-02): 300.00
        # CUST-A (2024-01): 150.00 (100 + 50)
        # CUST-B (2024-02): 150.00
        self.assertEqual(records[0].customer_id, "CUST-B")
        self.assertEqual(records[0].month, "2024-01")
        self.assertEqual(records[0].revenue, Decimal("500.00"))
        self.assertEqual(records[0].order_count, 1)

        self.assertEqual(records[1].customer_id, "CUST-A")
        self.assertEqual(records[1].month, "2024-02")
        self.assertEqual(records[1].revenue, Decimal("300.00"))
        self.assertEqual(records[1].order_count, 1)

        # Both records[2] and records[3] have revenue 150.00
        self.assertEqual(records[2].revenue, Decimal("150.00"))
        self.assertEqual(records[3].revenue, Decimal("150.00"))

    def test_decimal_precision(self):
        # 0.10 + 0.20 in float is 0.30000000000000004
        # In Decimal it must be exact 0.30
        csv_data = """order_id,customer_id,amount,created_at
ORD-1,CUST-A,0.10,2024-01-01
ORD-2,CUST-A,0.20,2024-01-02
"""
        csv_file = self._create_csv("precision.csv", csv_data)
        records, invalid, _ = process_orders(csv_file)
        self.assertEqual(len(invalid), 0)
        self.assertEqual(records[0].revenue, Decimal("0.30"))

    def test_missing_header(self):
        csv_data = """order_id,customer_id,created_at
ORD-1,CUST-A,2024-01-01
"""
        csv_file = self._create_csv("bad_header.csv", csv_data)
        with self.assertRaises(ValueError) as ctx:
            process_orders(csv_file)
        self.assertIn("amount", str(ctx.exception))

    def test_file_not_found(self):
        with self.assertRaises(FileNotFoundError):
            process_orders(self.temp_path / "non_existent.csv")

    def test_print_report_output(self):
        records = [
            # using process_orders to produce real records
        ]
        csv_data = """order_id,customer_id,amount,created_at
ORD-1,CUST-A,100.00,2024-01-01
ORD-2,,50.00,2024-01-02
"""
        csv_file = self._create_csv("report_test.csv", csv_data)
        records, invalid_rows, total = process_orders(csv_file)

        out = io.StringIO()
        print_report(records, invalid_rows, total, output_stream=out)
        output = out.getvalue()

        self.assertIn("ORDER PROCESSING REPORT", output)
        self.assertIn("Total Rows Read : 2", output)
        self.assertIn("Invalid Rows    : 1", output)
        self.assertIn("CUST-A", output)
        self.assertIn("$100.00", output)


if __name__ == "__main__":
    unittest.main()
