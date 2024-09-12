from datetime import datetime, timedelta

def promote_new(products, days: int):
    # Sorts products so that those product which is uploaded within the last `days` come first,
    # list of str: list of product IDs, with newly added product first
    time_threshold = datetime.now() - timedelta(days=days)
    new_products = [p for p in products if p['listed_date'] >= time_threshold]
    return sorted(new_products, key=lambda x: x['listed_date'], reverse=True)

# def promote_high_revenue_products(products, days: int, percentile: int):
#     # Sorts products so that those in the top percentile of 
#     time_threshold = datetime.now() - timedelta(days=days)    
#     recent_products = [p for p in products if p['listed_date'] >= time_threshold]    
#     sorted_by_revenue = sorted(recent_products, key=lambda x: x['revenue'], reverse=True)    
#     top_percent_index = max(1, len(sorted_by_revenue) * percentile // 100)    
#     return sorted_by_revenue[:top_percent_index]


def promote_high_revenue_products(products, days: int, percentile: int):
# Sorts products so that those in the top `percentile` of revenue within the last `days` come first,  
# list of str: List of product IDs, with top revenue products first.
    time_threshold = datetime.now() - timedelta(days=days)    
    recent_products = [p for p in products if p['listed_date'] >= time_threshold]    
    sorted_by_revenue = sorted(recent_products, key=lambda x: x['revenue'], reverse=True)    
    top_percent_index = max(1, len(sorted_by_revenue) * percentile // 100) #hmmm    
    top_products = sorted_by_revenue[:top_percent_index]    
    top_product_ids = {p['id'] for p in top_products}    
    reordered_products = sorted(products, key=lambda p: p['id'] not in top_product_ids)    
    return [p['id'] for p in reordered_products]


def promote_high_inventory_products(products, days: int, percentile: int):
    #Sorts products so that those in the bottom `percentile` of sales velocity within the last `days`
    #come first, but the rest of the products follow in their original order.
    # list of str: List of product IDs, with bottom sales velocity products first.
    time_threshold = datetime.now() - timedelta(days=days)    
    recent_products = [p for p in products if p['listed_date'] >= time_threshold]    
    sorted_by_velocity = sorted(recent_products, key=lambda x: x['sales_velocity'])    
    bottom_percent_index = max(1, len(sorted_by_velocity) * percentile // 100)    
    bottom_products = sorted_by_velocity[:bottom_percent_index]
    bottom_product_ids = {p['id'] for p in bottom_products}    
    reordered_products = sorted(products, key=lambda p: p['id'] not in bottom_product_ids)
    return [p['id'] for p in reordered_products]


def bestsellers_high_variant_availability(products, days: int, revenue_percentile: int, variant_threshold: float):
    # Sorts products to prioritize those with high variant availability and within the top `revenue_percentile` of revenue.
    # list of str: List of product IDs, with top revenue and high variant products first.
    time_threshold = datetime.now() - timedelta(days=days)    
    recent_high_variant_products = [
        p for p in products 
        if p['listed_date'] >= time_threshold and p['variant_availability'] > variant_threshold
    ]    
    sorted_by_revenue = sorted(recent_high_variant_products, key=lambda x: x['revenue'], reverse=True)    
    top_percent_index = max(1, len(sorted_by_revenue) * revenue_percentile // 100)    
    top_products = sorted_by_revenue[:top_percent_index]    
    top_product_ids = {p['id'] for p in top_products}    
    reordered_products = sorted(products, key=lambda p: p['id'] not in top_product_ids)
    
    return [p['id'] for p in reordered_products]

def promote_high_variant_availability(products, variant_threshold: float):
    # Sorts products to prioritize those with higher variant availability.
    # list of str: List of product IDs, with high variant availability products first.
    high_variant_products = [p for p in products if p['variant_availability'] >= variant_threshold]
    high_variant_ids = {p['id'] for p in high_variant_products}
    reordered_products = sorted(products, key=lambda p: p['id'] not in high_variant_ids)
    return [p['id'] for p in reordered_products]


def clearance_sale(products, lookback_days: int, bottom_percentile_threshold: int):
    # Sorts products to prioritize those with low sales velocity and listed before the lookback period.
    # list of str: List of product IDs, with low sales velocity products first.
    lookback_date = datetime.now() - timedelta(days=lookback_days)
    eligible_products = [p for p in products if p['listed_date'] < lookback_date]
    sorted_by_sales_velocity = sorted(eligible_products, key=lambda p: p['sales_velocity'])
    bottom_percentile_index = max(1, len(sorted_by_sales_velocity) * bottom_percentile_threshold // 100)
    low_sales_velocity_products = sorted_by_sales_velocity[:bottom_percentile_index]
    low_sales_velocity_ids = {p['id'] for p in low_sales_velocity_products}
    reordered_products = sorted(products, key=lambda p: p['id'] not in low_sales_velocity_ids)
    return [p['id'] for p in reordered_products]


def promote_high_revenue_new_products(products, lookback_days: int, top_percentile_threshold: int):
    # Sorts products so that new products (based on the lookback period) with high revenue come first.
    # list of str: List of product IDs, with high revenue new products first.
    lookback_date = datetime.now() - timedelta(days=lookback_days)
    new_products = [p for p in products if p['listed_date'] >= lookback_date]
    sorted_by_revenue = sorted(new_products, key=lambda p: p['revenue'], reverse=True)
    top_percentile_index = max(1, len(sorted_by_revenue) * top_percentile_threshold // 100)
    top_revenue_new_products = sorted_by_revenue[:top_percentile_index]
    top_revenue_new_product_ids = {p['id'] for p in top_revenue_new_products}
    reordered_products = sorted(products, key=lambda p: p['id'] not in top_revenue_new_product_ids)
    

    return [p['id'] for p in reordered_products]

def sort_alphabetically(products):
    if not isinstance(products, list) or not all(isinstance(p, dict) for p in products):
        raise ValueError("Expected a list of dictionaries for products")
    sorted_products = sorted(products, key=lambda x: x['title'].lower())
    return [p['id'] for p in sorted_products]
