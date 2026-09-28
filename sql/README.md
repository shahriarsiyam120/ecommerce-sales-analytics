# MySQL Analytics Layer

This folder contains a MySQL 8.0+ schema, CSV loading instructions, and reusable read-only analysis queries. The SQL uses the cleaned files in `data/processed/`; it does not modify those CSVs or contain hard-coded results.

## Database design

The database is named `ecommerce_analytics` and uses InnoDB with `utf8mb4` text support.

- `customers` stores one row per customer; `customer_id` is the primary key.
- `products` stores one row per product; `product_id` is the primary key.
- `orders` stores one row per order record, including quantity, discount, and the derived gross, discount, and net sales amounts. `order_id` is the primary key.

`orders.customer_id` references `customers.customer_id`, and `orders.product_id` references `products.product_id`. The schema indexes order customer, product, date, and status fields, plus product category and customer region/segment fields to support common joins and filters.

The current input format has one product per order ID. If a future source represents multi-product orders with one row per order line, model that source with a separate order header and order-line table before loading; the current primary key represents the present cleaned schema.

## Create the database and tables

From the repository root, run the schema using a MySQL account that can create databases and tables:

```bash
mysql -u YOUR_MYSQL_USER -p < sql/schema.sql
```

The database and tables are created if they do not already exist. The schema does not delete existing objects.

## Load the cleaned CSV files

1. Open `sql/load_data.sql` and replace `/PATH/TO/PROJECT` in each `LOAD DATA LOCAL INFILE` statement with the absolute location of this project on your machine. Use forward slashes in Windows paths.
2. Ensure the CSVs exist at `data/processed/customers_cleaned.csv`, `products_cleaned.csv`, and `orders_cleaned.csv`.
3. Enable `LOCAL INFILE` in the MySQL client and server. For the command-line client, connect with the local-infile option and run the loading script:

```bash
mysql --local-infile=1 -u YOUR_MYSQL_USER -p ecommerce_analytics < sql/load_data.sql
```

`LOCAL INFILE` transfers files from the client machine and may be disabled by client/server policy. Enable it only for a trusted local workflow. Load customers and products before orders; the script follows this order to satisfy foreign keys. If loading a CSV that was edited by a Windows tool with CRLF line endings, change the relevant `LINES TERMINATED BY '\n'` clause to `LINES TERMINATED BY '\r\n'`.

## Run the analysis queries

Run any query file from the repository root:

```bash
mysql -u YOUR_MYSQL_USER -p ecommerce_analytics < sql/01_basic_analysis.sql
mysql -u YOUR_MYSQL_USER -p ecommerce_analytics < sql/02_product_analysis.sql
mysql -u YOUR_MYSQL_USER -p ecommerce_analytics < sql/03_customer_analysis.sql
mysql -u YOUR_MYSQL_USER -p ecommerce_analytics < sql/04_time_analysis.sql
```

## Query guide

- `01_basic_analysis.sql` returns headline KPIs and breakdowns by category, subcategory, customer region, payment method, and order status.
- `02_product_analysis.sql` ranks products by sales and quantity, includes products with no sales in the bottom-sales query and revenue-contribution table, and ranks selling products within category.
- `03_customer_analysis.sql` compares customers, segments, and regions. Average customer revenue includes customers with no orders as zero.
- `04_time_analysis.sql` aggregates monthly order and sales measures, calculates average order value, uses `LAG()` for month-over-month net-sales growth, and calculates running cumulative net sales with a windowed `SUM()`.

All queries calculate results from database contents at runtime. They are descriptive and do not imply causal effects or statistical significance.
