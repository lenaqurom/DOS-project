import csv
from flask import Flask, jsonify, request
import requests
from multiprocessing import Process
import sys

app = Flask(__name__)

# Load catalog data from a CSV file
catalog = []
cache = {}

# Load catalog data from the 'catalog_replica.csv' file
def load_catalog():
    global catalog
    with open('catalog_replica.csv', 'r') as csvfile:
        reader = csv.DictReader(csvfile)
        catalog = list(reader)
        return catalog
# Save catalog data to the 'catalog_replica.csv' file
def save_catalog(local_catalog):
    with open('catalog_replica.csv', 'w', newline='') as csvfile:
        fieldnames = ['ID', 'Title', 'Quantity', 'Price', 'Topic']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(local_catalog)

    print(f"Replica {replica_server_id} on Port {replica_server_port}: Catalog saved successfully to 'catalog_replica.csv'")
    print(f"Replica {replica_server_id} on Port {replica_server_port}: Catalog content after saving: {local_catalog}")

load_catalog()

def invalidate_frontend_cache(item_number):
    try:
        frontend_url = 'http://localhost:5002'  # Update with the actual URL of your frontend server
        response = requests.post(f'{frontend_url}/invalidate_cache/{item_number}')
        response.raise_for_status()
        print(f'Cache invalidated successfully in the frontend server for item {item_number}')
    except requests.exceptions.RequestException as e:
        print(f"Error invalidating cache in the frontend server: {e}")

# Notify other replicas about the update for a specific book
def notify_replicas_update(item_number, old_quantity, old_price):
    for port in [5000, 5003]:  # Update the list with ports of all replicas
        if port != replica_server_port:
            try:
                data = {'quantity': request.json.get('quantity', old_quantity),
                        'price': request.json.get('price', old_price)}
                requests.put(f'http://localhost:{port}/update_replica/{item_number}', json=data, timeout=1)
            except requests.exceptions.RequestException as e:
                print(f"Error notifying replica on port {port}: {e}")

def notify_replicas():
    for port in [5000, 5003]:  # Update the list with ports of all replicas
        if port != replica_server_port:
            try:
                requests.post(f'http://localhost:{port}/notify', timeout=1)
            except requests.exceptions.RequestException as e:
                print(f"Error notifying replica on port {port}: {e}")

# Replica server information
replica_server_id = int(sys.argv[2]) if len(sys.argv) > 2 else 1
replica_server_port = int(sys.argv[1]) if len(sys.argv) > 1 else 5000

# Search for items in the catalog based on the provided item name (topic)
@app.route('/search/<item_name>', methods=['GET'])
def search_items(item_name):
    if item_name in cache:
        print(f'Replica {replica_server_id} on Port {replica_server_port}: Catalog Search Cache Hit! Item Name: {item_name}, Cache Capacity: {len(cache)}/100')
        return jsonify(cache[item_name])

    results = []
    for book_id, book in enumerate(catalog, start=1):
        if item_name.lower() in book.get('Topic', '').lower():
            results.append({
                'id': book['ID'],
                'title': book['Title']
            })

    # Update the cache
    if len(cache) >= 100:
        cache.popitem(last=False)  # Remove the least recently used item

    cache[item_name] = results
    print(f'Replica {replica_server_id} on Port {replica_server_port}: Catalog Search Cache Miss! Item Name: {item_name}, Cache Capacity: {len(cache)}/100')
    return jsonify(results)

# Retrieve information about a book based on the provided item number
@app.route('/info/<item_number>', methods=['GET'])
def book_info(item_number):
    if item_number in cache:
        print(f'Replica {replica_server_id} on Port {replica_server_port}: Catalog Info Cache Hit! Item Number: {item_number}, Cache Capacity: {len(cache)}/100')
        return jsonify(cache[item_number])

    for book_id, book in enumerate(catalog, start=1):
        if str(book_id) == item_number:
            result = {
                'title': book['Title'],
                'quantity': int(book['Quantity']),
                'price': float(book['Price'])
            }
            # Update the cache
            if len(cache) >= 100:
                cache.popitem(last=False)  # Remove the least recently used item

            cache[item_number] = result
            print(f'Replica {replica_server_id} on Port {replica_server_port}: Catalog Info Cache Miss! Item Number: {item_number}, Cache Capacity: {len(cache)}/100')
            return jsonify(result)

    return jsonify({'error': 'Book not found'})

# Add a new route to handle updates from the main catalog
@app.route('/update/<item_number>', methods=['PUT'])
def update_book(item_number):
    data = request.get_json()

    # This is a regular update request
    local_catalog = load_catalog()

    for book_id, book in enumerate(local_catalog, start=1):
        if str(book_id) == item_number:
            # Save the current values for reference
            old_quantity = book['Quantity']
            old_price = book['Price']

            # Update the book details
            if 'quantity' in data:
                new_quantity = data.get('quantity')
                book['Quantity'] = str(new_quantity)
            if 'price' in data:
                new_price = data.get('price')
                book['Price'] = str(new_price)

            print(f"Replica {replica_server_id} on Port {replica_server_port}: Updated catalog content: {local_catalog}")

            # Update the CSV file
            save_catalog(local_catalog)
            invalidate_frontend_cache(item_number)
            # If it's not a notification, notify other replicas
            if not data.get('is_notification', False):
                notify_replicas_update(item_number, old_quantity, old_price)

            # Update the cache
            cache.clear()

            print(f"Replica {replica_server_id} on Port {replica_server_port}: Catalog saved successfully to 'catalog_replica.csv'")
            print(f"Replica {replica_server_id} on Port {replica_server_port}: Catalog content after saving: {local_catalog}")

            print(f'Replica {replica_server_id} on Port {replica_server_port}: Book updated successfully (Replica)')
            return jsonify({'message': 'Book updated successfully (Replica)'})

    return jsonify({'error': 'Book not found'}), 404


