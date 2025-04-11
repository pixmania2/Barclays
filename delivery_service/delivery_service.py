from flask import Flask, request, jsonify
import logging
import uuid
from datetime import datetime
from logging.handlers import RotatingFileHandler
import os
import json
from flask_cors import CORS

app = Flask(__name__)
CORS(app)
deliveries = {}

# Status code constants
SUCCESS_STATUSES = [200, 201]
ERROR_STATUSES = [400, 404, 500, 503]

LOG_DIR = "/app/logs"
os.makedirs(LOG_DIR, exist_ok=True)
log_file_path = os.path.join(LOG_DIR, "delivery_service.log")

logging.basicConfig(format='%(asctime)s %(levelname)s %(message)s', level=logging.INFO, handlers=[
    RotatingFileHandler(log_file_path, maxBytes=1000000, backupCount=3),
    logging.StreamHandler()
])

def log_with_status(event, status_code, **kwargs):
    log_entry = {
        "event": event,
        "status_code": status_code,
        "status_type": "success" if status_code in SUCCESS_STATUSES else "error",
        "timestamp": datetime.now().isoformat(),
        "service": "delivery_service",
        **kwargs
    }
    if status_code in SUCCESS_STATUSES:
        app.logger.info(json.dumps(log_entry))
    else:
        app.logger.error(json.dumps(log_entry))
    return log_entry

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
    log_with_status("DELIVERY_CREATED", 201, 
                   delivery_id=delivery_id,
                   order_id=order_id,
                   driver_id=driver_id,
                   status="ASSIGNED")
    return jsonify({"status": "assigned", "delivery_id": delivery_id}), 201

@app.route('/api/deliveries/<delivery_id>', methods=['GET'])
def get_delivery(delivery_id):
    delivery = deliveries.get(delivery_id)
    if not delivery:
        log_with_status("DELIVERY_NOT_FOUND", 404, delivery_id=delivery_id)
        return jsonify({"error": "Delivery not found"}), 404
    log_with_status("DELIVERY_RETRIEVED", 200, 
                   delivery_id=delivery_id,
                   status=delivery["status"])
    return jsonify(delivery)

@app.route('/api/deliveries/<delivery_id>/update_status', methods=['PATCH'])
def update_delivery_status(delivery_id):
    data = request.json or {}
    delivery = deliveries.get(delivery_id)
    if not delivery:
        log_with_status("DELIVERY_UPDATE_FAILED", 404, delivery_id=delivery_id)
        return jsonify({"error": "Delivery not found"}), 404
    new_status = data.get("status", delivery["status"])
    delivery["status"] = new_status
    log_with_status("DELIVERY_STATUS_UPDATED", 200, 
                   delivery_id=delivery_id,
                   status=new_status)
    return jsonify({"status": "delivery_updated", "delivery": delivery}), 200

@app.route('/api/deliveries/<delivery_id>/update_location', methods=['PATCH'])
def update_delivery_location(delivery_id):
    data = request.json or {}
    delivery = deliveries.get(delivery_id)
    if not delivery:
        log_with_status("LOCATION_UPDATE_FAILED", 404, delivery_id=delivery_id)
        return jsonify({"error": "Delivery not found"}), 404
    new_location = data.get("location")
    delivery["location"] = new_location
    log_with_status("DELIVERY_LOCATION_UPDATED", 200, 
                   delivery_id=delivery_id,
                   location=new_location)
    return jsonify({"status": "location_updated", "delivery": delivery}), 200

@app.route('/api/deliveries/<delivery_id>/reassign', methods=['PATCH'])
def reassign_delivery(delivery_id):
    data = request.json or {}
    delivery = deliveries.get(delivery_id)
    if not delivery:
        log_with_status("REASSIGNMENT_FAILED", 404, delivery_id=delivery_id)
        return jsonify({"error": "Delivery not found"}), 404
    new_driver_id = data.get("driverId", delivery["driver_id"])
    delivery["driver_id"] = new_driver_id
    log_with_status("DELIVERY_REASSIGNED", 200, 
                   delivery_id=delivery_id,
                   new_driver_id=new_driver_id)
    return jsonify({"status": "reassigned", "delivery": delivery}), 200

@app.route('/api/deliveries/<delivery_id>/tracking', methods=['GET'])
def tracking_info(delivery_id):
    delivery = deliveries.get(delivery_id)
    if not delivery:
        log_with_status("TRACKING_INFO_FAILED", 404, delivery_id=delivery_id)
        return jsonify({"error": "Delivery not found"}), 404
    tracking_data = {
        "delivery_id": delivery_id,
        "status": delivery["status"],
        "location": delivery.get("location"),
        "driver_id": delivery["driver_id"]
    }
    log_with_status("TRACKING_INFO_RETRIEVED", 200, 
                   delivery_id=delivery_id,
                   status=delivery["status"])
    return jsonify(tracking_data), 200

@app.route('/api/deliveries/<delivery_id>/mark_delivered', methods=['PATCH'])
def mark_delivered(delivery_id):
    delivery = deliveries.get(delivery_id)
    if not delivery:
        log_with_status("DELIVERY_MARK_FAILED", 404, delivery_id=delivery_id)
        return jsonify({"error": "Delivery not found"}), 404
    delivery["status"] = "DELIVERED"
    log_with_status("DELIVERY_COMPLETED", 200, 
                   delivery_id=delivery_id,
                   status="DELIVERED")
    return jsonify({"status": "delivered", "delivery": delivery}), 200

# Prometheus metrics
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
    app.run(port=5005, host='0.0.0.0')
