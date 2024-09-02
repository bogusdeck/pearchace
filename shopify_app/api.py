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
