from datetime import datetime, timedelta

def promote_new(products):
    one_week_ago = datetime.now() - timedelta(days=7)
    return sorted(
        [p for p in products if p['listed_date'] >= one_week_ago], 
        key=lambda x: x['listed_date'], 
        reverse=True
    )

def promote_high_revenue_products(products):
    products_sorted = sorted(products, key=lambda x: x['revenue'], reverse=True)
    top_5_percent_index = max(1, len(products_sorted) * 5 // 100)
    return products_sorted[:top_5_percent_index]

def promote_high_inventory_products(products):
    products_sorted = sorted(products, key=lambda x: x['sales_velocity'])
    bottom_10_percent_index = max(1, len(products_sorted) * 10 // 100)
    return products_sorted[:bottom_10_percent_index]

def bestsellers_high_variant_availability(products):
    high_variant_products = [p for p in products if p['variant_availability'] > 0.5]
    sorted_by_revenue = sorted(high_variant_products, key=lambda x: x['revenue'], reverse=True)
    top_20_percent_index = max(1, len(sorted_by_revenue) * 20 // 100)
    return sorted_by_revenue[:top_20_percent_index]

def promote_high_variant_availability(products):
    return sorted(products, key=lambda x: x['variant_availability'], reverse=True)

def clearance_sale(products):
    ninety_days_ago = datetime.now() - timedelta(days=90)
    clearance_products = [p for p in products if p['sales_velocity'] < 0.1 and p['listed_date'] < ninety_days_ago]
    return sorted(clearance_products, key=lambda x: x['sales_velocity'])

def promote_high_revenue_new_products(products):
    one_week_ago = datetime.now() - timedelta(days=7)
    new_products = [p for p in products if p['listed_date'] >= one_week_ago]
    return sorted(new_products, key=lambda x: x['revenue'], reverse=True)

def sort_alphabetically(products):
    if not isinstance(products, list) or not all(isinstance(p, dict) for p in products):
        raise ValueError("Expected a list of dictionaries for products")
    sorted_products = sorted(products, key=lambda x: x['title'].lower())
    return [p['id'] for p in sorted_products]