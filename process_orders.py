#!/usr/bin/env python3
"""
Order Revenue Analyzer
======================

Reads a CSV file containing order data (order_id, customer_id, amount, created_at),
validates each row, skips and reports invalid rows, and aggregates & prints
total revenue per customer per month, sorted by revenue descending.
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
import sys
from typing import Dict, List, Optional, Tuple


@dataclass(frozen=True)
class InvalidRow:
    """Represents a skipped row with its row number, raw content, and failure reason."""
    row_number: int
    raw_data: dict[str, str]
    reason: str


@dataclass(frozen=True)
class RevenueRecord:
    """Represents aggregated revenue for a customer in a given month."""
    customer_id: str
    month: str
    revenue: Decimal
    order_count: int


def parse_created_at_to_month(date_str: str) -> str:
    """
    Parses a created_at date/timestamp string and returns the 'YYYY-MM' month string.

    Supported formats include:
      - ISO formats: '2024-05-18T14:30:00Z', '2024-05-18 14:30:00', '2024-05-18'
      - Slash-separated: '2024/05/18', '2024/05/18 14:30:00'
      - Timestamps with timezone offsets: '2024-05-18T14:30:00+00:00'
    """
    clean_str = date_str.strip()
    if not clean_str:
        raise ValueError("created_at is empty")

    # Handle trailing Z for UTC in ISO strings
    iso_candidate = clean_str.replace("Z", "+00:00") if clean_str.endswith("Z") else clean_str

    # 1. Try standard ISO parsing (handles 'YYYY-MM-DD', 'YYYY-MM-DDTHH:MM:SS', etc.)
    try:
        dt = datetime.fromisoformat(iso_candidate)
        return dt.strftime("%Y-%m")
    except ValueError:
        pass

    # 2. Try common alternate date formats
    alternate_formats = [
        "%Y/%m/%d %H:%M:%S",
        "%Y/%m/%d",
        "%d-%m-%Y %H:%M:%S",
        "%d-%m-%Y",
        "%d/%m/%Y %H:%M:%S",
        "%d/%m/%Y",
        "%m/%d/%Y %H:%M:%S",
        "%m/%d/%Y",
    ]
    for fmt in alternate_formats:
        try:
            dt = datetime.strptime(clean_str, fmt)
            return dt.strftime("%Y-%m")
        except ValueError:
            continue

    raise ValueError(f"Unrecognized date/timestamp format: '{clean_str}'")


def validate_and_parse_row(
    row: dict[str, str], row_number: int
) -> Tuple[Optional[Tuple[str, str, Decimal]], Optional[InvalidRow]]:
    """
    Validates a single CSV row.

    Required columns: 'order_id', 'customer_id', 'amount', 'created_at'.

    Validation rules:
      - 'order_id': non-empty string.
      - 'customer_id': non-empty string.
      - 'amount': valid positive decimal number (> 0).
      - 'created_at': valid parseable date/timestamp.

    Returns:
      Tuple of ((customer_id, month, amount), None) on success,
      or (None, InvalidRow) on failure.
    """
    # 1. Check for missing required columns in dictionary
    required_fields = ["order_id", "customer_id", "amount", "created_at"]
    missing_fields = [f for f in required_fields if f not in row or row[f] is None]
    if missing_fields:
        return None, InvalidRow(
            row_number=row_number,
            raw_data=row,
            reason=f"Missing required field(s): {', '.join(missing_fields)}"
        )

    # 2. Check order_id
    order_id = str(row["order_id"]).strip()
    if not order_id:
        return None, InvalidRow(
            row_number=row_number,
            raw_data=row,
            reason="Empty or whitespace 'order_id'"
        )

    # 3. Check customer_id
    customer_id = str(row["customer_id"]).strip()
    if not customer_id:
        return None, InvalidRow(
            row_number=row_number,
            raw_data=row,
            reason="Empty or whitespace 'customer_id'"
        )

    # 4. Check amount
    amount_str = str(row["amount"]).strip()
    if not amount_str:
        return None, InvalidRow(
            row_number=row_number,
            raw_data=row,
            reason="Missing or empty 'amount'"
        )
    # Strip optional leading currency sign if present (e.g. '$50.00')
    cleaned_amount_str = amount_str.lstrip("$").replace(",", "").strip()
    try:
        amount = Decimal(cleaned_amount_str)
        if amount.is_nan() or amount.is_infinite():
            raise InvalidOperation("Non-finite decimal")
    except (InvalidOperation, ValueError):
        return None, InvalidRow(
            row_number=row_number,
            raw_data=row,
            reason=f"Invalid 'amount' value '{amount_str}' (must be a valid numeric amount)"
        )

    if amount <= Decimal("0"):
        return None, InvalidRow(
            row_number=row_number,
            raw_data=row,
            reason=f"Invalid 'amount' value '{amount_str}' (must be greater than 0)"
        )

    # 5. Check created_at
    created_at_str = str(row["created_at"]).strip()
    if not created_at_str:
        return None, InvalidRow(
            row_number=row_number,
            raw_data=row,
            reason="Missing or empty 'created_at'"
        )

    try:
        month = parse_created_at_to_month(created_at_str)
    except ValueError as e:
        return None, InvalidRow(
            row_number=row_number,
            raw_data=row,
            reason=f"Invalid 'created_at': {e}"
        )

    return (customer_id, month, amount), None


def process_orders(
    file_path: str | Path,
    descending: bool = True
) -> Tuple[List[RevenueRecord], List[InvalidRow], int]:
    """
    Reads an orders CSV file, validates rows, tracks invalid ones,
    and aggregates revenue per customer per month.

    Returns:
      (sorted_records, invalid_rows, total_rows_read)
    """
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"Orders file not found at: {path.resolve()}")

    # Aggregator: (customer_id, month) -> {"revenue": Decimal, "count": int}
    revenue_map: Dict[Tuple[str, str], Dict[str, any]] = {}
    invalid_rows: List[InvalidRow] = []
    total_rows = 0

    with path.open(mode="r", encoding="utf-8-sig", newline="") as csvfile:
        reader = csv.DictReader(csvfile)

        # Validate that the CSV has the expected headers
        if reader.fieldnames is None:
            raise ValueError(f"File '{path}' is empty or has no header row.")

        # Normalize field names (strip leading/trailing whitespace)
        fieldnames = [f.strip() if f else "" for f in reader.fieldnames]
        required_headers = {"order_id", "customer_id", "amount", "created_at"}
        if not required_headers.issubset(set(fieldnames)):
            missing = required_headers - set(fieldnames)
            raise ValueError(
                f"CSV header is missing required column(s): {', '.join(sorted(missing))}. "
                f"Found columns: {', '.join(fieldnames)}"
            )

        for row_idx, raw_row in enumerate(reader, start=2):  # line 2 is first data row
            total_rows += 1
            # Normalize keys by stripping whitespace
            cleaned_row = {
                (k.strip() if k else ""): (v.strip() if v else "")
                for k, v in raw_row.items()
            }

            parsed_data, invalid_info = validate_and_parse_row(cleaned_row, row_idx)

            if invalid_info is not None:
                invalid_rows.append(invalid_info)
                continue

            customer_id, month, amount = parsed_data
            key = (customer_id, month)
            if key not in revenue_map:
                revenue_map[key] = {"revenue": Decimal("0.00"), "count": 0}
            revenue_map[key]["revenue"] += amount
            revenue_map[key]["count"] += 1

    records: List[RevenueRecord] = [
        RevenueRecord(
            customer_id=cid,
            month=month,
            revenue=data["revenue"],
            order_count=data["count"]
        )
        for (cid, month), data in revenue_map.items()
    ]

    # Sort primarily by revenue (descending by default), secondarily by month and customer_id
    records.sort(
        key=lambda r: (r.revenue if not descending else -r.revenue, r.month, r.customer_id)
    )

    return records, invalid_rows, total_rows


def format_currency(amount: Decimal) -> str:
    """Formats a Decimal amount as a standard currency string (e.g. '$1,234.56')."""
    return f"${amount:,.2f}"


def print_report(
    records: List[RevenueRecord],
    invalid_rows: List[InvalidRow],
    total_rows: int,
    output_stream=sys.stdout
) -> None:
    """Prints a formatted report including skipped rows and aggregated revenue table."""
    valid_count = total_rows - len(invalid_rows)

    print("=" * 76, file=output_stream)
    print("                    ORDER PROCESSING REPORT                     ", file=output_stream)
    print("=" * 76, file=output_stream)
    print(f"Total Rows Read : {total_rows}", file=output_stream)
    print(f"Valid Rows      : {valid_count}", file=output_stream)
    print(f"Invalid Rows    : {len(invalid_rows)}", file=output_stream)
    print("=" * 76, file=output_stream)

    # 1. Report invalid rows if any
    if invalid_rows:
        print("\n" + "-" * 76, file=output_stream)
        print("                 SKIPPED / INVALID ROWS REPORT                  ", file=output_stream)
        print("-" * 76, file=output_stream)
        for inv in invalid_rows:
            raw_preview = ", ".join(f"{k}: '{v}'" for k, v in inv.raw_data.items() if k)
            print(f"  • Row {inv.row_number:3d}: {inv.reason}", file=output_stream)
            print(f"    Raw Data: {{{raw_preview}}}", file=output_stream)
        print("-" * 76, file=output_stream)
    else:
        print("\nAll rows were valid. No rows were skipped.", file=output_stream)

    # 2. Print revenue table
    print("\n" + "=" * 76, file=output_stream)
    print("           REVENUE PER CUSTOMER PER MONTH (SORTED BY REVENUE)   ", file=output_stream)
    print("=" * 76, file=output_stream)

    if not records:
        print("No valid order data to display.", file=output_stream)
        print("=" * 76, file=output_stream)
        return

    # Table headers
    header_fmt = "{:<12} | {:<24} | {:>12} | {:>18}"
    row_fmt    = "{:<12} | {:<24} | {:>12} | {:>18}"
    separator  = "-" * 13 + "+" + "-" * 26 + "+" + "-" * 14 + "+" + "-" * 19

    print(header_fmt.format("Month", "Customer ID", "Orders", "Revenue ($)"), file=output_stream)
    print(separator, file=output_stream)

    total_revenue = Decimal("0.00")
    total_orders = 0

    for r in records:
        total_revenue += r.revenue
        total_orders += r.order_count
        print(row_fmt.format(
            r.month,
            r.customer_id,
            str(r.order_count),
            format_currency(r.revenue)
        ), file=output_stream)

    print(separator, file=output_stream)
    print(row_fmt.format(
        "TOTAL",
        f"{len(records)} grouping(s)",
        str(total_orders),
        format_currency(total_revenue)
    ), file=output_stream)
    print("=" * 76, file=output_stream)


def main() -> None:
    """CLI entry point for the order revenue analyzer."""
    parser = argparse.ArgumentParser(
        description="Process orders CSV, skip/report invalid rows, and calculate monthly revenue per customer."
    )
    parser.add_argument(
        "file",
        nargs="?",
        default="orders.csv",
        help="Path to orders CSV file (default: orders.csv in current directory)",
    )
    parser.add_argument(
        "--ascending",
        action="store_true",
        help="Sort revenue in ascending order instead of descending",
    )
    parser.add_argument(
        "--quiet-skips",
        action="store_true",
        help="Do not display detailed list of skipped rows",
    )

    args = parser.parse_args()

    try:
        records, invalid_rows, total_rows = process_orders(
            file_path=args.file,
            descending=not args.ascending
        )
    except (FileNotFoundError, ValueError) as err:
        print(f"Error: {err}", file=sys.stderr)
        sys.exit(1)

    displayed_invalids = [] if args.quiet_skips else invalid_rows
    print_report(records, displayed_invalids, total_rows)


if __name__ == "__main__":
    main()
