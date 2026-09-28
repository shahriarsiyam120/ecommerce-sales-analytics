# E-Commerce Sales Analytics & Intelligence

A reproducible analytics project for validating, cleaning, exploring, and reporting on e-commerce order data. The included sample is generated for demonstration and does not represent real customers, products, or business results.

## Project overview

The project turns related customer, product, and order tables into quality reports, descriptive analyses, SQL queries, and an interactive dashboard. It starts with local sample CSVs and provides a configurable boundary for CSV, Excel, Parquet, or MySQL sources.

## Business problem

E-commerce teams need a consistent view of sales trends, product performance, customer purchasing behavior, discounts, order statuses, payment methods, and regions. This project makes those measures reproducible from validated source tables rather than hard-coding business results in the dashboard.

## Architecture

- `data/raw/` — source files kept as received.
- `data/processed/` — validated and cleaned outputs for analysis.
- `data/sample/` — reproducible synthetic sample inputs.
- `notebooks/` — exploratory analysis and documentation.
- `src/ingestion/` — sample generation and configurable CSV, Excel, Parquet, and MySQL adapters.
- `src/validation/` — checking input structure and data quality.
- `src/cleaning/` — reusable cleaning and normalization steps.
- `src/features/` — reusable derived fields for analysis.
- `src/analytics/` — business metric calculations and analysis.
- `src/visualization/` — reusable charts and reporting visuals.
- `sql/` — SQL queries and transformations.
- `dashboard/` — Streamlit app and reusable dashboard data functions.
- `reports/` — generated analysis reports and deliverables.
- `tests/` — automated checks for pipeline components.
- `config/` — configuration for sources and pipeline behavior.

The flow is ingestion → raw validation → cleaning → processed validation → features/analytics → dashboard or SQL. Source-specific logic stays at the ingestion boundary; downstream stages consume a consistent tabular format.

```mermaid
flowchart LR
	A[Sample CSVs or configured source] --> B[Ingestion and column mapping]
	B --> C[Raw validation]
	C --> D[Cleaning and financial fields]
	D --> E[Processed standard tables]
	E --> F[EDA and existing SQL layer]
	E --> G[Advanced analytics and reusable features]
	G --> H[Streamlit dashboard]
```

## Data pipeline

The sample flow is `data/sample/` → validation → cleaning → processed validation → `data/processed/` → EDA/advanced analytics → dashboard or MySQL. Configured sources use the same downstream stages after raw validation. Source files are opened read-only; generated tables and reports stay in processed/output directories.

## Dataset description

The three related tables describe customers, products, and order records. Customer fields include region and segment; product fields include category, subcategory, unit cost, and unit price; order fields include date, quantity, discount, payment method, status, and derived sales values. The current sample has 500 customers, 100 products, and 5,000 orders. Names and emails are illustrative and use the reserved `.invalid` domain. The SQL schema represents one product per order record.

## Technologies

Python, pandas, Streamlit, MySQL 8.0+, Jupyter, and pytest are used for processing, reporting, and validation.

## Real-data integration

For real data, keep an unchanged local source in `data/raw/`, configure column mappings, and use the configured pipeline. Validation runs before cleaning. Raw data and credentials must not be committed.

## Generate the synthetic sample

Run from the project root with Python 3.10 or newer:

```bash
python src/ingestion/generate_sample_data.py
```

The script uses only the Python standard library and a fixed seed. It writes `customers.csv`, `products.csv`, and `orders.csv` to `data/sample/`. The customer and product tables use `customer_id` and `product_id` as unique keys; each order references one row from each table. Order dates span January through December 2025.

The generator checks row counts, unique IDs, missing values, order foreign keys, and the order date range before writing output. The CSV files are generated artifacts and can be recreated by running the script.

## Data validation

The validation layer checks the customer, product, and order CSVs before they enter later pipeline stages. It verifies required schemas, reports unexpected columns, checks missing values and duplicate primary keys, validates text/date/numeric fields and supported categories, applies product and order business rules, and checks order-to-customer and order-to-product references. A schema mismatch, missing value, duplicate key, invalid value, or broken reference is a failure; additional unrecognized columns are reported as a warning so downstream changes are visible.

