from datetime import datetime, timedelta
from dateutil import parser
import pytz

############################################################################################
# sorting rules 
############################################################################################

# Updated to handle capping  # done
def new_products(products, days: int = None, date_type: int = 0, capping: int = None):
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

    # Return two lists: capped and uncapped products if capping is provided
    capped_products = sorted_products[:capping] if capping else sorted_products
    uncapped_products = sorted_products[capping:] if capping else []
    
    return capped_products, uncapped_products


# Updated to handle capping
def revenue_generated(products, days: int = None, high_to_low: bool = True, capping: int = None):
    lookback_date = datetime.now() - timedelta(days=days) if days else None

    filtered_products = [
        p for p in products
        if isinstance(p, dict) and 'total_revenue' in p and 'created_at' in p and 'product_id' in p
        and isinstance(p['created_at'], str)
        and (lookback_date is None or parser.isoparse(p['created_at']) >= lookback_date)
    ]

    sorted_products = sorted(filtered_products, key=lambda p: p['total_revenue'], reverse=high_to_low)

    # Capping logic
    capped_products = sorted_products[:capping] if capping else sorted_products
    uncapped_products = sorted_products[capping:] if capping else []
    
    return capped_products, uncapped_products

# Updated to handle capping
def Number_of_sales(products, days: int = None, high_to_low: bool = True, capping: int = None):
    lookback_date = datetime.now() - timedelta(days=days) if days else None

    filtered_products = [
        p for p in products
        if isinstance(p, dict) and 'total_sold_units' in p and 'created_at' in p and 'product_id' in p
        and isinstance(p['created_at'], str)
        and (lookback_date is None or parser.isoparse(p['created_at']) >= lookback_date)
    ]

    sorted_products = sorted(filtered_products, key=lambda p: p['total_sold_units'], reverse=high_to_low)

    # Capping logic
    capped_products = sorted_products[:capping] if capping else sorted_products
    uncapped_products = sorted_products[capping:] if capping else []
    
    return capped_products, uncapped_products


# Updated to handle capping
def inventory_quantity(products, days: int = None, high_to_low: bool = True, capping: int = None):
    lookback_date = datetime.now() - timedelta(days=days) if days else None

    filtered_products = [
        p for p in products
        if isinstance(p, dict) and 'total_inventory' in p and 'created_at' in p and 'id' in p
        and isinstance(p['created_at'], str)
        and (lookback_date is None or parser.isoparse(p['created_at']) >= lookback_date)
    ]

    sorted_products = sorted(filtered_products, key=lambda p: p['total_inventory'], reverse=high_to_low)

    # Capping logic
    capped_products = sorted_products[:capping] if capping else sorted_products
    uncapped_products = sorted_products[capping:] if capping else []
    
    return capped_products, uncapped_products


# Updated to handle capping
def variant_availability_ratio(products, days: int = None, high_to_low: bool = True, capping: int = None):
    lookback_date = datetime.now() - timedelta(days=days) if days else None

    filtered_products = [
        p for p in products
        if isinstance(p, dict) and 'variant_availability' in p and 'created_at' in p and 'id' in p
        and isinstance(p['created_at'], str)
        and (lookback_date is None or parser.isoparse(p['created_at']) >= lookback_date)
    ]

    sorted_products = sorted(filtered_products, key=lambda p: p['variant_availability'], reverse=high_to_low)

    # Capping logic
    capped_products = sorted_products[:capping] if capping else sorted_products
    uncapped_products = sorted_products[capping:] if capping else []
    
    return capped_products, uncapped_products


# Updated to handle capping # not using will deploy this after 7
def product_tags(products, days: int = None, is_equal_to: bool = True, tags: list = [], capping: int = None):
    lookback_date = datetime.now() - timedelta(days=days) if days else None

    filtered_products = [
        p for p in products
        if isinstance(p, dict) and 'tags' in p and 'created_at' in p and 'id' in p
        and isinstance(p['created_at'], str)
        and isinstance(p['tags'], list)
        and (lookback_date is None or parser.isoparse(p['created_at']) >= lookback_date)
    ]

    if is_equal_to:
        filtered_by_tags = [
            p for p in filtered_products 
            if any(tag in p['tags'] for tag in tags)
        ]
    else:
        filtered_by_tags = [
            p for p in filtered_products 
            if not any(tag in p['tags'] for tag in tags)
        ]

    capped_products = filtered_by_tags[:capping] if capping else filtered_by_tags
    uncapped_products = filtered_by_tags[capping:] if capping else []
    
    return capped_products, uncapped_products


# Updated to handle capping
def product_inventory(products, days: int = None, comparison_type: int = 0, inventory_threshold: int = 0, capping: int = None):
    comparison_mapping = {
        0: lambda p: p['total_inventory'] > inventory_threshold,   
        1: lambda p: p['total_inventory'] < inventory_threshold,   
        2: lambda p: p['total_inventory'] == inventory_threshold,  
        3: lambda p: p['total_inventory'] != inventory_threshold   
    }
    
    comparison_function = comparison_mapping.get(comparison_type, comparison_mapping[0])

    lookback_date = datetime.now() - timedelta(days=days) if days else None

    filtered_products = [
        p for p in products
        if isinstance(p, dict) and 'total_inventory' in p and 'created_at' in p and 'id' in p
        and isinstance(p['created_at'], str) and isinstance(p['inventory'], int)
        and (lookback_date is None or parser.isoparse(p['created_at']) >= lookback_date)
        and comparison_function(p)
    ]

    sorted_products = sorted(filtered_products, key=lambda p: p['total_inventory'], reverse=True)

    capped_products = sorted_products[:capping] if capping else sorted_products
    uncapped_products = sorted_products[capping:] if capping else []
    
    return capped_products, uncapped_products



###############################################################
#primary strategies

def promote_new(products, days: int, date_type: int = 0, capping: int = None):
    return new_products(products, days=days, date_type=date_type, capping=capping)

def promote_high_revenue(products, days: int, high_to_low: bool = True, capping: int = None):
    return revenue_generated(products, days=days, high_to_low=high_to_low, capping=capping)

def promote_high_inventory(products, capping: int = None):
    return inventory_quantity(products, high_to_low=True, capping=capping)

def promote_bestsellers(products, days: int, high_to_low: bool = True, capping: int = None):
    return Number_of_sales(products, days=days, high_to_low=high_to_low, capping=capping)

def promote_high_variant_availability(products, days: int, high_to_low: bool = True, capping: int = None):
    return variant_availability_ratio(products, days=days, high_to_low=high_to_low, capping=capping)
