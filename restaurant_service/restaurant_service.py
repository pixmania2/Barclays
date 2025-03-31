from flask import Flask, request, jsonify
import logging
import uuid
from datetime import datetime

app = Flask(__name__)

# In-memory store for restaurants
restaurants = {}

# Plaintext logs
logging.basicConfig(
    format='%(asctime)s %(levelname)s %(message)s',
    level=logging.INFO
)

@app.route('/api/restaurants', methods=['GET'])
def list_restaurants():
    return jsonify(list(restaurants.values()))

@app.route('/api/restaurants', methods=['POST'])
def create_restaurant():
    data = request.json or {}
    restaurant_id = str(uuid.uuid4())
    restaurant_record = {
        "id": restaurant_id,
        "name": data.get("name", "Unnamed Restaurant"),
        "location": data.get("location", "Unknown"),
        "created_at": datetime.now().isoformat()
    }
    restaurants[restaurant_id] = restaurant_record

    # Plaintext logging example
    app.logger.info(f"RESTAURANT_CREATED: {restaurant_id} at {datetime.now().isoformat()}")

    return jsonify({"status": "created", "restaurant": restaurant_record}), 201

@app.route('/api/restaurants/<restaurant_id>/menu', methods=['GET'])
def get_menu(restaurant_id):
    restaurant = restaurants.get(restaurant_id)
    if not restaurant:
        return jsonify({"error": "Restaurant not found"}), 404

    # Mocked menu for demonstration
    menu_items = ["Pizza", "Burger", "Salad"]
    return jsonify({"restaurant_id": restaurant_id, "menu": menu_items})

if __name__ == '__main__':
    # Run on port 5002
    app.run(port=5002, host='0.0.0.0')
