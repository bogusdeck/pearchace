import requests
import json
import shopify
from django.apps import apps
from .models import Client
from datetime import datetime
import pytz
from django.utils import timezone
from datetime import datetime, timedelta

from celery import shared_task

def _get_shopify_headers(access_token):
    return {"Content-Type": "application/json", "X-Shopify-Access-Token": access_token}

def fetch_collections(shop_url):
    client = _get_client(shop_url)
    if not client:
        return []
    
    access_token = client.access_token
    api_version = apps.get_app_config("shopify_app").SHOPIFY_API_VERSION
    headers = _get_shopify_headers(access_token)

    url = f"https://{shop_url}/admin/api/{api_version}/graphql.json"
    collections = []
    has_next_page = True
    cursor = None

    while has_next_page:
        query = """
        query($after: String) {
            collections(first: 250, after: $after) {
                edges {
                    cursor
                    node {
                        id
                        title
                        updatedAt
                        productsCount {
                            count
                        }
                    }
                }
                pageInfo {
                    hasNextPage
                }
            }
        }
        """

        variables = {"after": cursor} if cursor else {}
        response = requests.post(url, json={"query": query, "variables": variables}, headers=headers)

        
        if response.status_code == 200:
            data = response.json()
            new_collections = data.get("data", {}).get("collections", {}).get("edges", [])
            collections.extend(new_collections)
            page_info = data.get("data", {}).get("collections", {}).get("pageInfo", {})
            has_next_page = page_info.get("hasNextPage", False)
            if has_next_page:
                cursor = new_collections[-1]["cursor"] if new_collections else None
        else:
            print(f"Error fetching collections: {response.status_code} - {response.text}")
            break
        
    return [
        {
            "id": collection["node"]["id"],
            "title": collection["node"]["title"],
            "products_count": collection["node"]["productsCount"]["count"],
            "updated_at": collection["node"]["updatedAt"],
        }
        for collection in collections
    ]

def fetch_products_by_collection_with_img(shop_url, collection_id): #will remove later
    """
    Fetches all products from a specific collection in a Shopify store using the GraphQL API.

    Args:
        shop_url (str): The URL of the Shopify store.
        collection_id (str): The ID of the collection to fetch products from.

    Returns:
        list: A list of products or an empty list if an error occurs.
    """
    client = _get_client(shop_url)
    if not client:
        return []

    access_token = client.access_token
    api_version = apps.get_app_config("shopify_app").SHOPIFY_API_VERSION
    headers = _get_shopify_headers(access_token)
   

    url = f"https://{shop_url}/admin/api/{api_version}/graphql.json"

    query = f"""
    {{
      collection(id: "gid://shopify/Collection/{collection_id}") {{
        products(first: 250) {{
          edges {{
            node {{
              id
              title
              images(first: 5) {{
                edges {{
                  node {{
                    id
                    src
                    altText
                  }}
                }}
              }}
            }}
          }}
        }}
      }}
    }}
    """

    response = requests.post(url, json={"query": query}, headers=headers)
    if response.status_code == 200:
        data = response.json()
        products = (
            data.get("data", {})
            .get("collection", {})
            .get("products", {})
            .get("edges", [])
        )
        return [
            {
                "id": product["node"]["id"],
                "title": product["node"]["title"],
                "images": [
                    image["node"]
                    for image in product["node"].get("images", {}).get("edges", [])
                ],
            }
            for product in products
        ]
    else:
        print(f"Error fetching products: {response.status_code} - {response.text}")
        return []

