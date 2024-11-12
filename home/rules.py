from dateutil import parser
import pytz
from datetime import datetime, timedelta, timezone
import json 
from typing import List, Dict, Tuple, Optional

############################################################################################
# sorting rules 
############################################################################################

# Updated and tested
def new_products(products: List[Dict], days: Optional[int] = None, date_type: int = 0, capping: Optional[int] = None) -> Tuple[List[Dict], List[Dict]]:
    date_field_mapping = {
        0: 'created_at',
        1: 'published_at',
        2: 'updated_at'
    }
    
    date_field = date_field_mapping.get(date_type, 'created_at')
    
    lookback_date = datetime.now(timezone.utc) - timedelta(days=days) if days else None
    
    filtered_products = []
    for product in products:
        if isinstance(product, dict) and date_field in product and 'product_id' in product:
            product_date = product[date_field]
            if isinstance(product_date, datetime):
                product_date_parsed = product_date
            else:
                try:
                    product_date_parsed = parser.isoparse(product_date)
                except Exception as e:
                    print(f"Error parsing {date_field} for product {product['product_id']}: {e}")
                    continue
            
            if lookback_date is None or product_date_parsed >= lookback_date:
                filtered_products.append(product)
    
    sorted_products = sorted(filtered_products, key=lambda p: p[date_field], reverse=True)
    
    capped_products = sorted_products[:capping] if capping else sorted_products
    uncapped_products = sorted_products[capping:] if capping else []
    
    return capped_products, uncapped_products


# Updated and tested
def revenue_generated(products: List[Dict],days: Optional[int] = None,high_to_low: bool = True, capping: Optional[int] = None) -> Tuple[List[Dict], List[Dict]]:
    lookback_date = datetime.now(timezone.utc) - timedelta(days=days) if days else None

    filtered_products = []
    for product in products:
        if isinstance(product, dict) and 'total_revenue' in product and 'created_at' in product and 'product_id' in product:
            try:
                product_date = parser.isoparse(product['created_at']) if isinstance(product['created_at'], str) else product['created_at']
            except Exception as e:
                print(f"Error parsing created_at for product {product['product_id']}: {e}")
                continue
            
            if lookback_date is None or product_date >= lookback_date:
                filtered_products.append(product)
    
    sorted_products = sorted(filtered_products, key=lambda p: p['total_revenue'], reverse=high_to_low)
    
    capped_products = sorted_products[:capping] if capping else sorted_products
    uncapped_products = sorted_products[capping:] if capping else []

    return capped_products, uncapped_products


# Updated and tested
def Number_of_sales(products: List[Dict],days: Optional[int] = None,high_to_low: bool = True,capping: Optional[int] = None) -> Tuple[List[Dict], List[Dict]]:
    lookback_date = datetime.now(timezone.utc) - timedelta(days=days) if days else None

    filtered_products = []
    for product in products:
        if isinstance(product, dict) and 'total_sold_units' in product and 'created_at' in product and 'product_id' in product:
            try:
                product_date = parser.isoparse(product['created_at']) if isinstance(product['created_at'], str) else product['created_at']
            except Exception as e:
                print(f"Error parsing created_at for product {product['product_id']}: {e}")
                continue
            
            if lookback_date is None or product_date >= lookback_date:
                filtered_products.append(product)
    
    sorted_products = sorted(filtered_products, key=lambda p: p['total_sold_units'], reverse=high_to_low)

    capped_products = sorted_products[:capping] if capping else sorted_products
    uncapped_products = sorted_products[capping:] if capping else []

    return capped_products, uncapped_products

# Updated and not tested as no primary strategy is using this 
def inventory_quantity(products: List[Dict],days: Optional[int] = None,high_to_low: bool = True,capping: Optional[int] = None) -> Tuple[List[Dict], List[Dict]]:
    lookback_date = datetime.now(timezone.utc) - timedelta(days=days) if days else None

    filtered_products = []
    for product in products:
        if isinstance(product, dict) and 'total_inventory' in product and 'created_at' in product and 'product_id' in product:
            try:
                product_date = parser.isoparse(product['created_at']) if isinstance(product['created_at'], str) else product['created_at']
            except Exception as e:
                print(f"Error parsing created_at for product {product['product_id']}: {e}")
                continue

            if lookback_date is None or product_date >= lookback_date:
                filtered_products.append(product)
    
    sorted_products = sorted(filtered_products, key=lambda p: p['total_inventory'], reverse=high_to_low)

    capped_products = sorted_products[:capping] if capping else sorted_products
    uncapped_products = sorted_products[capping:] if capping else []

    return capped_products, uncapped_products

