from flask import Flask, request, jsonify
import logging
import uuid
from datetime import datetime

app = Flask(__name__)
notifications = {}

logging.basicConfig(format='%(asctime)s %(levelname)s %(message)s', level=logging.INFO)

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
    app.logger.info(f"NOTIFICATION_SENT: {notification_id} to user {notification['userId']} at {datetime.now().isoformat()}")
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
    app.logger.info(f"NOTIFICATION_READ: {notification_id} at {datetime.now().isoformat()}")
    return jsonify({"status": "read", "notification": notification}), 200

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
    app.run(port=5006, host='0.0.0.0')

