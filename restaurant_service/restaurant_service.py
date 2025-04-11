from flask import Flask, request, jsonify
import logging
import uuid
from datetime import datetime
from logging.handlers import RotatingFileHandler
import os
import json
import psutil
from flask_cors import CORS
from time import time
from prometheus_client import Counter, Histogram, generate_latest

app = Flask(__name__)
CORS(app)
restaurants = {}

LOG_DIR = "/app/logs"
os.makedirs(LOG_DIR, exist_ok=True)

log_file_path = os.path.join(LOG_DIR, "restaurant_service.log")

logging.basicConfig(format='%(asctime)s %(levelname)s %(message)s', level=logging.INFO, handlers=[
    RotatingFileHandler(log_file_path, maxBytes=1000000, backupCount=3),
    logging.StreamHandler()
])

@app.before_request
def start_timer():
    request.start_time = time()
    request.request_id = str(uuid.uuid4())
    request.payload_size = len(request.data or b'')
    request.cpu = psutil.cpu_percent(interval=None)
    request.mem = psutil.Process().memory_info().rss / (1024 * 1024)

@app.after_request
def log_and_metrics(response):
    duration = round((time() - request.start_time) * 1000, 2)
    error_flag = response.status_code >= 400
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "service": "restaurant_service",
        "environment": os.getenv("ENVIRONMENT", "unknown"),
        "endpoint": request.path,
        "http_method": request.method,
        "http_status": response.status_code,
        "response_time_ms": duration,
        "error_flag": error_flag,
        "request_id": request.request_id,
        "trace_id": None,
        "span_id": None,
        "payload_size_bytes": request.payload_size,
        "cpu_usage_percent": request.cpu,
        "memory_usage_mb": request.mem,
        "log_level": "ERROR" if error_flag else "INFO",
        "error_message": None
    }

    logger = app.logger.error if error_flag else app.logger.info
    logger(json.dumps(log_entry))

    REQUEST_LATENCY.labels(
        method=request.method,
        endpoint=request.path,
        http_status=response.status_code
    ).observe(duration / 1000)

    REQUEST_COUNT.labels(
        method=request.method,
        endpoint=request.path,
        http_status=response.status_code
    ).inc()

    return response

# Prometheus metrics
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
        "menu": []
    }
    restaurants[restaurant_id] = restaurant_record
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
            return jsonify({"status": "item_deleted"}), 200
    return jsonify({"error": "Menu item not found"}), 404

@app.route('/metrics')
def metrics():
    return generate_latest(), 200, {'Content-Type': 'text/plain; version=0.0.4; charset=utf-8'}

if __name__ == '__main__':
    print("Registered routes:", app.url_map)
    app.run(port=5002, host='0.0.0.0')
