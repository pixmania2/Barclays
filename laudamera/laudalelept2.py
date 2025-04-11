import pandas as pd
import numpy as np
import random
from datetime import datetime, timedelta
from sklearn.cluster import KMeans
from scipy.stats import genpareto

# =============================================================================
# STEP 1: Load and Prepare the Synthetic Dataset
# =============================================================================
# Assume your synthetic dataset (with 10,000 rows, including "Browser", "Operating System", etc.)
# is stored in a CSV file. Uncomment the next line if needed.
df = pd.read_csv("./synthetic_full_dataset.csv")

# For demonstration purposes, if you want to test with a smaller dataset, you can generate sample data.
# (Comment/remove this block if you already have your dataset.)
"""
import uuid
def generate_sample_log_record(start_time):
    timestamp = start_time + timedelta(seconds=random.randint(0, 86400))
    return {
        "timestamp": timestamp.isoformat(),
        "http_status": random.choice([200, 500, 500, 200, 404, 403, 503]),
        "http_method": random.choice(["GET", "POST", "PATCH"]),
        "Browser": random.choice(["Safari 13.1.2", "Chrome 90.0.4430", "Firefox 88.0", "Edge 91.0", "Opera 75.0", "UNKNOWN"]),
        "cpu_usage_percent": round(random.uniform(10, 90), 2),
        "memory_usage_mb": round(random.uniform(30, 500), 2)
    }

start_time = datetime.now() - timedelta(days=1)
records = [generate_sample_log_record(start_time) for _ in range(1000)]
df = pd.DataFrame(records)
"""

# Ensure that the timestamp is parsed as datetime; store it in a new column for filtering.
df["timestamp_dt"] = pd.to_datetime(df["timestamp"])

# =============================================================================
# STEP 2: Define Basic Condition Functions for the Metrics
# =============================================================================
def count_status(df, status_code):
    """Return the count of log records where http_status equals the given status_code."""
    return df[df["http_status"] == status_code].shape[0]

def count_combined_4xx_5xx(df):
    """Return the count where http_status is between 400 and 599 (inclusive)."""
    return df[df["http_status"].between(400, 599)].shape[0]

def count_post_safari(df):
    """Return the count of logs with POST method and Browser containing 'Safari'."""
    return df[(df["http_method"] == "POST") & (df["Browser"].str.contains("Safari", case=False))].shape[0]

def count_unknown_browser(df):
    """Return the count of logs where the Browser string is 'UNKNOWN' (case-insensitive)."""
    return df[df["Browser"].str.upper() == "UNKNOWN"].shape[0]

def avg_cpu_usage(df):
    """Return the average CPU usage over the window (0 if empty)."""
    return df["cpu_usage_percent"].mean() if not df.empty else 0

# =============================================================================
# STEP 3: Hybrid Approach Functions (Clustering + EVT)
# =============================================================================
def compute_sliding_window_metrics(df, window_minutes, condition_func):
    """
    Slide a window of length 'window_minutes' (in minutes) over the data.
    Returns a list of metric values computed by condition_func for each window.
    """
    df_local = df.copy()
    # Make sure timestamps are datetime objects.
    df_local["timestamp_dt"] = pd.to_datetime(df_local["timestamp_dt"])
    
    window_delta = timedelta(minutes=window_minutes)
    start_time = df_local["timestamp_dt"].min()
    end_time = df_local["timestamp_dt"].max()
    metric_values = []
    
    current_time = start_time
    while current_time + window_delta <= end_time:
        window_df = df_local[(df_local["timestamp_dt"] >= current_time) & (df_local["timestamp_dt"] < current_time + window_delta)]
        value = condition_func(window_df)
        metric_values.append(value)
        current_time += timedelta(minutes=1)
    
    return np.array(metric_values)

