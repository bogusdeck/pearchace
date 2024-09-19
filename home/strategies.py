from datetime import datetime, timedelta
from dateutil import parser
import pytz


def promote_new(products, days: int, percentile: int, variant_threshold: float):
    time_threshold = datetime.now(pytz.utc) - timedelta(days=days)
    recent_products = [
        p for p in products 
        if isinstance(p, dict) and 'listed_date' in p and 'id' in p and isinstance(p['listed_date'], str) and
        parser.isoparse(p['listed_date']) >= time_threshold
    ]
    
    sorted_new_products = sorted(recent_products, key=lambda x: parser.isoparse(x['listed_date']), reverse=True)
    top_percent_index = max(1, len(sorted_new_products) * percentile // 100)
    
    return [{'id': p['id'], 'listed_date': p['listed_date']} for p in sorted_new_products[:top_percent_index]]

def promote_high_revenue_products(products, days: int, percentile: int, variant_threshold: float):
    time_threshold = datetime.now(pytz.utc) - timedelta(days=days)

    recent_products = [
        p for p in products 
        if isinstance(p, dict) and 'listed_date' in p and 'revenue' in p and 'id' in p and
        isinstance(p['listed_date'], str) and
        parser.isoparse(p['listed_date']) >= time_threshold
    ]

    sorted_by_revenue = sorted(recent_products, key=lambda x: x['revenue'], reverse=True)
    top_percent_index = max(1, len(sorted_by_revenue) * percentile // 100)
    top_products = sorted_by_revenue[:top_percent_index]
    top_product_ids = {p['id'] for p in top_products}
    
    reordered_products = sorted(products, key=lambda p: p['id'] not in top_product_ids)
    
    return [{'id': p['id'], 'listed_date': p['listed_date']} for p in reordered_products]


def promote_high_inventory_products(products, days: int, percentile: int, variant_threshold: float):
    time_threshold = datetime.now() - timedelta(days=days)
    recent_products = [
        p for p in products 
        if datetime.fromisoformat(p['listed_date']) >= time_threshold
    ]
    
    sorted_by_velocity = sorted(recent_products, key=lambda x: x['sales_velocity'])
    bottom_percent_index = max(1, len(sorted_by_velocity) * percentile // 100)
    bottom_products = sorted_by_velocity[:bottom_percent_index]
    bottom_product_ids = {p['id'] for p in bottom_products}
    
    reordered_products = sorted(products, key=lambda p: p['id'] not in bottom_product_ids)
    return [{'id': p['id'], 'listed_date': p['listed_date']} for p in reordered_products]

def bestsellers_high_variant_availability(products, days: int, percentile: int, variant_threshold: float):
    time_threshold = datetime.now() - timedelta(days=days)
    recent_high_variant_products = [
        p for p in products 
        if datetime.fromisoformat(p['listed_date']) >= time_threshold and p['variant_availability'] > variant_threshold
    ]
    sorted_by_revenue = sorted(recent_high_variant_products, key=lambda x: x['revenue'], reverse=True)
    top_percent_index = max(1, len(sorted_by_revenue) * percentile // 100)
    top_products = sorted_by_revenue[:top_percent_index]
    top_product_ids = {p['id'] for p in top_products}
    
    reordered_products = sorted(products, key=lambda p: p['id'] not in top_product_ids)
    return [{'id': p['id'], 'listed_date': p['listed_date']} for p in reordered_products]

def promote_high_variant_availability(products, days: int, percentile: int, variant_threshold: float):
    high_variant_products = [
        p for p in products 
        if p['variant_availability'] >= variant_threshold
    ]
    high_variant_ids = {p['id'] for p in high_variant_products}
    
    reordered_products = sorted(products, key=lambda p: p['id'] not in high_variant_ids)
    return [{'id': p['id'], 'listed_date': p['listed_date']} for p in reordered_products]

def clearance_sale(products, days: int, percentile: int, variant_threshold: float):
    lookback_date = datetime.now() - timedelta(days=days)
    eligible_products = [
        p for p in products 
        if datetime.fromisoformat(p['listed_date']) < lookback_date
    ]
    sorted_by_sales_velocity = sorted(eligible_products, key=lambda p: p['sales_velocity'])
    bottom_percentile_index = max(1, len(sorted_by_sales_velocity) * percentile // 100)
    low_sales_velocity_products = sorted_by_sales_velocity[:bottom_percentile_index]
    low_sales_velocity_ids = {p['id'] for p in low_sales_velocity_products}
    
    reordered_products = sorted(products, key=lambda p: p['id'] not in low_sales_velocity_ids)
    return [{'id': p['id'], 'listed_date': p['listed_date']} for p in reordered_products]

def promote_high_revenue_new_products(products, days: int, percentile: int, variant_threshold: float):
    lookback_date = datetime.now() - timedelta(days=days)
    new_products = [
        p for p in products 
        if datetime.fromisoformat(p['listed_date']) >= lookback_date
    ]
    sorted_by_revenue = sorted(new_products, key=lambda p: p['revenue'], reverse=True)
    top_percentile_index = max(1, len(sorted_by_revenue) * percentile // 100)
    top_revenue_new_products = sorted_by_revenue[:top_percentile_index]
    top_revenue_new_product_ids = {p['id'] for p in top_revenue_new_products}
    
    reordered_products = sorted(products, key=lambda p: p['id'] not in top_revenue_new_product_ids)
    return [{'id': p['id'], 'listed_date': p['listed_date']} for p in reordered_products]


# def push_pinned_products_to_top(products, pinned_product_ids):
#     pinned_product_ids_str = set(map(str, pinned_product_ids))
#     sorted_products = sorted(products, key=lambda product: product['id'] not in pinned_product_ids_str)
#     return sorted_products

def push_pinned_products_to_top(products, pinned_product_ids):
    # Convert pinned_product_ids to strings
    pinned_product_ids_str = list(map(str, pinned_product_ids))
    
    pinned_products = []
    non_pinned_products = []

    for product in products:
        if product['id'] in pinned_product_ids_str:
            pinned_products.append(product)
        else:
            non_pinned_products.append(product)

    pinned_products.sort(key=lambda p: pinned_product_ids_str.index(p['id']))

    sorted_products = pinned_products + non_pinned_products
    
    return sorted_products

def push_out_of_stock_down(products, pinned_product_ids):
    pinned_products = []
    non_pinned_products = []
    
    for product in products:
        if int(product['id']) in pinned_product_ids:
            pinned_products.append(product)
        else:
            non_pinned_products.append(product)
    
    in_stock_non_pinned = [p for p in non_pinned_products if p['totalInventory'] > 0]
    out_of_stock_non_pinned = [p for p in non_pinned_products if p['totalInventory'] == 0]
    
    return pinned_products + in_stock_non_pinned + out_of_stock_non_pinned



def push_pinned_out_of_stock_down(products, pinned_product_ids):
    pinned_products = []
    non_pinned_products = []
    
    for product in products:
        if int(product['id']) in pinned_product_ids:
            pinned_products.append(product)
        else:
            non_pinned_products.append(product)
    
    in_stock_pinned = [p for p in pinned_products if p['totalInventory'] > 0]
    out_of_stock_pinned = [p for p in pinned_products if p['totalInventory'] == 0]
    
    return in_stock_pinned + non_pinned_products + out_of_stock_pinned
