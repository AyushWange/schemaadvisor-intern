BEGIN;

CREATE TABLE customers (
    id BIGSERIAL PRIMARY KEY NOT NULL,
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) UNIQUE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);


CREATE TABLE orders (
    id BIGSERIAL PRIMARY KEY NOT NULL,
    customer_id BIGINT NOT NULL,
    total DECIMAL(18,6) NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'draft',
    shipping_address_id BIGINT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE CASCADE
);

CREATE INDEX idx_orders_customer_id ON orders(customer_id);
CREATE INDEX idx_orders_shipping_address_id ON orders(shipping_address_id);
COMMENT ON COLUMN orders.shipping_address_id IS 'Optional link to shipping address (not enforced)';

COMMIT;