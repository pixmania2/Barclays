from flask import Flask, request, jsonify
import logging
import uuid
from datetime import datetime

app = Flask(__name__)

# In-memory transactions
transactions = {}

# Custom text logs
logging.basicConfig(
    format='%(asctime)s %(levelname)s %(message)s',
    level=logging.INFO
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

    # Custom text log format:
    # "PAYMENT_LOG | tx_id=... | order_id=... | amount=... | status=..."
    log_entry = f"PAYMENT_LOG | tx_id={transaction_id} | order_id={order_id} | amount={amount} | status=CHARGED"
    app.logger.info(log_entry)

    return jsonify({"status": "charged", "transaction_id": transaction_id}), 201

@app.route('/api/payments/refund', methods=['POST'])
def refund():
    data = request.json or {}
    transaction_id = data.get("transactionId")
    if not transaction_id or transaction_id not in transactions:
        return jsonify({"error": "Transaction not found"}), 404

    transactions[transaction_id]["status"] = "REFUNDED"
    log_entry = f"PAYMENT_LOG | tx_id={transaction_id} | status=REFUNDED"
    app.logger.info(log_entry)

    return jsonify({"status": "refunded", "transaction_id": transaction_id}), 200

@app.route('/api/payments/<transaction_id>', methods=['GET'])
def get_transaction(transaction_id):
    tx = transactions.get(transaction_id)
    if not tx:
        return jsonify({"error": "Transaction not found"}), 404
    return jsonify(tx)

if __name__ == '__main__':
    # Run on port 5004
    app.run(port=5004, host='0.0.0.0')
