# shopify_app/tasks.py
from celery import shared_task, chord
from django.db import transaction
from django.utils import timezone
from datetime import datetime, timedelta
from .models import Client, ClientCollections, ClientProducts, ClientAlgo, ClientGraph , Usage, Subscription, SortingPlan, History
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
    i_am_feeling_lucky,
    rfm_sort
)

ALGO_ID_TO_FUNCTION = {
    "new_products": new_products,  
    "revenue_generated": revenue_generated,  
    "inventory_quantity": inventory_quantity,  
    "variant_availability_ratio": variant_availability_ratio,  
    "Number_of_sales": Number_of_sales, 
    "product_tags": product_tags,  
    "product_inventory": product_inventory,
    "i_am_feeling_lucky":i_am_feeling_lucky,
    "rfm_sort":rfm_sort
}

from decimal import Decimal
import logging

logger = logging.getLogger(__name__)

@shared_task
def test_task():
    print("Celery is working!")

@shared_task
def async_fetch_and_store_collections(shop_id):
    try:
        logger.info(f"Starting async fetch and store collections for shop_id: {shop_id}")

        try:
            client = Client.objects.get(shop_id=shop_id)
            logger.debug(f"Client found for shop_id: {shop_id}")
        except Client.DoesNotExist:
            logger.error(f"Client not found for shop_id: {shop_id}")
            return {"status": "error", "message": f"Client not found for shop_id {shop_id}"}

        collections = fetch_collections(client.shop_url)
        logger.debug(f"Fetched {len(collections)} collections for shop_id: {shop_id}")

        for collection in collections:
            collection_id = int(collection["id"].split("/")[-1])
            collection_name = collection["title"]
            products_count = collection["products_count"]
            updated_at = collection["updated_at"]
            is_smart = collection["type"] == "Automatic Collection"

            try:
                default_algo = ClientAlgo.objects.get(algo_name="Promote New")
                logger.debug(f"Default algorithm found for collection: {collection_name}")
            except ClientAlgo.DoesNotExist:
                logger.error(f"Default algorithm 'Promote New' not found.")
                default_algo = None

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
                    "is_smart": is_smart,
                },
            )

            if not created:
                logger.debug(f"Updating existing collection: {collection_name}")
                client_collection.collection_name = collection_name
                client_collection.products_count = products_count
                client_collection.updated_at = updated_at
                client_collection.refetch = True
                client_collection.is_smart = is_smart
                client_collection.save()

        logger.info(f"Collections fetched and stored for shop_id: {shop_id}, total: {len(collections)}")
        return {"status": "success", "collections_fetched": len(collections)}

    except Exception as e:
        logger.error(f"Error fetching and storing collections for shop_id {shop_id}: {str(e)}")
        return {"status": "error", "message": str(e)}
    
@shared_task
def async_fetch_and_store_products(shop_url, shop_id, collection_id, days):
    try:
        logger.info(f"Starting product fetch for shop_id: {shop_id}, collection_id: {collection_id}, days: {days}")

        products = fetch_products_by_collection(shop_url, collection_id, days)
        logger.debug(f"Fetched {len(products)} products from collection_id {collection_id} for shop_id {shop_id}")

        total_revenue = 0  
        total_sales = 0

        if products:
            logger.info(f"Products fetched successfully: {len(products)}")

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
            recency_score = product.get("recency_score", None)
            discount_percentage = product.get('discount_percentage')
            discount_absolute = product.get('discount_absolute')

            total_revenue += revenue
            total_sales += total_sold_units

            logger.debug(f"Updating product in database: {product_name} (ID: {product_id})")

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
                    'sales_velocity': float(sales_velocity),
                    'recency_score': recency_score,
                    'discount_absolute':discount_absolute,
                    'discount_percentage': discount_percentage  
                }
            )

        ClientCollections.objects.filter(collection_id=collection_id, shop_id=shop_id).update(
            collection_total_revenue=total_revenue,
            collection_sold_units=total_sales
        )

        logger.info(f"Product fetch and store completed for shop_id: {shop_id}, collection_id: {collection_id}")
        return {"status": "success", "products_fetched": len(products), "total_revenue": total_revenue}
    
    except Exception as e:
        logger.error(f"Error storing products for shop_id {shop_id}, collection_id {collection_id}: {str(e)}")
        return {"status": "error", "message": str(e)}

