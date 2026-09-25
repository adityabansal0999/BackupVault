

CREATE DATABASE IF NOT EXISTS customer_db;
USE customer_db;

CREATE TABLE customers (
customer_id BIGINT AUTO_INCREMENT PRIMARY KEY,
first_name VARCHAR(50) NOT NULL,
last_name VARCHAR(50) NOT NULL,
email VARCHAR(150) NOT NULL UNIQUE,
country VARCHAR(50) NOT NULL,
created_at DATETIME NOT NULL
) ENGINE=InnoDB;

CREATE TABLE orders (
order_id BIGINT AUTO_INCREMENT PRIMARY KEY,
customer_id BIGINT NOT NULL,
order_total DECIMAL(10,2) NOT NULL,
status ENUM('PENDING','SHIPPED','DELIVERED','CANCELLED') NOT NULL,
ordered_at DATETIME NOT NULL,
FOREIGN KEY (customer_id) REFERENCES customers(customer_id) ON DELETE RESTRICT,
INDEX idx_customer_id (customer_id),
INDEX idx_ordered_at (ordered_at)
) ENGINE=InnoDB;
