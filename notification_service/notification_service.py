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
notifications = {}

LOG_DIR = "/app/logs"
os.makedirs(LOG_DIR, exist_ok=True)

log_file_path = os.path.join(LOG_DIR, "notification_service.log")

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
        "service": "notification_service",
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

@app.route('/api/notifications/send', methods=['POST'])
def send_notification():
    data = request.json or {}
    notification_id = str(uuid.uuid4())
    notification = {
        "id": notification_id,
        "userId": data.get("userId"),
        "message": data.get("message", ""),
        "type": data.get("type", "info"),
        "sent_at": datetime.now().isoformat(),
        "read": False
    }
    notifications[notification_id] = notification
    return jsonify({"status": "sent", "notification": notification}), 201

@app.route('/api/notifications/user/<user_id>', methods=['GET'])
def get_notifications(user_id):
    user_notifications = [n for n in notifications.values() if n["userId"] == user_id]
    return jsonify({"userId": user_id, "notifications": user_notifications}), 200

@app.route('/api/notifications/<notification_id>/read', methods=['PATCH'])
def mark_notification_read(notification_id):
    notification = notifications.get(notification_id)
    if not notification:
        return jsonify({"error": "Notification not found"}), 404
    notification["read"] = True
    return jsonify({"status": "read", "notification": notification}), 200

@app.route('/metrics')
def metrics():
    return generate_latest(), 200, {'Content-Type': 'text/plain; version=0.0.4; charset=utf-8'}

if __name__ == '__main__':
    print("Registered routes:", app.url_map)
    app.run(port=5006, host='0.0.0.0')
