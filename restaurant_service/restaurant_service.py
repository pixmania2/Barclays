from flask import Flask, request, jsonify
import logging
import uuid
from datetime import datetime
from logging.handlers import RotatingFileHandler
import os
import json

app = Flask(__name__)
restaurants = {}

# Status code constants
SUCCESS_STATUSES = [200, 201]
ERROR_STATUSES = [400, 404, 500, 503]

LOG_DIR = "/app/logs"
os.makedirs(LOG_DIR, exist_ok=True)

log_file_path = os.path.join(LOG_DIR, "restaurant_service.log")

logging.basicConfig(format='%(asctime)s %(levelname)s %(message)s', level=logging.INFO, handlers=[
    RotatingFileHandler(log_file_path, maxBytes=1000000, backupCount=3),
    logging.StreamHandler()  # Optional: keep console logs
])

def log_with_status(event, status_code, **kwargs):
    log_entry = {
        "event": event,
        "status_code": status_code,
        "status_type": "success" if status_code in SUCCESS_STATUSES else "error",
        "timestamp": datetime.now().isoformat(),
        "service": "restaurant_service",
        **kwargs
    }
    if status_code in SUCCESS_STATUSES:
        app.logger.info(json.dumps(log_entry))
    else:
        app.logger.error(json.dumps(log_entry))
    return log_entry

@app.route('/api/restaurants', methods=['GET'])
def list_restaurants():
    log_with_status("RESTAURANTS_LISTED", 200)
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
        "menu": []
    }
    restaurants[restaurant_id] = restaurant_record
    log_with_status("RESTAURANT_CREATED", 201, restaurant_id=restaurant_id)
    return jsonify({"status": "created", "restaurant": restaurant_record}), 201

@app.route('/api/restaurants/<restaurant_id>', methods=['GET'])
def get_restaurant(restaurant_id):
    restaurant = restaurants.get(restaurant_id)
    if not restaurant:
        log_with_status("RESTAURANT_NOT_FOUND", 404, restaurant_id=restaurant_id)
        return jsonify({"error": "Restaurant not found"}), 404
    log_with_status("RESTAURANT_RETRIEVED", 200, restaurant_id=restaurant_id)
    return jsonify(restaurant)

@app.route('/api/restaurants/<restaurant_id>/update', methods=['PATCH'])
def update_restaurant(restaurant_id):
    data = request.json or {}
    restaurant = restaurants.get(restaurant_id)
    if not restaurant:
        log_with_status("RESTAURANT_UPDATE_FAILED", 404, restaurant_id=restaurant_id)
        return jsonify({"error": "Restaurant not found"}), 404

    restaurant["name"] = data.get("name", restaurant["name"])
    restaurant["location"] = data.get("location", restaurant["location"])
    log_with_status("RESTAURANT_UPDATED", 200, restaurant_id=restaurant_id)
    return jsonify({"status": "updated", "restaurant": restaurant}), 200

@app.route('/api/restaurants/<restaurant_id>/menu', methods=['GET'])
def get_menu(restaurant_id):
    restaurant = restaurants.get(restaurant_id)
    if not restaurant:
        log_with_status("MENU_RETRIEVAL_FAILED", 404, restaurant_id=restaurant_id)
        return jsonify({"error": "Restaurant not found"}), 404
    log_with_status("MENU_RETRIEVED", 200, restaurant_id=restaurant_id)
    return jsonify({"restaurant_id": restaurant_id, "menu": restaurant["menu"]})

@app.route('/api/restaurants/<restaurant_id>/menu/add', methods=['POST'])
def add_menu_item(restaurant_id):
    data = request.json or {}
    restaurant = restaurants.get(restaurant_id)
    if not restaurant:
        log_with_status("MENU_ITEM_ADD_FAILED", 404, restaurant_id=restaurant_id)
        return jsonify({"error": "Restaurant not found"}), 404

    menu_item = {
        "id": str(uuid.uuid4()),
        "name": data.get("name", "Unnamed Item"),
        "price": data.get("price", 0.0)
    }
    restaurant["menu"].append(menu_item)
    log_with_status("MENU_ITEM_ADDED", 201, restaurant_id=restaurant_id, menu_item_id=menu_item["id"])
    return jsonify({"status": "item_added", "menu_item": menu_item}), 201

@app.route('/api/restaurants/<restaurant_id>/menu/update', methods=['PATCH'])
def update_menu_item(restaurant_id):
    data = request.json or {}
    menu_item_id = data.get("id")
    restaurant = restaurants.get(restaurant_id)
    if not restaurant:
        log_with_status("MENU_ITEM_UPDATE_FAILED", 404, restaurant_id=restaurant_id)
        return jsonify({"error": "Restaurant not found"}), 404

    for item in restaurant["menu"]:
        if item["id"] == menu_item_id:
            item["name"] = data.get("name", item["name"])
            item["price"] = data.get("price", item["price"])
            log_with_status("MENU_ITEM_UPDATED", 200, restaurant_id=restaurant_id, menu_item_id=menu_item_id)
            return jsonify({"status": "item_updated", "menu_item": item}), 200

    log_with_status("MENU_ITEM_NOT_FOUND", 404, restaurant_id=restaurant_id, menu_item_id=menu_item_id)
    return jsonify({"error": "Menu item not found"}), 404

@app.route('/api/restaurants/<restaurant_id>/menu/<menu_item_id>', methods=['DELETE'])
def delete_menu_item(restaurant_id, menu_item_id):
    restaurant = restaurants.get(restaurant_id)
    if not restaurant:
        log_with_status("MENU_ITEM_DELETE_FAILED", 404, restaurant_id=restaurant_id)
        return jsonify({"error": "Restaurant not found"}), 404

    for item in restaurant["menu"]:
        if item["id"] == menu_item_id:
            restaurant["menu"].remove(item)
            log_with_status("MENU_ITEM_DELETED", 200, restaurant_id=restaurant_id, menu_item_id=menu_item_id)
            return jsonify({"status": "item_deleted"}), 200

    log_with_status("MENU_ITEM_NOT_FOUND", 404, restaurant_id=restaurant_id, menu_item_id=menu_item_id)
    return jsonify({"error": "Menu item not found"}), 404

# Monitoring & Prometheus
from time import time
from prometheus_client import Counter, Histogram, generate_latest

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

@app.before_request
def start_timer():
    request.start_time = time()

@app.after_request
def record_metrics(response):
    resp_time = time() - request.start_time
    REQUEST_LATENCY.labels(
        method=request.method, 
        endpoint=request.path, 
        http_status=response.status_code
    ).observe(resp_time)
    REQUEST_COUNT.labels(
        method=request.method, 
        endpoint=request.path, 
        http_status=response.status_code
    ).inc()
    return response

@app.route('/metrics')
def metrics():
    log_with_status("METRICS_ENDPOINT_CALLED", 200)
    return generate_latest(), 200, {'Content-Type': 'text/plain; version=0.0.4; charset=utf-8'}

if __name__ == '__main__':
    print("Registered routes:", app.url_map)
    app.run(port=5002, host='0.0.0.0')
