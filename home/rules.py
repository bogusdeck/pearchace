from datetime import datetime, timedelta
from dateutil import parser
import pytz

############################################################################################
# sorting rules 
############################################################################################

#done
def new_products(products, days: int = None, date_type: int = 0):
    date_field_mapping = {
        0: 'created_at',
        1: 'published_at',
        2: 'updated_at'
    }

    # Ensure the provided date_type is valid, default to 'created_at' if not
    date_field = date_field_mapping.get(date_type, 'created_at')

    lookback_date = datetime.now() - timedelta(days=days) if days else None

    # Filter products based on the selected date field and the lookback period
    filtered_products = [
        p for p in products
        if isinstance(p, dict) and date_field in p and isinstance(p[date_field], str) and 'id' in p
        and (lookback_date is None or parser.isoparse(p[date_field]) >= lookback_date)
    ]
    
    sorted_products = sorted(filtered_products, key=lambda p: parser.isoparse(p[date_field]), reverse=True)

    return sorted_products

#done
def revenue_generated(products, days: int = None, high_to_low: bool = True):
    lookback_date = datetime.now() - timedelta(days=days) if days else None

    # Filter products based on the lookback period and check for 'revenue' and 'id' fields
    filtered_products = [
        p for p in products
        if isinstance(p, dict) and 'revenue' in p and 'listed_date' in p and 'id' in p
        and isinstance(p['listed_date'], str) 
        and (lookback_date is None or parser.isoparse(p['listed_date']) >= lookback_date)
    ]

    # Sort products by revenue (high to low if True, low to high if False)
    sorted_products = sorted(
        filtered_products,
        key=lambda p: p['revenue'],
        reverse=high_to_low
    )

    return sorted_products


def Number_of_sales(products, days: int = None, high_to_low: bool = True):
    lookback_date = datetime.now() - timedelta(days=days) if days else None

    # Filter products based on the lookback period and check for 'number_of_sales' and 'id' fields
    filtered_products = [
        p for p in products
        if isinstance(p, dict) and 'number_of_sales' in p and 'listed_date' in p and 'id' in p
        and isinstance(p['listed_date'], str)
        and (lookback_date is None or parser.isoparse(p['listed_date']) >= lookback_date)
    ]

    # Sort products by number_of_sales (high to low if True, low to high if False)
    sorted_products = sorted(
        filtered_products,
        key=lambda p: p['number_of_sales'],
        reverse=high_to_low
    )

    return sorted_products