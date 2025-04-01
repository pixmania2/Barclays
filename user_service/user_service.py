from flask import Flask, request, jsonify
import logging
import uuid
from datetime import datetime

app = Flask(__name__)
users = {}

logging.basicConfig(format='%(asctime)s %(levelname)s %(message)s', level=logging.INFO)

@app.route('/api/users/register', methods=['POST'])
def register_user():
    data = request.json or {}
    user_id = str(uuid.uuid4())
    user_record = {
        "id": user_id,
        "name": data.get("name", "Anonymous"),
        "email": data.get("email", ""),
        "password": data.get("password", ""),  # For demo only (not secure)
        "created_at": datetime.now().isoformat()
    }
    users[user_id] = user_record
    app.logger.info({"event": "USER_REGISTERED", "user_id": user_id, "timestamp": datetime.now().isoformat()})
    return jsonify({"status": "registered", "user": user_record}), 201

@app.route('/api/users/login', methods=['POST'])
def login_user():
    data = request.json or {}
    email = data.get("email", "")
    password = data.get("password", "")
    for user in users.values():
        if user["email"] == email and user["password"] == password:
            app.logger.info({"event": "USER_LOGGED_IN", "user_id": user["id"], "timestamp": datetime.now().isoformat()})
            return jsonify({"status": "logged_in", "user": user}), 200
    app.logger.warning({"event": "LOGIN_FAILED", "email": email, "timestamp": datetime.now().isoformat()})
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
    app.logger.info({"event": "USER_UPDATED", "user_id": user_id, "timestamp": datetime.now().isoformat()})
    return jsonify({"status": "updated", "user": user}), 200

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

@app.route('/hello')
def hello():
    return "Hello, World!", 200

# Expose a /metrics endpoint for Prometheus to scrape
@app.route('/metrics')
def metrics():
    return generate_latest(), 200, {'Content-Type': 'text/plain; version=0.0.4; charset=utf-8'}
from prometheus_client import generate_latest



if __name__ == '__main__':
    print("Registered routes:", app.url_map)
    app.run(port=5001, host='0.0.0.0')


