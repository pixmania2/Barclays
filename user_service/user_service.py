from flask import Flask, request, jsonify
import logging
import uuid
from datetime import datetime

app = Flask(__name__)

# In-memory user store
users = {}

# Configure JSON-like logging
logging.basicConfig(
    format='%(asctime)s %(levelname)s %(message)s',
    level=logging.INFO
)

@app.route('/api/users/register', methods=['POST'])
def register_user():
    data = request.json or {}
    user_id = str(uuid.uuid4())
    user_record = {
        "id": user_id,
        "name": data.get("name", "Anonymous"),
        "email": data.get("email", ""),
        "created_at": datetime.now().isoformat()
    }
    users[user_id] = user_record

    # Log in a JSON-like format
    app.logger.info({
        "event": "USER_REGISTERED",
        "user_id": user_id,
        "timestamp": datetime.now().isoformat()
    })

    return jsonify({"status": "registered", "user": user_record}), 201

@app.route('/api/users/<user_id>', methods=['GET'])
def get_user(user_id):
    user = users.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404
    return jsonify(user)

if __name__ == '__main__':
    # Run on port 5001
    app.run(port=5001, host='0.0.0.0')
