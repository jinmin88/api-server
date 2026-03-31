# Interviewer Guide: API Server High Throughput

## Hidden Bottlenecks (Priority Order)

| Layer | Problem | Why It's Slow / Dangerous | Impact |
|-------|---------|---------------------------|--------|
| **Fatal** | SQL injection — f-string SQL everywhere | Not performance, but candidate MUST notice | Security red flag |
| **Fatal** | `app.run(debug=True)` — Flask dev server, single-threaded | Cannot handle concurrent requests at all; 80 QPS bottleneck explained | Must fix first |
| **Major** | Every request creates a new `psycopg2.connect()` | TCP handshake + auth = 3-10ms per request; under load, DB connections explode | 5-10x latency improvement |
| **Major** | `/api/product/<id>` makes 2 sequential DB queries | product + related = 2 round-trips, doubling latency | 2x latency |
| **Major** | `/api/products` fetches ALL rows then paginates in Python | `SELECT * FROM products` returns 500K rows, Python slices to 50 | Catastrophic for large datasets |
| **Major** | `/api/stats` loads entire products table into Python and aggregates in app code | Should be a SQL `GROUP BY` query | 10-100x |
| **Medium** | `SELECT *` everywhere | Fetches unnecessary columns (description, created_at, etc.) | 10-30% I/O waste |
| **Medium** | `serialize_row` does `json.dumps` → `json.loads` per row | Double serialization just for type conversion | Constant factor |
| **Medium** | `LIKE '%query%'` — leading wildcard prevents index use | Full table scan for every search | Depends on data size |
| **Arch** | No caching at any level | Product data rarely changes; identical queries repeated | 10-100x for hot data |
| **Arch** | No pagination in search results | Search could return thousands of results in one response | Memory + latency spike |
| **Arch** | No connection cleanup on error (no try/finally or context manager) | Connection leaks on exceptions | Gradual degradation |

## Why 80 QPS is the Ceiling

```
Flask dev server = single-threaded, synchronous
Each request:
  - connect to DB: ~5ms
  - query 1 (product): ~3ms
  - query 2 (related): ~3ms
  - serialize + respond: ~2ms
  Total: ~13ms per request
Theoretical max: 1000ms / 13ms ≈ 77 QPS ← matches the observed ~80 QPS ceiling
```

## Questions a Good Candidate Should Ask

