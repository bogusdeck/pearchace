# shopify_app/tasks.py
from celery import shared_task
from .models import Client, ClientCollections, ClientProducts, SortingAlgorithm
from .api import (
    fetch_collections,
    fetch_products_by_collection,
    update_collection_products_order,
)
from home.strategies import (
    promote_new,
    promote_high_revenue_products,
    promote_high_inventory_products,
    bestsellers_high_variant_availability,
    promote_high_variant_availability,
    clearance_sale,
    promote_high_revenue_new_products,
    remove_pinned_products,
    push_out_of_stock_down,
    segregate_pinned_products,
    push_pinned_products_to_top
) 

ALGO_ID_TO_FUNCTION = {
    "001": promote_new,
    "002": promote_high_revenue_products,
    "003": promote_high_inventory_products,
    "004": bestsellers_high_variant_availability,
    "005": promote_high_variant_availability,
    "006": clearance_sale,
    "007": promote_high_revenue_new_products,
}


@shared_task
def test_task():
    print("Celery is working!")

@shared_task
def async_fetch_and_store_collections(shop_id):
    try:
        client = Client.objects.get(shop_id=shop_id)
        collections = fetch_collections(client.shop_url)

        for collection in collections:
            collection_id = int(collection["id"].split("/")[-1])
            collection_name = collection["title"]
            products_count = collection["products_count"]
            updated_at = collection["updated_at"]

            default_algo = SortingAlgorithm.objects.get(algo_id=1)

            client_collection, created = ClientCollections.objects.get_or_create(
                collection_id=collection_id,
                shop_id=shop_id,
                defaults={
                    "collection_name": collection_name,
                    "products_count": products_count,
                    "status": False,
                    "algo": default_algo,
                    "parameters_used": {},
                    "updated_at": updated_at,
                    "refetch": True,
                },
            )

            if not created:
                client_collection.collection_name = collection_name
                client_collection.products_count = products_count
                client_collection.updated_at = updated_at
                client_collection.refetch = True
                client_collection.save()

        print("collections fetched:",len(collections))
        return {"status": "success", "collections_fetched": len(collections)}

    except Exception as e:
        return {"status": "error", "message": str(e)}

@shared_task
def async_fetch_and_store_products(shop_url, shop_id, collection_id, days):
    try:
        products = fetch_products_by_collection(shop_url, collection_id, days)
        total_revenue = 0  

        if products:
            print("Products fetched successfully:", len(products))

        for product in products:
            product_id = product.get("id")
            product_name = product.get("title", "")
            image_link = product.get("image")
            created_at = product.get("listed_date", "")
            updated_at = product.get("updated_at", "")
            published_at = product.get("published_at", "")
            total_inventory = product.get("totalInventory", 0)
            tags = product.get("tags", [])
            variant_count = product.get("variants_count", 0)
            variant_availability = product.get("variant_availability", 0)
            revenue = product.get("revenue", 0.00)  
            sales_velocity = product.get("sales_velocity", 0.00)
            total_sold_units = product.get("total_sold_units", 0)

            total_revenue += revenue

            ClientProducts.objects.update_or_create(
                product_id=product_id,
                defaults={
                    'shop_id': shop_id,
                    'collection_id': collection_id,
                    'product_name': product_name,
                    'image_link': image_link,
                    'created_at': created_at,   
                    'tags': tags,
                    'updated_at': updated_at,
                    'published_at': published_at,
                    'total_revenue': float(revenue),
                    'variant_count': variant_count,
                    'variant_availability': variant_availability,
                    'total_inventory': total_inventory,
                    'total_sold_units': total_sold_units,
                    'sales_velocity': float(sales_velocity)
                }
            )

        # Update the total revenue in the ClientCollections model
        ClientCollections.objects.filter(collection_id=collection_id, shop_id=shop_id).update(
            total_revenue=total_revenue
        )

        return {"status": "success", "products_fetched": len(products), "total_revenue": total_revenue}
    
    except Exception as e:
        print(f"Error storing products: {str(e)}")
        return {"status": "error", "message": str(e)}

@shared_task
def async_sort_product_order(shop_id, collection_id, algo_id, parameters):
    try:
        client = Client.objects.get(shop_id=shop_id)
        client_collections = ClientCollections.objects.get(shop_id=shop_id, collection_id=collection_id)

        products = fetch_products_by_collection(client.shop_url, collection_id, parameters['days'])
        
        pinned_product_ids = client_collections.pinned_products

        sort_function = ALGO_ID_TO_FUNCTION.get(algo_id)

        if sort_function:
            print("sort function yeah rha:",sort_function)

        products = ClientProducts.objects.filter(shop_id=shop_id, collection_id=collection_id).values(
            "product_id", "product_name", "total_sold_units", "image_link",
            "tags", "variant_count", "variant_availability", "total_revenue",
            "sales_velocity"
        )

        if products:
            print("products ah gye")
        
        if pinned_product_ids:
            products, pinned_products = remove_pinned_products(
                products, pinned_product_ids
            )
        else:
            pinned_products = []

        sorted_products = sort_function(
            products,
            days=parameters['days'],
            percentile=parameters['percentile'],
            variant_threshold=parameters['variant_threshold'],
        )

        if sorted_products:
            print("print hai sorted wale niche")

        print(sorted_products)

        if client_collections.pinned_out_of_stock_down:
            pinned_products, ofs_pinned = segregate_pinned_products(pinned_products)
        
        if client_collections.out_of_stock_down:
            sorted_products, ofs_sorted_products = push_out_of_stock_down(sorted_products)
        
        if client_collections.pinned_out_of_stock_down:
            if client_collections.out_of_stock_down:
                sorted_products = pinned_products + sorted_products + ofs_pinned + ofs_sorted_products
            else :
                sorted_products = pinned_products + sorted_products + ofs_pinned
        else:
            if client_collections.out_of_stock_down:
                sorted_products = pinned_products + sorted_products + ofs_sorted_products
            else:
                sorted_products = pinned_products + sorted_products

        pid = pid_extractor(sorted_products)
        success = update_collection_products_order(client.shop_url, client.access_token, collection_id, pid)
        
        if success:
            print("success in updating product order")
        return success

    except Exception as e:
        print(f"Error in async task: {str(e)}")
        return False

def pid_extractor(products):
    return [int(product['product_id']) for product in products]