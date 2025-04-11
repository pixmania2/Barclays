import pandas as pd
import numpy as np
import random
from datetime import datetime, timedelta

# --------------------------------------------------------------------
# STEP 1: Load the Synthetic Dataset
# --------------------------------------------------------------------
# Assume your synthetic dataset is already generated.
# Uncomment the next line if you have the CSV file.
# df = pd.read_csv("synthetic_full_dataset.csv")

# For demonstration, below is commented sample-code to generate a small dataset.
# (You already have the full dataset with 10,000 rows.)
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

df = pd.read_csv("./synthetic_full_dataset.csv")
# Ensure that the timestamp column is in datetime format.
df["timestamp_dt"] = pd.to_datetime(df["timestamp"])

# --------------------------------------------------------------------
# STEP 2: Define Condition Functions for the Rules
# --------------------------------------------------------------------
def count_status(df, status_code):
    """Return the count of logs where http_status equals status_code."""
    return df[df["http_status"] == status_code].shape[0]

def count_combined_4xx_5xx(df):
    """Return the count of logs where http_status is in the 4xx or 5xx range."""
    return df[df["http_status"].between(400,599)].shape[0]

def count_post_safari(df):
    """Return the count of logs with POST method and Browser containing 'Safari'."""
    return df[(df["http_method"] == "POST") & (df["Browser"].str.contains("Safari", case=False))].shape[0]

def count_unknown_browser(df):
    """Return the count of logs from UNKNOWN browsers."""
    return df[df["Browser"].str.upper() == "UNKNOWN"].shape[0]

def avg_cpu_usage(df):
    """Return the average CPU usage in the window."""
    if df.empty:
        return 0
    return df["cpu_usage_percent"].mean()

# --------------------------------------------------------------------
# Helper Function: Compute Optimal Threshold via Sliding Window
# --------------------------------------------------------------------
def compute_optimal_threshold(df, window_minutes, condition_func, percentile):
    """
    Slide a fixed window over the data and compute the metric for each window using condition_func.
    Return the value at the specified percentile.
    """
    df_local = df.copy()
    df_local["timestamp_dt"] = pd.to_datetime(df_local["timestamp_dt"])
    
    window_delta = timedelta(minutes=window_minutes)
    start_time = df_local["timestamp_dt"].min()
    end_time = df_local["timestamp_dt"].max()
    values = []
    
    current_time = start_time
    while current_time + window_delta <= end_time:
        window_df = df_local[(df_local["timestamp_dt"] >= current_time) & (df_local["timestamp_dt"] < current_time + window_delta)]
        value = condition_func(window_df)
        values.append(value)
        current_time += timedelta(minutes=1)
    
    if len(values) == 0:
        return 0
    optimal_val = np.percentile(values, percentile)
    return int(optimal_val)

# --------------------------------------------------------------------
# For average metrics (like CPU), we create a similar function:
def compute_optimal_avg_threshold(df, window_minutes, metric_func, percentile):
    """
    Compute the average metric over sliding windows then return the specified percentile.
    """
    df_local = df.copy()
    df_local["timestamp_dt"] = pd.to_datetime(df_local["timestamp_dt"])
    
    window_delta = timedelta(minutes=window_minutes)
    start_time = df_local["timestamp_dt"].min()
    end_time = df_local["timestamp_dt"].max()
    averages = []
    
    current_time = start_time
    while current_time + window_delta <= end_time:
        window_df = df_local[(df_local["timestamp_dt"] >= current_time) & (df_local["timestamp_dt"] < current_time + window_delta)]
        avg_val = metric_func(window_df)
        averages.append(avg_val)
        current_time += timedelta(minutes=1)
    
    if len(averages) == 0:
        return 0
    optimal_avg = np.percentile(averages, percentile)
    return round(optimal_avg, 2)

