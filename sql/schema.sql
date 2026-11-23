CREATE DATABASE diyar_market;

CREATE TABLE customers (
    customer_id SERIAL PRIMARY KEY ,
    customer_name VARCHAR(50) NOT NULL,
    phone VARCHAR(20) UNIQUE
);
CREATE TABLE products (
    id_product SERIAL PRIMARY KEY,
    product_name VARCHAR(100) NOT NULL,
    price NUMERIC(10,2) NOT NULL
);

CREATE TABLE orders (
    order_id SERIAL PRIMARY KEY,
    order_ref VARCHAR(50) UNIQUE NOT NULL,
    shipping_city VARCHAR(100),
    total_amount NUMERIC(10, 2) ,
    order_date TIMESTAMP,
    customer_id INT REFERENCES customers(customer_id)
);
CREATE TABLE order_items(
    order_id INT REFERENCES orders(order_id),
    id_product INT REFERENCES products(id_product),
    quantite INT NOT NULL,
    PRIMARY KEY (order_id, id_product)
);

CREATE TABLE shipments (
    shipment_id SERIAL PRIMARY KEY,
    order_id INT NOT NULL REFERENCES orders(order_id),
    carrier_name VARCHAR(50) NOT NULL,
    tracking_ref VARCHAR(100),
    status VARCHAR(50),
    shipped_at TIMESTAMP,
    delivered_at TIMESTAMP
);