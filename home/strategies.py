from datetime import datetime, timedelta

from datetime import datetime, timedelta

def promote_new(products, days: int):
    time_threshold = datetime.now() - timedelta(days=days)
    
    new_products = [p for p in products if p['listed_date'] >= time_threshold]
    
    return sorted(new_products, key=lambda x: x['listed_date'], reverse=True)

# def promote_high_revenue_products(products, days: int, percentile: int):
#     time_threshold = datetime.now() - timedelta(days=days)
    
#     # Filter products that were listed within the lookback period
#     recent_products = [p for p in products if p['listed_date'] >= time_threshold]
    
#     # Sort the recent products by revenue in descending order
#     sorted_by_revenue = sorted(recent_products, key=lambda x: x['revenue'], reverse=True)
    
#     # Calculate the top `percentile` index
#     top_percent_index = max(1, len(sorted_by_revenue) * percentile // 100)
    
#     # Return only the products within the top `percentile`
#     return sorted_by_revenue[:top_percent_index]


def promote_high_revenue_products(products, days: int, percentile: int):
    """
    Sorts products so that those in the top `percentile` of revenue within the last `days` come first,
    but the rest of the products follow in their original order.
    
    Args:
        products (list of dict): List of product details fetched from Shopify.
        days (int): Number of days to consider for the lookback period.
        percentile (int): Top percentile threshold for revenue filtering.
        
    Returns:
        list of str: List of product IDs, with top revenue products first.
    """
    # Calculate the time threshold for lookback period
    time_threshold = datetime.now() - timedelta(days=days)
    
    # Filter products that were listed within the lookback period
    recent_products = [p for p in products if p['listed_date'] >= time_threshold]
    
    # Sort recent products by revenue in descending order
    sorted_by_revenue = sorted(recent_products, key=lambda x: x['revenue'], reverse=True)
    
    # Calculate the top `percentile` index
    top_percent_index = max(1, len(sorted_by_revenue) * percentile // 100) #hmmm
    
    # Get the top products within the percentile
    top_products = sorted_by_revenue[:top_percent_index]
    
    # Create a set of product IDs for the top products
    top_product_ids = {p['id'] for p in top_products}
    
    # Reorder the original product list, putting top products first
    reordered_products = sorted(products, key=lambda p: p['id'] not in top_product_ids)
    
    # Return the reordered list of product IDs
    return [p['id'] for p in reordered_products]


def promote_high_inventory_products(products, days: int, percentile: int):
    """
    Sorts products so that those in the bottom `percentile` of sales velocity within the last `days`
    come first, but the rest of the products follow in their original order.
    
    Args:
        products (list of dict): List of product details fetched from Shopify.
        days (int): Number of days to consider for the lookback period.
        percentile (int): Bottom percentile threshold for sales velocity filtering.
        
    Returns:
        list of str: List of product IDs, with bottom sales velocity products first.
    """
    # Calculate the time threshold for lookback period
    time_threshold = datetime.now() - timedelta(days=days)
    
    # Filter products that were listed within the lookback period
    recent_products = [p for p in products if p['listed_date'] >= time_threshold]
    
    # Sort recent products by sales velocity in ascending order (bottom percentile will be low sales velocity)
    sorted_by_velocity = sorted(recent_products, key=lambda x: x['sales_velocity'])
    
    # Calculate the bottom `percentile` index
    bottom_percent_index = max(1, len(sorted_by_velocity) * percentile // 100)
    
    # Get the bottom products within the percentile
    bottom_products = sorted_by_velocity[:bottom_percent_index]
    
    # Create a set of product IDs for the bottom products
    bottom_product_ids = {p['id'] for p in bottom_products}
    
    # Reorder the original product list, putting bottom products first
    reordered_products = sorted(products, key=lambda p: p['id'] not in bottom_product_ids)
    
    # Return the reordered list of product IDs
    return [p['id'] for p in reordered_products]


def bestsellers_high_variant_availability(products, days: int, revenue_percentile: int, variant_threshold: float):
    """
    Sorts products to prioritize those with high variant availability and within the top `revenue_percentile` of revenue.
    
    Args:
        products (list of dict): List of product details fetched from Shopify.
        days (int): Number of days to consider for the lookback period.
        revenue_percentile (int): Top percentile threshold for revenue filtering.
        variant_threshold (float): Minimum variant availability to consider a product "high availability".
        
    Returns:
        list of str: List of product IDs, with top revenue and high variant products first.
    """
    # Calculate the time threshold for the lookback period
    time_threshold = datetime.now() - timedelta(days=days)
    
    # Filter products that were listed within the lookback period and have high variant availability
    recent_high_variant_products = [
        p for p in products 
        if p['listed_date'] >= time_threshold and p['variant_availability'] > variant_threshold
    ]
    
    # Sort the filtered products by revenue in descending order
    sorted_by_revenue = sorted(recent_high_variant_products, key=lambda x: x['revenue'], reverse=True)
    
    # Calculate the top `revenue_percentile` index
    top_percent_index = max(1, len(sorted_by_revenue) * revenue_percentile // 100)
    
    # Get the top products within the percentile
    top_products = sorted_by_revenue[:top_percent_index]
    
    # Create a set of product IDs for the top products
    top_product_ids = {p['id'] for p in top_products}
    
    # Reorder the original product list, putting top products first
    reordered_products = sorted(products, key=lambda p: p['id'] not in top_product_ids)
    
    # Return the reordered list of product IDs
    return [p['id'] for p in reordered_products]

def promote_high_variant_availability(products, variant_threshold: float):
    """
    Sorts products to prioritize those with higher variant availability.
    
    Args:
        products (list of dict): List of product details fetched from Shopify.
        variant_threshold (float): Minimum variant availability to consider a product for priority.
        
    Returns:
        list of str: List of product IDs, with high variant availability products first.
    """
    # Filter products with variant availability above the threshold
    high_variant_products = [p for p in products if p['variant_availability'] >= variant_threshold]
    
    # Create a set of high variant availability product IDs
    high_variant_ids = {p['id'] for p in high_variant_products}
    
    # Reorder the original product list, putting high variant availability products first
    reordered_products = sorted(products, key=lambda p: p['id'] not in high_variant_ids)
    
    # Return the reordered list of product IDs
    return [p['id'] for p in reordered_products]


def clearance_sale(products, lookback_days: int, bottom_percentile_threshold: int):
    """
    Sorts products to prioritize those with low sales velocity and listed before the lookback period.
    
    Args:
        products (list of dict): List of product details fetched from Shopify.
        lookback_days (int): The number of days to look back from the current date.
        bottom_percentile_threshold (int): The percentile threshold for sales velocity, where lower is prioritized.
        
    Returns:
        list of str: List of product IDs, with low sales velocity products first.
    """
    # Calculate the cutoff date based on the lookback period
    lookback_date = datetime.now() - timedelta(days=lookback_days)
    
    # Filter products listed before the lookback date
    eligible_products = [p for p in products if p['listed_date'] < lookback_date]
    
    # Sort the eligible products by sales velocity in ascending order (low velocity first)
    sorted_by_sales_velocity = sorted(eligible_products, key=lambda p: p['sales_velocity'])
    
    # Determine the bottom percentile index for sales velocity
    bottom_percentile_index = max(1, len(sorted_by_sales_velocity) * bottom_percentile_threshold // 100)
    low_sales_velocity_products = sorted_by_sales_velocity[:bottom_percentile_index]
    
    # Create a set of product IDs with low sales velocity
    low_sales_velocity_ids = {p['id'] for p in low_sales_velocity_products}
    
    # Reorder the original product list, putting low sales velocity products first
    reordered_products = sorted(products, key=lambda p: p['id'] not in low_sales_velocity_ids)
    
    # Return the reordered list of product IDs
    return [p['id'] for p in reordered_products]


def promote_high_revenue_new_products(products, lookback_days: int, top_percentile_threshold: int):
    """
    Sorts products so that new products (based on the lookback period) with high revenue come first.
    
    Args:
        products (list of dict): List of product details fetched from Shopify.
        lookback_days (int): The number of days to look back for determining new products.
        top_percentile_threshold (int): The percentile threshold for revenue, where high revenue products are prioritized.
    
    Returns:
        list of str: List of product IDs, with high revenue new products first.
    """
    # Calculate the cutoff date based on the lookback period
    lookback_date = datetime.now() - timedelta(days=lookback_days)
    
    # Filter products that are listed within the lookback period (considered as new products)
    new_products = [p for p in products if p['listed_date'] >= lookback_date]
    
    # Sort the new products by revenue in descending order (high revenue first)
    sorted_by_revenue = sorted(new_products, key=lambda p: p['revenue'], reverse=True)
    
    # Determine the top percentile index for revenue
    top_percentile_index = max(1, len(sorted_by_revenue) * top_percentile_threshold // 100)
    top_revenue_new_products = sorted_by_revenue[:top_percentile_index]
    
    # Create a set of product IDs with high revenue in the new products
    top_revenue_new_product_ids = {p['id'] for p in top_revenue_new_products}
    
    # Reorder the original product list, putting high-revenue new products first
    reordered_products = sorted(products, key=lambda p: p['id'] not in top_revenue_new_product_ids)
    
    # Return the reordered list of product IDs
    return [p['id'] for p in reordered_products]

def sort_alphabetically(products):
    if not isinstance(products, list) or not all(isinstance(p, dict) for p in products):
        raise ValueError("Expected a list of dictionaries for products")
    sorted_products = sorted(products, key=lambda x: x['title'].lower())
    return [p['id'] for p in sorted_products]
