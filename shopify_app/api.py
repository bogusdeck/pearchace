import asyncio
import aiohttp
import json
import shopify
from django.apps import apps
from .models import Client

# Utility function to create headers for Shopify GraphQL requests
def _get_shopify_headers(access_token):
    return {
        "Content-Type": "application/json",
        "X-Shopify-Access-Token": access_token
    }

# Async function to fetch collections
async def fetch_collections(shop_url):
    """
    Fetches all collections from a Shopify store using the GraphQL API.
    
    Args:
        shop_url (str): The URL of the Shopify store.
        
    Returns:
        list: A list of collections or an empty list if an error occurs.
    """
    client = await _get_client(shop_url)
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
    
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json={"query": query}, headers=headers) as response:
            if response.status == 200:
                data = await response.json()
                collections = data.get("data", {}).get("collections", {}).get("edges", [])
                return [collection['node'] for collection in collections]
            else:
                # Log error or handle it accordingly
                print(f"Error fetching collections: {response.status} - {await response.text()}")
                return []

# Async function to fetch products of a specific collection
async def fetch_products_by_collection(shop_url, collection_id):
    """
    Fetches all products from a specific collection in a Shopify store using the GraphQL API.
    
    Args:
        shop_url (str): The URL of the Shopify store.
        collection_id (str): The ID of the collection to fetch products from.
        
    Returns:
        list: A list of products or an empty list if an error occurs.
    """
    client = await _get_client(shop_url)
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

    async with aiohttp.ClientSession() as session:
        async with session.post(url, json={"query": query}, headers=headers) as response:
            if response.status == 200:
                data = await response.json()
                products = data.get("data", {}).get("collection", {}).get("products", {}).get("edges", [])
                return [product['node'] for product in products]
            else:
                print(f"Error fetching products: {response.status} - {await response.text()}")
                return []

async def _get_client(shop_url):
    """
    Fetches the Client instance for a specific shop URL.

    Args:
        shop_url (str): The URL of the Shopify store.

    Returns:
        Client: The Client instance or None if not found.
    """
    try:
        return await asyncio.to_thread(Client.objects.get, shop_name=shop_url)
    except Client.DoesNotExist:
        print(f"Client with shop URL {shop_url} does not exist.")
        return None


async def update_collection_products_order(shop_url, collection_id, products_order):
    """
    Updates the display order of products in a specific collection in a Shopify store using the GraphQL API.

    Args:
        shop_url (str): The URL of the Shopify store.
        collection_id (str): The ID of the collection to update.
        products_order (list): A list of product IDs in the desired display order.

    Returns:
        bool: True if the update was successful, False otherwise.
    """
    client = await _get_client(shop_url)
    if not client:
        return False

    access_token = client.access_token
    api_version = apps.get_app_config('shopify_app').SHOPIFY_API_VERSION
    headers = _get_shopify_headers(access_token)

    # Shopify GraphQL endpoint
    url = f"https://{shop_url}/admin/api/{api_version}/graphql.json"

    # Build the moves part of the mutation
    moves_list = [
        f'{{id: "gid://shopify/Product/{product_id}", newPosition: {index}}}'
        for index, product_id in enumerate(products_order)
    ]
    moves_str = ", ".join(moves_list)

    # Complete GraphQL mutation
    mutation = f"""
    mutation {{
      collectionReorderProducts(
        id: "gid://shopify/Collection/{collection_id}",
        moves: [{moves_str}]
      ) {{
        job {{
          id
          status
        }}
        userErrors {{
          field
          message
        }}
      }}
    }}
    """

    async with aiohttp.ClientSession() as session:
        async with session.post(url, json={"query": mutation}, headers=headers) as response:
            if response.status == 200:
                data = await response.json()
                errors = data.get("data", {}).get("collectionReorderProducts", {}).get("userErrors", [])
                if errors:
                    print(f"Errors encountered: {errors}")
                    return False
                return True
            else:
                print(f"Error updating products order: {response.status} - {await response.text()}")
                return False

# async def fetch_client_data(shop_url):
#     """
#     Fetches the client's shop data from Shopify using the GraphQL API, including currency code and contact email.

#     Args:
#         shop_url (str): The URL of the Shopify store.

#     Returns:
#         dict: A dictionary containing the client's shop data or an empty dictionary if an error occurs.
#     """
#     client = await _get_client(shop_url)
#     if not client:
#         return {}

#     access_token = client.access_token
#     api_version = apps.get_app_config('shopify_app').SHOPIFY_API_VERSION
#     headers = _get_shopify_headers(access_token)

#     url = f"https://{shop_url}/admin/api/{api_version}/graphql.json"

#     query = """
#     {
#       shop {
#         id
#         name
#         email
#         primaryDomain {
#           url
#           host
#         }
#         myshopifyDomain
#         plan {
#           displayName
#         }
#         createdAt
#         timezoneAbbreviation
#         currencyCode
#         contactEmail: email
#         billingAddress {
#           address1
#           address2
#           city
#           province
#           countryCodeV2
#           phone
#           zip
#         }
#       }
#     }
#     """
    
#     async with aiohttp.ClientSession() as session:
#         async with session.post(url, json={"query": query}, headers=headers) as response:
#             if response.status == 200:
#                 data = await response.json()
#                 print(data)
#                 shop_data = data.get("data", {}).get("shop", {})
#                 return shop_data
#             else:
#                 print(f"Error fetching shop data: {response.status} - {await response.text()}")
#                 return {}



async def fetch_client_data(shop_url):
    """
    Fetches the client's shop data from Shopify using the GraphQL API, including currency code and contact email,
    and returns a flattened dictionary of the shop's details.

    Args:
        shop_url (str): The URL of the Shopify store.

    Returns:
        dict: A flattened dictionary containing the client's shop data or an empty dictionary if an error occurs.
    """
    client = await _get_client(shop_url)
    if not client:
        return {}

    access_token = client.access_token
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
    
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json={"query": query}, headers=headers) as response:
            if response.status == 200:
                data = await response.json()
                shop_data = data.get("data", {}).get("shop", {})
                
                flattened_data = {
                    "id": shop_data.get("id"),
                    "name": shop_data.get("name"),
                    "email": shop_data.get("email"),
                    "primary_domain_url": shop_data.get("primaryDomain", {}).get("url"),
                    "primary_domain_host": shop_data.get("primaryDomain", {}).get("host"),
                    "myshopify_domain": shop_data.get("myshopifyDomain"),
                    "plan": shop_data.get("plan", {}).get("displayName"),
                    "created_at": shop_data.get("createdAt"),
                    "timezone_abbreviation": shop_data.get("timezoneAbbreviation"),
                    "currency_code": shop_data.get("currencyCode"),
                    "contact_email": shop_data.get("contactEmail"),
                    "billing_address1": shop_data.get("billingAddress", {}).get("address1"),
                    "billing_address2": shop_data.get("billingAddress", {}).get("address2"),
                    "billing_city": shop_data.get("billingAddress", {}).get("city"),
                    "billing_province": shop_data.get("billingAddress", {}).get("province"),
                    "billing_country": shop_data.get("billingAddress", {}).get("countryCodeV2"),
                    "billing_phone": shop_data.get("billingAddress", {}).get("phone"),
                    "billing_zip": shop_data.get("billingAddress", {}).get("zip"),
                }
                
                return flattened_data
            else:
                print(f"Error fetching shop data: {response.status} - {await response.text()}")
                return {}