# Updated and tested
def variant_availability_ratio(products: List[Dict],days: Optional[int] = None,high_to_low: bool = True,capping: Optional[int] = None) -> Tuple[List[Dict], List[Dict]]:
    lookback_date = datetime.now(timezone.utc) - timedelta(days=days) if days else None

    filtered_products = []
    for product in products:
        if isinstance(product, dict) and 'variant_count' in product and 'created_at' in product and 'product_id' in product:
            try:
                product_date = parser.isoparse(product['created_at']) if isinstance(product['created_at'], str) else product['created_at']
            except Exception as e:
                print(f"Error parsing created_at for product {product['product_id']}: {e}")
                continue

            if lookback_date is None or product_date >= lookback_date:
                filtered_products.append(product)
    
    sorted_products = sorted(filtered_products, key=lambda p: p['variant_count'], reverse=high_to_low)

    capped_products = sorted_products[:capping] if capping else sorted_products
    uncapped_products = sorted_products[capping:] if capping else []

    return capped_products, uncapped_products


# not using will deploy this after 7 # not tested but updated
def product_tags(products: List[Dict], days: Optional[int] = None, is_equal_to: bool = True, tags: List[str] = [], capping: Optional[int] = None) -> Tuple[List[Dict], List[Dict]]:
    lookback_date = datetime.now(timezone.utc) - timedelta(days=days) if days else None

    filtered_products = []
    for product in products:
        if isinstance(product, dict) and 'tags' in product and 'created_at' in product and 'product_id' in product:
            try:
                product_date = parser.isoparse(product['created_at']) if isinstance(product['created_at'], str) else product['created_at']
            except Exception as e:
                print(f"Error parsing created_at for product {product['product_id']}: {e}")
                continue

            if lookback_date is None or product_date >= lookback_date:
                filtered_products.append(product)

    if is_equal_to:
        filtered_by_tags = [p for p in filtered_products if any(tag in p['tags'] for tag in tags)]
    else:
        filtered_by_tags = [p for p in filtered_products if not any(tag in p['tags'] for tag in tags)]

    capped_products = filtered_by_tags[:capping] if capping else filtered_by_tags
    uncapped_products = filtered_by_tags[capping:] if capping else []

    return capped_products, uncapped_products

# Updated and tested
def product_inventory(products: List[Dict], days: Optional[int] = None, comparison_type: int = 0, inventory_threshold: int = 0, capping: Optional[int] = None) -> Tuple[List[Dict], List[Dict]]:
    comparison_mapping = {
        0: lambda p: p['total_inventory'] > inventory_threshold,   
        1: lambda p: p['total_inventory'] < inventory_threshold,   
        2: lambda p: p['total_inventory'] == inventory_threshold,
        3: lambda p: p['total_inventory'] != inventory_threshold   
    }

    comparison_function = comparison_mapping.get(comparison_type, comparison_mapping[0])
    
    lookback_date = datetime.now(timezone.utc) - timedelta(days=days) if days else None

    filtered_products = []
    for product in products:
        if isinstance(product, dict) and 'total_inventory' in product and 'created_at' in product and 'product_id' in product:
            try:
                product_date = parser.isoparse(product['created_at']) if isinstance(product['created_at'], str) else product['created_at']
            except Exception as e:
                print(f"Error parsing created_at for product {product['product_id']}: {e}")
                continue

            if (lookback_date is None or product_date >= lookback_date) and comparison_function(product):
                filtered_products.append(product)


    sorted_products = sorted(filtered_products, key=lambda p: p['total_inventory'], reverse=True)

    capped_products = sorted_products[:capping] if capping else sorted_products
    uncapped_products = sorted_products[capping:] if capping else []

    return capped_products, uncapped_products



