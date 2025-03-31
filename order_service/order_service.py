from flask import Flask, request, jsonify
import logging
import uuid
from datetime import datetime

# If you want to call payment or delivery, you can do:
import requests

app = Flask(__name__)

# In-memory order store
orders = {}

# CSV-like logs
logging.basicConfig(
    format='%(asctime)s %(levelname)s %(message)s',
    level=logging.INFO
)

@app.route('/api/orders/create', methods=['POST'])
def create_order():
    data = request.json or {}
    order_id = str(uuid.uuid4())
    order_record = {
        "id": order_id,
        "userId": data.get("userId"),
        "restaurantId": data.get("restaurantId"),
        "items": data.get("items", []),
        "status": "CREATED",
        "created_at": datetime.now().isoformat()
    }
    orders[order_id] = order_record

    # CSV-like log entry:
    # timestamp, order_id, user_id, restaurant_id, status
    log_entry = f"{datetime.now().isoformat()},{order_id},{order_record['userId']},{order_record['restaurantId']},CREATED"
    app.logger.info(log_entry)

    return jsonify({"status": "order_created", "order": order_record}), 201

@app.route('/api/orders/<order_id>', methods=['GET'])
def get_order(order_id):
    order = orders.get(order_id)
    if not order:
        return jsonify({"error": "Order not found"}), 404
    return jsonify(order)

@app.route('/api/orders/<order_id>/update_status', methods=['PATCH'])
def update_order_status(order_id):
    data = request.json or {}
    order = orders.get(order_id)
    if not order:
        return jsonify({"error": "Order not found"}), 404

    new_status = data.get("status", "CREATED")
    order["status"] = new_status

    # Another CSV-like log entry
    log_entry = f"{datetime.now().isoformat()},{order_id},{order['userId']},{order['restaurantId']},{new_status}"
    app.logger.info(log_entry)

    return jsonify({"status": "order_updated", "order": order})

if __name__ == '__main__':
    # Run on port 5003
    app.run(port=5003, host='0.0.0.0')
