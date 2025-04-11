import pandas as pd
import numpy as np
import uuid
import random
from datetime import datetime, timedelta

# Seed for reproducibility
np.random.seed(42)
random.seed(42)

# Define microservices and their endpoints with corresponding HTTP methods
services = {
    "User": [
        {"endpoint": "/api/users/register", "http_method": "POST"},
        {"endpoint": "/api/users/login", "http_method": "POST"},
        {"endpoint": "/api/users/<user_id>", "http_method": "GET"},
        {"endpoint": "/api/users/<user_id>/update", "http_method": "PATCH"}
    ],
    "Restaurant": [
        {"endpoint": "/api/restaurants", "http_method": "GET"},
        {"endpoint": "/api/restaurants", "http_method": "POST"},
        {"endpoint": "/api/restaurants/<restaurant_id>", "http_method": "GET"},
        {"endpoint": "/api/restaurants/<restaurant_id>/update", "http_method": "PATCH"},
        {"endpoint": "/api/restaurants/<restaurant_id>/menu", "http_method": "GET"},
        {"endpoint": "/api/restaurants/<restaurant_id>/menu/add", "http_method": "POST"},
        {"endpoint": "/api/restaurants/<restaurant_id>/menu/update", "http_method": "PATCH"},
        {"endpoint": "/api/restaurants/<restaurant_id>/menu/<menu_item_id>", "http_method": "DELETE"}
    ],
    "Order": [
        {"endpoint": "/api/orders/create", "http_method": "POST"},
        {"endpoint": "/api/orders/<order_id>", "http_method": "GET"},
        {"endpoint": "/api/orders/<order_id>/update_status", "http_method": "PATCH"},
        {"endpoint": "/api/orders/<order_id>/cancel", "http_method": "PATCH"},
        {"endpoint": "/api/orders/user/<user_id>", "http_method": "GET"},
        {"endpoint": "/api/orders/<order_id>/reorder", "http_method": "POST"}
    ],
    "Payment": [
        {"endpoint": "/api/payments/charge", "http_method": "POST"},
        {"endpoint": "/api/payments/refund", "http_method": "POST"},
        {"endpoint": "/api/payments/<transaction_id>", "http_method": "GET"},
        {"endpoint": "/api/payments/<transaction_id>/update_status", "http_method": "PATCH"}
    ],
    "Delivery": [
        {"endpoint": "/api/deliveries/create", "http_method": "POST"},
        {"endpoint": "/api/deliveries/<delivery_id>", "http_method": "GET"},
        {"endpoint": "/api/deliveries/<delivery_id>/update_status", "http_method": "PATCH"},
        {"endpoint": "/api/deliveries/<delivery_id>/update_location", "http_method": "PATCH"},
        {"endpoint": "/api/deliveries/<delivery_id>/reassign", "http_method": "PATCH"},
        {"endpoint": "/api/deliveries/<delivery_id>/tracking", "http_method": "GET"},
        {"endpoint": "/api/deliveries/<delivery_id>/mark_delivered", "http_method": "PATCH"}
    ],
    "Notification": [
        {"endpoint": "/api/notifications/send", "http_method": "POST"},
        {"endpoint": "/api/notifications/user/<user_id>", "http_method": "GET"},
        {"endpoint": "/api/notifications/<notification_id>/read", "http_method": "PATCH"}
    ]
}

# Define possible environments, log levels, browsers, and operating systems
environments = ["on-premises", "cloud", "multi-cloud"]
log_levels = ["INFO", "WARN", "ERROR"]

# List of possible error messages
error_messages = [
    "Database connection failed",
    "Timeout error",
    "Null pointer exception",
    "Invalid request payload",
    "Authentication failed"
]

# List of sample browsers and operating systems
browsers = ["Chrome", "Firefox", "Edge", "Safari", "Opera"]
operating_systems = ["Windows", "macOS", "Linux", "Android", "iOS"]

def simulate_log_record(start_time):
    # Randomly pick a service and one of its endpoints
    service = random.choice(list(services.keys()))
    endpoint_info = random.choice(services[service])
    endpoint = endpoint_info["endpoint"]
    http_method = endpoint_info["http_method"]
    
    # Generate timestamp within the last 24 hours
    timestamp = start_time + timedelta(seconds=random.randint(0, 86400))
    
    # Simulate response time based on service (ms)
    base_rt = {
        "User": 150,
        "Restaurant": 200,
        "Order": 250,
        "Payment": 180,
        "Delivery": 300,
        "Notification": 100
    }[service]
    response_time = np.random.normal(loc=base_rt, scale=base_rt * 0.1)
    
    # Randomly inject spike anomalies (e.g., 5% chance)
    if random.random() < 0.05:
        response_time *= random.uniform(3, 6)
    
    # Determine HTTP status (simulate 90% success, 10% error)
    success_statuses = [200, 201]
    error_statuses = [400, 404, 500, 503]
    if random.random() < 0.4:
        http_status = random.choice(success_statuses)
    else:
        http_status = random.choice(error_statuses)
    
    error_flag = http_status in error_statuses
    
    # Generate additional metrics
    payload_size = random.randint(500, 5000)  # in bytes
    cpu_usage = round(random.uniform(10, 90), 2)  # percent
    memory_usage = round(random.uniform(30, 500), 2)  # in MB
    
    # Determine log level (errors are more likely to be ERROR level)
    if error_flag:
        log_level = random.choice(["ERROR", "WARN"])
        error_message = random.choice(error_messages)
    else:
        log_level = random.choice(["INFO", "WARN"])
        error_message = ""
    
    # Generate Browser with version number
    browser_choice = random.choice(browsers)
    browser_version = f"{browser_choice} {random.randint(70, 100)}.{random.randint(0,9)}.{random.randint(0,9)}"
    
    # Generate Operating System with version number
    os_choice = random.choice(operating_systems)
    os_version = f"{os_choice} {random.randint(10, 15)}.{random.randint(0,9)}"
    
    return {
        "timestamp": timestamp.isoformat(),
        "service": service,
        "endpoint": endpoint,
        "http_method": http_method,
        "http_status": http_status,
        "response_time_ms": round(response_time, 2),
        "error_flag": error_flag,
        "environment": random.choice(environments),
        "request_id": str(uuid.uuid4()),
        "trace_id": str(uuid.uuid4()),
        "span_id": str(uuid.uuid4()),
        "payload_size_bytes": payload_size,
        "cpu_usage_percent": cpu_usage,
        "memory_usage_mb": memory_usage,
        "log_level": log_level,
        "error_message": error_message,
        "Browser": browser_version,
        "Operating System": os_version
    }

# Generate a synthetic dataset with 10,000 records
start_time = datetime.now() - timedelta(days=1)
records = [simulate_log_record(start_time) for _ in range(10000)]
df = pd.DataFrame(records)

# Optionally sort by timestamp
df.sort_values("timestamp", inplace=True)

# Save the dataset to CSV
output_filename = "synthetic_full_datasetlakh.csv"
df.to_csv(output_filename, index=False)
print(f"Synthetic dataset generated and saved as {output_filename}")