Run from the project root:

```bash
python src/validation/data_validator.py
```

`PASS` means all configured checks passed. `WARNING` means the required data checks passed but unexpected columns were found. `FAIL` means a critical schema or data-quality rule failed; the command exits with a non-zero status.

## Data cleaning

The reusable cleaning pipeline reads `data/sample/customers.csv`, `products.csv`, and `orders.csv` as source inputs and writes cleaned copies to `data/processed/customers_cleaned.csv`, `products_cleaned.csv`, and `orders_cleaned.csv`. It never writes to `data/sample/`.

Cleaning trims text, standardizes blank and common null markers as missing, normalizes categorical text, parses dates, and converts product prices and order quantity/discount to numeric values. Invalid dates and numbers become missing so they remain visible to quality checks. Exact duplicate rows are removed with the first occurrence retained; no other records are dropped. Conflicting duplicate IDs and invalid business values remain for review and cause processed validation to fail.

Orders include `gross_sales`, `discount_amount`, and `net_sales`, calculated from quantity, the referenced product's unit price, and discount. Profit is not calculated because order-level product cost is not available. Before/after summaries and a per-dataset cleaning report are written to `data/processed/cleaning_report.json`.

Run from the project root:

```bash
python src/cleaning/data_cleaner.py
```

The cleaner validates the processed data with the validation layer after writing the output files. Its exit status is nonzero if required inputs are missing or processed data fails validation.

## Exploratory data analysis

The reusable EDA module loads the cleaned CSVs from `data/processed/`, parses dates, joins orders to product and customer attributes, calculates requested KPIs and descriptive summaries, and writes analytical CSVs and an EDA summary to `data/processed/analytics/`. A focused set of labeled charts is saved to `reports/figures/`. The notebook at `notebooks/ecommerce_eda.ipynb` presents the analysis and supports interpretation. No raw or cleaned input files are modified.

The analysis includes order, customer, product, quantity, gross sales, discounts, net sales, and average order value KPIs; product, category, subcategory, customer, segment, regional, and monthly summaries; and month-over-month net sales growth where a previous month and nonzero denominator are available. Results are descriptive and do not imply statistical significance or causality.

Install the listed dependencies with `pip install -r requirements.txt`. From the project root, generate all output tables and charts with:

```bash
python src/analytics/basic_eda.py
```

The notebook can also be opened and run from a Jupyter environment after installing the dependencies.

## MySQL analytics layer

The `sql/` directory contains the MySQL 8.0+ schema, CSV loading instructions, and reusable queries for core KPIs, product and customer rankings, category/region/payment/status breakdowns, and monthly sales trends. The schema relates orders to customers and products with foreign keys. SQL analysis reads values at execution time; query results are not stored in the source files.

See [sql/README.md](sql/README.md) for database setup, `LOCAL INFILE` configuration, path placeholders, and commands to load the cleaned CSVs and run each query file.

For example, after configuring MySQL and loading the CSVs as described there:

```bash
mysql -u YOUR_MYSQL_USER -p < sql/schema.sql
mysql --local-infile=1 -u YOUR_MYSQL_USER -p ecommerce_analytics < sql/load_data.sql
mysql -u YOUR_MYSQL_USER -p ecommerce_analytics < sql/01_basic_analysis.sql
```

## Advanced analytics

Run after cleaning to write reusable order features and business summaries under `data/processed/analytics/`:

```bash
python -m src.analytics.advanced_analytics
```

The outputs include enriched orders, KPIs, customer historical revenue/order frequency/average order value, relative value segments, product and category/subcategory contributions, cumulative Pareto fields, monthly revenue/order growth, regions, payment methods, order statuses, and discount bands. Feature fields include `order_value`, `discount_rate`, `month`, `quarter`, `year`, `customer_order_count`, `customer_total_revenue`, `customer_average_order_value`, `product_total_quantity`, and `product_total_revenue`.

