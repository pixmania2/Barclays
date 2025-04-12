import streamlit as st
import pandas as pd
import numpy as np
import random
from datetime import datetime, timedelta
from sklearn.cluster import KMeans
from scipy.stats import genpareto
import matplotlib.pyplot as plt

# ============================================================================
# HELPER FUNCTIONS: Basic Conditions & Sliding Window Calculations
# ============================================================================

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

def compute_sliding_window_metrics(df, window_minutes, condition_func):
    """
    Slide a window of length 'window_minutes' (in minutes) over the data.
    Returns a NumPy array of metric values computed by condition_func for each window.
    """
    df_local = df.copy()
    df_local["timestamp_dt"] = pd.to_datetime(df_local["timestamp_dt"])
    window_delta = timedelta(minutes=window_minutes)
    start_time = df_local["timestamp_dt"].min()
    end_time = df_local["timestamp_dt"].max()
    metric_values = []
    current_time = start_time
    while current_time + window_delta <= end_time:
        window_df = df_local[(df_local["timestamp_dt"] >= current_time) & 
                             (df_local["timestamp_dt"] < current_time + window_delta)]
        value = condition_func(window_df)
        metric_values.append(value)
        current_time += timedelta(minutes=1)
    return np.array(metric_values)

def compute_hybrid_threshold(df, window_minutes, condition_func, ev_target_quantile):
    """
    Hybrid approach (clustering + EVT) to compute a threshold for a given metric.
    """
    metric_values = compute_sliding_window_metrics(df, window_minutes, condition_func)
    if len(metric_values) == 0:
        return 0

    # Reshape for KMeans clustering.
    X = metric_values.reshape(-1, 1)
    kmeans = KMeans(n_clusters=2, random_state=42).fit(X)
    labels = kmeans.labels_
    centers = kmeans.cluster_centers_.flatten()
    normal_cluster_label = np.argmin(centers)  # Choose the lower center as normal

    normal_values = metric_values[labels == normal_cluster_label]
    if len(normal_values) == 0:
        return int(np.percentile(metric_values, ev_target_quantile * 100))
    
    # Use the 90th percentile as baseline u.
    u = np.percentile(normal_values, 90)
    exceedances = normal_values[normal_values > u] - u
    if len(exceedances) < 10:
        return int(np.percentile(normal_values, ev_target_quantile * 100))
    
    shape, loc, scale = genpareto.fit(exceedances)
    q = genpareto.ppf(ev_target_quantile, shape, loc=loc, scale=scale)
    threshold = u + q
    return int(threshold)

def compute_sliding_window_avg(df, window_minutes, avg_func):
    """
    Compute a sliding window average using avg_func (for example, avg_cpu_usage).
    """
    df_local = df.copy()
    df_local["timestamp_dt"] = pd.to_datetime(df_local["timestamp_dt"])
    window_delta = timedelta(minutes=window_minutes)
    start_time = df_local["timestamp_dt"].min()
    end_time = df_local["timestamp_dt"].max()
    avg_values = []
    current_time = start_time
    while current_time + window_delta <= end_time:
        window_df = df_local[(df_local["timestamp_dt"] >= current_time) & 
                             (df_local["timestamp_dt"] < current_time + window_delta)]
        avg_val = avg_func(window_df)
        avg_values.append(avg_val)
        current_time += timedelta(minutes=1)
    return np.array(avg_values)

def compute_hybrid_avg_threshold(df, window_minutes, avg_func, ev_target_quantile):
    """
    For average metrics (e.g., CPU usage), compute a fixed percentile of the sliding window averages.
    """
    avg_values = compute_sliding_window_avg(df, window_minutes, avg_func)
    if len(avg_values) == 0:
        return 0
    return round(np.percentile(avg_values, ev_target_quantile*100), 2)

# ============================================================================
# RULE CLASS DEFINITION & RULE CREATION
# ============================================================================

class Rule:
    def __init__(self, rule_id, description, window_minutes, condition_func, threshold, level="Warning"):
        """
        rule_id: Identifier for the rule.
        description: Text description of the rule.
        window_minutes: Evaluation window size in minutes.
        condition_func: Function to compute metric over a window.
        threshold: Hybrid threshold value.
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
        Evaluate the rule on the data ending at current_time.
        Returns a tuple: (triggered: bool, observed_metric)
        """
        window_start = current_time - timedelta(minutes=self.window_minutes)
        window_df = df[(df["timestamp_dt"] >= window_start) & (df["timestamp_dt"] <= current_time)]
        metric = self.condition_func(window_df)
        return (metric >= self.threshold, metric)

    def __str__(self):
        return (f"Rule {self.rule_id} ({self.level}): {self.description} | "
                f"Window: {self.window_minutes} min | Threshold: {self.threshold}")

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

# ============================================================================
# STREAMLIT DASHBOARD LAYOUT WITH SESSION STATE FOR PERSISTENCE
# ============================================================================

st.set_page_config(page_title="Hybrid Anomaly Detection Dashboard", layout="wide")
st.title("Hybrid Anomaly Detection Dashboard")

