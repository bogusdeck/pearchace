import requests
import json
import shopify
from django.apps import apps
from .models import Client
from datetime import datetime
import pytz

def _get_shopify_headers(access_token):
    return {
        "Content-Type": "application/json",
        "X-Shopify-Access-Token": access_token
    }

def fetch_collections(shop_url):
    """
    Fetches all collections from a Shopify store using the GraphQL API.
    
    Args:
        shop_url (str): The URL of the Shopify store.
        
    Returns:
        list: A list of collections or an empty list if an error occurs.
    """
    client = _get_client(shop_url)
    if not client:
        return []

    access_token = client.access_token
    api_version = apps.get_app_config('shopify_app').SHOPIFY_API_VERSION
    headers = _get_shopify_headers(access_token)
    
    url = f"https://{shop_url}/admin/api/{api_version}/graphql.json"

    query = """
    {
      collections(first: 250) {
        edges {
          node {
            id
            title
            handle
          }
        }
      }
    }
    """
    
    response = requests.post(url, json={"query": query}, headers=headers)
    if response.status_code == 200:
        data = response.json()
        collections = data.get("data", {}).get("collections", {}).get("edges", [])
        return [collection['node'] for collection in collections]
    else:
        print(f"Error fetching collections: {response.status_code} - {response.text}")
        return []

def fetch_products_by_collection(shop_url, collection_id):
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
    api_version = apps.get_app_config('shopify_app').SHOPIFY_API_VERSION
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
            }}
          }}
        }}
      }}
    }}
    """

    response = requests.post(url, json={"query": query}, headers=headers)
    if response.status_code == 200:
        data = response.json()
        products = data.get("data", {}).get("collection", {}).get("products", {}).get("edges", [])
        return [product['node'] for product in products]
    else:
        print(f"Error fetching products: {response.status_code} - {response.text}")
        return []

def _get_client(shop_url):
    """
    Fetches the Client instance for a specific shop URL.

    Args:
        shop_url (str): The URL of the Shopify store.

    Returns:
        Client: The Client instance or None if not found.
    """
    try:
        return Client.objects.get(shop_name=shop_url)
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
    api_version = apps.get_app_config('shopify_app').SHOPIFY_API_VERSION
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
def update_collection_products_order(shop_url, access_token, collection_id, sorted_product_ids):
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
        api_version = apps.get_app_config('shopify_app').SHOPIFY_API_VERSION
        headers = _get_shopify_headers(access_token)
        url = f"https://{shop_url}/admin/api/{api_version}/graphql.json"

        # Convert collection_id to global ID
        collection_global_id = f"gid://shopify/Collection/{collection_id}"

        # GraphQL mutation for updating collection order
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

        # Prepare variables
        moves = [
            {
                "id": product_id,
                "newPosition": str(position)  # Position should be a string
            }
            for position, product_id in enumerate(sorted_product_ids)
        ]

        variables = {
            "id": collection_global_id,  # Pass the global collection ID here
            "moves": moves
        }

        response = requests.post(url, json={"query": mutation, "variables": variables}, headers=headers)
        if response.status_code == 200:
            result = response.json()
            errors = result.get('data', {}).get('collectionReorderProducts', {}).get('userErrors', [])
            if not errors:
                return True
            else:
                print(f"User errors: {errors}")
        else:
            print(f"Failed to reorder products: {response.status_code} - {response.text}")
        return False

    except Exception as e:
        print(f"Exception during product order update: {str(e)}")
        return False