##########################
def fetch_products_by_collection(shop_url, collection_id, days):
    print("api running start")
    client = _get_client(shop_url)
    if not client:
        return []

    access_token = client.access_token
    api_version = apps.get_app_config("shopify_app").SHOPIFY_API_VERSION
    headers = _get_shopify_headers(access_token)

    orders = fetch_orders(shop_url, days, headers)
    print("orders fetching done")

    product_sales_data = {}
    
    url = f"https://{shop_url}/admin/api/{api_version}/graphql.json"
    products = []
    has_next_page = True
    cursor = None

    while has_next_page:
        query = f"""
        query($after: String) {{
            collection(id: "gid://shopify/Collection/{collection_id}") {{
                products(first: 250, after: $after) {{
                    edges {{
                        cursor
                        node {{
                            id
                            title
                            totalInventory
                            createdAt
                            publishedAt
                            updatedAt
                            tags
                            images(first: 1) {{
                                edges {{
                                    node {{
                                        src
                                        altText
                                    }}
                                }}
                            }}
                            variantsCount {{  
                                count
                            }}
                            variants(first: 10) {{
                                edges {{
                                    node {{
                                        id
                                        price
                                        inventoryQuantity
                                    }}
                                }}
                            }}
                        }}
                    }}
                    pageInfo {{
                        hasNextPage
                    }}
                }}
            }}
        }}
        """

        variables = {"after": cursor} if cursor else {}
        response = requests.post(url, json={"query": query, "variables": variables}, headers=headers)
        print("response done")


        if response.status_code == 200:
            data = response.json()
            new_products = (
                data.get("data", {})
                .get("collection", {})
                .get("products", {})
                .get("edges", [])
            )
            products.extend(new_products)
            page_info = (
                data.get("data", {})
                .get("collection", {})
                .get("products", {})
                .get("pageInfo", {})
            )
            has_next_page = page_info.get("hasNextPage", False)
            if has_next_page:
                cursor = new_products[-1]["cursor"]
        else:
            print(f"Error fetching products: {response.status_code} - {response.text}")
            break

    products_data = []
    for product in products:
        product_id = product["node"]["id"].split("/")[-1]

        recency_score = calculate_recency_score(orders, product["node"]["id"])
        print("recency score : ", recency_score)
        revenue = calculate_revenue_from_orders(orders, product["node"]["id"])
        sales_velocity = calculate_sales_velocity_from_orders(orders, product["node"]["id"], days)
        total_sold_units =  calculate_sales_velocity_from_orders(orders, product["node"]["id"], days, return_units=True)

        # try:
        #     client_product = ClientProducts.objects.get(product_id=product_id, shop=client)
        #     client_product.recency_score = recency_score
        #     client_product.save()
        # except ClientProducts.DoesNotExist:
        #     print(f"Product {product_id} not found in ClientProducts. Skipping update.")

        products_data.append({
            "id": product_id,
            "title": product["node"]["title"],
            "image": product["node"]["images"]["edges"][0]["node"]["src"] if product["node"]["images"]["edges"] else None,
            "totalInventory": product["node"]["totalInventory"],
            "listed_date": product["node"]["createdAt"],
            "published_at": product["node"]["publishedAt"],
            "updated_at": product["node"]["updatedAt"],
            "tags": product["node"].get("tags", []),
            "revenue": revenue,
            "sales_velocity": sales_velocity,
            "total_sold_units": total_sold_units,
            "variants_count": product["node"]["variantsCount"]["count"],
            "variant_availability": sum(
                variant["node"]["inventoryQuantity"]
                for variant in product["node"]["variants"]["edges"]
            ),
            "recency_score": recency_score,
        })

    return products_data

def fetch_orders(shop_url, days, headers):
    """
    Fetches orders within a specified date range using Shopify's GraphQL API.
    """

    print("orders fetching start")
    api_version = apps.get_app_config("shopify_app").SHOPIFY_API_VERSION
    url = f"https://{shop_url}/admin/api/{api_version}/graphql.json"
    end_date = timezone.now()
    start_date = end_date - timedelta(days=days)
    start_date_iso = start_date.isoformat()
    end_date_iso = end_date.isoformat()
    
    has_next_page = True
    after_cursor = None
    orders = []

    while has_next_page:
        pagination_query = f', after: "{after_cursor}"' if after_cursor else ""
        query = f"""
        {{
          orders(first: 250, query: "created_at:>{start_date} AND created_at:<{end_date}"{pagination_query}) {{
            edges {{
              cursor
              node {{
                id
                createdAt
                lineItems(first: 250) {{
                  edges {{
                    node {{
                      product {{
                        id  
                      }}
                      quantity
                      originalUnitPriceSet {{
                        shopMoney {{
                          amount
                        }}
                      }}
                    }}
                  }}
                }}
              }}
            }}
            pageInfo {{
              hasNextPage
            }}
          }}
        }}
        """

        response = requests.post(url, json={"query": query}, headers=headers)
        
        if response.status_code != 200:
            print(f"Error fetching orders: {response.status_code} - {response.text}")
            return []

        data = response.json().get("data", {}).get("orders", {})
        has_next_page = data.get("pageInfo", {}).get("hasNextPage", False)
        after_cursor = data["edges"][-1]["cursor"] if has_next_page else None
        orders.extend(data["edges"])

    return orders