@shared_task #not ussing i guess
def async_cron_sort_product_order(shop_id, collection_id, algo_id):
    try:
        logger.info(f"Starting advanced sort for shop_id: {shop_id}, collection_id: {collection_id}, algo_id: {algo_id}")

        client = Client.objects.get(shop_id=shop_id)
        logger.info(f"Client found: {client}")
        
        client_collection = ClientCollections.objects.get(shop_id=shop_id, collection_id=collection_id)
        logger.info(f"Client collection found: {client_collection}")
        

        days = client.lookback_period
        products = fetch_products_by_collection(client.shop_url, collection_id, days)
        logger.debug(f"Total products fetched from database: {len(products)}")

        total_collection_revenue = sum(product['total_revenue'] for product in products)
        logger.info(f"Total collection revenue calculated: {total_collection_revenue}")

        if client_collection.collection_total_revenue is not None:
            logger.info(f"Existing total collection revenue found: {client_collection.collection_total_revenue}, overwriting...")
        else:
            logger.info("No previous total collection revenue found, saving for the first time...")

        client_collection.collection_total_revenue = total_collection_revenue
        client_collection.save()

        pinned_product_ids = client_collection.pinned_products
        new_order = []  

        if pinned_product_ids:
            logger.info("Pinned products found, processing...")
            products, pinned_products = remove_pinned_products(products, pinned_product_ids)

            if client_collection.pinned_out_of_stock_down:
                pinned_products, ofs_pinned = segregate_pinned_products(pinned_products)
                logger.info(f"Out of stock pinned products segregated: {len(ofs_pinned)}")
            else:
                ofs_pinned = []
            new_order.extend(pinned_products)
        else:
            pinned_products = []
            ofs_pinned = []

        if client_collection.out_of_stock_down:
            products, ofs_products = push_out_of_stock_down(products)
            logger.info(f"Out of stock products pushed down: {len(ofs_products)}")
        else:
            ofs_products = []

        client_algo = ClientAlgo.objects.get(algo_id=algo_id)
        boost_tags = client_algo.boost_tags
        bury_tags = client_algo.bury_tags
        buckets = client_algo.bucket_parameters

        boost_tag_products = [product for product in products if any(tag in product["tags"] for tag in boost_tags)]
        new_order.extend(boost_tag_products)
        logger.info(f"Boost tag products added: {len(boost_tag_products)}")

        products = [product for product in products if product not in boost_tag_products]

        bury_tag_products = [product for product in products if any(tag in product["tags"] for tag in bury_tags)]
        products = [product for product in products if product not in bury_tag_products]
        logger.info(f"Bury tag products removed: {len(bury_tag_products)}")

        if isinstance(buckets, dict):
            buckets = [buckets]

        for bucket in buckets:
            rule_name = bucket.get("rule_name")
            rule_params = bucket.get("parameters", {})
            capping = rule_params.pop("capping", None)

            sort_function = ALGO_ID_TO_FUNCTION.get(rule_name)
            if sort_function:
                logger.info(f"Sorting function found for rule: {rule_name}, applying sort...")
                capped_products, uncapped_products = sort_function(products, capping=capping, **rule_params)

                if capped_products:
                    new_order.extend(capped_products)
                    logger.info(f"Capped products added: {len(capped_products)}")

                products = uncapped_products if uncapped_products else products
            else:
                logger.warning(f"No sort function found for rule: {rule_name}")

        new_order.extend(bury_tag_products)
        new_order.extend(ofs_pinned)
        new_order.extend(ofs_products)

        logger.info(f"Total products sorted: {len(new_order)}")

        pid = pid_extractor(new_order)
        success = update_collection_products_order(client.shop_url, client.access_token, collection_id, pid)

        for index, product_id in enumerate(pid):
            ClientProducts.objects.filter(product_id=product_id, collection_id=collection_id).update(position_in_collection=index + 1)

        if success:
            logger.info("Product order updated successfully!")
        return success

    except Exception as e:
        logger.error(f"Error in async task: {str(e)}")
        return False

def pid_extractor(products):
    return [int(product['product_id']) for product in products]

import json

