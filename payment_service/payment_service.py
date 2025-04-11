from flask import Flask, request, jsonify
import logging
import uuid
import json
from datetime import datetime
from logging.handlers import RotatingFileHandler
import os
from flask_cors import CORS

app = Flask(__name__)
CORS(app)
transactions = {}

# Status code constants
SUCCESS_STATUSES = [200, 201]
ERROR_STATUSES = [400, 404, 500, 503]

LOG_DIR = "/app/logs"
os.makedirs(LOG_DIR, exist_ok=True)

log_file_path = os.path.join(LOG_DIR, "payment_service.log")

logging.basicConfig(format='%(asctime)s %(levelname)s %(message)s', level=logging.INFO, handlers=[
        RotatingFileHandler(log_file_path, maxBytes=1000000, backupCount=3),
        logging.StreamHandler()  # Optional: keep console logs
    ]
)

def log_with_status(event, status_code, **kwargs):
    log_entry = {
        "event": event,
        "status_code": status_code,
        "status_type": "success" if status_code in SUCCESS_STATUSES else "error",
        "timestamp": datetime.now().isoformat(),
        "service": "payment_service",
        **kwargs
    }
    if status_code in SUCCESS_STATUSES:
        app.logger.info(json.dumps(log_entry))
    else:
        app.logger.error(json.dumps(log_entry))
    return log_entry

@app.route('/api/payments/charge', methods=['POST'])
def charge():
    data = request.json or {}
    transaction_id = str(uuid.uuid4())
    order_id = data.get("orderId", "unknown")
    amount = data.get("amount", 0.0)
    transactions[transaction_id] = {
        "transaction_id": transaction_id,
        "order_id": order_id,
        "amount": amount,
        "status": "CHARGED",
        "timestamp": datetime.now().isoformat()
    }
    log_with_status("PAYMENT_CHARGED", 201, 
                   tx_id=transaction_id,
                   order_id=order_id,
                   amount=amount,
                   status="CHARGED")
    return jsonify({"status": "charged", "transaction_id": transaction_id}), 201

@app.route('/api/payments/refund', methods=['POST'])
def refund():
    data = request.json or {}
    transaction_id = data.get("transactionId")
    if not transaction_id or transaction_id not in transactions:
        log_with_status("REFUND_FAILED", 404, tx_id=transaction_id)
        return jsonify({"error": "Transaction not found"}), 404
    transactions[transaction_id]["status"] = "REFUNDED"
    log_with_status("PAYMENT_REFUND", 200, 
                   tx_id=transaction_id,
                   status="REFUNDED")
    return jsonify({"status": "refunded", "transaction_id": transaction_id}), 200

@app.route('/api/payments/<transaction_id>', methods=['GET'])
def get_transaction(transaction_id):
    tx = transactions.get(transaction_id)
    if not tx:
        log_with_status("TRANSACTION_NOT_FOUND", 404, tx_id=transaction_id)
        return jsonify({"error": "Transaction not found"}), 404
    log_with_status("TRANSACTION_RETRIEVED", 200, 
                   tx_id=transaction_id,
                   status=tx["status"])
    return jsonify(tx)

@app.route('/api/payments/<transaction_id>/update_status', methods=['PATCH'])
def update_payment_status(transaction_id):
    data = request.json or {}
    tx = transactions.get(transaction_id)
    if not tx:
        log_with_status("PAYMENT_UPDATE_FAILED", 404, tx_id=transaction_id)
        return jsonify({"error": "Transaction not found"}), 404
    new_status = data.get("status", tx["status"])
    tx["status"] = new_status
    log_with_status("PAYMENT_UPDATED", 200, 
                   tx_id=transaction_id,
                   status=new_status)
    return jsonify({"status": "updated", "transaction": tx}), 200

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
    log_with_status("METRICS_ENDPOINT_CALLED", 200)
    return generate_latest(), 200, {'Content-Type': 'text/plain; version=0.0.4; charset=utf-8'}

if __name__ == '__main__':
    print("Registered routes:", app.url_map)
    app.run(port=5004, host='0.0.0.0')
