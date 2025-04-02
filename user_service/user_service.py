from flask import Flask, request, jsonify
import logging
import uuid
from datetime import datetime
from logging.handlers import RotatingFileHandler
import os
import json

app = Flask(__name__)
users = {}

LOG_DIR = "/app/logs"
os.makedirs(LOG_DIR, exist_ok=True)

log_file_path = os.path.join(LOG_DIR, "user_service.log")

logging.basicConfig(format='%(asctime)s %(levelname)s %(message)s', level=logging.INFO, handlers=[
    RotatingFileHandler(log_file_path, maxBytes=1000000, backupCount=3),
    logging.StreamHandler()
])

@app.route('/api/users/register', methods=['POST'])
def register_user():
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
    log_entry = {
        "event": "USER_REGISTERED",
        "user_id": user_id,
        "timestamp": datetime.now().isoformat(),
        "service": "user_service"
    }
    app.logger.info(json.dumps(log_entry))
    return jsonify({"status": "registered", "user": user_record}), 201

@app.route('/api/users/login', methods=['POST'])
def login_user():
    data = request.json or {}
    email = data.get("email", "")
    password = data.get("password", "")
    for user in users.values():
        if user["email"] == email and user["password"] == password:
            log_entry = {
                "event": "USER_LOGGED_IN",
                "user_id": user["id"],
                "timestamp": datetime.now().isoformat(),
                "service": "user_service"
            }
            app.logger.info(json.dumps(log_entry))
            return jsonify({"status": "logged_in", "user": user}), 200
    log_entry = {
        "event": "LOGIN_FAILED",
        "email": email,
        "timestamp": datetime.now().isoformat(),
        "service": "user_service"
    }
    app.logger.warning(json.dumps(log_entry))
    return jsonify({"error": "Invalid credentials"}), 401

@app.route('/api/users/<user_id>', methods=['GET'])
def get_user(user_id):
    user = users.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404
    return jsonify(user)

@app.route('/api/users/<user_id>/update', methods=['PATCH'])
def update_user(user_id):
    data = request.json or {}
    user = users.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404
    user["name"] = data.get("name", user["name"])
    user["email"] = data.get("email", user["email"])
    log_entry = {
        "event": "USER_UPDATED",
        "user_id": user_id,
        "timestamp": datetime.now().isoformat(),
        "service": "user_service"
    }
    app.logger.info(json.dumps(log_entry))
    return jsonify({"status": "updated", "user": user}), 200

@app.route('/hello')
def hello():
    return "Hello, World!", 200

# Prometheus monitoring
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
    return generate_latest(), 200, {'Content-Type': 'text/plain; version=0.0.4; charset=utf-8'}

if __name__ == '__main__':
    print("Registered routes:", app.url_map)
    app.run(port=5001, host='0.0.0.0')
