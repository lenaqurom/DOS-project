import csv
from flask import Flask, jsonify, request

app = Flask(__name__)

# Load catalog data from a CSV file
catalog = []

# Load catalog data from the 'catalog.csv' file
def load_catalog():
    global catalog  # Use the global variable

    with open('catalog.csv', 'r') as csvfile:
        reader = csv.DictReader(csvfile)
        catalog = list(reader)

# Save catalog data to the 'catalog.csv' file
def save_catalog():
    with open('catalog.csv', 'w', newline='') as csvfile:
        fieldnames = ['ID', 'Title', 'Quantity', 'Price', 'Topic']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(catalog)

load_catalog()

# Search for items in the catalog based on the provided item name (topic)
@app.route('/search/<item_name>', methods=['GET'])
def search_items(item_name):
    results = []
    for book_id, book in enumerate(catalog, start=1):
        if item_name.lower() in book.get('Topic', '').lower():
            results.append({
                'id': book['ID'],
                'title': book['Title']
            })
    return jsonify(results)

# Retrieve information about a book based on the provided item number
@app.route('/info/<item_number>', methods=['GET'])
def book_info(item_number):
    for book_id, book in enumerate(catalog, start=1):
        if str(book_id) == item_number:
            return jsonify({
                'title': book['Title'],
                'quantity': int(book['Quantity']),
                'price': float(book['Price'])
            })
    return jsonify({'error': 'Book not found'})

# Update the quantity or price of a book based on the provided item number
@app.route('/update/<item_number>', methods=['PUT'])
def update_book(item_number):
    for book_id, book in enumerate(catalog, start=1):
        if str(book_id) == item_number:
            # Update the book details
            if 'quantity' in request.json:
                new_quantity = request.json.get('quantity')
                book['Quantity'] = str(new_quantity)
            if 'price' in request.json:
                new_price = request.json.get('price')
                book['Price'] = str(new_price)

            # Update the CSV file
            save_catalog()

            return jsonify({'message': 'Book updated successfully'})
    return jsonify({'error': 'Book not found'}), 404

# Retrieve the entire catalog
@app.route('/catalog', methods=['GET'])
def get_catalog():
    return jsonify(catalog)

# Notify about catalog updates and reload catalog data from the CSV file
@app.route('/notify', methods=['POST'])
def notify_update():
    load_catalog()
    return jsonify({'message': 'Catalog updated successfully'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