def compute_hybrid_threshold(df, window_minutes, condition_func, ev_target_quantile):
    """
    Uses a hybrid approach (clustering + EVT) to compute a threshold for a given metric.
    - Compute the metric over sliding windows.
    - Cluster the metric values (KMeans, k=2) and select the cluster with lower mean as normal behavior.
    - Set a baseline u as a high percentile (e.g., 90th) of the normal cluster.
    - Fit a Generalized Pareto Distribution (GPD) to the exceedances (values - u).
    - Return the threshold u + the quantile from the fitted GPD.
    
    Args:
      df: DataFrame of log data.
      window_minutes: Length of the sliding window.
      condition_func: Function to compute metric from a DataFrame.
      ev_target_quantile: The target quantile (e.g., 0.99 or 0.995) for EVT threshold.
      
    Returns:
      The computed hybrid threshold (integer).
    """
    # Compute sliding window metrics.
    metric_values = compute_sliding_window_metrics(df, window_minutes, condition_func)
    if len(metric_values) == 0:
        return 0

    # Reshape for clustering (KMeans requires 2D array)
    X = metric_values.reshape(-1, 1)
    # Use KMeans with k=2 to separate normal vs. elevated behavior.
    kmeans = KMeans(n_clusters=2, random_state=42).fit(X)
    labels = kmeans.labels_
    # Identify cluster centers; select the cluster with the lower center as normal.
    centers = kmeans.cluster_centers_.flatten()
    normal_cluster_label = np.argmin(centers)
    
    # Select normal cluster values.
    normal_values = metric_values[labels == normal_cluster_label]
    if len(normal_values) == 0:
        return int(np.percentile(metric_values, ev_target_quantile * 100))
    
    # Set baseline u as the 90th percentile of normal cluster values.
    u = np.percentile(normal_values, 90)
    # Compute exceedances: values above u.
    exceedances = normal_values[normal_values > u] - u
    
    # If there are not enough exceedances, fall back to a high percentile of normal values.
    if len(exceedances) < 10:
        return int(np.percentile(normal_values, ev_target_quantile * 100))
    
    # Fit the Generalized Pareto Distribution (GPD) to the exceedances.
    shape, loc, scale = genpareto.fit(exceedances)
    # Use the fitted GPD to compute the quantile for the exceedances.
    # Note: ev_target_quantile is expressed relative to the tail; here we use it directly.
    q = genpareto.ppf(ev_target_quantile, shape, loc=loc, scale=scale)
    threshold = u + q
    return int(threshold)

# =============================================================================
# STEP 4: Compute Hybrid Thresholds for Each Rule
# =============================================================================
# For each rule we define:
#   - a window (in minutes)
#   - a condition function (e.g., count_status 500, 404, etc.)
#   - a target quantile for EVT (e.g., 0.99 for Warning, 0.995 for Critical)
#
# You can adjust these quantiles based on how strict you want the rule to be.

# 500 errors (20-minute window)
hybrid_500_warning   = compute_hybrid_threshold(df, 20, lambda d: count_status(d, 500), 0.99)
hybrid_500_critical  = compute_hybrid_threshold(df, 20, lambda d: count_status(d, 500), 0.995)

# 404 errors (20-minute window)
hybrid_404_warning   = compute_hybrid_threshold(df, 20, lambda d: count_status(d, 404), 0.99)
hybrid_404_critical  = compute_hybrid_threshold(df, 20, lambda d: count_status(d, 404), 0.995)

# 403 errors (20-minute window)
hybrid_403_warning   = compute_hybrid_threshold(df, 20, lambda d: count_status(d, 403), 0.99)
hybrid_403_critical  = compute_hybrid_threshold(df, 20, lambda d: count_status(d, 403), 0.995)

# Combined 4xx & 5xx errors (20-minute window)
hybrid_combined_warning  = compute_hybrid_threshold(df, 20, count_combined_4xx_5xx, 0.99)
hybrid_combined_critical = compute_hybrid_threshold(df, 20, count_combined_4xx_5xx, 0.995)

# POST from Safari (15-minute window)
hybrid_post_safari_warning = compute_hybrid_threshold(df, 15, count_post_safari, 0.99)

# Unknown Browsers (30-minute window)
hybrid_unknown_warning = compute_hybrid_threshold(df, 30, count_unknown_browser, 0.99)

