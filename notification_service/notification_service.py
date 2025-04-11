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
notifications = {}

# Status code constants
SUCCESS_STATUSES = [200, 201]
ERROR_STATUSES = [400, 404, 500, 503]

LOG_DIR = "/app/logs"
os.makedirs(LOG_DIR, exist_ok=True)

log_file_path = os.path.join(LOG_DIR, "notification_service.log")

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
        "service": "notification_service",
        **kwargs
    }
    if status_code in SUCCESS_STATUSES:
        app.logger.info(json.dumps(log_entry))
    else:
        app.logger.error(json.dumps(log_entry))
    return log_entry

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
    log_with_status("NOTIFICATION_SENT", 201, 
                   notification_id=notification_id,
                   user_id=notification["userId"],
                   type=notification["type"])
    return jsonify({"status": "sent", "notification": notification}), 201

@app.route('/api/notifications/user/<user_id>', methods=['GET'])
def get_notifications(user_id):
    user_notifications = [n for n in notifications.values() if n["userId"] == user_id]
    log_with_status("NOTIFICATIONS_RETRIEVED", 200, user_id=user_id)
    return jsonify({"userId": user_id, "notifications": user_notifications}), 200

@app.route('/api/notifications/<notification_id>/read', methods=['PATCH'])
def mark_notification_read(notification_id):
    notification = notifications.get(notification_id)
    if not notification:
        log_with_status("NOTIFICATION_READ_FAILED", 404, notification_id=notification_id)
        return jsonify({"error": "Notification not found"}), 404
    notification["read"] = True
    log_with_status("NOTIFICATION_READ", 200, notification_id=notification_id)
    return jsonify({"status": "read", "notification": notification}), 200

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
    app.run(port=5006, host='0.0.0.0')
