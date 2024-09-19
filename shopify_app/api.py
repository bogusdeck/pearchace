import requests
import json
import shopify
from django.apps import apps
from .models import Client
from datetime import datetime
import pytz
from django.utils import timezone
from datetime import datetime, timedelta


def _get_shopify_headers(access_token):
    return {"Content-Type": "application/json", "X-Shopify-Access-Token": access_token}


def fetch_collections(shop_url):
    """
    Fetches all collections from a Shopify store using the GraphQL API.

    Args:
        shop_url (str): The URL of the Shopify store.

    Returns:
        list: A list of collections with id, title, and products_count.
    """
    client = _get_client(shop_url)
    if not client:
        return []

    access_token = client.access_token
    api_version = apps.get_app_config("shopify_app").SHOPIFY_API_VERSION
    headers = _get_shopify_headers(access_token)

    url = f"https://{shop_url}/admin/api/{api_version}/graphql.json"

    query = """
    {
      collections(first: 250) {
        edges {
          node {
            id
            title
            productsCount {
              count
              precision
            }
          }
        }
      }
    }
    """

    response = requests.post(url, json={"query": query}, headers=headers)
    if response.status_code == 200:
        data = response.json()
        collections = data.get("data", {}).get("collections", {}).get("edges", [])
        return [
            {
                "id": collection["node"]["id"],
                "title": collection["node"]["title"],
                "products_count": collection["node"]["productsCount"]["count"],
            }
            for collection in collections
        ]
    else:
        print(f"Error fetching collections: {response.status_code} - {response.text}")
        return []


# def fetch_products_by_collection(shop_url, collection_id):
#     """
#     Fetches all products from a specific collection in a Shopify store using the GraphQL API.

#     Args:
#         shop_url (str): The URL of the Shopify store.
#         collection_id (str): The ID of the collection to fetch products from.

#     Returns:
#         list: A list of products or an empty list if an error occurs.
#     """
#     client = _get_client(shop_url)
#     if not client:
#         return []

#     access_token = client.access_token
#     api_version = apps.get_app_config('shopify_app').SHOPIFY_API_VERSION
#     headers = _get_shopify_headers(access_token)

#     url = f"https://{shop_url}/admin/api/{api_version}/graphql.json"

#     query = f"""
#     {{
#       collection(id: "gid://shopify/Collection/{collection_id}") {{
#         products(first: 250) {{
#           edges {{
#             node {{
#               id
#               title
#               handle
#             }}
#           }}
#         }}
#       }}
#     }}
#     """

#     response = requests.post(url, json={"query": query}, headers=headers)
#     if response.status_code == 200:
#         data = response.json()
#         products = data.get("data", {}).get("collection", {}).get("products", {}).get("edges", [])
#         return [product['node'] for product in products]
#     else:
#         print(f"Error fetching products: {response.status_code} - {response.text}")
#         return []


def fetch_products_by_collection_with_img(shop_url, collection_id):
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
              handle
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
                "handle": product["node"]["handle"],
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


def fetch_products_by_collection(shop_url, collection_id, days):
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
              handle
              totalInventory
              publishedAt
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
              createdAt 
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

        if not products:
            print("No products found in the collection.")
            return []

        return [
            {
                "id": product["node"]["id"].split("/")[-1],  
                "title": product["node"]["title"],
                "handle": product["node"]["handle"],
                "totalInventory":product["node"]["totalInventory"],
                # "publishedAt":product["node"]["publishedAt"],
                "listed_date": product["node"]["createdAt"],  
                "revenue": calculate_revenue(shop_url, product["node"]["id"], days, headers),  
                "variants_count": product["node"]["variantsCount"]["count"],
                # "variant_availability": sum(variant["node"]["inventoryQuantity"] for variant in product["node"]["variants"]["edges"]), 
                # "variants_precision": product["node"]["variantsCount"]["count"],  
            }
            for product in products
        ]
    else:
        print(f"Error fetching products: {response.status_code} - {response.text}")
        return []

def calculate_revenue(shop_url, product_id, days, headers):
    """
    Fetches the total revenue generated by sales of the product (based on order data)
    over the specified number of days.
    """
    # Define the GraphQL query to fetch orders for the given product
    api_version = apps.get_app_config("shopify_app").SHOPIFY_API_VERSION

    query = f"""
    {{
      orders(first: 250, query: "created_at:>={days} days ago") {{
        edges {{
          node {{
            lineItems(first: 100) {{
              edges {{
                node {{
                  productId
                  variantId
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
      }}
    }}
    """
    
    url = f"https://{shop_url}/admin/api/{api_version}/graphql.json"
    response = requests.post(url, json={"query": query}, headers=headers)

    if response.status_code != 200:
        print(f"Error fetching orders: {response.status_code} - {response.text}")
        return 0

    orders_data = response.json().get("data", {}).get("orders", {}).get("edges", [])

    total_revenue = 0

    for order in orders_data:
        line_items = order["node"]["lineItems"]["edges"]

        for item in line_items:
            if item["node"]["productId"] == f"gid://shopify/Product/{product_id}":
                price = float(item["node"]["originalUnitPriceSet"]["shopMoney"]["amount"])
                quantity = int(item["node"]["quantity"])
                total_revenue += price * quantity

    return total_revenue


