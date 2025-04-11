from flask import Flask, request, jsonify
import logging
import uuid
import json
from datetime import datetime
from logging.handlers import RotatingFileHandler
import os
import psutil
from flask_cors import CORS
from time import time
from prometheus_client import Counter, Histogram, generate_latest

app = Flask(__name__)
CORS(app)
transactions = {}

LOG_DIR = "/app/logs"
os.makedirs(LOG_DIR, exist_ok=True)

log_file_path = os.path.join(LOG_DIR, "payment_service.log")

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
        "service": "payment_service",
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
    return jsonify({"status": "charged", "transaction_id": transaction_id}), 201

@app.route('/api/payments/refund', methods=['POST'])
def refund():
    data = request.json or {}
    transaction_id = data.get("transactionId")
    if not transaction_id or transaction_id not in transactions:
        return jsonify({"error": "Transaction not found"}), 404
    transactions[transaction_id]["status"] = "REFUNDED"
    return jsonify({"status": "refunded", "transaction_id": transaction_id}), 200

@app.route('/api/payments/<transaction_id>', methods=['GET'])
def get_transaction(transaction_id):
    tx = transactions.get(transaction_id)
    if not tx:
        return jsonify({"error": "Transaction not found"}), 404
    return jsonify(tx)

@app.route('/api/payments/<transaction_id>/update_status', methods=['PATCH'])
def update_payment_status(transaction_id):
    data = request.json or {}
    tx = transactions.get(transaction_id)
    if not tx:
        return jsonify({"error": "Transaction not found"}), 404
    new_status = data.get("status", tx["status"])
    tx["status"] = new_status
    return jsonify({"status": "updated", "transaction": tx}), 200

@app.route('/metrics')
def metrics():
    return generate_latest(), 200, {'Content-Type': 'text/plain; version=0.0.4; charset=utf-8'}

if __name__ == '__main__':
    print("Registered routes:", app.url_map)
    app.run(port=5004, host='0.0.0.0')
