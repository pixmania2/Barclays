import pandas as pd
import numpy as np
import random
from datetime import datetime, timedelta

# Seed for reproducibility
np.random.seed(42)
random.seed(42)

# Define microservices and their endpoints
services = {
    "User": [
        {"endpoint": "/api/users/register", "method": "POST"},
        {"endpoint": "/api/users/login", "method": "POST"},
        {"endpoint": "/api/users/<user_id>", "method": "GET"},
        {"endpoint": "/api/users/<user_id>/update", "method": "PATCH"}
    ],
    "Restaurant": [
        {"endpoint": "/api/restaurants", "method": "GET"},
        {"endpoint": "/api/restaurants", "method": "POST"},
        {"endpoint": "/api/restaurants/<restaurant_id>", "method": "GET"},
        {"endpoint": "/api/restaurants/<restaurant_id>/update", "method": "PATCH"},
        {"endpoint": "/api/restaurants/<restaurant_id>/menu", "method": "GET"},
        {"endpoint": "/api/restaurants/<restaurant_id>/menu/add", "method": "POST"},
        {"endpoint": "/api/restaurants/<restaurant_id>/menu/update", "method": "PATCH"},
        {"endpoint": "/api/restaurants/<restaurant_id>/menu/<menu_item_id>", "method": "DELETE"}
    ],
    "Order": [
        {"endpoint": "/api/orders/create", "method": "POST"},
        {"endpoint": "/api/orders/<order_id>", "method": "GET"},
        {"endpoint": "/api/orders/<order_id>/update_status", "method": "PATCH"},
        {"endpoint": "/api/orders/<order_id>/cancel", "method": "PATCH"},
        {"endpoint": "/api/orders/user/<user_id>", "method": "GET"},
        {"endpoint": "/api/orders/<order_id>/reorder", "method": "POST"}
    ],
    "Payment": [
        {"endpoint": "/api/payments/charge", "method": "POST"},
        {"endpoint": "/api/payments/refund", "method": "POST"},
        {"endpoint": "/api/payments/<transaction_id>", "method": "GET"},
        {"endpoint": "/api/payments/<transaction_id>/update_status", "method": "PATCH"}
    ],
    "Delivery": [
        {"endpoint": "/api/deliveries/create", "method": "POST"},
        {"endpoint": "/api/deliveries/<delivery_id>", "method": "GET"},
        {"endpoint": "/api/deliveries/<delivery_id>/update_status", "method": "PATCH"},
        {"endpoint": "/api/deliveries/<delivery_id>/update_location", "method": "PATCH"},
        {"endpoint": "/api/deliveries/<delivery_id>/reassign", "method": "PATCH"},
        {"endpoint": "/api/deliveries/<delivery_id>/tracking", "method": "GET"},
        {"endpoint": "/api/deliveries/<delivery_id>/mark_delivered", "method": "PATCH"}
    ],
    "Notification": [
        {"endpoint": "/api/notifications/send", "method": "POST"},
        {"endpoint": "/api/notifications/user/<user_id>", "method": "GET"},
        {"endpoint": "/api/notifications/<notification_id>/read", "method": "PATCH"}
    ]
}

# Define environments
environments = ["on-premises", "cloud", "multi-cloud"]

# Define possible status codes
success_codes = [200, 201]
error_codes = [400, 404, 500, 503]
status_code_choices = success_codes + error_codes

# Function to simulate a log record for an API call
def simulate_log(start_time):
    # Randomly pick a service and one of its endpoints
    service = random.choice(list(services.keys()))
    ep = random.choice(services[service])
    method = ep["method"]
    endpoint = ep["endpoint"]
    env = random.choice(environments)
    
    # Simulate timestamp (spread over last 24 hours)
    timestamp = start_time + timedelta(seconds=random.randint(0, 86400))
    
    # Base response time (in ms) with a slight variation per service
    base_rt = {
        "User": 150,
        "Restaurant": 200,
        "Order": 250,
        "Payment": 180,
        "Delivery": 300,
        "Notification": 100
    }[service]
    response_time = np.random.normal(loc=base_rt, scale=base_rt * 0.1)
    
    # Inject occasional anomalies in response time (spikes)
    if random.random() < 0.05:  # 5% chance of spike anomaly
        response_time *= random.uniform(3, 6)
    
    # Determine status code (simulate more success than errors)
    if random.random() < 0.9:
        status_code = random.choice(success_codes)
    else:
        status_code = random.choice(error_codes)
    
    error_flag = status_code in error_codes
    
    # Create a unique request ID
    request_id = f"{service[:2].upper()}_{np.random.randint(100000,999999)}"
    
    return {
        "timestamp": timestamp.isoformat(),
        "service": service,
        "endpoint": endpoint,
        "method": method,
        "environment": env,
        "status_code": status_code,
        "response_time_ms": round(response_time, 2),
        "error": error_flag,
        "request_id": request_id
    }

# Generate synthetic dataset with 1000 records
start_time = datetime.now() - timedelta(days=1)
records = [simulate_log(start_time) for _ in range(1000)]
df = pd.DataFrame(records)

# Optionally, sort the dataframe by timestamp
df.sort_values("timestamp", inplace=True)

# Save the dataframe to CSV
output_filename = "synthetic_dataset.csv"
df.to_csv(output_filename, index=False)

print(f"Synthetic dataset generated and saved as {output_filename}")
