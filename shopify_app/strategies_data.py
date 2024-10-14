PRIMARY_STRATEGIES = [
    {
        "algo_name": "Promote New",
        "number_of_buckets": 1,
        "bucket_parameters": {
            "rule_name": "new_products",
            "parameters": {
                "days": 30,
                "date_type": 0,  # Created date
                "capping": None
            }
        },
        "is_primary": True,
    },
    {
        "algo_name": "Promote High Revenue Products",
        "number_of_buckets": 1,
        "bucket_parameters": {
            "rule_name": "revenue_generated",
            "parameters": {
                "days": 30,
                "high_to_low": True,
                "capping": None,
            }
        },
        "is_primary": True,
    },
    {
        "algo_name": "Promote High Inventory Products",
        "number_of_buckets": 1,
        "bucket_parameters": {
            "rule_name": "product_inventory",
            "parameters": {
                "days": 30,
                "capping": None,
                "comparison_type": 0,
                "inventory_threshold": 0
            }
        },
        "is_primary": True,
    },
    {
        "algo_name": "Bestsellers",
        "number_of_buckets": 1,
        "bucket_parameters": {
            "rule_name": "Number_of_sales",
            "parameters": {
                "days": 30,
                "high_to_low": True,
                "capping": None,
            }
        },
        "is_primary": True,
    },
    {
        "algo_name": "Promote High Variant Availability",
        "number_of_buckets": 1,
        "bucket_parameters": {
            "rule_name": "variant_availability_ratio",
            "parameters": {
                "days": 30,
                "high_to_low": True,
                "capping": None,
            }
        },
        "is_primary": True,
    },
    {
        "algo_name": "Occasion Based Promotions",
        "number_of_buckets": 1,
        "bucket_parameters": {
            "rule_name": "product_tags",
            "parameters": {
                "days": None,
                "is_equal_to": True,
                "tags": ["Sale", "Discount"]
            }
        },
        "is_primary": True,
    },
    {
        "algo_name": "Promote Discounted Products",
        "number_of_buckets": 1,
        "bucket_parameters": {
            "rule_name": "product_inventory",
            "parameters": {
                "comparison_type": 0,  
                "inventory_threshold": 10,
                "capping": None
            }
        },
        "is_primary": True,
    },
    {
        "algo_name": "RFM Sort",
        "number_of_buckets": 1,
        "bucket_parameters": {
            "rule_name": "rfm_sort",
            "parameters": {
                "days": 30,
                "high_to_low": True,
                "capping": None
            }
        },
        "is_primary": True,
    },
    {
        "algo_name": "I Am Feeling Lucky",
        "number_of_buckets": 1,
        "bucket_parameters": {
            "rule_name": "i_am_feeling_lucky",
            "parameters": {
                "days": None,
                "capping": None
            }
        },
        "is_primary": True,
    },
]