Customer groups are descriptive and rule-based: customers with non-positive observed net revenue are low value; remaining customers are ranked by observed net revenue, with the bottom 20% low value, the top 20% high value, and the middle group medium value. Ties can affect group sizes. Historical revenue covers the observed window, not a customer's full lifetime or predicted future value. Revenue includes all recorded statuses unless filtered. Discount-band comparisons are descriptive, not causal.

## Interactive dashboard

The Streamlit app reads the persisted advanced analytics layer rather than rerunning cleaning or analytics in the UI. It includes executive KPIs and trends, sales breakdowns, product performance, customer segments/frequency, and date, region, customer segment, category, status, and payment filters.

```bash
streamlit run dashboard/app.py
```

Generate cleaned data and advanced analytics first. If files are missing or incompatible, the app gives a setup message. Revenue uses source currency units; there is no currency conversion.

## Real dataset integration

Copy `config/data_source.example.json` to a local config, then set source paths, formats, sheets, and `column_mapping`. Mapping keys are source column names and values are standardized internal names. Supported files are CSV, Excel (`.xlsx`), and Parquet. The configured pipeline validates source data before cleaning, validates processed outputs, then runs advanced analytics:

```bash
python -m src.ingestion.configured_pipeline --config config/data_source.json
```

For MySQL, use `source_type: "mysql"`, specify table names, and set `database.url_env` to the name of an environment variable containing the SQLAlchemy connection URL. For example: `mysql+pymysql://USER:PASSWORD@HOST/DATABASE`. Do not store credentials in JSON, source code, or version control. Excel, Parquet, and MySQL support use `openpyxl`, `pyarrow`, SQLAlchemy, and PyMySQL.

The pipeline only writes derived files under the configured processed output directory. A source missing a required business field must be resolved explicitly; the pipeline does not invent it.

## Testing

Install development dependencies and run from the project root:

```bash
python -m pip install -r requirements-dev.txt
python -m pytest
```

Tests cover analytics calculations and edge cases, dashboard filtering/KPIs, cleaning and financial calculations, missing values, duplicate keys, category configuration, and foreign-key validation. Tests use in-memory fixtures and do not overwrite project data files.

## Installation and sample workflow

Use Python 3.10 or newer. For PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
```

From the repository root, the sample workflow is:

```bash
python -m src.ingestion.generate_sample_data
python -m src.validation.data_validator
python -m src.cleaning.data_cleaner
python -m src.analytics.basic_eda
python -m src.analytics.advanced_analytics
```

The generator writes only to `data/sample/`; cleaning reads those files and writes processed copies. MySQL server/client installation and execution are separate; see [sql/README.md](sql/README.md).

## Key business metrics

- Net revenue is the sum of `net_sales` in scope.
- Average order value is selected net revenue divided by distinct order IDs.
- Customer frequency is the distinct order count per customer in scope.
- Revenue contribution is product/category revenue divided by total revenue in that analysis.
- Monthly growth compares against the previous observed month and is undefined when the previous month is unavailable or zero.
- Customer value segment is a relative historical-revenue rank, not a prediction.

## Project structure

```text
config/                 Example source configuration
dashboard/              Streamlit app and data functions
data/sample/            Reproducible demonstration inputs
data/raw/               Local source inputs, kept unchanged
data/processed/         Generated cleaned tables and analytics
notebooks/              Exploratory analysis notebook
reports/figures/        Generated EDA figures
sql/                    MySQL schema, load script, and queries
src/analytics/          Existing EDA and advanced analytics
src/cleaning/           Cleaning and financial calculations
src/ingestion/          Sample generator and configured adapters
src/validation/         Schema, value, business-rule, and FK checks
tests/                  Automated unit tests
```

## Limitations and future work

Sample data is synthetic and does not represent business outcomes. Historical customer revenue is limited to the supplied window and may include non-completed statuses. Discount comparisons are observational. Profit, tax, shipping, returns accounting, and currency conversion are not inferred when source fields are unavailable. The current SQL schema expects one product per order record; multi-line order support requires an explicit order/header-line model. No live database deployment or hosted dashboard is configured. Future improvements could add configurable revenue-recognition rules, order-line support, data freshness checks, scheduled refreshes, and explicit currency/cost fields when available.
