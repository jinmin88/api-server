-- Database schema for API server interview question
-- Usage: psql -d products -f init_db.sql

DROP TABLE IF EXISTS product_relations;
DROP TABLE IF EXISTS products;

CREATE TABLE products (
    id            INTEGER PRIMARY KEY,
    name          VARCHAR(255) NOT NULL,
    description   TEXT,
    category      VARCHAR(100) NOT NULL,
    brand         VARCHAR(100),
    price         DECIMAL(10, 2) NOT NULL,
    stock         INTEGER DEFAULT 0,
    rating        DECIMAL(2, 1),
    created_at    TIMESTAMP DEFAULT NOW()
);

CREATE TABLE product_relations (
    id            SERIAL PRIMARY KEY,
    product_id    INTEGER NOT NULL REFERENCES products(id),
    related_id    INTEGER NOT NULL REFERENCES products(id),
    relation_type VARCHAR(50) DEFAULT 'similar'
);

-- Minimal indexes (intentionally not over-indexed)
CREATE INDEX idx_products_category ON products(category);
CREATE INDEX idx_relations_product_id ON product_relations(product_id);
