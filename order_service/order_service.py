from flask import Flask, request, jsonify
import logging
import uuid
from datetime import datetime

app = Flask(__name__)
orders = {}

logging.basicConfig(format='%(asctime)s %(levelname)s %(message)s', level=logging.INFO)

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
    log_entry = f"{datetime.now().isoformat()},{order_id},{order_record['userId']},{order_record['restaurantId']},CREATED"
    app.logger.info(log_entry)
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
    log_entry = f"{datetime.now().isoformat()},{order_id},{order['userId']},{order['restaurantId']},{new_status}"
    app.logger.info(log_entry)
    return jsonify({"status": "order_updated", "order": order})

@app.route('/api/orders/<order_id>/cancel', methods=['PATCH'])
def cancel_order(order_id):
    order = orders.get(order_id)
    if not order:
        return jsonify({"error": "Order not found"}), 404
    order["status"] = "CANCELLED"
    log_entry = f"{datetime.now().isoformat()},{order_id},{order['userId']},{order['restaurantId']},CANCELLED"
    app.logger.info(log_entry)
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
    log_entry = f"{datetime.now().isoformat()},{new_order_id},{new_order['userId']},{new_order['restaurantId']},REORDERED"
    app.logger.info(log_entry)
    return jsonify({"status": "order_created", "order": new_order}), 201

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
    app.run(port=5003, host='0.0.0.0')