@shared_task
def async_sort_product_order(shop_id, collection_id, algo_id, history_entry_id):
    try:
        logger.info("Async advanced sort product order running")
        
        history_entry = History.objects.get(id=history_entry_id)
        
        history_entry.started_at = datetime.now()
        history_entry.save()
        
        client = Client.objects.get(shop_id=shop_id)
        logger.info(f"Client found: {client}")
        
        client_collection = ClientCollections.objects.get(shop_id=shop_id, collection_id=collection_id)
        logger.info(f"Client collection found: {client_collection}")
        
        days = client.lookback_period  
        
        products = ClientProducts.objects.filter(shop_id=shop_id, collection_id=collection_id).values(
            "product_id", "product_name", "total_sold_units", "created_at", "updated_at", "published_at", 
            "tags", "variant_count", "variant_availability", "total_revenue", "total_inventory", 
            "sales_velocity", "recency_score"
        )
        logger.info(f"Total products fetched from database: {len(products)}")

        total_collection_revenue = sum(product['total_revenue'] for product in products)

        if client_collection.collection_total_revenue is not None:
            logger.info(f"Existing total collection revenue found: {client_collection.collection_total_revenue}, overwriting...")
        else:
            logger.info("No previous total collection revenue found, saving for the first time...")

        client_collection.collection_total_revenue = total_collection_revenue
        client_collection.save()

        pinned_product_ids = client_collection.pinned_products
        new_order = []

        if pinned_product_ids:
            products, pinned_products = remove_pinned_products(products, pinned_product_ids)
            if client_collection.pinned_out_of_stock_down:
                pinned_products, ofs_pinned = segregate_pinned_products(pinned_products)
            else:
                ofs_pinned = []
            new_order.extend(pinned_products)
        else:
            pinned_products = []
            ofs_pinned = []
        
        logger.info(f"Products and pinned products segregated: {len(products)} products, {len(pinned_products)} pinned, {len(ofs_pinned)} out-of-stock pinned")

        if client_collection.out_of_stock_down:
            products, ofs_products = push_out_of_stock_down(products)
        else:
            ofs_products = []

        logger.info(f"Out-of-stock products segregated: {len(products)} products, {len(ofs_pinned)} pinned, {len(ofs_products)} out-of-stock products")

        client_algo = ClientAlgo.objects.get(algo_id=algo_id)
        logger.info(f"Client algorithm found: {client_algo}")

        boost_tags = client_algo.boost_tags
        bury_tags = client_algo.bury_tags
        buckets = client_algo.bucket_parameters
        
        logger.info(f"Boost tags: {boost_tags}, Bury tags: {bury_tags}, Buckets: {buckets}")

        boost_tag_products = [product for product in products if any(tag in product["tags"] for tag in boost_tags)]
        new_order.extend(boost_tag_products)

        products = [product for product in products if product not in boost_tag_products]

        bury_tag_products = [product for product in products if any(tag in product["tags"] for tag in bury_tags)]
        products = [product for product in products if product not in bury_tag_products]

        if isinstance(buckets, dict):
            buckets = [buckets]
            
        for bucket in buckets:
            logger.info(f"Processing bucket: {bucket}")

            rule_name = bucket.get("rule_name")
            rule_params = bucket.get("parameters", {})
            capping = rule_params.pop("capping", None)

            sort_function = ALGO_ID_TO_FUNCTION.get(rule_name)
            if sort_function:
                logger.info(f"Sorting function found for rule: {rule_name}")

                capped_products, uncapped_products = sort_function(products, capping=capping, **rule_params)

                if capped_products:
                    new_order.extend(capped_products)

                products = uncapped_products if uncapped_products else products
            else:
                logger.warning(f"No sort function found for rule: {rule_name}")

        new_order.extend(bury_tag_products)
        new_order.extend(ofs_pinned)
        new_order.extend(ofs_products)

        logger.info(f"Total products sorted: {len(new_order)}")
        
        pid = pid_extractor(new_order)
        success = update_collection_products_order(client.shop_url, client.access_token, collection_id, pid)

        for index, product_id in enumerate(pid):
            ClientProducts.objects.filter(product_id=product_id, collection_id=collection_id).update(position_in_collection=index + 1)

        if success:
            logger.info("Product order updated successfully!")
            history_entry.status = 'Done'
            history_entry.product_count = ClientProducts.objects.filter(shop_id=shop_id,collection_id=collection_id).count()
            client_collection.sort_date = datetime.now()
            client_collection.save()
        else:
            history_entry.status = 'Failed'
            
        history_entry.ended_at = datetime.now()
        history_entry.save()    
        
        return success

    except Exception as e:
        logger.error(f"Error in async task: {str(e)}")
        history_entry.status = 'Failed'
        history_entry.ended_at = datetime.now()
        history_entry.save()
        
        return False

