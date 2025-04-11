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
users = {}

LOG_DIR = "/app/logs"
os.makedirs(LOG_DIR, exist_ok=True)

log_file_path = os.path.join(LOG_DIR, "user_service.log")

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
    request.mem = psutil.Process().memory_info().rss / (1024 * 1024)  # in MB

@app.after_request
def record_metrics_and_log(response):
    duration = round((time() - request.start_time) * 1000, 2)  # ms
    error_flag = response.status_code >= 400
    log_level = "ERROR" if error_flag else "INFO"

    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "service": "user_service",
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
        "log_level": log_level,
        "error_message": None
    }

    logger = app.logger.error if error_flag else app.logger.info
    logger(json.dumps(log_entry))
    return response

@app.route('/api/users/register', methods=['POST'])
def register_user():
    try:
        data = request.json or {}
        user_id = str(uuid.uuid4())
        user_record = {
            "id": user_id,
            "name": data.get("name", "Anonymous"),
            "email": data.get("email", ""),
            "password": data.get("password", ""),
            "created_at": datetime.now().isoformat()
        }
        users[user_id] = user_record
        return jsonify({"status": "registered", "user": user_record}), 201
    except Exception as e:
        request.error_message = str(e)
        return jsonify({"error": "Registration failed"}), 500

@app.route('/api/users/login', methods=['POST'])
def login_user():
    try:
        data = request.json or {}
        email = data.get("email", "")
        password = data.get("password", "")
        for user in users.values():
            if user["email"] == email and user["password"] == password:
                return jsonify({"status": "logged_in", "user": user}), 200
        return jsonify({"error": "Invalid credentials"}), 401
    except Exception as e:
        request.error_message = str(e)
        return jsonify({"error": "Login failed"}), 500

@app.route('/api/users/<user_id>', methods=['GET'])
def get_user(user_id):
    try:
        user = users.get(user_id)
        if not user:
            return jsonify({"error": "User not found"}), 404
        return jsonify(user)
    except Exception as e:
        request.error_message = str(e)
        return jsonify({"error": "Error retrieving user"}), 500

@app.route('/api/users/<user_id>/update', methods=['PATCH'])
def update_user(user_id):
    try:
        data = request.json or {}
        user = users.get(user_id)
        if not user:
            return jsonify({"error": "User not found"}), 404
        user["name"] = data.get("name", user["name"])
        user["email"] = data.get("email", user["email"])
        return jsonify({"status": "updated", "user": user}), 200
    except Exception as e:
        request.error_message = str(e)
        return jsonify({"error": "Update failed"}), 500

@app.route('/hello')
def hello():
    return "Hello, World!", 200

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
    return generate_latest(), 200, {'Content-Type': 'text/plain; version=0.0.4; charset=utf-8'}

if __name__ == '__main__':
    print("Registered routes:", app.url_map)
    app.run(port=5001, host='0.0.0.0')
