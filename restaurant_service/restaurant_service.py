from flask import Flask, request, jsonify
import logging
import uuid
from datetime import datetime

app = Flask(__name__)
restaurants = {}

logging.basicConfig(format='%(asctime)s %(levelname)s %(message)s', level=logging.INFO)

@app.route('/api/restaurants', methods=['GET'])
def list_restaurants():
    return jsonify(list(restaurants.values()))

@app.route('/api/restaurants', methods=['POST'])
def create_restaurant():
    data = request.json or {}
    restaurant_id = str(uuid.uuid4())
    restaurant_record = {
        "id": restaurant_id,
        "name": data.get("name", "Unnamed Restaurant"),
        "location": data.get("location", "Unknown"),
        "created_at": datetime.now().isoformat(),
        "menu": []  # Initialize empty menu
    }
    restaurants[restaurant_id] = restaurant_record
    app.logger.info(f"RESTAURANT_CREATED: {restaurant_id} at {datetime.now().isoformat()}")
    return jsonify({"status": "created", "restaurant": restaurant_record}), 201

@app.route('/api/restaurants/<restaurant_id>', methods=['GET'])
def get_restaurant(restaurant_id):
    restaurant = restaurants.get(restaurant_id)
    if not restaurant:
        return jsonify({"error": "Restaurant not found"}), 404
    return jsonify(restaurant)

@app.route('/api/restaurants/<restaurant_id>/update', methods=['PATCH'])
def update_restaurant(restaurant_id):
    data = request.json or {}
    restaurant = restaurants.get(restaurant_id)
    if not restaurant:
        return jsonify({"error": "Restaurant not found"}), 404
    restaurant["name"] = data.get("name", restaurant["name"])
    restaurant["location"] = data.get("location", restaurant["location"])
    app.logger.info(f"RESTAURANT_UPDATED: {restaurant_id} at {datetime.now().isoformat()}")
    return jsonify({"status": "updated", "restaurant": restaurant}), 200

@app.route('/api/restaurants/<restaurant_id>/menu', methods=['GET'])
def get_menu(restaurant_id):
    restaurant = restaurants.get(restaurant_id)
    if not restaurant:
        return jsonify({"error": "Restaurant not found"}), 404
    return jsonify({"restaurant_id": restaurant_id, "menu": restaurant["menu"]})

@app.route('/api/restaurants/<restaurant_id>/menu/add', methods=['POST'])
def add_menu_item(restaurant_id):
    data = request.json or {}
    restaurant = restaurants.get(restaurant_id)
    if not restaurant:
        return jsonify({"error": "Restaurant not found"}), 404
    menu_item = {
        "id": str(uuid.uuid4()),
        "name": data.get("name", "Unnamed Item"),
        "price": data.get("price", 0.0)
    }
    restaurant["menu"].append(menu_item)
    app.logger.info(f"MENU_ITEM_ADDED: {menu_item['id']} to Restaurant {restaurant_id} at {datetime.now().isoformat()}")
    return jsonify({"status": "item_added", "menu_item": menu_item}), 201

@app.route('/api/restaurants/<restaurant_id>/menu/update', methods=['PATCH'])
def update_menu_item(restaurant_id):
    data = request.json or {}
    menu_item_id = data.get("id")
    restaurant = restaurants.get(restaurant_id)
    if not restaurant:
        return jsonify({"error": "Restaurant not found"}), 404
    for item in restaurant["menu"]:
        if item["id"] == menu_item_id:
            item["name"] = data.get("name", item["name"])
            item["price"] = data.get("price", item["price"])
            app.logger.info(f"MENU_ITEM_UPDATED: {menu_item_id} in Restaurant {restaurant_id} at {datetime.now().isoformat()}")
            return jsonify({"status": "item_updated", "menu_item": item}), 200
    return jsonify({"error": "Menu item not found"}), 404

@app.route('/api/restaurants/<restaurant_id>/menu/<menu_item_id>', methods=['DELETE'])
def delete_menu_item(restaurant_id, menu_item_id):
    restaurant = restaurants.get(restaurant_id)
    if not restaurant:
        return jsonify({"error": "Restaurant not found"}), 404
    for item in restaurant["menu"]:
        if item["id"] == menu_item_id:
            restaurant["menu"].remove(item)
            app.logger.info(f"MENU_ITEM_DELETED: {menu_item_id} from Restaurant {restaurant_id} at {datetime.now().isoformat()}")
            return jsonify({"status": "item_deleted"}), 200
    return jsonify({"error": "Menu item not found"}), 404

from time import time
from flask import request
from prometheus_client import Counter, Histogram, generate_latest

# Create Prometheus metrics objects
REQUEST_LATENCY = Histogram(
    'flask_request_duration_seconds', 
    'Flask Request Latency',
    ['method', 'endpoint', 'http_status']
)
REQUEST_COUNT = Counter(
    'flask_request_count', 
    'Flask Request Count',
    ['method', 'endpoint', 'http_status']
)

# Before each request, record the start time
@app.before_request
def start_timer():
    request.start_time = time()

# After each request, record latency and count
@app.after_request
def record_metrics(response):
    resp_time = time() - request.start_time
    # Record the latency for the given method, endpoint, and HTTP status code
    REQUEST_LATENCY.labels(
        method=request.method, 
        endpoint=request.path, 
        http_status=response.status_code
    ).observe(resp_time)
    
    # Increment the request counter
    REQUEST_COUNT.labels(
        method=request.method, 
        endpoint=request.path, 
        http_status=response.status_code
    ).inc()
    
    return response

# Expose a /metrics endpoint for Prometheus to scrape
@app.route('/metrics')
def metrics():
    return generate_latest(), 200, {'Content-Type': 'text/plain; version=0.0.4; charset=utf-8'}

if __name__ == '__main__':
    print("Registered routes:", app.url_map)
    app.run(port=5002, host='0.0.0.0')
