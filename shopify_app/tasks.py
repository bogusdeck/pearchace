# shopify_app/tasks.py
from celery import shared_task
from .models import Client, ClientCollections, ClientProducts, SortingAlgorithm, ClientAlgo
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

from home.rules import (
    new_products,
    revenue_generated,
    inventory_quantity,
    variant_availability_ratio,
    product_inventory,
    Number_of_sales,
    product_tags,
    product_inventory,
)

ALGO_ID_TO_FUNCTION = {
    "new products": new_products,  
    "revenue generated": revenue_generated,  
    "inventory quantity": inventory_quantity,  
    "variant availability ratio": variant_availability_ratio,  
    "number of sales": Number_of_sales, 
    "product tags": product_tags,  
    "product inventory": product_inventory,  
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

            default_algo = ClientAlgo.objects.get(algo_name="Promote New")

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
def async_quick_sort_product_order(shop_id, collection_id, algo_id):
    try:
        client = Client.objects.get(shop_id=shop_id)
        client_collection = ClientCollections.objects.get(shop_id=shop_id, collection_id=collection_id)
        days = client.lookback_period
        # products = fetch_products_by_collection(client.shop_url, collection_id, days)
        products = ClientProducts.objects.filter(shop_id=shop_id, collection_id=collection_id).values(
            "product_id", "product_name", "total_sold_units", "image_link",
            "tags", "variant_count", "variant_availability", "total_revenue",
            "sales_velocity"
        )

        print("total products fetched from database :", len(products))
        
        pinned_product_ids = client_collection.pinned_products
        new_order = []

        if pinned_product_ids:
            products, pinned_products = remove_pinned_products(products, pinned_product_ids)
            if client_collection.pinned_out_of_stock_down:
                pinned_products, ofs_pinned = segregate_pinned_products(pinned_products)
            else:
                ofs_pinned = []
            new_order.extend(pinned_products)  #
        else:
            pinned_products = []
        
        if client_collection.out_of_stock_down:
            products, ofs_products = push_out_of_stock_down(products)
        else:
            ofs_products = []
   
        client_algo = ClientAlgo.objects.get(clalgo_id=algo_id)
        buckets = client_algo.bucket_parameters
        
        for bucket in buckets:
            rule_name = bucket.get("rule_name")
            rule_params = bucket.get("parameters", {})
            capping = bucket.get("capping", None)

            sort_function = ALGO_ID_TO_FUNCTION.get(rule_name)
            if sort_function:
                print("sort function yeah rha:",sort_function)

            if sort_function:
                capped_products, uncapped_products = sort_function(products, capping=capping, **rule_params)

                if capped_products:
                    new_order.extend(capped_products)

                products = uncapped_products if uncapped_products else products


        new_order.extend(ofs_pinned)
        new_order.extend(ofs_products)
        
        print("total products sorted", len(new_order))

        
        pid = pid_extractor(new_order)
        print(pid)

        success = update_collection_products_order(client.shop_url, client.access_token, collection_id, pid)
        
        for index, product_id in enumerate(pid):
                ClientProducts.objects.filter(
                     product_id=product_id, collection_id=collection_id
                ).update(position_in_collection=index + 1) 

        if success:
            print("success in updating product order")
        return success

    except Exception as e:
        print(f"Error in async task: {str(e)}")
        return False

def pid_extractor(products):
    return [int(product['product_id']) for product in products]

@shared_task
def async_advance_sort_product_order(shop_id, collection_id, clalgo_id):
    try:
        client = Client.objects.get(shop_id=shop_id)
        client_collection = ClientCollections.objects.get(shop_id=shop_id, collection_id=collection_id)
        days = client.lookback_period  
        # products = fetch_products_by_collection(client.shop_url, collection_id, days)
        products = ClientProducts.objects.filter(shop_id=shop_id, collection_id=collection_id).values(
            "product_id", "product_name", "total_sold_units" , "created_at", "updated_at", "published_at", 
            "tags", "variant_count", "variant_availability", "total_revenue", "total_inventory", 
            "sales_velocity"
        )

        print("total products fetched from database :", len(products))

        pinned_product_ids = client_collection.pinned_products
        new_order = []

        if pinned_product_ids:
            products, pinned_products = remove_pinned_products(products, pinned_product_ids)
            if client_collection.pinned_out_of_stock_down:
                pinned_products, ofs_pinned = segregate_pinned_products(pinned_products)
            else:
                ofs_pinned = []
            new_order.extend(pinned_products)  #
        else:
            pinned_products = []
        
        if client_collection.out_of_stock_down:
            products, ofs_products = push_out_of_stock_down(products)
        else:
            ofs_products = []

    
        client_algo = ClientAlgo.objects.get(clalgo_id=clalgo_id)
        boost_tags = client_algo.boost_tags
        bury_tags = client_algo.bury_tags
        buckets = client_algo.bucket_parameters

        
        boost_tag_products = [product for product in products if any(tag in product["tags"] for tag in boost_tags)]
        new_order.extend(boost_tag_products) #

        products = [product for product in products if product not in boost_tag_products]

        
        bury_tag_products = [product for product in products if any(tag in product["tags"] for tag in bury_tags)]
        products = [product for product in products if product not in bury_tag_products]
 

        for bucket in buckets:
            rule_name = bucket.get("rule_name")
            rule_params = bucket.get("parameters", {})
            capping = bucket.get("capping", None)  

            sort_function = ALGO_ID_TO_FUNCTION.get(rule_name)
            if sort_function:
                print("sort function yeah rha:",sort_function)

            if sort_function:
                capped_products, uncapped_products = sort_function(products, capping=capping, **rule_params)

                if capped_products:
                    new_order.extend(capped_products)

                products = uncapped_products if uncapped_products else products

        new_order.extend(bury_tag_products)
        new_order.extend(ofs_pinned)
        new_order.extend(ofs_products)

        print("total products sorted", len(new_order))
        
    
        pid = pid_extractor(new_order)
        success = update_collection_products_order(client.shop_url, client.access_token, collection_id, pid)

        for index, product_id in enumerate(pid):
            ClientProducts.objects.filter(product_id=product_id, collection_id=collection_id).update(position_in_collection=index + 1)

        if success:
            print("Product order updated successfully!")
        return success

    except Exception as e:
        print(f"Error in async task: {str(e)}")
        return False
