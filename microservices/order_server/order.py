from flask import Flask, jsonify, request
import csv
import requests
import os
from datetime import datetime
import threading

app = Flask(__name__)

CATALOG_SERVER_URL = os.environ.get('CATALOG_SERVER_URL', 'http://localhost:5000')
REPLICA_SERVER_URL = os.environ.get('REPLICA_SERVER_URL', 'http://localhost:5004')

# Threading and shared resources
lock = threading.Lock()

# Retrieve catalog information from the catalog server
def get_catalog():
    try:
        url = f'{CATALOG_SERVER_URL}/catalog'
        response = requests.get(url)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error connecting to catalog server: {e}")
        print(f"URL: {url}")
        return None

# Notify the catalog server about the purchase and update stock quantity
def notify_catalog_server(item_number):
    try:
        catalog = get_catalog()

        if catalog is None:
            return jsonify({'error': 'Error retrieving catalog information'})

        for book in catalog:
            if str(book['ID']) == item_number:
                current_quantity = int(book.get('Quantity', 0))
                if current_quantity > 0:
                    update_response = requests.put(f'{CATALOG_SERVER_URL}/update/{item_number}', json={'quantity': current_quantity - 1})

                    if update_response.status_code == 200:
                        print(f"Catalog server updated successfully: {update_response.json()['message']}")
                    else:
                        print(f"Error updating catalog server: {update_response.json()['error']}")
                    return jsonify({'message': f'Book {book.get("Title", "Unknown Title")} purchased successfully'})

                else:
                    return jsonify({'error': 'Book out of stock'})

        return jsonify({'error': 'Book not found'}), 404

    except requests.exceptions.RequestException as e:
        print(f"Error connecting to catalog server: {e}")
        return jsonify({'error': f'Error connecting to catalog server: {e}'}), 500

# Verify if the book with a given ID is in stock
def verify_stock(item_id):
    try:
        url = f'{CATALOG_SERVER_URL}/verify/{item_id}'
        response = requests.post(url)
        response.raise_for_status()
        result = response.json()

        if 'message' in result and result['message'] == 'Book is in stock':
            return True
        else:
            return False

    except requests.exceptions.RequestException as e:
        print(f"Error verifying stock with catalog server: {e}")
        print(f"URL: {url}")
        return False

# Invalidate the cache in the frontend server for the given item number
def invalidate_frontend_cache(item_number):
    try:
        frontend_url = 'http://localhost:5002'
        response = requests.post(f'{frontend_url}/invalidate_cache/{item_number}')
        response.raise_for_status()
        print(f'Cache invalidated successfully in the frontend server for item {item_number}')
    except requests.exceptions.RequestException as e:
        print(f"Error invalidating cache in the frontend server: {e}")

# Update the 'order.csv' file with the given orders
def update_orders_csv(orders, filename='order.csv'):
    with open(filename, 'w', newline='') as csvfile:
        fieldnames = list(orders[0].keys()) if orders else ['item_number', 'timestamp']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(orders)

# Notify the other replica about the purchase and update the order file
def notify_other_replica(item_number, filename='order_replica.csv'):
    try:
        with lock:
            orders = []
            if os.path.exists(filename):
                with open(filename, 'r') as csvfile:
                    reader = csv.DictReader(csvfile)
                    for row in reader:
                        orders.append(row)

            catalog = get_catalog()
            if catalog is None:
                return jsonify({'error': 'Error retrieving catalog information'})

            for book in catalog:
                if str(book['ID']) == item_number:
                    orders.append({'item_number': item_number, 'timestamp': datetime.utcnow().isoformat()})
                    update_orders_csv(orders, filename)

                    other_replica_url = f'{REPLICA_SERVER_URL}/notify_purchase/{item_number}'
                    response = requests.post(other_replica_url)
                    response.raise_for_status()

                    return jsonify({'message': f'Book {book.get("Title", "Unknown Title")} purchased successfully'})

        return jsonify({'error': 'Book not found in the catalog'})

    except Exception as e:
        return jsonify({'error': f'Error notifying other replica: {e}'}), 500

# Purchase a book and update relevant files
@app.route('/purchase/<item_number>', methods=['POST'])
def purchase_book(item_number):
    if not verify_stock(item_number):
        return jsonify({'error': 'Book out of stock'})

    orders_csv_file = 'order.csv'
    orders = []

    if os.path.exists(orders_csv_file):
        with open(orders_csv_file, 'r') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                orders.append(row)

    catalog = get_catalog()
    if catalog is None:
        return jsonify({'error': 'Error retrieving catalog information'})

    for book in catalog:
        if str(book['ID']) == item_number:
            orders.append({'item_number': item_number, 'timestamp': datetime.utcnow().isoformat()})
            update_orders_csv(orders)
            notify_other_replica(item_number, 'order_replica.csv')
            invalidate_frontend_cache(item_number)
            notify_catalog_server(item_number)

            return jsonify({'message': f'Book {book.get("Title", "Unknown Title")} purchased successfully'})

    return jsonify({'error': 'Book not found in the catalog'})


if __name__ == '__main__':
    replica_server_id = 1
    replica_server_port = 5001
    print(f'Replica {replica_server_id} on Port {replica_server_port}: Order Server Running')
    app.run(host='0.0.0.0', port=replica_server_port, debug=True)
