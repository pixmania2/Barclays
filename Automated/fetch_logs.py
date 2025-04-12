from elasticsearch import Elasticsearch
from elasticsearch.helpers import scan
import pandas as pd

def fetch_logs(index_pattern="logstash-microservices-*", size=10000):
    es = Elasticsearch("http://localhost:9200")
    
    desired_fields = [
        "timestamp", "service", "endpoint", "http_method", "http_status",
        "response_time_ms", "error_flag", "environment", "request_id",
        "trace_id", "span_id", "payload_size_bytes", "cpu_usage_percent",
        "memory_usage_mb", "log_level", "error_message"
    ]
    
    results = scan(es, index=index_pattern, query={"query": {"match_all": {}}}, size=size)
    
    logs = []
    for res in results:
        src = res["_source"]
        if all(field in src for field in desired_fields):
            logs.append({field: src.get(field) for field in desired_fields})
    
    return pd.DataFrame(logs)