# New extra rule: High CPU usage (average over 10 minutes)
# For average metrics, we can use a similar approach.
def compute_sliding_window_avg(df, window_minutes, avg_func):
    df_local = df.copy()
    df_local["timestamp_dt"] = pd.to_datetime(df_local["timestamp_dt"])
    
    window_delta = timedelta(minutes=window_minutes)
    start_time = df_local["timestamp_dt"].min()
    end_time = df_local["timestamp_dt"].max()
    avg_values = []
    
    current_time = start_time
    while current_time + window_delta <= end_time:
        window_df = df_local[(df_local["timestamp_dt"] >= current_time) & (df_local["timestamp_dt"] < current_time + window_delta)]
        avg_val = avg_func(window_df)
        avg_values.append(avg_val)
        current_time += timedelta(minutes=1)
    
    return np.array(avg_values)

def compute_hybrid_avg_threshold(df, window_minutes, avg_func, ev_target_quantile):
    avg_values = compute_sliding_window_avg(df, window_minutes, avg_func)
    if len(avg_values) == 0:
        return 0
    # For simplicity, we use a fixed percentile of the whole distribution.
    # For a more complex approach, you could also cluster and fit EVT to the average values.
    return round(np.percentile(avg_values, ev_target_quantile*100), 2)

hybrid_cpu_warning = compute_hybrid_avg_threshold(df, 10, avg_cpu_usage, 0.99)

# =============================================================================
# STEP 5: Define the Rule Class and Create Rule Objects
# =============================================================================
class Rule:
    def __init__(self, rule_id, description, window_minutes, condition_func, threshold, level="Warning"):
        """
        rule_id: Identifier for the rule.
        description: Text description of the rule.
        window_minutes: Length of the evaluation window.
        condition_func: Function to compute the metric over a window.
        threshold: The threshold computed from the hybrid approach.
        level: "Warning" or "Critical".
        """
        self.rule_id = rule_id
        self.description = description
        self.window_minutes = window_minutes
        self.condition_func = condition_func
        self.threshold = threshold
        self.level = level

    def evaluate(self, df, current_time):
        """
        Evaluate the rule over a time window ending at current_time.
        Returns (triggered: bool, actual_metric: value).
        """
        window_start = current_time - timedelta(minutes=self.window_minutes)
        window_df = df[(df["timestamp_dt"] >= window_start) & (df["timestamp_dt"] <= current_time)]
        metric = self.condition_func(window_df)
        return (metric >= self.threshold, metric)

    def __str__(self):
        return (f"Rule {self.rule_id} ({self.level}): {self.description} | "
                f"Window: {self.window_minutes} min | Threshold: {self.threshold}")

