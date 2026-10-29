# Order Revenue Analyzer

A robust, dependency-free Python application that reads order records from a CSV file (`orders.csv`), validates each row, reports skipped/corrupted entries with detailed diagnostics, and calculates and displays total revenue per customer per month sorted by revenue.

---

## 📋 Features

- **Zero External Dependencies**: Implemented entirely with Python's built-in standard library (`csv`, `decimal`, `datetime`, `pathlib`, `argparse`).
- **Financial Precision**: Uses `Decimal` rather than floating-point arithmetic to avoid rounding inaccuracies in revenue sums.
- **Strict Data Validation**:
  - `order_id`: Must be a non-empty string.
  - `customer_id`: Must be a non-empty string.
  - `amount`: Must be a valid positive numeric value (`> 0.00`). Handles currency symbols (e.g., `$`) and comma thousand-separators gracefully.
  - `created_at`: Parses ISO-8601 timestamps (including UTC `Z` and timezone offsets) as well as common standard date formats, mapping them accurately to `YYYY-MM`.
- **Informative Reporting**:
  - Skips invalid rows without crashing.
  - Reports each skipped row with its exact CSV line number, raw content, and the specific failure reason.
  - Displays summary statistics (total rows read, valid rows, invalid rows).
- **Sorted Aggregate Output**:
  - Aggregates total revenue and order count per customer per calendar month.
  - Sorts results in descending order by revenue (highest grossing customer-month first).
  - Clean, formatted ASCII table with monetary formatting.
- **Unit Tested**: Comprehensive test suite covering validation rules, edge cases, aggregations, precision, and sorting.

---

## 📂 Repository Structure

```text
├── process_orders.py       # Main processing script and CLI entry point
├── test_process_orders.py  # Unit test suite using unittest
├── orders.csv              # Sample dataset with valid & invalid rows
├── .gitignore              # Standard Python gitignore
└── README.md               # Documentation and usage guide
```

---

## 📊 CSV Schema

The input CSV file must include a header with the following four columns:

| Column | Type | Description | Validation Rule |
| :--- | :--- | :--- | :--- |
| `order_id` | String | Unique identifier for the order | Non-empty, non-whitespace |
| `customer_id` | String | Identifier for the customer | Non-empty, non-whitespace |
| `amount` | Numeric / Decimal | Monetary value of the order | Must be a valid number `> 0` |
| `created_at` | Date / Timestamp | Timestamp when the order was placed | Parseable ISO date or standard format |

---

## 🚀 Quickstart & Usage

### Prerequisites
- Python 3.8 or higher. No external libraries (`pip install`) required.

### 1. Run with Default File (`orders.csv`)
```bash
python3 process_orders.py
```

### 2. Run with a Custom CSV File
```bash
python3 process_orders.py path/to/my_orders.csv
```

### 3. CLI Options
```text
usage: process_orders.py [-h] [--ascending] [--quiet-skips] [file]

Process orders CSV, skip/report invalid rows, and calculate monthly revenue per customer.

positional arguments:
  file           Path to orders CSV file (default: orders.csv in current directory)

options:
  -h, --help     show this help message and exit
  --ascending    Sort revenue in ascending order instead of descending
  --quiet-skips  Do not display detailed list of skipped rows
```

---

## 🖥️ Example Output

Running `python3 process_orders.py orders.csv` produces:

```text
============================================================================
                    ORDER PROCESSING REPORT                     
============================================================================
Total Rows Read : 20
Valid Rows      : 13
Invalid Rows    : 7
============================================================================

----------------------------------------------------------------------------
                 SKIPPED / INVALID ROWS REPORT                  
----------------------------------------------------------------------------
  • Row   7: Empty or whitespace 'customer_id'
    Raw Data: {order_id: 'ORD-006', customer_id: '', amount: '99.00', created_at: '2024-02-05T12:00:00Z'}
  • Row   8: Invalid 'amount' value '-45.00' (must be greater than 0)
    Raw Data: {order_id: 'ORD-007', customer_id: 'CUST-004', amount: '-45.00', created_at: '2024-02-08T16:30:00Z'}
  • Row  10: Invalid 'amount' value 'invalid_amt' (must be a valid numeric amount)
    Raw Data: {order_id: 'ORD-009', customer_id: 'CUST-003', amount: 'invalid_amt', created_at: '2024-02-20T13:10:00Z'}
  • Row  13: Invalid 'amount' value '0.00' (must be greater than 0)
    Raw Data: {order_id: 'ORD-012', customer_id: 'CUST-004', amount: '0.00', created_at: '2024-03-05T09:40:00Z'}
  • Row  15: Invalid 'created_at': Unrecognized date/timestamp format: 'not-a-valid-date'
    Raw Data: {order_id: 'ORD-014', customer_id: 'CUST-001', amount: '420.00', created_at: 'not-a-valid-date'}
  • Row  17: Empty or whitespace 'order_id'
    Raw Data: {order_id: '', customer_id: 'CUST-006', amount: '125.00', created_at: '2024-03-20T11:00:00Z'}
  • Row  19: Missing or empty 'created_at'
    Raw Data: {order_id: 'ORD-018', customer_id: 'CUST-006', amount: '340.00', created_at: ''}
----------------------------------------------------------------------------

============================================================================
           REVENUE PER CUSTOMER PER MONTH (SORTED BY REVENUE)   
============================================================================
Month        | Customer ID              |       Orders |        Revenue ($)
-------------+--------------------------+--------------+-------------------
2024-01      | CUST-003                 |            2 |          $1,650.00
2024-03      | CUST-003                 |            1 |            $750.50
2024-03      | CUST-005                 |            1 |            $610.00
2024-02      | CUST-005                 |            1 |            $520.75
2024-02      | CUST-001                 |            1 |            $350.00
2024-02      | CUST-002                 |            1 |            $310.25
2024-03      | CUST-002                 |            2 |            $275.25
2024-01      | CUST-002                 |            1 |            $240.50
2024-01      | CUST-001                 |            2 |            $239.99
2024-03      | CUST-001                 |            1 |            $215.50
-------------+--------------------------+--------------+-------------------
TOTAL        | 10 grouping(s)           |           13 |          $5,162.74
============================================================================
```

---

## 🧪 Running Tests

Execute the automated test suite with Python's built-in `unittest` runner:

```bash
python3 -m unittest -v test_process_orders.py
```

All tests run locally in milliseconds with zero dependencies.

---

## 📄 License

This project is licensed under the MIT License.
