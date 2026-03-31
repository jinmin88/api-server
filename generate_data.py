"""
Generate seed data for the API server interview question.

Usage:
    python generate_data.py --scale small   # 1K products (~quick)
    python generate_data.py --scale medium  # 50K products
    python generate_data.py --scale full    # 500K products
"""

import argparse
import random

CATEGORIES = [
    'Electronics', 'Clothing', 'Home & Kitchen', 'Sports', 'Books',
    'Beauty', 'Food', 'Toys', 'Automotive', 'Garden',
    'Health', 'Office', 'Pet Supplies', 'Music', 'Movies',
]

ADJECTIVES = [
    'Premium', 'Ultra', 'Pro', 'Classic', 'Deluxe', 'Essential',
    'Advanced', 'Basic', 'Elite', 'Smart', 'Eco', 'Turbo',
    'Mini', 'Max', 'Super', 'Mega', 'Lite', 'Plus',
]

NOUNS = [
    'Widget', 'Gadget', 'Device', 'Tool', 'Kit', 'Set',
    'Pack', 'Bundle', 'System', 'Unit', 'Module', 'Component',
    'Station', 'Hub', 'Controller', 'Adapter', 'Connector', 'Guard',
]

BRANDS = [
    'TechCorp', 'ValueMax', 'ProSeries', 'EcoLine', 'SmartBuy',
    'QualityFirst', 'BestDeal', 'TopChoice', 'UltraGood', 'PrimePick',
]

SCALE_CONFIG = {
    'small': {'products': 1_000, 'relations_per_product': 3},
    'medium': {'products': 50_000, 'relations_per_product': 5},
    'full': {'products': 500_000, 'relations_per_product': 5},
}


def escape_sql(s):
    return s.replace("'", "''")


def generate_product_name():
    adj = random.choice(ADJECTIVES)
    noun = random.choice(NOUNS)
    suffix = random.randint(100, 9999)
    return f'{adj} {noun} {suffix}'


def main():
    parser = argparse.ArgumentParser(description='Generate seed data SQL')
    parser.add_argument('--scale', choices=['small', 'medium', 'full'], default='small')
    args = parser.parse_args()

    config = SCALE_CONFIG[args.scale]
    num_products = config['products']
    relations_per = config['relations_per_product']

    filepath = 'seed_data.sql'
    print(f'Generating {num_products:,} products with ~{relations_per} relations each -> {filepath}')

    with open(filepath, 'w') as f:
        f.write('-- Auto-generated seed data\n')
        f.write('-- Run after init_db.sql\n\n')

        # Generate products in batches
        batch_size = 1000
        f.write('-- Products\n')
        for batch_start in range(0, num_products, batch_size):
            batch_end = min(batch_start + batch_size, num_products)
            f.write('INSERT INTO products (id, name, description, category, brand, price, stock, rating, created_at) VALUES\n')
            rows = []
            for i in range(batch_start, batch_end):
                name = escape_sql(generate_product_name())
                desc = escape_sql(f'High quality {name.lower()} for everyday use')
                category = random.choice(CATEGORIES)
                brand = random.choice(BRANDS)
                price = round(random.uniform(5.0, 999.99), 2)
                stock = random.randint(0, 5000)
                rating = round(random.uniform(1.0, 5.0), 1)
                rows.append(
                    f"  ({i + 1}, '{name}', '{desc}', '{category}', '{brand}', {price}, {stock}, {rating}, "
                    f"NOW() - INTERVAL '{random.randint(1, 730)} days')"
                )
            f.write(',\n'.join(rows))
            f.write(';\n\n')

            if (batch_end) % 50_000 == 0:
                print(f'  Products: {batch_end:,} / {num_products:,}')

        # Generate relations
        f.write('-- Product Relations\n')
        relation_count = 0
        for batch_start in range(0, num_products, batch_size):
            batch_end = min(batch_start + batch_size, num_products)
            f.write('INSERT INTO product_relations (product_id, related_id, relation_type) VALUES\n')
            rows = []
            for i in range(batch_start, batch_end):
                product_id = i + 1
                num_related = random.randint(1, relations_per)
                for _ in range(num_related):
                    related_id = random.randint(1, num_products)
                    if related_id != product_id:
                        rel_type = random.choice(['similar', 'accessory', 'bundle', 'upgrade'])
                        rows.append(f"  ({product_id}, {related_id}, '{rel_type}')")
                        relation_count += 1
            f.write(',\n'.join(rows))
            f.write(';\n\n')

            if (batch_end) % 50_000 == 0:
                print(f'  Relations: through product {batch_end:,}')

        print(f'  Total relations: {relation_count:,}')

    print(f'Done. Run: psql -d products -f seed_data.sql')


if __name__ == '__main__':
    main()
