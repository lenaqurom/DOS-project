from flask import Flask, jsonify, request
import requests

app = Flask(__name__)

# Use configuration or environment variables for server URLs
CATALOG_SERVER_URL = 'http://172.19.0.2:5000'
ORDER_SERVER_URL = 'http://172.19.0.3:5001'

# Search for books in the catalog based on the provided topic
@app.route('/search/<topic>', methods=['GET'])
def search_books(topic):
    try:
        response = requests.get(f'{CATALOG_SERVER_URL}/search/{topic}')
        response.raise_for_status()  # Check for HTTP errors
        return response.json()
    except requests.exceptions.RequestException as e:
        return jsonify({'error': f'Catalog server error: {str(e)}'})

# Retrieve information about a book based on the provided item number
@app.route('/info/<item_number>', methods=['GET'])
def book_info(item_number):
    try:
        response = requests.get(f'{CATALOG_SERVER_URL}/info/{item_number}')
        response.raise_for_status()  # Check for HTTP errors
        return response.json()
    except requests.exceptions.RequestException as e:
        return jsonify({'error': f'Catalog server error: {str(e)}'})

# Purchase a book based on the provided item number
@app.route('/purchase/<item_number>', methods=['POST'])
def purchase_book(item_number):
    try:
        response = requests.post(f'{ORDER_SERVER_URL}/purchase/{item_number}')
        response.raise_for_status()  # Check for HTTP errors
        return response.json()
    except requests.exceptions.RequestException as e:
        return jsonify({'error': f'Order server error: {str(e)}'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5002, debug=True)