- What WSGI/ASGI server is being used? (If `app.run()` — that's the first problem)
- What's the DB query latency? (Is the bottleneck in Python or PostgreSQL?)
- How often does product data change? (Cache TTL strategy)
- What's the request distribution? (Are 80% of requests for the same popular products?)
- What indexes exist on the products table?
- How many concurrent DB connections can PostgreSQL handle? (`max_connections`)

## Expected Fix Priority (Tiers)

### Tier 0: Prerequisite fixes (without these, nothing else matters)

**WSGI Server:**
```bash
# Replace app.run() with gunicorn
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:8080 server:app
# Or async: gunicorn -w 4 -k uvicorn.workers.UvicornWorker server_async:app
```

**SQL Injection → Parameterized queries:**
```python
cur.execute("SELECT * FROM products WHERE id = %s", (product_id,))
```

### Tier 1: Connection pooling

```python
from psycopg2.pool import ThreadedConnectionPool

pool = ThreadedConnectionPool(minconn=5, maxconn=20, **DB_CONFIG)

def get_connection():
    return pool.getconn()

# Must return connection after use:
# pool.putconn(conn)
# Or use context manager pattern
```

### Tier 2: Fix the worst queries

**`/api/products` — push pagination to SQL:**
```python
cur.execute(
    "SELECT id, name, category, brand, price, rating FROM products "
    "WHERE category = %s ORDER BY id LIMIT %s OFFSET %s",
    (category, per_page, (page - 1) * per_page)
)
```

**`/api/stats` — SQL aggregation instead of Python:**
```python
cur.execute("""
    SELECT category,
           COUNT(*) as count,
           AVG(price) as avg_price,
           SUM(price * stock) as total_revenue
    FROM products
    GROUP BY category
""")
```

**`/api/product/<id>` — single query with JOIN:**
```python
cur.execute("""
    SELECT p.*, r.related_id, rp.name as related_name, rp.price as related_price
    FROM products p
    LEFT JOIN product_relations r ON p.id = r.product_id
    LEFT JOIN products rp ON r.related_id = rp.id
    WHERE p.id = %s
""", (product_id,))
```

### Tier 3: Caching

```python
# In-process LRU for product detail (simple, no external dependency)
from functools import lru_cache

@lru_cache(maxsize=10000)
def get_product_cached(product_id):
    return get_product(product_id)

# Or Redis for shared cache across workers
import redis
r = redis.Redis()

def get_product_cached(product_id):
    key = f'product:{product_id}'
    cached = r.get(key)
    if cached:
        return json.loads(cached)
    product = get_product(product_id)
    r.setex(key, 60, json.dumps(product, default=str))
    return product
```

### Tier 4: Search optimization

```sql
-- PostgreSQL trigram index for LIKE queries
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE INDEX idx_products_name_trgm ON products USING gin (name gin_trgm_ops);

-- Or full-text search
CREATE INDEX idx_products_name_fts ON products USING gin (to_tsvector('english', name));
```

## Tool / Architecture Choice Evaluation

| Candidate Says | How to Evaluate |
|----------------|-----------------|
| "Switch to gunicorn with workers" | Correct first step. Ask: how many workers? sync vs async? |
| "Switch to FastAPI + uvicorn" | Good. Ask: will you also switch DB to asyncpg? If not, what's the benefit? |
| "Add Redis cache" | Reasonable. Ask: cache key design? TTL? Cache stampede protection? Invalidation? |
| "Add nginx reverse proxy" | Ask what problem it solves (rate limiting, static caching, load balancing) |
| "Horizontally scale — add more servers" | Red flag if said first. Ask: each server still hits 80 QPS — you've just delayed the problem |
| "Use ORM (SQLAlchemy)" | Neutral. Ask: ORM adds overhead — why would this be faster? (Answer: connection pool management, query builder) |
| "Use connection pooler (pgbouncer)" | Advanced. Shows understanding of DB-level connection management |

## Estimation Ability (What "Good" Looks Like)

> "Flask dev server is single-threaded synchronous. If each request takes
> ~13ms (5ms connect + 3ms query + 3ms query + 2ms serialize), max throughput
> is ~77 QPS — that matches the 80 QPS ceiling exactly.
>
> Switch to gunicorn with 4 workers: 4 × 77 ≈ 308 QPS.
> Add connection pooling (save 5ms/req): each worker handles ~125 QPS → 500 QPS.
> Add caching with 80% hit rate: only 100 QPS hit DB, 400 QPS served from cache
> at <5ms → P95 well under 200ms. Target achieved."

## Security Issues the Candidate Should Identify

1. **SQL Injection** (critical): f-string SQL in every query
   - `/api/search?q=' OR '1'='1` dumps entire table
   - `/api/product/' OR '1'='1' --` bypasses ID lookup
2. **No input validation**: `per_page` could be set to 1000000
3. **Debug mode enabled**: `debug=True` exposes stack traces
4. **Credentials in source code**: DB password hardcoded

A strong candidate identifies SQL injection immediately, even before talking about performance.

## Measurement Design (Expected Answer)

- Use `locust` or `wrk` to establish baseline (QPS, P50, P95, P99, error rate)
- Enable PostgreSQL `log_min_duration_statement = 100` to find slow queries
- Use `py-spy` for Python-side profiling under load
- Benchmark each change independently under the same load pattern
- Simulate realistic traffic distribution (not all requests hitting same ID)

## Follow-up Questions (Optional)

1. "After optimization, QPS is at 500 but P99 occasionally spikes to 3 seconds."
   → Investigate: cache stampede on popular products? GC pause? Connection pool exhaustion? PostgreSQL autovacuum?

2. "Product data now updates every 5 minutes. Users complain about stale prices."
   → Cache invalidation: TTL-based vs event-driven (listen/notify in PostgreSQL)

3. "Target is now 5000 QPS."
   → Read replicas, connection pooler (pgbouncer), CDN for public API, horizontal scaling with load balancer

## Scoring Guide

| Level | What They Do |
|-------|-------------|
| **Fail** | Doesn't notice SQL injection. Says "add more servers" without understanding single-machine bottleneck |
| **Junior** | Notices dev server issue. May miss SQL injection. Suggests "use async" without specifics |
| **Mid** | Fixes dev server + connection pool. Notices SQL injection. May not estimate throughput accurately |
| **Senior** | Calculates theoretical QPS limit. Fixes in correct priority order. Identifies SQL injection immediately. Estimates impact of each change. Sets up proper load testing |
| **Staff+** | All of the above, plus: discusses cache invalidation strategies, connection pool sizing, database-level optimizations (pgbouncer, read replicas), monitoring/alerting under load, graceful degradation |