# --------------------------------------------------------------------
# STEP 3: Compute Optimal Thresholds for Each Rule from Historical Data
# We use different percentiles for warning and critical tiers.
# --------------------------------------------------------------------
# For 500 errors (20-minute window)
opt_500_warning = compute_optimal_threshold(df, 20, lambda d: count_status(d, 500), 90)
opt_500_critical  = compute_optimal_threshold(df, 20, lambda d: count_status(d, 500), 95)

# For 404 errors (20-minute window)
opt_404_warning = compute_optimal_threshold(df, 20, lambda d: count_status(d, 404), 90)
opt_404_critical  = compute_optimal_threshold(df, 20, lambda d: count_status(d, 404), 95)

# For 403 errors (20-minute window)
opt_403_warning = compute_optimal_threshold(df, 20, lambda d: count_status(d, 403), 90)
opt_403_critical  = compute_optimal_threshold(df, 20, lambda d: count_status(d, 403), 95)

# Combined 4xx & 5xx (20-minute window)
opt_combined_warning = compute_optimal_threshold(df, 20, count_combined_4xx_5xx, 90)
opt_combined_critical  = compute_optimal_threshold(df, 20, count_combined_4xx_5xx, 95)

# POST from Safari (15-minute window)
opt_post_safari_warning = compute_optimal_threshold(df, 15, count_post_safari, 90)
# (We won’t define a critical tier for this one in our example.)

# Unknown Browsers (30-minute window)
opt_unknown_warning = compute_optimal_threshold(df, 30, count_unknown_browser, 90)

# New Rule: High CPU Usage (averaged over a 10-minute window)
opt_cpu_warning = compute_optimal_avg_threshold(df, 10, avg_cpu_usage, 90)

# --------------------------------------------------------------------
# STEP 4: Define the Rule Class and Create Rule Objects
# --------------------------------------------------------------------
class Rule:
    def __init__(self, rule_id, description, window_minutes, condition_func, threshold, level="Warning"):
        """
        rule_id: An identifier for the rule.
        description: A textual description.
        window_minutes: How long the window is (in minutes).
        condition_func: A function that takes a DataFrame and returns a metric.
        threshold: The threshold value that triggers the rule.
        level: "Warning" or "Critical" (used in description).
        """
        self.rule_id = rule_id
        self.description = description
        self.window_minutes = window_minutes
        self.condition_func = condition_func
        self.threshold = threshold
        self.level = level

    def evaluate(self, df, current_time):
        """
        Evaluates the rule over the time window ending at current_time.
        Returns (triggered: bool, actual_value).
        """
        window_start = current_time - timedelta(minutes=self.window_minutes)
        window_df = df[(df["timestamp_dt"] >= window_start) & (df["timestamp_dt"] <= current_time)]
        metric = self.condition_func(window_df)
        return (metric >= self.threshold, metric)

    def __str__(self):
        return f"Rule {self.rule_id} ({self.level}): {self.description} | Window: {self.window_minutes} min | Threshold: {self.threshold}"

# Create all rule objects using computed optimal thresholds.
rules = []

# 500 errors rules
rules.append(Rule(
    rule_id=1,
    description=f"Internal Server Errors (500) - Warning: if count >= {opt_500_warning} in 20 minutes",
    window_minutes=20,
    condition_func=lambda d: count_status(d, 500),
    threshold=opt_500_warning,
    level="Warning"
))
rules.append(Rule(
    rule_id=2,
    description=f"Internal Server Errors (500) - Critical: if count >= {opt_500_critical} in 20 minutes",
    window_minutes=20,
    condition_func=lambda d: count_status(d, 500),
    threshold=opt_500_critical,
    level="Critical"
))

# 404 errors rules
rules.append(Rule(
    rule_id=3,
    description=f"404 Not Found - Warning: if count >= {opt_404_warning} in 20 minutes",
    window_minutes=20,
    condition_func=lambda d: count_status(d, 404),
    threshold=opt_404_warning,
    level="Warning"
))
rules.append(Rule(
    rule_id=4,
    description=f"404 Not Found - Critical: if count >= {opt_404_critical} in 20 minutes",
    window_minutes=20,
    condition_func=lambda d: count_status(d, 404),
    threshold=opt_404_critical,
    level="Critical"
))

