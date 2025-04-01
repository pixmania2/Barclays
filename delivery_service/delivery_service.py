from flask import Flask, request, jsonify
import logging
import uuid
from datetime import datetime

app = Flask(__name__)
deliveries = {}

logging.basicConfig(format='%(asctime)s %(levelname)s %(message)s', level=logging.INFO)

@app.route('/api/deliveries/create', methods=['POST'])
def create_delivery():
    data = request.json or {}
    delivery_id = str(uuid.uuid4())
    order_id = data.get("orderId", "unknown")
    driver_id = data.get("driverId", "unknown")
    deliveries[delivery_id] = {
        "delivery_id": delivery_id,
        "order_id": order_id,
        "driver_id": driver_id,
        "status": "ASSIGNED",
        "timestamp": datetime.now().isoformat(),
        "location": None
    }
    log_entry = f"DELIVERY_LOG delivery_id={delivery_id} order_id={order_id} driver_id={driver_id} status=ASSIGNED"
    app.logger.info(log_entry)
    return jsonify({"status": "assigned", "delivery_id": delivery_id}), 201

@app.route('/api/deliveries/<delivery_id>', methods=['GET'])
def get_delivery(delivery_id):
    delivery = deliveries.get(delivery_id)
    if not delivery:
        return jsonify({"error": "Delivery not found"}), 404
    return jsonify(delivery)

@app.route('/api/deliveries/<delivery_id>/update_status', methods=['PATCH'])
def update_delivery_status(delivery_id):
    data = request.json or {}
    delivery = deliveries.get(delivery_id)
    if not delivery:
        return jsonify({"error": "Delivery not found"}), 404
    new_status = data.get("status", delivery["status"])
    delivery["status"] = new_status
    log_entry = f"DELIVERY_LOG delivery_id={delivery_id} status={new_status}"
    app.logger.info(log_entry)
    return jsonify({"status": "delivery_updated", "delivery": delivery}), 200

@app.route('/api/deliveries/<delivery_id>/update_location', methods=['PATCH'])
def update_delivery_location(delivery_id):
    data = request.json or {}
    delivery = deliveries.get(delivery_id)
    if not delivery:
        return jsonify({"error": "Delivery not found"}), 404
    new_location = data.get("location")
    delivery["location"] = new_location
    log_entry = f"DELIVERY_LOG delivery_id={delivery_id} location={new_location}"
    app.logger.info(log_entry)
    return jsonify({"status": "location_updated", "delivery": delivery}), 200

@app.route('/api/deliveries/<delivery_id>/reassign', methods=['PATCH'])
def reassign_delivery(delivery_id):
    data = request.json or {}
    delivery = deliveries.get(delivery_id)
    if not delivery:
        return jsonify({"error": "Delivery not found"}), 404
    new_driver_id = data.get("driverId", delivery["driver_id"])
    delivery["driver_id"] = new_driver_id
    log_entry = f"DELIVERY_LOG delivery_id={delivery_id} reassigned_driver={new_driver_id}"
    app.logger.info(log_entry)
    return jsonify({"status": "reassigned", "delivery": delivery}), 200

@app.route('/api/deliveries/<delivery_id>/tracking', methods=['GET'])
def tracking_info(delivery_id):
    delivery = deliveries.get(delivery_id)
    if not delivery:
        return jsonify({"error": "Delivery not found"}), 404
    tracking_data = {
        "delivery_id": delivery_id,
        "status": delivery["status"],
        "location": delivery.get("location"),
        "driver_id": delivery["driver_id"]
    }
    return jsonify(tracking_data), 200

@app.route('/api/deliveries/<delivery_id>/mark_delivered', methods=['PATCH'])
def mark_delivered(delivery_id):
    delivery = deliveries.get(delivery_id)
    if not delivery:
        return jsonify({"error": "Delivery not found"}), 404
    delivery["status"] = "DELIVERED"
    log_entry = f"DELIVERY_LOG delivery_id={delivery_id} marked=DELIVERED"
    app.logger.info(log_entry)
    return jsonify({"status": "delivered", "delivery": delivery}), 200

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
    app.run(port=5005, host='0.0.0.0')

