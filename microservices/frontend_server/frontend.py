from flask import Flask, jsonify, request
import requests
from collections import OrderedDict
import time  

app = Flask(__name__)

# Define URLs for catalog and order servers
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

# Get the next catalog server URL using round-robin.
def get_next_catalog_server():
    global catalog_index
    catalog_index = (catalog_index + 1) % len(CATALOG_SERVER_URLS)
    return CATALOG_SERVER_URLS[catalog_index]

# Get the next order server URL using round-robin.
def get_next_order_server():
    global order_index
    order_index = (order_index + 1) % len(ORDER_SERVER_URLS)
    return ORDER_SERVER_URLS[order_index]

# Measure time taken
def measure_time():
    return time.time()

# Invalidate cache for a specific item number.
@app.route('/invalidate_cache/<item_number>', methods=['POST'])
def invalidate_cache(item_number):
    global cache
    try:
        start_time = measure_time()  # Record the start time

        if item_number in cache:
            cache.pop(item_number)
            print(f'Cache invalidated successfully for item {item_number}')
            end_time = measure_time()  # Record the end time
            print(f'Time Taken for Cache Invalidation: {end_time - start_time:.5f} seconds')
            return jsonify({'message': f'Cache invalidated successfully for item {item_number}'})
        else:
            return jsonify({'error': f'Item {item_number} not found in cache'}), 404
    except Exception as e:
        print(f"Error during cache invalidation: {str(e)}")
        return jsonify({'error': f'Internal server error during cache invalidation: {str(e)}'}), 500

# Search for items and utilize caching.
@app.route('/search/<item_name>', methods=['GET'])
def search_items(item_name):
    """Search for items and utilize caching."""
    global cache_hits, cache_misses

    if item_name in cache:
        cache.move_to_end(item_name)
        cache_hits += 1
        print(f'Cache Hit! Item Name: {item_name}, Cache Capacity: {len(cache)}/{MAX_CACHE_SIZE}, Time Taken: 0.00000 seconds')
        return jsonify(cache[item_name])

    try:
        start_time = time.time()  # Record the start time
        catalog_server_url = get_next_catalog_server()
        print(f'Search endpoint. Using catalog server: {catalog_server_url}')

        response = requests.get(f'{catalog_server_url}/search/{item_name}')
        response.raise_for_status()

        result = response.json()

        if len(cache) >= MAX_CACHE_SIZE:
            # Clear the entire cache and start caching again
            cache.clear()

        cache[item_name] = result
        cache_misses += 1
        end_time = time.time()  # Record the end time
        print(f'Cache Miss! Item Name: {item_name}, Cache Capacity: {len(cache)}/{MAX_CACHE_SIZE}, Time Taken: {end_time - start_time:.5f} seconds')

        return jsonify(result)
    except requests.exceptions.RequestException as e:
        print(f"Error: {e}")
        return jsonify({'error': f'Catalog server error: {str(e)}'})

# Retrieve information about a book based on the provided item number.
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
        print(f'Cache Hit! Item Number: {item_number}, Cache Capacity: {len(cache)}/{MAX_CACHE_SIZE}, Time Taken: 0.00000 seconds')
        return cache[item_number]

    try:
        start_time = time.time()  # Record the start time
        for catalog_server_url in CATALOG_SERVER_URLS:
            response = requests.get(f'{catalog_server_url}/info/{item_number}')
            if response.status_code == 200:
                response.raise_for_status()
                result = response.json()

                # Cache the response and clear the entire cache if it reaches the maximum size
                if len(cache) >= MAX_CACHE_SIZE:
                    cache.clear()

                cache[item_number] = result
                cache_misses += 1
                end_time = time.time()  # Record the end time
                print(f'Cache Miss! Item Number: {item_number}, Cache Capacity: {len(cache)}/{MAX_CACHE_SIZE}, Time Taken: {end_time - start_time:.5f} seconds')

                return result
        return jsonify({'error': 'Book not found'})
    except requests.exceptions.RequestException as e:
        return jsonify({'error': f'Catalog server error: {str(e)}'})

# Purchase a book based on the provided item number.
@app.route('/purchase/<item_number>', methods=['POST'])
def purchase_book(item_number):

    # Load balancing for order servers
    order_server_url = get_next_order_server()
    print(f'Purchase endpoint. Using order server: {order_server_url}')

    try:
        start_time = time.time()  # Record the start time
        response = requests.post(f'{order_server_url}/purchase/{item_number}')
        response.raise_for_status()
        end_time = time.time()  # Record the end time

        print(f'Time Taken for Purchase: {end_time - start_time:.5f} seconds')

        return response.json()
    except requests.exceptions.RequestException as e:
        return jsonify({'error': f'Order server error: {str(e)}'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5002, debug=True)
