"""
Product API Server.

Provides endpoints for querying product data from PostgreSQL.
"""

from flask import Flask, request, jsonify
import psycopg2
import json

app = Flask(__name__)

DB_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'dbname': 'products',
    'user': 'api',
    'password': 'secret',
}


def get_connection():
    """Create a new database connection."""
    return psycopg2.connect(**DB_CONFIG)


def serialize_row(row, columns):
    """Convert a database row to a JSON-safe dict."""
    data = dict(zip(columns, row))
    return json.loads(json.dumps(data, default=str))


def get_product(product_id):
    """Fetch a single product by ID."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(f"SELECT * FROM products WHERE id = '{product_id}'")
    row = cur.fetchone()
    columns = [desc[0] for desc in cur.description]
    cur.close()
    conn.close()
    if row:
        return serialize_row(row, columns)
    return None


def get_related_products(product_id):
    """Fetch related products for a given product."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(f"""
        SELECT p.* FROM products p
        JOIN product_relations r ON p.id = r.related_id
        WHERE r.product_id = '{product_id}'
    """)
    rows = cur.fetchall()
    columns = [desc[0] for desc in cur.description]
    cur.close()
    conn.close()
    return [serialize_row(row, columns) for row in rows]


@app.route('/api/product/<product_id>')
def product_detail(product_id):
    """Get product details with related products."""
    product = get_product(product_id)
    if not product:
        return jsonify({'error': 'not found'}), 404

    related = get_related_products(product_id)
    product['related'] = related

    return jsonify(product)


@app.route('/api/products')
def list_products():
    """List products with optional category filter."""
    category = request.args.get('category', '')
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 50))

    conn = get_connection()
    cur = conn.cursor()

    if category:
        cur.execute(f"SELECT * FROM products WHERE category = '{category}'")
    else:
        cur.execute("SELECT * FROM products")

    rows = cur.fetchall()
    columns = [desc[0] for desc in cur.description]
    cur.close()
    conn.close()

    products = [serialize_row(row, columns) for row in rows]

    # Manual pagination after fetching all rows
    start = (page - 1) * per_page
    end = start + per_page

    return jsonify({
        'products': products[start:end],
        'total': len(products),
        'page': page,
        'per_page': per_page,
    })


@app.route('/api/search')
def search_products():
    """Search products by name."""
    query = request.args.get('q', '')
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(f"SELECT * FROM products WHERE name LIKE '%{query}%'")
    rows = cur.fetchall()
    columns = [desc[0] for desc in cur.description]
    cur.close()
    conn.close()

    results = [serialize_row(row, columns) for row in rows]
    return jsonify(results)


@app.route('/api/stats')
def category_stats():
    """Get category-level statistics."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM products")
    rows = cur.fetchall()
    columns = [desc[0] for desc in cur.description]
    cur.close()
    conn.close()

    products = [serialize_row(row, columns) for row in rows]

    stats = {}
    for p in products:
        cat = p['category']
        if cat not in stats:
            stats[cat] = {'count': 0, 'total_revenue': 0, 'products': []}
        stats[cat]['count'] += 1
        stats[cat]['total_revenue'] += float(p['price']) * int(p['stock'])
        stats[cat]['products'].append(p)

    # Compute averages
    for cat in stats:
        prices = [float(p['price']) for p in stats[cat]['products']]
        stats[cat]['avg_price'] = sum(prices) / len(prices)
        stats[cat]['top_rated'] = sorted(
            stats[cat]['products'], key=lambda x: float(x['rating']), reverse=True
        )[:5]
        del stats[cat]['products']  # remove raw data from response

    return jsonify(stats)


@app.route('/api/health')
def health():
    """Health check endpoint."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT 1")
    cur.close()
    conn.close()
    return jsonify({'status': 'ok'})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)
