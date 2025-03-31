from flask import Flask, request, jsonify
import logging
import uuid
from datetime import datetime

app = Flask(__name__)

# In-memory deliveries
deliveries = {}

# Another custom or K/V logs
logging.basicConfig(
    format='%(asctime)s %(levelname)s %(message)s',
    level=logging.INFO
)

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
        "timestamp": datetime.now().isoformat()
    }

    # K/V style log
    log_entry = f"DELIVERY_LOG delivery_id={delivery_id} order_id={order_id} driver_id={driver_id} status=ASSIGNED"
    app.logger.info(log_entry)

    return jsonify({"status": "assigned", "delivery_id": delivery_id}), 201

@app.route('/api/deliveries/<delivery_id>/update_status', methods=['PATCH'])
def update_delivery_status(delivery_id):
    data = request.json or {}
    delivery = deliveries.get(delivery_id)
    if not delivery:
        return jsonify({"error": "Delivery not found"}), 404

    new_status = data.get("status", "ASSIGNED")
    delivery["status"] = new_status

    log_entry = f"DELIVERY_LOG delivery_id={delivery_id} status={new_status}"
    app.logger.info(log_entry)

    return jsonify({"status": "delivery_updated", "delivery": delivery})

@app.route('/api/deliveries/<delivery_id>', methods=['GET'])
def get_delivery(delivery_id):
    delivery = deliveries.get(delivery_id)
    if not delivery:
        return jsonify({"error": "Delivery not found"}), 404
    return jsonify(delivery)

if __name__ == '__main__':
    # Run on port 5005
    app.run(port=5005, host='0.0.0.0')
