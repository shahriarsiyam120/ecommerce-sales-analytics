-- MySQL 8.0+ relational schema for the cleaned e-commerce datasets.
CREATE DATABASE IF NOT EXISTS ecommerce_analytics
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_0900_ai_ci;

USE ecommerce_analytics;

CREATE TABLE IF NOT EXISTS customers (
    customer_id       VARCHAR(20)  NOT NULL,
    customer_name     VARCHAR(150) NOT NULL,
    customer_email    VARCHAR(254) NOT NULL,
    customer_region   VARCHAR(100) NOT NULL,
    customer_city     VARCHAR(100) NOT NULL,
    customer_segment  VARCHAR(100) NOT NULL,
    signup_date       DATE         NOT NULL,
    PRIMARY KEY (customer_id),
    KEY idx_customers_region (customer_region),
    KEY idx_customers_segment (customer_segment)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS products (
    product_id    VARCHAR(20)  NOT NULL,
    product_name  VARCHAR(200) NOT NULL,
    category      VARCHAR(100) NOT NULL,
    subcategory   VARCHAR(100) NOT NULL,
    unit_cost     DECIMAL(12,2) NOT NULL,
    unit_price    DECIMAL(12,2) NOT NULL,
    PRIMARY KEY (product_id),
    KEY idx_products_category (category),
    KEY idx_products_subcategory (subcategory)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS `orders` (
    order_id          VARCHAR(20) NOT NULL,
    order_date        DATE NOT NULL,
    customer_id       VARCHAR(20) NOT NULL,
    product_id        VARCHAR(20) NOT NULL,
    quantity          INT UNSIGNED NOT NULL,
    discount          DECIMAL(5,4) NOT NULL,
    payment_method    VARCHAR(100) NOT NULL,
    order_status      VARCHAR(50) NOT NULL,
    gross_sales       DECIMAL(14,2) NOT NULL,
    discount_amount   DECIMAL(14,2) NOT NULL,
    net_sales         DECIMAL(14,2) NOT NULL,
    PRIMARY KEY (order_id),
    KEY idx_orders_customer_id (customer_id),
    KEY idx_orders_product_id (product_id),
    KEY idx_orders_order_date (order_date),
    KEY idx_orders_order_status (order_status),
    CONSTRAINT fk_orders_customer
        FOREIGN KEY (customer_id) REFERENCES customers (customer_id),
    CONSTRAINT fk_orders_product
        FOREIGN KEY (product_id) REFERENCES products (product_id)
) ENGINE=InnoDB;