def calculate_revenue_from_orders(orders, product_id):
    total_revenue = 0
    print("order revenue calculating.....")
    for order in orders:
        for line_item in order["node"]["lineItems"]["edges"]:
            if line_item["node"]["product"]["id"] == product_id :
                price = float(line_item["node"]["originalUnitPriceSet"]["shopMoney"]["amount"])
                quantity = int(line_item["node"]["quantity"])
                total_revenue += price * quantity
                print("total revuenue" ,total_revenue)

    return total_revenue


from datetime import datetime, timezone as dt_timezone
from django.utils import timezone

def calculate_recency_score(orders, product_id):
    last_order_date = None

    for order in orders:
        for line_item in order["node"]["lineItems"]["edges"]:
            if line_item["node"]["product"]["id"] == product_id:
                order_date_str = order["node"]["createdAt"]


                if order_date_str.endswith('Z'):
                    order_date = datetime.strptime(order_date_str, '%Y-%m-%dT%H:%M:%SZ')
                    order_date = order_date.replace(tzinfo=dt_timezone.utc)  
                else:
                    order_date = datetime.fromisoformat(order_date_str)

                if not last_order_date or order_date > last_order_date:
                    last_order_date = order_date

    if last_order_date:
        recency_score = (timezone.now() - last_order_date).days
    else:
        # recency_score = float('inf')
        recency_score = 0

    return recency_score


def calculate_sales_velocity_from_orders(orders, product_id, days, return_units=False):
    total_sold_units = 0
    print("total sold unit calculation done!")
    for order in orders:
        for line_item in order["node"]["lineItems"]["edges"]:
            if line_item["node"]["product"]["id"] == product_id :
                quantity = int(line_item["node"]["quantity"])
                total_sold_units += quantity
                print("total_sold_units", total_sold_units)

    sales_velocity = total_sold_units / days if days > 0 else 0
    return total_sold_units if return_units else sales_velocity

#########################

def get_past_date(days):
    date = datetime.utcnow() - timedelta(days=days)
    return date.strftime('%Y-%m-%dT%H:%M:%SZ')  

def _get_client(shop_url):
    """
    Fetches the Client instance for a specific shop URL.

    Args:
        shop_url (str): The URL of the Shopify store.

    Returns:
        Client: The Client instance or None if not found.
    """
    try:
        return Client.objects.get(shop_url=shop_url)
    except Client.DoesNotExist:
        print(f"Client with shop URL {shop_url} does not exist.")
        return None

def fetch_client_data(shop_url, access_token):
    """
    Fetches the client's shop data from Shopify using the GraphQL API.

    Args:
        shop_url (str): The URL of the Shopify store.
        access_token (str): The access token for the Shopify store.

    Returns:
        dict: A dictionary containing the client's shop data or an empty dictionary if an error occurs.
    """
    api_version = apps.get_app_config("shopify_app").SHOPIFY_API_VERSION
    headers = _get_shopify_headers(access_token)

    url = f"https://{shop_url}/admin/api/{api_version}/graphql.json"

    query = """
    {
      shop {
        id
        name
        email
        primaryDomain {
          url
          host
        }
        myshopifyDomain
        plan {
          displayName
        }
        createdAt
        timezoneAbbreviation
        currencyCode
        contactEmail: email
        billingAddress {
          address1
          address2
          city
          province
          countryCodeV2
          phone
          zip
        }
      }
    }
    """

    response = requests.post(url, json={"query": query}, headers=headers)
    if response.status_code == 200:
        data = response.json()
        print("Data from Shopify:", data) 
        return data.get("data", {}).get("shop", {})
    else:
        print(f"Error fetching shop data: {response.status_code} - {response.text}")
        return {}