# ---------------------
# Sidebar: Data Loading
# ---------------------
st.sidebar.header("Data Loading")
uploaded_file = st.sidebar.file_uploader("Upload CSV File", type=["csv"])

if uploaded_file is not None:
    df = pd.read_csv(uploaded_file)
    df["timestamp_dt"] = pd.to_datetime(df["timestamp"])
    st.session_state.df = df
else:
    st.sidebar.info("No file uploaded; generating sample data.")
    if "df" not in st.session_state:
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
        df["timestamp_dt"] = pd.to_datetime(df["timestamp"])
        st.session_state.df = df

st.write("### Data Preview")
st.dataframe(st.session_state.df.head())

# ---------------------
# Compute Hybrid Thresholds & Define Rules (Only once)
# ---------------------
if "rules" not in st.session_state:
    df = st.session_state.df

    # Compute thresholds for count-based rules
    hybrid_500_warning   = compute_hybrid_threshold(df, 20, lambda d: count_status(d, 500), 0.99)
    hybrid_500_critical  = compute_hybrid_threshold(df, 20, lambda d: count_status(d, 500), 0.995)
    hybrid_404_warning   = compute_hybrid_threshold(df, 20, lambda d: count_status(d, 404), 0.99)
    hybrid_404_critical  = compute_hybrid_threshold(df, 20, lambda d: count_status(d, 404), 0.995)
    hybrid_403_warning   = compute_hybrid_threshold(df, 20, lambda d: count_status(d, 403), 0.99)
    hybrid_403_critical  = compute_hybrid_threshold(df, 20, lambda d: count_status(d, 403), 0.995)
    hybrid_combined_warning  = compute_hybrid_threshold(df, 20, count_combined_4xx_5xx, 0.99)
    hybrid_combined_critical = compute_hybrid_threshold(df, 20, count_combined_4xx_5xx, 0.995)
    hybrid_post_safari_warning = compute_hybrid_threshold(df, 15, count_post_safari, 0.99)
    hybrid_unknown_warning = compute_hybrid_threshold(df, 30, count_unknown_browser, 0.99)

    # Compute threshold for average metric (CPU usage)
    hybrid_cpu_warning = compute_hybrid_avg_threshold(df, 10, avg_cpu_usage, 0.99)

    # Define rule objects
    rules = []
    rules.append(Rule(rule_id=1,
                      description=f"Internal Server Errors (500) - Warning: if count ≥ {hybrid_500_warning} in 20 minutes",
                      window_minutes=20,
                      condition_func=lambda d: count_status(d, 500),
                      threshold=hybrid_500_warning, level="Warning"))
    rules.append(Rule(rule_id=2,
                      description=f"Internal Server Errors (500) - Critical: if count ≥ {hybrid_500_critical} in 20 minutes",
                      window_minutes=20,
                      condition_func=lambda d: count_status(d, 500),
                      threshold=hybrid_500_critical, level="Critical"))
    rules.append(Rule(rule_id=3,
                      description=f"404 Not Found - Warning: if count ≥ {hybrid_404_warning} in 20 minutes",
                      window_minutes=20,
                      condition_func=lambda d: count_status(d, 404),
                      threshold=hybrid_404_warning, level="Warning"))
    rules.append(Rule(rule_id=4,
                      description=f"404 Not Found - Critical: if count ≥ {hybrid_404_critical} in 20 minutes",
                      window_minutes=20,
                      condition_func=lambda d: count_status(d, 404),
                      threshold=hybrid_404_critical, level="Critical"))
    rules.append(Rule(rule_id=5,
                      description=f"403 Forbidden - Warning: if count ≥ {hybrid_403_warning} in 20 minutes",
                      window_minutes=20,
                      condition_func=lambda d: count_status(d, 403),
                      threshold=hybrid_403_warning, level="Warning"))
    rules.append(Rule(rule_id=6,
                      description=f"403 Forbidden - Critical: if count ≥ {hybrid_403_critical} in 20 minutes",
                      window_minutes=20,
                      condition_func=lambda d: count_status(d, 403),
                      threshold=hybrid_403_critical, level="Critical"))
    rules.append(Rule(rule_id=7,
                      description=f"Combined 4xx & 5xx Errors - Warning: if count ≥ {hybrid_combined_warning} in 20 minutes",
                      window_minutes=20,
                      condition_func=count_combined_4xx_5xx,
                      threshold=hybrid_combined_warning, level="Warning"))
    rules.append(Rule(rule_id=8,
                      description=f"Combined 4xx & 5xx Errors - Critical: if count ≥ {hybrid_combined_critical} in 20 minutes",
                      window_minutes=20,
                      condition_func=count_combined_4xx_5xx,
                      threshold=hybrid_combined_critical, level="Critical"))
    rules.append(Rule(rule_id=9,
                      description=f"POST Requests from Safari - Warning: if count ≥ {hybrid_post_safari_warning} in 15 minutes",
                      window_minutes=15,
                      condition_func=count_post_safari,
                      threshold=hybrid_post_safari_warning, level="Warning"))
    rules.append(Rule(rule_id=10,
                      description=f"Requests from UNKNOWN Browsers - Warning: if count ≥ {hybrid_unknown_warning} in 30 minutes",
                      window_minutes=30,
                      condition_func=count_unknown_browser,
                      threshold=hybrid_unknown_warning, level="Warning"))
    rules.append(Rule(rule_id=11,
                      description=f"High CPU Usage - Warning: if average CPU usage ≥ {hybrid_cpu_warning}% in 10 minutes",
                      window_minutes=10,
                      condition_func=lambda d: avg_cpu_usage(d),
                      threshold=hybrid_cpu_warning, level="Warning"))
    
    st.session_state.rules = rules

    # Optionally, also store computed thresholds for display
    st.session_state.thresholds = {
        "Hybrid 500 Warning": hybrid_500_warning,
        "Hybrid 500 Critical": hybrid_500_critical,
        "Hybrid 404 Warning": hybrid_404_warning,
        "Hybrid Combined (4xx & 5xx) Warning": hybrid_combined_warning,
        "Hybrid CPU Usage Warning": hybrid_cpu_warning
    }

