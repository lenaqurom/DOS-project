from flask import Flask, jsonify, request
import csv
import requests
import os
from datetime import datetime

app = Flask(__name__)

CATALOG_SERVER_URL = os.environ.get('CATALOG_SERVER_URL', 'http://172.19.0.2:5000')
CATALOG_CSV_FILE = '../microservices/catalog_server/catalog.csv'

# Retrieve catalog information from the catalog server
def get_catalog():
    try:
        url = f'{CATALOG_SERVER_URL}/catalog'
        response = requests.get(url)
        response.raise_for_status()  # Raise an HTTPError for bad responses
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error connecting to catalog server: {e}")
        print(f"URL: {url}")
        return None

# Update the 'order.csv' file with the given orders
def update_orders_csv(orders):
    with open('order.csv', 'w', newline='') as csvfile:
        # Extract fieldnames from the first line in orders (assuming orders is not empty)
        fieldnames = list(orders[0].keys()) if orders else ['item_number', 'timestamp']

        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(orders)

# Notify the catalog server about the update
def notify_catalog_server():
    try:
        url = f'{CATALOG_SERVER_URL}/notify'
        response = requests.post(url)
        response.raise_for_status()
        print(response.json())
    except requests.exceptions.RequestException as e:
        print(f"Error notifying catalog server: {e}")
        print(f"URL: {url}")

# Update the 'catalog.csv' file with the modified catalog information
def update_catalog_csv(catalog, catalog_csv_file, item_number):
    # Read the existing content of the catalog CSV file
    existing_catalog = []
    try:
        with open(catalog_csv_file, 'r', newline='') as csvfile:
            reader = csv.DictReader(csvfile)
            existing_catalog = list(reader)
    except FileNotFoundError:
        pass

    # Update the quantity of the purchased book
    for existing_book in existing_catalog:
        if existing_book['ID'] == item_number:
            current_quantity = int(existing_book['Quantity'])
            new_quantity = max(0, current_quantity - 1)  # Decrease the quantity by 1
            existing_book['Quantity'] = str(new_quantity)
            break  # Break out of the loop once the book is found and updated

    # Write the modified content back to the catalog CSV file
    with open(catalog_csv_file, 'w', newline='') as csvfile:
        fieldnames = ['ID', 'Title', 'Quantity', 'Price', 'Topic']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(existing_catalog)
        
# Purchase a book and update relevant files
@app.route('/purchase/<item_number>', methods=['POST'])
def purchase_book(item_number):
    # Load order data from a CSV file
    orders_csv_file = 'order.csv'
    orders = []

    if os.path.exists(orders_csv_file):
        with open(orders_csv_file, 'r') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                orders.append(row)

    catalog = get_catalog()

    if catalog is None:
        return jsonify({'error': 'Unable to retrieve catalog information'})

    found = False

    for book in catalog:
        if str(book['ID']) == item_number:
            found = True
            current_quantity = int(book.get('Quantity', 0))
            if current_quantity > 0:
                book['Quantity'] = str(current_quantity - 1)
                # Record the purchase in the orders list
                orders.append({'item_number': item_number, 'timestamp': datetime.utcnow().isoformat()})
                # Update the 'order.csv' file
                update_orders_csv(orders)
                # Update the 'catalog.csv' file in the specified directory
                update_catalog_csv(catalog, CATALOG_CSV_FILE, item_number)
                # Notify the catalog server about the update
                notify_catalog_server()
                # Use 'get' method to avoid KeyError, and fetch the title using the book ID
                return jsonify({'message': f'Book {book.get("Title", "Unknown Title")} purchased successfully'})
            else:
                return jsonify({'error': 'Book out of stock'})

    if not found:
        return jsonify({'error': 'Book not found in the catalog'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)