# 403 errors rules
rules.append(Rule(
    rule_id=5,
    description=f"403 Forbidden - Warning: if count >= {opt_403_warning} in 20 minutes",
    window_minutes=20,
    condition_func=lambda d: count_status(d, 403),
    threshold=opt_403_warning,
    level="Warning"
))
rules.append(Rule(
    rule_id=6,
    description=f"403 Forbidden - Critical: if count >= {opt_403_critical} in 20 minutes",
    window_minutes=20,
    condition_func=lambda d: count_status(d, 403),
    threshold=opt_403_critical,
    level="Critical"
))

# Combined 4xx & 5xx errors
rules.append(Rule(
    rule_id=7,
    description=f"Combined 4xx & 5xx Errors - Warning: if count >= {opt_combined_warning} in 20 minutes",
    window_minutes=20,
    condition_func=count_combined_4xx_5xx,
    threshold=opt_combined_warning,
    level="Warning"
))
rules.append(Rule(
    rule_id=8,
    description=f"Combined 4xx & 5xx Errors - Critical: if count >= {opt_combined_critical} in 20 minutes",
    window_minutes=20,
    condition_func=count_combined_4xx_5xx,
    threshold=opt_combined_critical,
    level="Critical"
))

# POST from Safari rule
rules.append(Rule(
    rule_id=9,
    description=f"POST Requests from Safari - Warning: if count >= {opt_post_safari_warning} in 15 minutes",
    window_minutes=15,
    condition_func=count_post_safari,
    threshold=opt_post_safari_warning,
    level="Warning"
))

# Unknown Browser rule
rules.append(Rule(
    rule_id=10,
    description=f"Requests from UNKNOWN Browsers - Warning: if count >= {opt_unknown_warning} in 30 minutes",
    window_minutes=30,
    condition_func=count_unknown_browser,
    threshold=opt_unknown_warning,
    level="Warning"
))

# New extra rule: High CPU usage Warning (averaged over 10 minutes)
rules.append(Rule(
    rule_id=11,
    description=f"High CPU Usage - Warning: if average CPU usage >= {opt_cpu_warning}% in 10 minutes",
    window_minutes=10,
    condition_func=lambda d: avg_cpu_usage(d),
    threshold=opt_cpu_warning,
    level="Warning"
))

# --------------------------------------------------------------------
# STEP 5: Print All Defined Rules
# --------------------------------------------------------------------
print("Defined Rules:\n")
for rule in rules:
    print(rule)

# --------------------------------------------------------------------
# STEP 6: Let the User Choose to Club (Combine) Rules
# --------------------------------------------------------------------
print("\nYou can club (combine) two or more rules together to create a compound alert.")
print("Enter the rule IDs (comma separated) that you want to combine (or press Enter to skip):")
user_input = input("Your selection: ").strip()

# A simple combined rule will trigger an alert only if ALL of the selected rules are triggered.
combined_rule = None
if user_input:
    # Parse rule IDs from input.
    try:
        selected_ids = [int(x.strip()) for x in user_input.split(',') if x.strip().isdigit()]
        selected_rules = [r for r in rules if r.rule_id in selected_ids]
        if len(selected_rules) < 2:
            print("You must choose two or more rules to combine. No combined rule will be created.")
        else:
            # Create a combined rule object: It will have a description listing all rules.
            combined_description = "Combined Rule (" + " AND ".join([str(r.rule_id) for r in selected_rules]) + "): "
            combined_description += "Alert if all selected rules are triggered in their respective time windows."
            
            class CombinedRule:
                def __init__(self, description, rules):
                    self.description = description
                    self.rules = rules
                def evaluate(self, df, current_time):
                    # Evaluate each sub-rule; if all are triggered then combined alert is True.
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

# --------------------------------------------------------------------
# STEP 7: Evaluate the Rules and Display Alerts
# --------------------------------------------------------------------
# For evaluation, we use the latest timestamp in the dataset.
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