# Display computed thresholds and rule definitions
if "thresholds" in st.session_state:
    st.write("### Computed Thresholds")
    for key, val in st.session_state.thresholds.items():
        st.write(f"{key}: {val}")

rules_df = pd.DataFrame([{
    "Rule ID": r.rule_id,
    "Description": r.description,
    "Window (min)": r.window_minutes,
    "Threshold": r.threshold,
    "Level": r.level
} for r in st.session_state.rules])
st.write("### Defined Rules")
st.dataframe(rules_df)

# ---------------------
# Evaluate Rules (Once, then reuse)
# ---------------------
df = st.session_state.df
current_time = df["timestamp_dt"].max()
results = []
for r in st.session_state.rules:
    triggered, observed = r.evaluate(df, current_time)
    results.append({
        "Rule ID": r.rule_id,
        "Description": r.description,
        "Observed Metric": observed,
        "Threshold": r.threshold,
        "Status": "TRIGGERED" if triggered else "Not Triggered"
    })
results_df = pd.DataFrame(results)
st.write("### Rule Evaluation Results")
st.dataframe(results_df)

# ---------------------
# Combined Rule Input (Using Stored Rules without Reassembling)
# ---------------------
st.write("### Combine Rules")
user_input = st.text_input("Enter rule IDs (comma separated) to combine (minimum two):", key="combine_input")
if user_input:
    try:
        selected_ids = [int(x.strip()) for x in user_input.split(',') if x.strip().isdigit()]
        selected_rules = [r for r in st.session_state.rules if r.rule_id in selected_ids]
        if len(selected_rules) < 2:
            st.warning("Please select at least two rules to combine.")
        else:
            combined_description = "Combined Rule (" + " AND ".join([str(r.rule_id) for r in selected_rules]) + "): Alert if all rules are triggered."
            combined_rule = CombinedRule(combined_description, selected_rules)
            st.session_state.combined_rule = combined_rule  # store the combined rule
            st.success("Combined Rule Created:")
            st.write(combined_rule)
    except Exception as e:
        st.error("Error in combining rules. Please check your input.")

# Re-evaluate Combined Rule (if exists) without reassembling the model
# Re-evaluate Combined Rule (if exists) with detailed output
if "combined_rule" in st.session_state:
    combined_rule = st.session_state.combined_rule
    combined_triggered, _ = combined_rule.evaluate(df, current_time)
    
    overall_status = "TRIGGERED" if combined_triggered else "Not Triggered"
    st.write("#### Combined Rule Evaluation")
    st.write(f"Combined Rule ({' AND '.join([str(r.rule_id) for r in combined_rule.rules])}): {combined_rule.description}")
    st.write(f"Overall Status: **{overall_status}**")
    
    # Prepare a detailed table with each individual rule's evaluation:
    detailed_results = []
    for rule in combined_rule.rules:
        triggered, observed = rule.evaluate(df, current_time)
        detailed_results.append({
            "Rule ID": rule.rule_id,
            "Description": rule.description,
            "Observed Metric": observed,
            "Threshold": rule.threshold,
            "Status": "TRIGGERED" if triggered else "Not Triggered"
        })
    
    st.write("Individual Rule Evaluations:")
    st.table(detailed_results)


# ---------------------
# Visualization: Example Plot for CPU Usage Sliding Window
# ---------------------
st.write("### Visualization: CPU Usage Sliding Window")
cpu_avg_values = compute_sliding_window_avg(df, 10, avg_cpu_usage)
if len(cpu_avg_values) > 0:
    fig, ax = plt.subplots(figsize=(12, 6))
    ax.plot(cpu_avg_values, label="Sliding Window Average CPU Usage")
    ax.axhline(st.session_state.thresholds["Hybrid CPU Usage Warning"], color='red', linestyle='--',
               label=f"Threshold ({st.session_state.thresholds['Hybrid CPU Usage Warning']}%)")
    ax.set_xlabel("Window Index")
    ax.set_ylabel("CPU Usage (%)")
    ax.set_title("Sliding Window Average CPU Usage (10-minute window)")
    ax.legend()
    st.pyplot(fig)
else:
    st.write("Insufficient data for CPU usage visualization.")