# Create rule objects using the hybrid thresholds.
rules = []
rules.append(Rule(
    rule_id=1,
    description=f"Internal Server Errors (500) - Warning: if count >= {hybrid_500_warning} in 20 minutes",
    window_minutes=20,
    condition_func=lambda d: count_status(d, 500),
    threshold=hybrid_500_warning,
    level="Warning"
))
rules.append(Rule(
    rule_id=2,
    description=f"Internal Server Errors (500) - Critical: if count >= {hybrid_500_critical} in 20 minutes",
    window_minutes=20,
    condition_func=lambda d: count_status(d, 500),
    threshold=hybrid_500_critical,
    level="Critical"
))
rules.append(Rule(
    rule_id=3,
    description=f"404 Not Found - Warning: if count >= {hybrid_404_warning} in 20 minutes",
    window_minutes=20,
    condition_func=lambda d: count_status(d, 404),
    threshold=hybrid_404_warning,
    level="Warning"
))
rules.append(Rule(
    rule_id=4,
    description=f"404 Not Found - Critical: if count >= {hybrid_404_critical} in 20 minutes",
    window_minutes=20,
    condition_func=lambda d: count_status(d, 404),
    threshold=hybrid_404_critical,
    level="Critical"
))
rules.append(Rule(
    rule_id=5,
    description=f"403 Forbidden - Warning: if count >= {hybrid_403_warning} in 20 minutes",
    window_minutes=20,
    condition_func=lambda d: count_status(d, 403),
    threshold=hybrid_403_warning,
    level="Warning"
))
rules.append(Rule(
    rule_id=6,
    description=f"403 Forbidden - Critical: if count >= {hybrid_403_critical} in 20 minutes",
    window_minutes=20,
    condition_func=lambda d: count_status(d, 403),
    threshold=hybrid_403_critical,
    level="Critical"
))
rules.append(Rule(
    rule_id=7,
    description=f"Combined 4xx & 5xx Errors - Warning: if count >= {hybrid_combined_warning} in 20 minutes",
    window_minutes=20,
    condition_func=count_combined_4xx_5xx,
    threshold=hybrid_combined_warning,
    level="Warning"
))
rules.append(Rule(
    rule_id=8,
    description=f"Combined 4xx & 5xx Errors - Critical: if count >= {hybrid_combined_critical} in 20 minutes",
    window_minutes=20,
    condition_func=count_combined_4xx_5xx,
    threshold=hybrid_combined_critical,
    level="Critical"
))
rules.append(Rule(
    rule_id=9,
    description=f"POST Requests from Safari - Warning: if count >= {hybrid_post_safari_warning} in 15 minutes",
    window_minutes=15,
    condition_func=count_post_safari,
    threshold=hybrid_post_safari_warning,
    level="Warning"
))
rules.append(Rule(
    rule_id=10,
    description=f"Requests from UNKNOWN Browsers - Warning: if count >= {hybrid_unknown_warning} in 30 minutes",
    window_minutes=30,
    condition_func=count_unknown_browser,
    threshold=hybrid_unknown_warning,
    level="Warning"
))
rules.append(Rule(
    rule_id=11,
    description=f"High CPU Usage - Warning: if average CPU usage >= {hybrid_cpu_warning}% in 10 minutes",
    window_minutes=10,
    condition_func=lambda d: avg_cpu_usage(d),
    threshold=hybrid_cpu_warning,
    level="Warning"
))

# =============================================================================
# STEP 6: Print All Defined Rules and Their Descriptions
# =============================================================================
print("Defined Rules:\n")
for rule in rules:
    print(rule)

# =============================================================================
# STEP 7: Let the User Choose to Club (Combine) Rules
# =============================================================================
print("\nYou can club (combine) two or more rules together to create a compound alert.")
print("Enter the rule IDs (comma separated) that you want to combine (or press Enter to skip):")
user_input = input("Your selection: ").strip()

combined_rule = None
if user_input:
    try:
        selected_ids = [int(x.strip()) for x in user_input.split(',') if x.strip().isdigit()]
        selected_rules = [r for r in rules if r.rule_id in selected_ids]
        if len(selected_rules) < 2:
            print("You must choose two or more rules to combine. No combined rule will be created.")
        else:
            combined_description = "Combined Rule (" + " AND ".join([str(r.rule_id) for r in selected_rules]) + "): "
            combined_description += "Alert if all selected rules are triggered in their respective time windows."
            
            class CombinedRule:
                def __init__(self, description, rules):
                    self.description = description
                    self.rules = rules
                def evaluate(self, df, current_time):
                    results = [r.evaluate(df, current_time)[0] for r in self.rules]
                    metrics = [r.evaluate(df, current_time)[1] for r in self.rules]
                    return (all(results), metrics)
                def __str__(self):
                    return self.description
            
            combined_rule = CombinedRule(combined_description, selected_rules)
            print("\nCombined Rule Created:")
            print(combined_rule)
    except Exception as e:
        print("Invalid input. No combined rule will be created.")
else:
    print("No combined rule created.")

# =============================================================================
# STEP 8: Evaluate the Rules and Display Alerts
# =============================================================================
current_time = df["timestamp_dt"].max()
print("\nRule Evaluation Results:")
for rule in rules:
    triggered, metric = rule.evaluate(df, current_time)
    status = "TRIGGERED" if triggered else "Not triggered"
    print(f"Rule {rule.rule_id}: {status} (Observed: {metric}, Threshold: {rule.threshold})")

if combined_rule:
    combined_triggered, metrics = combined_rule.evaluate(df, current_time)
    status = "TRIGGERED" if combined_triggered else "Not triggered"
    print(f"\nCombined Rule Evaluation: {status}")
    print("Individual metrics for combined rules:", metrics)
