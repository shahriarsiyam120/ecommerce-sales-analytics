-- Load cleaned CSV files into ecommerce_analytics.
-- Replace each placeholder below with the absolute path to the corresponding file.
-- Use forward slashes in Windows paths, for example C:/path/to/file.csv.
-- LOCAL INFILE must be enabled in both the MySQL client and server configuration.

USE ecommerce_analytics;

-- Load dimensions before orders so that foreign-key references can be checked.
LOAD DATA LOCAL INFILE 'D:/E-commerce Product Analysis/ecommerce-sales-analytics/data/processed/customers_cleaned.csv'
INTO TABLE customers
CHARACTER SET utf8mb4
FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '"'
LINES TERMINATED BY '\n'
IGNORE 1 LINES
(customer_id, customer_name, customer_email, customer_region, customer_city, customer_segment, @signup_date)
SET signup_date = STR_TO_DATE(@signup_date, '%Y-%m-%d');

LOAD DATA LOCAL INFILE 'D:/E-commerce Product Analysis/ecommerce-sales-analytics/data/processed/products_cleaned.csv'
INTO TABLE products
CHARACTER SET utf8mb4
FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '"'
LINES TERMINATED BY '\n'
IGNORE 1 LINES
(product_id, product_name, category, subcategory, unit_cost, unit_price);

LOAD DATA LOCAL INFILE 'D:/E-commerce Product Analysis/ecommerce-sales-analytics/data/processed/orders_cleaned.csv'
INTO TABLE `orders`
CHARACTER SET utf8mb4
FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '"'
LINES TERMINATED BY '\n'
IGNORE 1 LINES
(order_id, @order_date, customer_id, product_id, quantity, discount, payment_method, order_status, gross_sales, discount_amount, net_sales)
SET order_date = STR_TO_DATE(@order_date, '%Y-%m-%d');