@app.route('/update/<item_number>', methods=['PUT'])
def update_replica_book(item_number):
    data = request.get_json()

    # This is a regular update request
    local_catalog = load_catalog()

    for book_id, book in enumerate(local_catalog, start=1):
        if str(book_id) == item_number:
            # Save the current values for reference
            old_quantity = book['Quantity']
            old_price = book['Price']

            # Update the book details
            if 'quantity' in data:
                new_quantity = data.get('quantity')
                book['Quantity'] = str(new_quantity)
            if 'price' in data:
                new_price = data.get('price')
                book['Price'] = str(new_price)

            print(f"Replica {replica_server_id} on Port {replica_server_port}: Updated catalog content: {local_catalog}")

            # Update the CSV file
            save_catalog(local_catalog)

            if not data.get('is_notification', False):
                # If it's not a notification, notify other replicas
                notify_replicas_update(item_number, old_quantity, old_price)

            # Update the cache
            cache.clear()

            print(f"Replica {replica_server_id} on Port {replica_server_port}: Catalog saved successfully to 'catalog_replica.csv'")
            print(f"Replica {replica_server_id} on Port {replica_server_port}: Catalog content after saving: {local_catalog}")

            print(f'Replica {replica_server_id} on Port {replica_server_port}: Book updated successfully (Replica)')
            return jsonify({'message': 'Book updated successfully (Replica)'})

    return jsonify({'error': 'Book not found'}), 404

@app.route('/update_replica/<item_number>', methods=['PUT'])
def update_replica_book2(item_number):
    data = request.get_json()

    # This is a regular update request
    local_catalog = load_catalog()

    for book_id, book in enumerate(local_catalog, start=1):
        if str(book_id) == item_number:
            # Save the current values for reference
            old_quantity = book['Quantity']
            old_price = book['Price']

            # Update the book details
            if 'quantity' in data:
                new_quantity = data.get('quantity')
                book['Quantity'] = str(new_quantity)
            if 'price' in data:
                new_price = data.get('price')
                book['Price'] = str(new_price)

            print(f"Replica {replica_server_id} on Port {replica_server_port}: Updated catalog content: {local_catalog}")

            # Update the CSV file
            save_catalog(local_catalog)

            if not data.get('is_notification', False):
                # If it's not a notification, notify other replicas
                notify_replicas_update(item_number, old_quantity, old_price)

            # Update the cache
            cache.clear()

            print(f"Replica {replica_server_id} on Port {replica_server_port}: Catalog saved successfully to 'catalog_replica.csv'")
            print(f"Replica {replica_server_id} on Port {replica_server_port}: Catalog content after saving: {local_catalog}")

            print(f'Replica {replica_server_id} on Port {replica_server_port}: Book updated successfully (Replica)')
            return jsonify({'message': 'Book updated successfully (Replica)'})

    return jsonify({'error': 'Book not found'}), 404


# Retrieve the entire catalog
@app.route('/catalog', methods=['GET'])
def get_catalog():
    return jsonify(catalog)

# Notify about catalog updates and reload catalog data from the CSV file
@app.route('/notify', methods=['POST'])
def notify_update():
    data = request.get_json()

    if 'message' in data and data['message'] == 'update':
        item_number = data.get('item_number')
        sender = data.get('sender')
        print(f'Received update notification for item {item_number} from replica on port {sender}')
        
        # Load the catalog from the 'catalog_replica.csv' file
        load_catalog()
        
        # Update the cache
        cache.clear()
        
        # Save the updated catalog to the 'catalog_replica.csv' file
        save_catalog()
        
        print(f'Replica {replica_server_id} on Port {replica_server_port}: Catalog updated successfully (Replica) for item {item_number}')
        return jsonify({'message': 'Catalog updated successfully (Replica)'})

    return jsonify({'error': 'Invalid notification'}), 400

# Verify if a book with a given ID is in stock
@app.route('/verify/<item_id>', methods=['POST'])
def verify_stock(item_id):
    for book_id, book in enumerate(catalog, start=1):
        if str(book_id) == item_id:
            current_quantity = int(book.get('Quantity', 0))

            if current_quantity > 0:
                return jsonify({'message': 'Book is in stock'})
            else:
                return jsonify({'error': 'Book out of stock'})

    return jsonify({'error': 'Book not found'}), 404

def run_app(port):
    app.run(host='0.0.0.0', port=port, debug=True)

if __name__ == '__main__':
    replica_server_id = 2
    replica_server_port = 5003  # Port for the second replica
    print(f'Replica {replica_server_id} on Port {replica_server_port}: Catalog Server Running on Port {replica_server_port}')
    app.run(host='0.0.0.0', port=replica_server_port, debug=True)
