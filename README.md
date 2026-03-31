# Performance Challenge: API Server High Throughput

## Background

You are joining a backend team responsible for an internal product data API. The service queries PostgreSQL and returns JSON responses. Traffic is growing and the current implementation can't keep up.

## The Problem

The API server currently handles about **50 QPS** on a single machine. The team needs it to support **500 QPS** with **P95 latency under 200ms**.

Load testing shows that beyond ~80 QPS, requests start timing out and P95 latency spikes to over 2 seconds.

## Setup

### Prerequisites
- Python 3.10+
- PostgreSQL (running locally or via Docker)

### Database Setup

```bash
# Create database and user
createdb products
psql -d products -c "CREATE USER api WITH PASSWORD 'secret';"
psql -d products -c "GRANT ALL PRIVILEGES ON DATABASE products TO api;"

# Create schema
psql -d products -f init_db.sql

# Generate and load seed data
python generate_data.py --scale small   # 1K products (quick start)
python generate_data.py --scale medium  # 50K products
python generate_data.py --scale full    # 500K products

psql -d products -f seed_data.sql
psql -d products -c "GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO api;"
psql -d products -c "GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO api;"
```

### Install Dependencies

```bash
pip install -r requirements.txt
```

### Run the Server

```bash
python server.py
```

Server runs at http://localhost:8080

### Load Testing

```bash
# Using locust (web UI)
locust -f locustfile.py --host http://localhost:8080

# Using locust (CLI, 50 users, ramp up 10/sec, run 60 seconds)
locust -f locustfile.py --host http://localhost:8080 --headless -u 50 -r 10 --run-time 60s
```

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /api/product/<id>` | Product detail with related products |
| `GET /api/products?category=X&page=N` | List products by category |
| `GET /api/search?q=term` | Search products by name |
| `GET /api/stats` | Category-level statistics |
| `GET /api/health` | Health check |

## Your Task

1. **Profile** the existing server and identify why it can't handle more than ~80 QPS.
2. **Optimize** the server to reach 500 QPS with P95 < 200ms.
3. All API responses must remain functionally equivalent.

## Constraints

- Python 3.10+
- Single machine deployment (no horizontal scaling as the first answer)
- You may change the web framework, database driver, or add caching
- You may modify database indexes

## Evaluation Criteria

- Did you identify the root cause before optimizing?
- Can you explain the theoretical throughput limit of the current architecture?
- Did you address issues in the right priority order?
- Can you estimate the impact of each change?
- Did you notice any security issues?
- How do you verify your improvements under load?