@shared_task
def sort_active_collections(client_id):
    history_entry = None  
    try:
        client = Client.objects.get(id=client_id)
        logger.info(f"Sorting active collections for client {client.shop_id}")
        
        history_entry = History.objects.create(
            shop_id=client,
            requested_by='cron job',
            product_count=0,
            collection_name='All active collections',
            status='pending'       
        )
        
        usage = Usage.objects.get(shop_id=client.shop_id)
        subscription = Subscription.objects.get(subscription_id=usage.subscription_id)
        sorting_plan = SortingPlan.objects.get(plan_id=subscription.plan_id)
        
        sort_limit = sorting_plan.sort_limit
        available_sort = sort_limit - usage.sorts_count

        logger.info(f"Sort limit: {sort_limit}, available sorts: {available_sort} for client {client.shop_id}")

        active_collections = ClientCollections.objects.filter(shop_id=client.shop_id, collection_status=True)

        if not active_collections.exists():
            logger.info(f"No active collections found for client {client.shop_id}")
            history_entry.status = "done"
            history_entry.ended_at = datetime.now()
            history_entry.save()
            return

        tasks = []
        for collection in active_collections:
            collection_id = collection.collection_id
            algo_id = collection.algo_id  

            logger.info(f"Triggering async sort for collection {collection_id} of client {client.shop_id}")
            
            tasks.append(async_sort_product_order.s(client.shop_id, collection_id, algo_id, history_entry.id))

        chord(tasks)(calculate_revenue.s(client.shop_id))
        logger.info(f"Completed triggering sorting for all active collections of client {client.shop_id}")

    except Client.DoesNotExist:
        logger.error(f"Client with id {client_id} does not exist")
    except Usage.DoesNotExist:
        logger.error(f"Usage data not found for client {client_id}")
    except Subscription.DoesNotExist:
        logger.error(f"Subscription data not found for client {client_id}")
    except SortingPlan.DoesNotExist:
        logger.error(f"Sorting plan not found for client {client_id}")
    except Exception as e:
        logger.error(f"Exception occurred while sorting active collections: {str(e)}")
    finally:
        
        if isinstance(history_entry, History):
            history_entry.status = "failed"
            history_entry.ended_at = datetime.now()
            history_entry.save()


@shared_task
def calculate_revenue(client_id):
    try:
        total_revenue = ClientCollections.objects.filter(shop_id=client_id).aggregate(
            total_revenue=Sum('collection_total_revenue')
        )['total_revenue'] or 0

        today = timezone.now().date()

        with transaction.atomic():
            client_graph, created = ClientGraph.objects.update_or_create(
                shop_id=client_id,
                date=today,
                defaults={'revenue': total_revenue}
            )

            if created:
                logger.info(f"Created new revenue entry for shop {client_id} on {today} with revenue {total_revenue}")
            else:
                logger.info(f"Updated revenue entry for shop {client_id} on {today} with revenue {total_revenue}")

    except Exception as e:
        logger.error(f"Exception occurred while calculating revenue for client {client_id}: {str(e)}")

@shared_task
def reset_sort_counts():
    try:
        reset_date = timezone.now() - timedelta(days=30)

        expired_usages = Usage.objects.filter(created_at__lte=reset_date)

        if not expired_usages.exists():
            logger.info("No expired usages found to reset sort counts.")
            return

        for usage in expired_usages:
            usage.sorts_count = 0
            usage.usage_date = timezone.now()  
            usage.save()

            logger.info(f"Reset sort counts for usage {usage.id} for shop {usage.shop_id}")

        logger.info(f"Successfully reset sort counts for {expired_usages.count()} usages.")

    except Exception as e:
        logger.error(f"Exception occurred while resetting sort counts: {str(e)}")