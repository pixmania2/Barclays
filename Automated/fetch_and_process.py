import time
import pandas as pd
from elasticsearch import Elasticsearch
from datetime import datetime, timedelta

# Connect to local Elasticsearch
es = Elasticsearch("http://localhost:9200")

# Keep track of the last timestamp
last_fetch_time = datetime.utcnow() - timedelta(minutes=5)

def fetch_new_logs(index="logstash-microservices-*", interval_minutes=5):
    global last_fetch_time
    now = datetime.utcnow()
    
    query = {
        "query": {
            "range": {
                "@timestamp": {
                    "gt": last_fetch_time.isoformat(),
                    "lte": now.isoformat()
                }
            }
        },
        "size": 1000
    }

    response = es.search(index=index, body=query)
    hits = response.get('hits', {}).get('hits', [])

    # Convert to DataFrame
    data = [hit["_source"] for hit in hits]
    df = pd.DataFrame(data)

    last_fetch_time = now
    return df

# LOOP to run every 5 minutes
while True:
    df_logs = fetch_new_logs()
    if not df_logs.empty:
        print(f"\nFetched {len(df_logs)} logs at {datetime.utcnow()}")
        # 🔁 process df_logs with your model here
        # save or push results...
    else:
        print("No new logs found.")
    
    time.sleep(5 * 60)  # sleep for 5 minutes
