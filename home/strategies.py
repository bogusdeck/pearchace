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

    # Sorting recent products by revenue
    sorted_by_revenue = sorted(recent_products, key=lambda x: x.get('revenue', 0), reverse=True)

    # Get the top percentile products based on revenue
    top_percent_index = max(1, len(sorted_by_revenue) * (percentile or 100) // 100)
    top_products = sorted_by_revenue[:top_percent_index]

    # Get the remaining products
    remaining_products = [p for p in products if p not in top_products]

    # Combine top products and remaining products
    reordered_products = top_products + remaining_products

    return reordered_products


def promote_high_inventory_products(products, days: int = None, percentile: int = 100, variant_threshold: float = 0.0):
    # Filter products by 'listed_date' if days is provided
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

    # Sort products by 'sales_velocity' in ascending order (lowest velocity first)
    sorted_by_velocity = sorted(recent_products, key=lambda x: x.get('sales_velocity', 0))
    
    # Calculate the top percentage of products based on the given percentile
    bottom_percent_index = max(1, len(sorted_by_velocity) * (percentile or 100) // 100)
    
    # Get the top percentile products and the remaining products
    bottom_products = sorted_by_velocity[:bottom_percent_index]
    remaining_products = sorted_by_velocity[bottom_percent_index:]

    # Combine the top percentile products with the remaining products
    reordered_products = bottom_products + remaining_products

    return reordered_products

def bestsellers_high_variant_availability(products, days: int = None, percentile: int = 100, variant_threshold: float = 0.0):
    # Filter products based on 'listed_date' and 'variant_availability'
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
    # Filter products with high variant availability
    high_variant_products = [
        p for p in products 
        if isinstance(p, dict) and 'variant_availability' in p and p['variant_availability'] >= variant_threshold
    ]
    
    # Sort the filtered products by variant availability (descending)
    sorted_by_variant = sorted(high_variant_products, key=lambda x: x.get('variant_availability', 0), reverse=True)
    
    # Calculate the top percentage of products based on the given percentile
    top_percent_index = max(1, len(sorted_by_variant) * (percentile or 100) // 100)
    
    # Get the top percentile products and the remaining products
    top_products = sorted_by_variant[:top_percent_index]
    remaining_products = sorted_by_variant[top_percent_index:]

    # Combine the top percentile products with the remaining products
    reordered_products = top_products + remaining_products

    return reordered_products

def clearance_sale(products, days: int = None, percentile: int = 100, variant_threshold: float = 0.0):
    # Set the lookback date if days parameter is provided
    lookback_date = datetime.now() - timedelta(days=days) if days else None
    
    # Filter products based on listed date and sales velocity
    eligible_products = [
        p for p in products 
        if isinstance(p, dict) and 'listed_date' in p and 'sales_velocity' in p and 'id' in p and
        (lookback_date is None or parser.isoparse(p['listed_date']) < lookback_date)
    ]
    
    # Sort eligible products by sales velocity (ascending, lower values first)
    sorted_by_sales_velocity = sorted(eligible_products, key=lambda p: p.get('sales_velocity', float('inf')))
    
    # Calculate the index for the bottom percentile products
    bottom_percentile_index = max(1, len(sorted_by_sales_velocity) * (percentile or 100) // 100)
    
    # Get the bottom percentile products and the remaining ones
    low_sales_velocity_products = sorted_by_sales_velocity[:bottom_percentile_index]
    remaining_products = sorted_by_sales_velocity[bottom_percentile_index:]
    
    # Combine the low sales velocity products with the remaining products
    reordered_products = low_sales_velocity_products + remaining_products

    return reordered_products

def promote_high_revenue_new_products(products, days: int = None, percentile: int = 100, variant_threshold: float = 0.0):
    # Set the lookback date if days parameter is provided
    lookback_date = datetime.now() - timedelta(days=days) if days else None
    
    # Filter new products based on listed date and revenue
    new_products = [
        p for p in products 
        if isinstance(p, dict) and 'listed_date' in p and 'revenue' in p and 'id' in p and
        (lookback_date is None or parser.isoparse(p['listed_date']) >= lookback_date)
    ]
    
    # Sort new products by revenue in descending order
    sorted_by_revenue = sorted(new_products, key=lambda p: p.get('revenue', 0), reverse=True)
    
    # Calculate the index for the top percentile products
    top_percentile_index = max(1, len(sorted_by_revenue) * (percentile or 100) // 100)
    
    # Get the top percentile high-revenue new products and the remaining products
    top_revenue_new_products = sorted_by_revenue[:top_percentile_index]
    remaining_products = sorted_by_revenue[top_percentile_index:]
    
    # Combine the top high-revenue new products with the remaining products
    reordered_products = top_revenue_new_products + remaining_products

    return reordered_products


def remove_pinned_products(products, pinned_product_ids):
    pinned_product_ids_str = list(map(str, pinned_product_ids))
    
    pinned_products = []
    non_pinned_products = []

    for product in products:
        if product['id'] in pinned_product_ids_str:
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
        if product['totalInventory'] > 0:
            in_stock_products.append(product)
        else:
            out_of_stock_products.append(product)  

    return in_stock_products, out_of_stock_products

def segregate_pinned_products(pinned_products):
    ofs_pinned_products = []
    in_stock_pinned_products = []
    for product in pinned_products:
        if product['totalInventory'] > 0:
            in_stock_pinned_products.append(product)
        else:
            ofs_pinned_products.append(product)

    return in_stock_pinned_products, ofs_pinned_products





############################################################################################
# sorting rules 
############################################################################################
#new_products   
def new_products(products, days: int = None, date_type: int = 0):
    date_field_mapping = {
        0: 'created_at',
        1: 'published_at',
        2: 'updated_at'
    }
    
    date_field = date_field_mapping.get(date_type, 'created_at')

    lookback_date = datetime.now() - timedelta(days=days) if days else None

    filtered_products = [
        p for p in products
        if isinstance(p, dict) and date_field in p and isinstance(p[date_field], str) and 'id' in p
        and (lookback_date is None or parser.isoparse(p[date_field]) >= lookback_date)
    ]

    
    sorted_products = sorted(filtered_products, key=lambda p: parser.isoparse(p[date_field]), reverse=True)

    return sorted_products

#Revenue Generated