def update_collection_products_order(
      shop_url, access_token, collection_id, sorted_product_ids
  ):
      """
      Updates the product order of a collection in Shopify.

      Args:
          shop_url (str): The Shopify store URL.
          access_token (str): The access token for Shopify API authentication.
          collection_id (str): The ID of the collection to update.
          sorted_product_ids (list): A list of product IDs in the desired order.

      Returns:
          bool: True if the update is successful, False otherwise.
      """
      try:
          api_version = apps.get_app_config("shopify_app").SHOPIFY_API_VERSION
          headers = _get_shopify_headers(access_token)
          url = f"https://{shop_url}/admin/api/{api_version}/graphql.json"
          collection_global_id = f"gid://shopify/Collection/{collection_id}"


          print("\n\n", api_version, headers, url, collection_global_id)
          
          mutation = """
          mutation updateProductOrder($id: ID!, $moves: [MoveInput!]!) {
              collectionReorderProducts(id: $id, moves: $moves) {
                  userErrors {
                      field
                      message
                  }
              }
          }
          """

          print("working till now")
          moves = [
              {
                  "id": f"gid://shopify/Product/{product_id}",
                  "newPosition": str(position),  
              }
              for position, product_id in enumerate(sorted_product_ids)
          ]

          print(moves)
          print("working till now 2")
          variables = {"id": collection_global_id, "moves": moves}
          print("working till now 3")
          response = requests.post(
              url, json={"query": mutation, "variables": variables}, headers=headers
          )

          print(response.json())
          if response.status_code == 200:
              result = response.json()
              errors = (
                  result.get("data", {})
                  .get("collectionReorderProducts", {})
                  .get("userErrors", [])
              )

              print("ho gya syd")
              if not errors:
                  return True
              else:
                  print(f"User errors: {errors}")
          else:
              print(
                  f"Failed to reorder products: {response.status_code} - {response.text}"
              )
          return False

      except Exception as e:
          print(f"Exception during product order update: {str(e)}")
          return False

#########################

##not needed now might be in future
def fetch_order_for_graph(shop_url, start_date, end_date):
    client = _get_client(shop_url)
    if not client:
        return []

    access_token = client.access_token
    api_version = apps.get_app_config("shopify_app").SHOPIFY_API_VERSION
    headers = _get_shopify_headers(access_token)
    url = f"https://{shop_url}/admin/api/{api_version}/graphql.json"

    orders = []
    has_next_page = True
    after_cursor = None
    total_revenue = 0

    while has_next_page:
        pagination_query = f', after: "{after_cursor}"' if after_cursor else ""
        query = f"""
        {{
          orders(first: 250, query: "created_at:>{start_date.isoformat()} AND created_at:<{end_date.isoformat()}"{pagination_query}) {{
            edges {{
              cursor
              node {{
                id
                createdAt
                lineItems(first: 250) {{
                  edges {{
                    node {{
                      product {{
                        id  
                      }}
                      quantity
                      originalUnitPriceSet {{
                        shopMoney {{
                          amount
                        }}
                      }}
                    }}
                  }}
                }}
              }}
            }}
            pageInfo {{
              hasNextPage
            }}
          }}
        }}
        """

        response = requests.post(url, json={"query": query}, headers=headers)
        if response.status_code != 200:
            print(f"Error fetching orders: {response.status_code} - {response.text}")
            return []

        data = response.json().get("data", {}).get("orders", {})
        new_orders = data.get("edges", [])
        has_next_page = data.get("pageInfo", {}).get("hasNextPage", False)
        after_cursor = new_orders[-1]["cursor"] if has_next_page else None
        orders.extend(new_orders)

    for order in orders:
        for line_item in order["node"]["lineItems"]["edges"]:
            price = float(line_item["node"]["originalUnitPriceSet"]["shopMoney"]["amount"])
            quantity = int(line_item["node"]["quantity"])
            total_revenue += price * quantity

    return {
        "orders": orders,
        "total_revenue": total_revenue,
    }

