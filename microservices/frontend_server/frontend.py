from flask import Flask, jsonify, request
import requests
from collections import OrderedDict

app = Flask(__name__)

CATALOG_SERVER_URLS = ['http://localhost:5000', 'http://localhost:5003']
ORDER_SERVER_URLS = ['http://localhost:5001', 'http://localhost:5004']

# Limit the cache size
MAX_CACHE_SIZE = 100

# In-memory cache with LRU policy
cache = OrderedDict()

# Load balancing algorithm (round-robin)
catalog_index = 0
order_index = 0

# Track cache hits and misses
cache_hits = 0
cache_misses = 0

def get_next_catalog_server():
    global catalog_index
    catalog_index = (catalog_index + 1) % len(CATALOG_SERVER_URLS)
    return CATALOG_SERVER_URLS[catalog_index]

def get_next_order_server():
    global order_index
    order_index = (order_index + 1) % len(ORDER_SERVER_URLS)
    return ORDER_SERVER_URLS[order_index]

# Search for items in the catalog based on the provided topic
@app.route('/search/<item_name>', methods=['GET'])
# Inside the 'search_items' function
def search_items(item_name):
    global cache_hits, cache_misses

    if item_name in cache:
        cache.move_to_end(item_name)
        cache_hits += 1
        print(f'Cache Hit! Item Name: {item_name}, Cache Capacity: {len(cache)}/{MAX_CACHE_SIZE}')
        return jsonify(cache[item_name])

    try:
        catalog_server_url = get_next_catalog_server()
        print(f'Search endpoint. Using catalog server: {catalog_server_url}')

        response = requests.get(f'{catalog_server_url}/search/{item_name}')
        response.raise_for_status()

        result = response.json()

        if len(cache) >= MAX_CACHE_SIZE:
            cache.popitem(last=False)

        cache[item_name] = result
        cache_misses += 1
        print(f'Cache Miss! Item Name: {item_name}, Cache Capacity: {len(cache)}/{MAX_CACHE_SIZE}')

        print(f"Search Results: {result}")  # Add this line to print the results for debugging

        return jsonify(result)
    except requests.exceptions.RequestException as e:
        print(f"Error: {e}")
        return jsonify({'error': f'Catalog server error: {str(e)}'})
    
# Retrieve information about a book based on the provided item number
@app.route('/info/<item_number>', methods=['GET'])
def book_info(item_number):
    global cache_hits, cache_misses

    # Load balancing for catalog servers
    catalog_server_url = get_next_catalog_server()
    print(f'Book info endpoint. Using catalog server: {catalog_server_url}')

    if item_number in cache:
        # Move the accessed item to the end to mark it as most recently used
        cache.move_to_end(item_number)
        cache_hits += 1
        print(f'Cache Hit! Item Number: {item_number}, Cache Capacity: {len(cache)}/{MAX_CACHE_SIZE}')
        return cache[item_number]

    try:
        for catalog_server_url in CATALOG_SERVER_URLS:
            response = requests.get(f'{catalog_server_url}/info/{item_number}')
            if response.status_code == 200:
                response.raise_for_status()
                result = response.json()

                # Cache the response and remove the least recently used item if the cache is full
                if len(cache) >= MAX_CACHE_SIZE:
                    cache.popitem(last=False)  # Remove the least recently used item

                cache[item_number] = result
                cache_misses += 1
                print(f'Cache Miss! Item Number: {item_number}, Cache Capacity: {len(cache)}/{MAX_CACHE_SIZE}')

                return result
        return jsonify({'error': 'Book not found'})
    except requests.exceptions.RequestException as e:
        return jsonify({'error': f'Catalog server error: {str(e)}'})

# Purchase a book based on the provided item number
@app.route('/purchase/<item_number>', methods=['POST'])
def purchase_book(item_number):
    # Load balancing for order servers
    order_server_url = get_next_order_server()
    print(f'Purchase endpoint. Using order server: {order_server_url}')

    try:
        response = requests.post(f'{order_server_url}/purchase/{item_number}')
        response.raise_for_status()


        return response.json()
    except requests.exceptions.RequestException as e:
        return jsonify({'error': f'Order server error: {str(e)}'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5002, debug=True)
