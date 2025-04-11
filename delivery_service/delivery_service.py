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
deliveries = {}

LOG_DIR = "/app/logs"
os.makedirs(LOG_DIR, exist_ok=True)
log_file_path = os.path.join(LOG_DIR, "delivery_service.log")

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
        "service": "delivery_service",
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
    return jsonify({"status": "delivery_updated", "delivery": delivery}), 200

@app.route('/api/deliveries/<delivery_id>/update_location', methods=['PATCH'])
def update_delivery_location(delivery_id):
    data = request.json or {}
    delivery = deliveries.get(delivery_id)
    if not delivery:
        return jsonify({"error": "Delivery not found"}), 404
    new_location = data.get("location")
    delivery["location"] = new_location
    return jsonify({"status": "location_updated", "delivery": delivery}), 200

@app.route('/api/deliveries/<delivery_id>/reassign', methods=['PATCH'])
def reassign_delivery(delivery_id):
    data = request.json or {}
    delivery = deliveries.get(delivery_id)
    if not delivery:
        return jsonify({"error": "Delivery not found"}), 404
    new_driver_id = data.get("driverId", delivery["driver_id"])
    delivery["driver_id"] = new_driver_id
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
    return jsonify({"status": "delivered", "delivery": delivery}), 200

@app.route('/metrics')
def metrics():
    return generate_latest(), 200, {'Content-Type': 'text/plain; version=0.0.4; charset=utf-8'}

if __name__ == '__main__':
    print("Registered routes:", app.url_map)
    app.run(port=5005, host='0.0.0.0')
