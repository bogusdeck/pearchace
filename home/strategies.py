from datetime import datetime, timedelta
from dateutil import parser
import pytz

def promote_new(products, days: int = None, percentile: int = 100, variant_threshold: float = 0.0):
    if days is not None:
        time_threshold = datetime.now(pytz.utc) - timedelta(days=days)
        recent_products = [
            p for p in products 
            if isinstance(p, dict) and 'listed_date' in p and 'id' in p 
            and isinstance(p['listed_date'], str)
            and parser.isoparse(p['listed_date']) >= time_threshold
        ]
    else:
        recent_products = products
        
    sorted_new_products = sorted(
        recent_products, 
        key=lambda x: parser.isoparse(x['listed_date']), 
        reverse=True
    )
    
    top_percent_index = max(1, len(sorted_new_products) * (percentile or 100) // 100)
    
    return sorted_new_products[:top_percent_index]

def promote_high_revenue_products(products, days: int = None, percentile: int = 100, variant_threshold: float = 0.0):
    if days is not None:
        time_threshold = datetime.now(pytz.utc) - timedelta(days=days)
        recent_products = [
            p for p in products 
            if isinstance(p, dict) and 'listed_date' in p and 'revenue' in p and 'id' in p and
            isinstance(p['listed_date'], str) and
            parser.isoparse(p['listed_date']) >= time_threshold
        ]
    else:
        recent_products = products

    sorted_by_revenue = sorted(recent_products, key=lambda x: x.get('revenue', 0), reverse=True)

    top_percent_index = max(1, len(sorted_by_revenue) * (percentile or 100) // 100)
    top_products = sorted_by_revenue[:top_percent_index]

    remaining_products = [p for p in products if p not in top_products]

    reordered_products = top_products + remaining_products

    return reordered_products

def promote_high_inventory_products(products, days: int = None, percentile: int = 100, variant_threshold: float = 0.0):
    if days is not None:
        time_threshold = datetime.now() - timedelta(days=days)
        recent_products = [
            p for p in products 
            if isinstance(p, dict) and 'listed_date' in p and 'sales_velocity' in p and 'id' in p and
            isinstance(p['listed_date'], str) and
            parser.isoparse(p['listed_date']) >= time_threshold
        ]
    else:
        recent_products = products

    sorted_by_velocity = sorted(recent_products, key=lambda x: x.get('sales_velocity', 0))
    
    bottom_percent_index = max(1, len(sorted_by_velocity) * (percentile or 100) // 100)
    
    bottom_products = sorted_by_velocity[:bottom_percent_index]
    remaining_products = sorted_by_velocity[bottom_percent_index:]

    reordered_products = bottom_products + remaining_products

    return reordered_products

def bestsellers_high_variant_availability(products, days: int = None, percentile: int = 100, variant_threshold: float = 0.0):
    if days is not None:
        time_threshold = datetime.now() - timedelta(days=days)
        recent_high_variant_products = [
            p for p in products 
            if isinstance(p, dict) and 'listed_date' in p and 'variant_availability' in p and 'id' in p and
            isinstance(p['listed_date'], str) and
            parser.isoparse(p['listed_date']) >= time_threshold and
            p['variant_availability'] > variant_threshold
        ]
    else:
        recent_high_variant_products = [
            p for p in products 
            if isinstance(p, dict) and 'variant_availability' in p and p['variant_availability'] > variant_threshold
        ]

    # Sort the filtered products by 'revenue' in descending order
    sorted_by_revenue = sorted(recent_high_variant_products, key=lambda x: x.get('revenue', 0), reverse=True)
    
    # Calculate the top percentage of products based on the given percentile
    top_percent_index = max(1, len(sorted_by_revenue) * (percentile or 100) // 100)
    
    # Get the top percentile products and the remaining products
    top_products = sorted_by_revenue[:top_percent_index]
    remaining_products = sorted_by_revenue[top_percent_index:]

    # Combine the top percentile products with the remaining products
    reordered_products = top_products + remaining_products

    return reordered_products

def promote_high_variant_availability(products, days: int = None, percentile: int = 100, variant_threshold: float = 0.0):
    high_variant_products = [
        p for p in products 
        if isinstance(p, dict) and 'variant_availability' in p and p['variant_availability'] >= variant_threshold
    ]
    
    sorted_by_variant = sorted(high_variant_products, key=lambda x: x.get('variant_availability', 0), reverse=True)
    
    top_percent_index = max(1, len(sorted_by_variant) * (percentile or 100) // 100)
    
    top_products = sorted_by_variant[:top_percent_index]
    remaining_products = sorted_by_variant[top_percent_index:]

    reordered_products = top_products + remaining_products

    return reordered_products

def clearance_sale(products, days: int = None, percentile: int = 100, variant_threshold: float = 0.0):
    lookback_date = datetime.now() - timedelta(days=days) if days else None
    
    eligible_products = [
        p for p in products 
        if isinstance(p, dict) and 'listed_date' in p and 'sales_velocity' in p and 'id' in p and
        (lookback_date is None or parser.isoparse(p['listed_date']) < lookback_date)
    ]
    
    sorted_by_sales_velocity = sorted(eligible_products, key=lambda p: p.get('sales_velocity', float('inf')))
    
    bottom_percentile_index = max(1, len(sorted_by_sales_velocity) * (percentile or 100) // 100)
    
    low_sales_velocity_products = sorted_by_sales_velocity[:bottom_percentile_index]
    remaining_products = sorted_by_sales_velocity[bottom_percentile_index:]
    
    reordered_products = low_sales_velocity_products + remaining_products

    return reordered_products

def promote_high_revenue_new_products(products, days: int = None, percentile: int = 100, variant_threshold: float = 0.0):
   
    lookback_date = datetime.now() - timedelta(days=days) if days else None
    
    new_products = [
        p for p in products 
        if isinstance(p, dict) and 'listed_date' in p and 'revenue' in p and 'id' in p and
        (lookback_date is None or parser.isoparse(p['listed_date']) >= lookback_date)
    ]
    
    sorted_by_revenue = sorted(new_products, key=lambda p: p.get('revenue', 0), reverse=True)
    
    top_percentile_index = max(1, len(sorted_by_revenue) * (percentile or 100) // 100)
    
    top_revenue_new_products = sorted_by_revenue[:top_percentile_index]
    remaining_products = sorted_by_revenue[top_percentile_index:]
    
    reordered_products = top_revenue_new_products + remaining_products

    return reordered_products




def remove_pinned_products(products, pinned_product_ids):
    pinned_product_ids_str = list(map(str, pinned_product_ids))
    
    pinned_products = []
    non_pinned_products = []

    for product in products:
        if product['product_id'] in pinned_product_ids_str:
            pinned_products.append(product)
        else:
            non_pinned_products.append(product)
            
    return non_pinned_products, pinned_products

def push_pinned_products_to_top(products, pinned_products):
    sorted_products = pinned_products + products
    return sorted_products

def push_out_of_stock_down(products):
    in_stock_products = []
    out_of_stock_products = []

    for product in products:
        if product['total_inventory'] > 0:
            in_stock_products.append(product)
        else:
            out_of_stock_products.append(product)  

    return in_stock_products, out_of_stock_products

def segregate_pinned_products(pinned_products):
    ofs_pinned_products = []
    in_stock_pinned_products = []
    for product in pinned_products:
        if product['total_inventory'] > 0:
            in_stock_pinned_products.append(product)
        else:
            ofs_pinned_products.append(product)

    return in_stock_pinned_products, ofs_pinned_products







# primary strategies

# def promote_new(products, days=7, capping=None):
#     return new_products(products, days=days, date_type=0, capping=capping)

# def promote_high_revenue(products, days=7, percentile=5, capping=None):
#     # Sort by revenue and filter products within the top 5 percentile
#     sorted_products = revenue_generated(products, days=days, high_to_low=True)
#     top_percentile_index = int(len(sorted_products) * (percentile / 100))
#     return sorted_products[:top_percentile_index] if capping is None else sorted_products[:top_percentile_index][:capping]

# def promote_high_inventory(products, days=None, percentile=10, capping=None):
#     # Sort by sales velocity and filter bottom 10%
#     sorted_products = Number_of_sales(products, days=days, high_to_low=False)
#     bottom_percentile_index = int(len(sorted_products) * (percentile / 100))
#     return sorted_products[:bottom_percentile_index] if capping is None else sorted_products[:bottom_percentile_index][:capping]

# def bestsellers_high_variant_availability(products, days=None, revenue_percentile=20, variant_availability_threshold=60, capping=None):
#     # Filter for high variant availability
#     filtered_by_variant = variant_availability_ratio(products, high_to_low=True)
#     # Further filter by revenue percentile
#     filtered_by_revenue = revenue_generated(filtered_by_variant, days=days, high_to_low=True)
#     top_revenue_index = int(len(filtered_by_revenue) * (revenue_percentile / 100))
#     filtered_products = [p for p in filtered_by_revenue[:top_revenue_index] if p['variant_availability'] > variant_availability_threshold]
#     return filtered_products[:capping] if capping else filtered_products

# def promote_high_variant_availability(products, variant_availability_threshold=60, capping=None):
#     # Filter for high variant availability
#     return variant_availability_ratio(products, high_to_low=True, capping=capping)

# def clearance_sale(products, days=90, percentile=10, capping=None):
#     # Filter for bottom 10% sales velocity and listed date > 90 days
#     low_sales_velocity = Number_of_sales(products, days=None, high_to_low=False)
#     bottom_sales_index = int(len(low_sales_velocity) * (percentile / 100))
#     filtered_by_sales_velocity = low_sales_velocity[:bottom_sales_index]
#     clearance_products = [p for p in filtered_by_sales_velocity if parser.isoparse(p['listed_date']) <= datetime.now() - timedelta(days=days)]
#     return clearance_products[:capping] if capping else clearance_products

# def promote_high_revenue_new(products, days=90, revenue_percentile=20, capping=None):
#     # Filter new products first
#     new_products_list = new_products(products, days=days, date_type=0)
#     # Filter by revenue
#     filtered_by_revenue = revenue_generated(new_products_list, high_to_low=True)
#     top_revenue_index = int(len(filtered_by_revenue) * (revenue_percentile / 100))
#     return filtered_by_revenue[:top_revenue_index] if capping is None else filtered_by_revenue[:top_revenue_index][:capping]