def fetch_products_for_graph(shop_url, collection_ids, start_date, end_date):
    client = _get_client(shop_url)
    if not client:
        return []

    access_token = client.access_token
    api_version = apps.get_app_config("shopify_app").SHOPIFY_API_VERSION
    headers = _get_shopify_headers(access_token)

    products_data = {}
    
    for collection_id in collection_ids:
        url = f"https://{shop_url}/admin/api/{api_version}/graphql.json"
        products = []
        has_next_page = True
        cursor = None

        while has_next_page:
            query = f"""
            query($after: String) {{
                collection(id: "gid://shopify/Collection/{collection_id}") {{
                    products(first: 250, after: $after) {{
                        edges {{
                            cursor
                            node {{
                                id
                                title
                                totalInventory
                                createdAt
                                publishedAt
                                updatedAt
                                tags
                                images(first: 1) {{
                                    edges {{
                                        node {{
                                            src
                                            altText
                                        }}
                                    }}
                                }}
                                variantsCount {{  
                                    count
                                }}
                                variants(first: 10) {{
                                    edges {{
                                        node {{
                                            id
                                            price
                                            inventoryQuantity
                                        }}
                                    }}
                                }}
                            }}
                        }}
                        pageInfo {{
                            hasNextPage
                        }}
                    }}
                }}
            }}
            """

            variables = {"after": cursor} if cursor else {}
            response = requests.post(url, json={"query": query, "variables": variables}, headers=headers)

            if response.status_code == 200:
                data = response.json()
                new_products = (
                    data.get("data", {})
                    .get("collection", {})
                    .get("products", {})
                    .get("edges", [])
                )
                products.extend(new_products)
                page_info = (
                    data.get("data", {})
                    .get("collection", {})
                    .get("products", {})
                    .get("pageInfo", {})
                )
                has_next_page = page_info.get("hasNextPage", False)
                if has_next_page:
                    cursor = new_products[-1]["cursor"]
            else:
                print(f"Error fetching products: {response.status_code} - {response.text}")
                break

        for product in products:
            product_id = product["node"]["id"].split("/")[-1]
            orders_data = fetch_order_for_graph(shop_url, start_date, end_date)
            total_revenue = calculate_revenue_from_orders(orders_data["orders"], product_id)

            products_data[product_id] = {
                "title": product["node"]["title"],
                "totalInventory": product["node"]["totalInventory"],
                "createdAt": product["node"]["createdAt"],
                "publishedAt": product["node"]["publishedAt"],
                "updatedAt": product["node"]["updatedAt"],
                "tags": product["node"].get("tags", []),
                "revenue": total_revenue,
                "sales_velocity": calculate_sales_velocity_from_orders(orders_data["orders"], product_id, (end_date - start_date).days),
                "total_sold_units": calculate_sales_velocity_from_orders(orders_data["orders"], product_id, (end_date - start_date).days, return_units=True),
                "variants_count": product["node"]["variantsCount"]["count"],
                "variant_availability": sum(
                    variant["node"]["inventoryQuantity"]
                    for variant in product["node"]["variants"]["edges"]
                ),
            }

    return products_data

#####################################################################################################
# orders feetching for billing checks
#####################################################################################################

def fetch_order_for_billing(shop_url, start_date, end_date):
    client = _get_client(shop_url)
    if not client:
        return None

    access_token = client.access_token
    api_version = apps.get_app_config("shopify_app").SHOPIFY_API_VERSION
    headers = _get_shopify_headers(access_token)
    url = f"https://{shop_url}/admin/api/{api_version}/graphql.json"

    total_orders = 0
    has_next_page = True
    after_cursor = None

    while has_next_page:
        pagination_query = f', after: "{after_cursor}"' if after_cursor else ""
        query = f"""
        {{
          orders(first: 250, query: "created_at:>{start_date.isoformat()} AND created_at:<{end_date.isoformat()}"{pagination_query}) {{
            edges {{
              cursor
            }}
            pageInfo {{
              hasNextPage
            }}
          }}
        }}
        """

        response = requests.post(url, json={"query": query}, headers=headers)
        if response.status_code != 200:
            print(f"Error fetching orders: {response.status_code} - {response.text}")
            return None

        data = response.json().get("data", {}).get("orders", {})
        new_orders = data.get("edges", [])
        has_next_page = data.get("pageInfo", {}).get("hasNextPage", False)
        after_cursor = new_orders[-1]["cursor"] if has_next_page else None
        total_orders += len(new_orders)

    return total_orders