# def calculate_revenue(variants):
#     """
#     Calculate total revenue for the product based on its variants.
#     Args:
#         variants (list): List of product variants.
#     Returns:
#         float: Total revenue for the product.
#     """
#     total_revenue = 0
#     for variant in variants:
#         if variant["inventoryQuantity"] > 0:
#             total_revenue += float(variant["price"]) * variant["inventoryQuantity"]
    
#     print("revenue calculate done")
#     return total_revenue

 # "sales_velocity": calculate_sales_velocity(shop_url, product["node"]["id"], days) ,  
def calculate_sales_velocity(shop_url, product_id, days):
    """
    Calculate the product's sales velocity based on total sold units over a specified number of days using Shopify's GraphQL API.
    
    Args:
        shop_url (str): The URL of the Shopify store.
        product_id (str): The ID of the product (in the format gid://shopify/Product/{product_id}).
        days (int): The number of days to calculate sales velocity for.
    
    Returns:
        float: Average sales velocity per day for the product.
    """
    if days <= 0:
        return 0

    end_date = timezone.now()
    start_date = end_date - timedelta(days=days)

    client = _get_client(shop_url)
    if not client:
        return 0

    access_token = client.access_token
    api_version = apps.get_app_config("shopify_app").SHOPIFY_API_VERSION
    headers = _get_shopify_headers(access_token)
    print(access_token)

    url = f"https://{shop_url}/admin/api/{api_version}/graphql.json"

    start_date_iso = start_date.isoformat()
    end_date_iso = end_date.isoformat()

    query = f"""
    {{
      orders(first: 250, query: "created_at:>{start_date_iso} AND created_at:<{end_date_iso}") {{
        edges {{
          node {{
            lineItems(first: 250) {{
              edges {{
                node {{
                  product {{
                    id  
                  }}
                  quantity
                }}
              }}
            }}
          }}
        }}
      }}
    }}
    """

    # query = """
    # {
    #   orders(first: 1) {
    #       edges {
    #         node {
    #           id
    #           lineItems(first: 1) {
    #             edges {
    #               node {
    #                 title
    #                 quantity
    #               }
    #             }
    #           }
    #         }
    #       }
    #     }
    #   }
    # """

    response = requests.post(url, json={"query": query}, headers=headers)

    print(response.json())

    if response.status_code == 200:
        data = response.json()
        orders = data.get("data", {}).get("orders", {}).get("edges", [])

        total_sold_units = 0

        for order in orders:
            for line_item in order["node"]["lineItems"]["edges"]:
                if line_item["node"]["product"]["id"] == f"gid://shopify/Product/{product_id}":
                    total_sold_units += int(line_item["node"]["quantity"])

        sales_velocity = total_sold_units / days if days > 0 else 0
        print('sales_velocity done')
        return sales_velocity
    else:
        print(f"Error fetching orders: {response.status_code} - {response.text}")
        return 0


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


# def update_collection_products_order(shop_url, collection_id, sorted_product_ids, access_token):
#     """
#     Updates the product order of a collection in Shopify.

#     Args:
#         shop_url (str): The Shopify store URL.  
#         collection_id (str): The ID of the collection to update.
#         sorted_product_ids (list): A list of product IDs in the desired order.

#     Returns:
#         bool: True if the update is successful, False otherwise.
#     """
#     try:
#         api_version = apps.get_app_config('shopify_app').SHOPIFY_API_VERSION
#         # access_token = request.session.get('shopify', {}).get('access_token')
#         headers = _get_shopify_headers(access_token)
#         url = f"https://{shop_url}/admin/api/{api_version}/graphql.json"

#         # GraphQL mutation for updating collection order
#         mutation = """
#         mutation updateProductOrder($collectionId: ID!, $productIds: [ID!]!) {
#             collectionReorderProducts(collectionId: $collectionId, moves: {
#                 newPosition: 1,
#                 productId: $productIds
#             }) {
#                 userErrors {
#                     field
#                     message
#                 }
#             }
#         }
#         """

#         variables = {
#             "collectionId": f"gid://shopify/Collection/{collection_id}",
#             "productIds": [f"gid://shopify/Product/{pid}" for pid in sorted_product_ids]
#         }

#         response = requests.post(url, json={"query": mutation, "variables": variables}, headers=headers)
#         if response.status_code == 200:
#             result = response.json()
#             print(f"Response JSON: {result}")
#             errors = result.get('data', {}).get('collectionReorderProducts', {}).get('userErrors', [])
#             if not errors:
#                 return True
#             else:
#                 print(f"User errors: {errors}")
#         else:
#             print(f"Failed to reorder products: {response.status_code} - {response.text}")
#         return False


#     except Exception as e:
#         print(f"Exception during product order update: {str(e)}")
#         return False
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
                  "id": product_id,
                  "newPosition": str(position),  
              }
              for position, product_id in enumerate(sorted_product_ids)
          ]

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
