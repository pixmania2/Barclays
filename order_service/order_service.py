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
orders = {}

LOG_DIR = "/app/logs"
os.makedirs(LOG_DIR, exist_ok=True)

log_file_path = os.path.join(LOG_DIR, "order_service.log")

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
        "service": "order_service",
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

    # Prometheus metrics
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

@app.route('/api/orders/create', methods=['POST'])
def create_order():
    data = request.json or {}
    order_id = str(uuid.uuid4())
    order_record = {
        "id": order_id,
        "userId": data.get("userId"),
        "restaurantId": data.get("restaurantId"),
        "items": data.get("items", []),
        "status": "CREATED",
        "created_at": datetime.now().isoformat()
    }
    orders[order_id] = order_record
    return jsonify({"status": "order_created", "order": order_record}), 201

@app.route('/api/orders/<order_id>', methods=['GET'])
def get_order(order_id):
    order = orders.get(order_id)
    if not order:
        return jsonify({"error": "Order not found"}), 404
    return jsonify(order)

@app.route('/api/orders/<order_id>/update_status', methods=['PATCH'])
def update_order_status(order_id):
    data = request.json or {}
    order = orders.get(order_id)
    if not order:
        return jsonify({"error": "Order not found"}), 404
    new_status = data.get("status", "CREATED")
    order["status"] = new_status
    return jsonify({"status": "order_updated", "order": order})

@app.route('/api/orders/<order_id>/cancel', methods=['PATCH'])
def cancel_order(order_id):
    order = orders.get(order_id)
    if not order:
        return jsonify({"error": "Order not found"}), 404
    order["status"] = "CANCELLED"
    return jsonify({"status": "order_cancelled", "order": order}), 200

@app.route('/api/orders/user/<user_id>', methods=['GET'])
def get_orders_by_user(user_id):
    user_orders = [order for order in orders.values() if order.get("userId") == user_id]
    return jsonify({"user_id": user_id, "orders": user_orders}), 200

@app.route('/api/orders/<order_id>/reorder', methods=['POST'])
def reorder(order_id):
    original_order = orders.get(order_id)
    if not original_order:
        return jsonify({"error": "Original order not found"}), 404
    new_order_id = str(uuid.uuid4())
    new_order = original_order.copy()
    new_order["id"] = new_order_id
    new_order["status"] = "CREATED"
    new_order["created_at"] = datetime.now().isoformat()
    orders[new_order_id] = new_order
    return jsonify({"status": "order_created", "order": new_order}), 201

@app.route('/metrics')
def metrics():
    return generate_latest(), 200, {'Content-Type': 'text/plain; version=0.0.4; charset=utf-8'}

if __name__ == '__main__':
    print("Registered routes:", app.url_map)
    app.run(port=5003, host='0.0.0.0')
