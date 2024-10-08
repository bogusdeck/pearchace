from datetime import datetime, timedelta
from dateutil import parser
import pytz

############################################################################################
# sorting rules 
############################################################################################

#done
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

    return sorted_products[:capping] if capping else sorted_products

#done
def revenue_generated(products, days: int = None, high_to_low: bool = True, capping: int = None):
    lookback_date = datetime.now() - timedelta(days=days) if days else None

    filtered_products = [
        p for p in products
        if isinstance(p, dict) and 'revenue' in p and 'listed_date' in p and 'id' in p
        and isinstance(p['listed_date'], str) 
        and (lookback_date is None or parser.isoparse(p['listed_date']) >= lookback_date)
    ]

    sorted_products = sorted(filtered_products, key=lambda p: p['revenue'], reverse=high_to_low)

    return sorted_products[:capping] if capping else sorted_products

#not done
def Number_of_sales(products, days: int = None, high_to_low: bool = True, capping: int = None):
    lookback_date = datetime.now() - timedelta(days=days) if days else None

    filtered_products = [
        p for p in products
        if isinstance(p, dict) and 'number_of_sales' in p and 'listed_date' in p and 'id' in p
        and isinstance(p['listed_date'], str)
        and (lookback_date is None or parser.isoparse(p['listed_date']) >= lookback_date)
    ]

    sorted_products = sorted(filtered_products, key=lambda p: p['number_of_sales'], reverse=high_to_low)

    return sorted_products[:capping] if capping else sorted_products

#not done
def inventory_quantity(products, days: int = None, high_to_low: bool = True, capping: int = None):
    lookback_date = datetime.now() - timedelta(days=days) if days else None

    filtered_products = [
        p for p in products
        if isinstance(p, dict) and 'inventory_quantity' in p and 'listed_date' in p and 'id' in p
        and isinstance(p['listed_date'], str)
        and (lookback_date is None or parser.isoparse(p['listed_date']) >= lookback_date)
    ]

    sorted_products = sorted(
        filtered_products,
        key=lambda p: p['inventory_quantity'],
        reverse=high_to_low
    )

    return sorted_products[:capping] if capping else sorted_products

#not done 
def variant_availability_ratio(products, days: int = None, high_to_low: bool = True, capping: int = None):
    lookback_date = datetime.now() - timedelta(days=days) if days else None

    filtered_products = [
        p for p in products
        if isinstance(p, dict) and 'variant_availability' in p and 'listed_date' in p and 'id' in p
        and isinstance(p['listed_date'], str)
        and (lookback_date is None or parser.isoparse(p['listed_date']) >= lookback_date)
    ]

    sorted_products = sorted(
        filtered_products,
        key=lambda p: p['variant_availability'],
        reverse=high_to_low
    )

    return sorted_products[:capping] if capping else sorted_products

#not done
def product_tags(products, days: int = None, is_equal_to: bool = True, tags: list = []):
    lookback_date = datetime.now() - timedelta(days=days) if days else None

    filtered_products = [
        p for p in products
        if isinstance(p, dict) and 'tags' in p and 'listed_date' in p and 'id' in p
        and isinstance(p['listed_date'], str)
        and isinstance(p['tags'], list)
        and (lookback_date is None or parser.isoparse(p['listed_date']) >= lookback_date)
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

    return filtered_by_tags


#not done
def product_inventory(products, days: int = None, comparison_type: int = 0, inventory_threshold: int = 0, capping: int = None):
    comparison_mapping = {
        0: lambda p: p['inventory'] > inventory_threshold,   
        1: lambda p: p['inventory'] < inventory_threshold,   
        2: lambda p: p['inventory'] == inventory_threshold,  
        3: lambda p: p['inventory'] != inventory_threshold   
    }
    
    comparison_function = comparison_mapping.get(comparison_type, comparison_mapping[0])

    lookback_date = datetime.now() - timedelta(days=days) if days else None

    filtered_products = [
        p for p in products
        if isinstance(p, dict) and 'inventory' in p and 'listed_date' in p and 'id' in p
        and isinstance(p['listed_date'], str) and isinstance(p['inventory'], int)
        and (lookback_date is None or parser.isoparse(p['listed_date']) >= lookback_date)
        and comparison_function(p)
    ]

    sorted_products = sorted(filtered_products, key=lambda p: p['inventory'], reverse=True)

    
    if capping is not None:
        sorted_products = sorted_products[:capping]

    return sorted_products