###############################################################
#primary strategies

#done
def promote_new(products, days: int, date_type: int = 0, capping: int = None): #new_products
    return new_products(products, days=days, date_type=date_type, capping=capping)

def promote_high_revenue(products, days: int, high_to_low: bool = True, capping: int = None):
    return revenue_generated(products, days=days, high_to_low=high_to_low, capping=capping)

def promote_high_inventory(products, days:int, high_to_low:bool =True,capping: int = None):
    return inventory_quantity(products, high_to_low=True, capping=capping)

def promote_bestsellers(products, days: int, high_to_low: bool = True, capping: int = None):
    return Number_of_sales(products, days=days, high_to_low=high_to_low, capping=capping)

def promote_high_variant_availability(products, days: int, high_to_low: bool = True, capping: int = None):
    return variant_availability_ratio(products, days=days, high_to_low=high_to_low, capping=capping)

# def promote_occasian_based_promotions(products, days:int, high_to_low:bool=True, capping:int=None):
#     return 1

def promote_discounted_products(products, days:int, high_to_low:bool=True, capping:int=None):
    return 1

import random
from typing import List, Dict, Optional, Tuple

def i_am_feeling_lucky(products: List[Dict],days: Optional[int] = None,capping: Optional[int] = None) -> Tuple[List[Dict], List[Dict]]:
    strategies = [
        promote_new,                     
        promote_high_revenue,            
        promote_high_inventory,           
        promote_bestsellers,              
        promote_high_variant_availability 
    ]

    chosen_strategy = random.choice(strategies)

    print("we are using : ", chosen_strategy)
    
    if chosen_strategy == promote_new:
        return promote_new(products, days=days, date_type=0, capping=capping)
    elif chosen_strategy == promote_high_revenue:
        return promote_high_revenue(products, days=days, high_to_low=True, capping=capping)
    elif chosen_strategy == promote_high_inventory:
        return promote_high_inventory(products, days=days, high_to_low=True, capping=capping)
    elif chosen_strategy == promote_bestsellers:
        return promote_bestsellers(products, days=days, high_to_low=True, capping=capping)
    elif chosen_strategy == promote_high_variant_availability:
        return promote_high_variant_availability(products, days=days, high_to_low=True, capping=capping)


    return [], []



def rfm_sort(products, days: int = None, capping: int = None, high_to_low: bool = True):
    # Calculate lookback date if days are provided
    lookback_date = datetime.now() - timedelta(days=days) if days else None

    print("Lookback date:", lookback_date)

    # Print product details before filtering
    for product in products:
        print("Product details:", product)
        print("created_at type:", type(product.get('created_at')))
        print("recency_score:", product.get('recency_score'))
        print("total_sold_units:", product.get('total_sold_units'))
        print("total_revenue:", product.get('total_revenue'))

    # Filter products that have necessary fields and match the date criteria
    filtered_products = [
        p for p in products
        if isinstance(p, dict)
        and isinstance(p.get('created_at'), datetime)  # Ensure 'created_at' is a datetime object
        and 'product_id' in p
        and p.get('recency_score') is not None  # Ensure recency_score is not None
        and 'total_sold_units' in p
        and 'total_revenue' in p
        and (lookback_date is None or p['created_at'] >= lookback_date)  # Direct datetime comparison
    ]

    print("rfm_filtered_products:", filtered_products)  # Debugging output

    # If no products pass the filter, return empty lists
    if not filtered_products:
        return [], []

    # Calculate RFM score for each product
    for product in filtered_products:
        product['rfm_score'] = product['recency_score'] + product['total_sold_units'] + product['total_revenue']

    # Sort products by the RFM score, descending or ascending based on high_to_low
    sorted_products = sorted(filtered_products, key=lambda p: p['rfm_score'], reverse=high_to_low)

    # Apply capping logic
    capped_products = sorted_products[:capping] if capping else sorted_products
    uncapped_products = sorted_products[capping:] if capping else []

    return capped_products, uncapped_products
