import time
import requests
import pandas as pd
from automodel import (
    load_data,
    preprocess_data,
    detect_response_time_spike_anomalies,
    detect_response_time_pattern_change,
    detect_error_rate_anomalies
)
from datetime import datetime
from elasticsearch import Elasticsearch
from io import StringIO

# Config
ELASTIC_URL = "http://localhost:9200"
PULL_INDEX = "logstash-microservices-*"
PUSH_INDEX_PREFIX = "anomaly"
FETCH_SIZE = 1000
POLL_INTERVAL = 3  # seconds (5 minutes)

es = Elasticsearch(ELASTIC_URL)

def fetch_logs_from_elasticsearch():
    query = {
        "size": FETCH_SIZE,
        "sort": [{"@timestamp": {"order": "desc"}}],
        "_source": [
            "timestamp", "service", "endpoint", "http_method", "http_status",
            "response_time_ms", "error_flag", "environment", "request_id",
            "trace_id", "span_id", "payload_size_bytes", "cpu_usage_percent",
            "memory_usage_mb", "log_level", "error_message"
        ]
    }
    res = es.search(index=PULL_INDEX, body=query)
    hits = res.get("hits", {}).get("hits", [])
    records = [hit["_source"] for hit in hits]
    return pd.DataFrame(records)

def push_anomalies_to_elasticsearch(anomalies_df, anomaly_type):
    if anomalies_df.empty:
        print(f"[{datetime.now()}] No {anomaly_type} anomalies detected.")
        return

    index_name = f"{PUSH_INDEX_PREFIX}-{anomaly_type}"
    for _, row in anomalies_df.iterrows():
        doc = row.to_dict()
        es.index(index=index_name, document=doc)
    print(f"[{datetime.now()}] Pushed {len(anomalies_df)} {anomaly_type} anomalies to {index_name}.")

def run_pipeline():
    print(f"[{datetime.now()}] Fetching logs from Elasticsearch...")
    df = fetch_logs_from_elasticsearch()

    if df.empty:
        print("No log data received.")
        return

    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df['timestamp_dt'] = df['timestamp']  # compatibility for automodel
    grouped = preprocess_data(df)

    # Anomaly detection
    rt_spike = detect_response_time_spike_anomalies(grouped)
    rt_pattern = detect_response_time_pattern_change(grouped)
    err_rate = detect_error_rate_anomalies(grouped)

    # Push results
    push_anomalies_to_elasticsearch(rt_spike, "response-spike")
    push_anomalies_to_elasticsearch(rt_pattern, "pattern-change")
    push_anomalies_to_elasticsearch(err_rate, "error-rate")

if __name__ == "__main__":
    while True:
        try:
            run_pipeline()
        except Exception as e:
            print(f"[{datetime.now()}] Pipeline error: {e}")
        time.sleep(POLL_INTERVAL)
