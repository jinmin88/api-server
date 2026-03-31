"""
Load test for the Product API server.

Usage:
    locust -f locustfile.py --host http://localhost:8080

Then open http://localhost:8089 in your browser to configure and start the test.

CLI mode (no UI):
    locust -f locustfile.py --host http://localhost:8080 --headless -u 50 -r 10 --run-time 60s
"""

import random
from locust import HttpUser, task, between


class ProductAPIUser(HttpUser):
    """Simulates a typical user browsing the product catalog."""

    wait_time = between(0.1, 0.5)

    def on_start(self):
        """Pre-generate some product IDs and search terms."""
        self.product_ids = list(range(1, 1001))
        self.search_terms = [
            'Premium', 'Ultra', 'Pro', 'Classic', 'Widget',
            'Gadget', 'Device', 'Smart', 'Kit', 'Elite',
        ]
        self.categories = [
            'Electronics', 'Clothing', 'Home & Kitchen', 'Sports', 'Books',
        ]

    @task(10)
    def get_product(self):
        """Most common: view a product detail page."""
        product_id = random.choice(self.product_ids)
        self.client.get(f'/api/product/{product_id}', name='/api/product/[id]')

    @task(5)
    def list_products(self):
        """Browse products by category."""
        category = random.choice(self.categories)
        page = random.randint(1, 5)
        self.client.get(
            f'/api/products?category={category}&page={page}',
            name='/api/products?category=[cat]',
        )

    @task(3)
    def search(self):
        """Search for products."""
        query = random.choice(self.search_terms)
        self.client.get(f'/api/search?q={query}', name='/api/search')

    @task(1)
    def stats(self):
        """View category statistics (heavy endpoint)."""
        self.client.get('/api/stats')

    @task(2)
    def health_check(self):
        """Health check."""
        self.client.get('/api/health')
