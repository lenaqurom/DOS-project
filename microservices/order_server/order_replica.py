from flask import Flask, jsonify, request
import csv
import requests
import os
from datetime import datetime
import threading

app = Flask(__name__)

CATALOG_SERVER_URL = os.environ.get('CATALOG_SERVER_URL', 'http://localhost:5000')

# retrieve catalog information from the catalog server
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

# update the 'order_replica.csv' file with the given orders
def update_orders_csv(orders, filename='order_replica.csv'):
    with open(filename, 'w', newline='') as csvfile:
        fieldnames = list(orders[0].keys()) if orders else ['item_number', 'timestamp']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(orders)

# invalidate the cache in the frontend server for a specific item
def invalidate_frontend_cache(item_number):
    try:
        frontend_url = 'http://localhost:5002'  
        response = requests.post(f'{frontend_url}/invalidate_cache/{item_number}')
        response.raise_for_status()
        print(f'Cache invalidated successfully in the frontend server for item {item_number}')
    except requests.exceptions.RequestException as e:
        print(f"Error invalidating cache in the frontend server: {e}")

# notify the catalog server about a purchase
def notify_catalog_server(item_number):
    # Verify if the book is in stock
    if not verify_stock(item_number):
        return jsonify({'error': 'Book out of stock'})

    # Retrieve catalog information from the catalog server
    catalog = get_catalog()

    if catalog is None:
        return jsonify({'error': 'Error retrieving catalog information'})

    # Find the book with the specified item number
    for book in catalog:
        if str(book['ID']) == item_number:
            # Decrement the quantity in stock
            current_quantity = int(book.get('Quantity', 0))
            if current_quantity > 0:
                book['Quantity'] = str(current_quantity - 1)

                # Update the catalog server with the new quantity
                update_response = requests.put(f'{CATALOG_SERVER_URL}/update/{item_number}', json={'quantity': current_quantity - 1})

                if update_response.status_code == 200:
                    print(f"Catalog server updated successfully: {update_response.json()['message']}")
                else:
                    print(f"Error updating catalog server: {update_response.json()['error']}")

            else:
                return jsonify({'error': 'Book out of stock'})

    return jsonify({'error': 'Book not found'}), 404

# verify if the book with a given ID is in stock
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

# handle purchase notifications
@app.route('/notify_purchase/<item_number>', methods=['POST'])
def notify_purchase(item_number):
    try:
        orders = []
        filename = 'order_replica.csv'
        if os.path.exists(filename):
            with open(filename, 'r') as csvfile:
                reader = csv.DictReader(csvfile)
                for row in reader:
                    orders.append(row)

        update_orders_csv(orders, filename)

        return jsonify({'message': f'Purchase notification received for item {item_number}'})

    except Exception as e:
        return jsonify({'error': f'Error processing purchase notification: {e}'}), 500

# handle book purchases and update relevant files
@app.route('/purchase/<item_number>', methods=['POST'])
def purchase_book(item_number):
    # Verify if the book is in stock
    if not verify_stock(item_number):
        return jsonify({'error': 'Book out of stock'})

    # Load order data from a CSV file
    orders_csv_file = 'order_replica.csv'
    orders = []

    if os.path.exists(orders_csv_file):
        with open(orders_csv_file, 'r') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                orders.append(row)

    # Retrieve book information from the catalog server
    catalog = get_catalog()

    if catalog is None:
        return jsonify({'error': 'Error retrieving catalog information'})

    # Find the book with the specified item number
    for book in catalog:
        if str(book['ID']) == item_number:
            # Record the purchase in the orders list
            orders.append({'item_number': item_number, 'timestamp': datetime.utcnow().isoformat()})
            
            update_orders_csv(orders)
            
            notify_catalog_server(item_number)
            
            invalidate_frontend_cache(item_number)
            
            return jsonify({'message': f'Book {book.get("Title", "Unknown Title")} purchased successfully'})

    return jsonify({'error': 'Book not found in the catalog'})

if __name__ == '__main__':
    replica_server_id = 1
    replica_server_port = 5004  
    print(f'Replica {replica_server_id} on Port {replica_server_port}: Order Server Running')
    app.run(host='0.0.0.0', port=replica_server_port, debug=True)
