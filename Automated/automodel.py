import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
from scipy.stats import linregress, genpareto
from prophet import Prophet
from sklearn.cluster import KMeans
import warnings

# Suppress common warnings for demonstration
warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=FutureWarning)

#############################
# HELPER FUNCTIONS: HYBRID THRESHOLD CALCULATIONS
#############################
def compute_sliding_window_metrics(df, window_minutes, condition_func):
    """
    Compute metric values using a sliding window of length 'window_minutes'.
    condition_func: function that takes a DataFrame and returns a scalar metric value.
    Returns a NumPy array of metric values.
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

def compute_hybrid_threshold(df, window_minutes, condition_func, ev_target_quantile, as_int=True):
    """
    Hybrid threshold calculation for count-based metrics.
    Uses sliding window metric values, clusters them (k=2), selects the cluster with the lower mean,
    sets baseline u as the 90th percentile of the normal cluster, fits an EVT (GPD) to the exceedances,
    and computes a final threshold at ev_target_quantile.
    """
    metric_values = compute_sliding_window_metrics(df, window_minutes, condition_func)
    if len(metric_values) == 0:
        return 0
    # Reshape for clustering
    X = metric_values.reshape(-1, 1)
    kmeans = KMeans(n_clusters=2, random_state=42).fit(X)
    labels = kmeans.labels_
    centers = kmeans.cluster_centers_.flatten()
    normal_cluster_label = np.argmin(centers)
    normal_values = metric_values[labels == normal_cluster_label]
    if len(normal_values) == 0:
        val = np.percentile(metric_values, ev_target_quantile * 100)
        return int(val) if as_int else round(val, 2)
    # Baseline u at 90th percentile of normal behavior
    u = np.percentile(normal_values, 90)
    # Exceedances: values above u
    exceedances = normal_values[normal_values > u] - u
    if len(exceedances) < 10:
        val = np.percentile(normal_values, ev_target_quantile * 100)
        return int(val) if as_int else round(val, 2)
    shape, loc, scale = genpareto.fit(exceedances)
    q = genpareto.ppf(ev_target_quantile, shape, loc=loc, scale=scale)
    threshold = u + q
    return int(threshold) if as_int else round(threshold, 2)

def compute_sliding_window_avg(df, window_minutes, avg_func):
    """
    Compute average metric values using a sliding window.
    avg_func: function that returns a scalar (e.g., average response time).
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
    For continuous metrics (e.g., avg response time), compute the ev_target_quantile
    (e.g., 99th percentile) on the sliding window averages.
    """
    avg_values = compute_sliding_window_avg(df, window_minutes, avg_func)
    if len(avg_values) == 0:
        return 0
    return round(np.percentile(avg_values, ev_target_quantile * 100), 2)

#############################
# DATA LOADING & PREPROCESSING
#############################
def load_data(filename):
    df = pd.read_csv(filename)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    # Create an extra column for compatibility with sliding window functions.
    df["timestamp_dt"] = df["timestamp"]
    return df

def preprocess_data(df, time_interval='15min'):
    df['time_bin'] = df['timestamp'].dt.floor(time_interval)
    grouped = df.groupby(['environment', 'endpoint', 'time_bin']).agg(
        request_count=('request_id', 'count'),
        error_count=('error_flag', 'sum'),
        avg_response_time=('response_time_ms', 'mean')
    ).reset_index()
    grouped['error_rate'] = grouped['error_count'] / grouped['request_count']
    # For compatibility with sliding window functions, set timestamp_dt as time_bin.
    grouped["timestamp_dt"] = grouped["time_bin"]
    return grouped

#############################
# BASIC CONDITION FUNCTIONS
#############################
def count_status(df, status_code):
    return df[df["http_status"] == status_code].shape[0]

def count_combined_4xx_5xx(df):
    return df[df["http_status"].between(400, 599)].shape[0]

def count_post_safari(df):
    return df[(df["http_method"] == "POST") & (df["Browser"].str.contains("Safari", case=False))].shape[0]

def count_unknown_browser(df):
    return df[df["Browser"].str.upper() == "UNKNOWN"].shape[0]

def avg_response_time(df):
    # Use the aggregated column from grouping.
    return df["avg_response_time"].mean() if not df.empty else 0

#############################
# UPDATED ANOMALY DETECTION FUNCTIONS USING DYNAMIC (HYBRID) THRESHOLDS
#############################
def detect_response_time_spike_anomalies(grouped):
    """
    Detect response time spikes per (environment, endpoint) by comparing the group's average response time
    against a dynamically computed threshold via the hybrid approach.
    """
    anomalies_list = []
    for (env, endpoint), group in grouped.groupby(['environment', 'endpoint']):
        # Compute dynamic threshold for avg response time over a 15-minute window.
        dynamic_threshold = compute_hybrid_avg_threshold(group, 15, avg_response_time, 0.99)
        anomaly_mask = group['avg_response_time'] > dynamic_threshold
        anomalies = group[anomaly_mask].copy()
        if not anomalies.empty:
            anomalies['anomaly_type'] = 'Spike'
            anomalies['dynamic_threshold'] = dynamic_threshold
            anomalies_list.append(anomalies)
    if anomalies_list:
        return pd.concat(anomalies_list)
    else:
        return pd.DataFrame()

def detect_response_time_pattern_change(grouped, min_intervals=6, ev_target_quantile=0.99):
    """
    Detect pattern change (sudden upward trend) in average response time.
    Calculates the overall slope for a group and compares to a dynamic slope threshold,
    computed as the ev_target_quantile percentile over sliding window slopes.
    """
    pattern_anomalies = []
    for (env, endpoint), group in grouped.groupby(['environment', 'endpoint']):
        group = group.sort_values('time_bin')
        if len(group) < min_intervals:
            continue
        # Compute overall slope for this group.
        x = group['time_bin'].map(lambda t: t.timestamp()).values
        y = group['avg_response_time'].values
        slope, intercept, r_value, p_value, std_err = linregress(x, y)
        # Compute dynamic slope threshold over sliding windows.
        slopes = []
        window_size = min_intervals
        for i in range(len(group) - window_size + 1):
            sub_group = group.iloc[i:i+window_size]
            x_sub = sub_group['time_bin'].map(lambda t: t.timestamp()).values
            y_sub = sub_group['avg_response_time'].values
            sub_slope, _, _, _, _ = linregress(x_sub, y_sub)
            # Convert slope to per interval (15min = 900 sec)
            slopes.append(sub_slope * 900)
        if len(slopes) == 0:
            continue
        dynamic_slope_threshold = np.percentile(slopes, ev_target_quantile * 100)
        # Check if the overall slope (converted per interval) is above the dynamic threshold.
        if (slope * 900) > dynamic_slope_threshold and p_value < 0.05:
            anomaly = group.iloc[-1].copy()
            anomaly['anomaly_type'] = 'Pattern Change'
            anomaly['slope_per_interval'] = slope * 900
            anomaly['dynamic_slope_threshold'] = dynamic_slope_threshold
            anomaly['p_value'] = p_value
            pattern_anomalies.append(anomaly)
    if pattern_anomalies:
        return pd.DataFrame(pattern_anomalies)
    else:
        return pd.DataFrame(columns=[
            'environment', 'endpoint', 'time_bin', 'request_count', 'error_count',
            'avg_response_time', 'error_rate', 'slope_per_interval', 'p_value', 'anomaly_type',
            'dynamic_slope_threshold'
        ])

def detect_error_rate_anomalies(grouped, ev_target_quantile=0.99):
    """
    Detect error rate anomalies using a hybrid dynamic threshold.
    For each (environment, endpoint) group, compute a dynamic threshold for error_rate
    using a 2-hour (120 min) window.
    """
    anomalies_list = []
    for (env, endpoint), group in grouped.groupby(['environment', 'endpoint']):
        dynamic_threshold = compute_hybrid_threshold(group, 120, 
                                                     lambda d: d['error_rate'].mean() if not d.empty else 0,
                                                     ev_target_quantile, as_int=False)
        anomaly_mask = group['error_rate'] > dynamic_threshold
        anomalies = group[anomaly_mask].copy()
        if not anomalies.empty:
            anomalies['anomaly_type'] = 'Error Rate'
            anomalies['dynamic_threshold'] = dynamic_threshold
            anomalies_list.append(anomalies)
    if anomalies_list:
        return pd.concat(anomalies_list)
    else:
        return pd.DataFrame()

#############################
# REQUEST JOURNEY ANALYSIS WITH DYNAMIC RISK THRESHOLD
#############################
def analyze_request_journeys(df):
    """
    Compute journey risk scores and set a dynamic risk threshold as the 99th percentile.
    """
    journey_group = df.groupby('request_id').agg(
        journey_start=('timestamp', 'min'),
        total_response_time_ms=('response_time_ms', 'sum'),
        total_requests=('request_id', 'count'),
        total_errors=('error_flag', 'sum'),
        distinct_environments=('environment', lambda x: x.nunique())
    ).reset_index()
    journey_group['risk_score'] = (
        journey_group['total_response_time_ms'] / journey_group['total_requests'] +
        100 * journey_group['total_errors'] +
        50 * (journey_group['distinct_environments'] - 1)
    )
    risk_threshold = np.percentile(journey_group['risk_score'], 99)
    journey_group['is_anomalous'] = journey_group['risk_score'] > risk_threshold
    journey_group['dynamic_risk_threshold'] = risk_threshold
    return journey_group

#############################
# FORECASTING FUNCTIONS (using Prophet)
#############################
def forecast_journey_anomalies(journey_group, time_interval='15min'):
    journey_group['journey_time_bin'] = pd.to_datetime(journey_group['journey_start']).dt.floor(time_interval)
    grouped_journeys = journey_group.groupby('journey_time_bin').agg(
        anomalous_count=('is_anomalous', 'sum')
    ).reset_index().rename(columns={'journey_time_bin': 'ds', 'anomalous_count': 'y'})
    if len(grouped_journeys) < 6:
        return None
    try:
        model = Prophet()
        model.fit(grouped_journeys)
        future = model.make_future_dataframe(periods=1, freq='15T')
        forecast = model.predict(future)
        forecast_value = forecast.iloc[-1]['yhat']
        return forecast_value
    except Exception as e:
        print(f"Error forecasting journey anomalies: {e}")
        return None

def forecast_next_interval_prophet(grouped, env, endpoint, column='avg_response_time'):
    group = grouped[(grouped['environment'] == env) & (grouped['endpoint'] == endpoint)].sort_values('time_bin')
    ts = group[['time_bin', column]].rename(columns={'time_bin': 'ds', column: 'y'}).dropna()
    if len(ts) < 6:
         return None
    try:
         model = Prophet()
         model.fit(ts)
         future = model.make_future_dataframe(periods=1, freq='15T')
         forecast = model.predict(future)
         forecast_value = forecast.iloc[-1]['yhat']
         return forecast_value
    except Exception as e:
         print(f"Error forecasting {column} for {env} - {endpoint}: {e}")
         return None

#############################
# UTILITY: Alert Generation
#############################
def alert_anomalies(anomalies, metric_name):
    if anomalies.empty:
        print(f"No anomalies detected for {metric_name}.")
        return
    for _, row in anomalies.iterrows():
        if metric_name in ['avg_response_time']:
            print(f"ALERT (Spike): {row['environment']} - {row['endpoint']} at {row['time_bin']} | "
                  f"Avg RT: {row['avg_response_time']:.2f} ms (Threshold: {row['dynamic_threshold']})")
        elif metric_name == 'error_rate':
            print(f"ALERT (Error Rate): {row['environment']} - {row['endpoint']} at {row['time_bin']} | "
                  f"Error Rate: {row['error_rate']:.2f} (Threshold: {row['dynamic_threshold']})")
        elif metric_name == 'pattern_change':
            print(f"ALERT (Pattern Change): {row['environment']} - {row['endpoint']} at {row['time_bin']} | "
                  f"Slope: {row['slope_per_interval']:.2f} ms/interval (Dynamic Threshold: {row['dynamic_slope_threshold']:.2f}, p={row['p_value']:.3f})")

#############################
# RULE COMBINATION CLASS
#############################
class Rule:
    def __init__(self, rule_id, description, window_minutes, condition_func, threshold, level="Warning"):
        self.rule_id = rule_id
        self.description = description
        self.window_minutes = window_minutes
        self.condition_func = condition_func
        self.threshold = threshold
        self.level = level

    def evaluate(self, df, current_time):
        window_start = current_time - timedelta(minutes=self.window_minutes)
        window_df = df[(df["timestamp_dt"] >= window_start) & (df["timestamp_dt"] <= current_time)]
        metric = self.condition_func(window_df)
        return (metric >= self.threshold, metric)

    def __str__(self):
        return (f"Rule {self.rule_id} ({self.level}): {self.description} | "
                f"Window: {self.window_minutes} min | Threshold: {self.threshold}")

#############################
# MAIN FUNCTION: INTEGRATE ALL STEPS
#############################
def main():
    filename = "synthetic_full_datasetlakh.csv"
    df = load_data(filename)
    grouped = preprocess_data(df, time_interval='15min')
    
    # ----------------------------
    # 1. Anomaly Detection with Dynamic Thresholds
    # ----------------------------
    rt_spike_anomalies = detect_response_time_spike_anomalies(grouped)
    rt_pattern_anomalies = detect_response_time_pattern_change(grouped, min_intervals=6, ev_target_quantile=0.99)
    error_rate_anomalies = detect_error_rate_anomalies(grouped, ev_target_quantile=0.99)
    
    print("--- Response Time Spike Anomalies (Dynamic) ---")
    print(rt_spike_anomalies)
    print("\n--- Response Time Pattern Change Anomalies (Dynamic) ---")
    print(rt_pattern_anomalies)
    print("\n--- Error Rate Anomalies (Dynamic) ---")
    print(error_rate_anomalies)
    
    alert_anomalies(rt_spike_anomalies, 'avg_response_time')
    alert_anomalies(rt_pattern_anomalies, 'pattern_change')
    alert_anomalies(error_rate_anomalies, 'error_rate')
    
    # ----------------------------
    # 2. End-to-End Request Journey Analysis with Dynamic Risk Threshold
    # ----------------------------
    journey_group = analyze_request_journeys(df)
    print("\n--- Request Journey Analysis (with Dynamic Risk Threshold) ---")
    print(journey_group.head(10))
    
    journey_forecast = forecast_journey_anomalies(journey_group, time_interval='15min')
    if journey_forecast is not None:
         print(f"\nForecasted anomalous journeys in next interval: {journey_forecast:.2f}")
    else:
         print("Insufficient journey data for forecasting.")
    
    # Forecasting using Prophet for each (environment, endpoint) group.
    unique_groups = grouped[['environment', 'endpoint']].drop_duplicates()
    forecasts = []
    for idx, row in unique_groups.iterrows():
        env = row['environment']
        endpoint = row['endpoint']
        forecast_rt = forecast_next_interval_prophet(grouped, env, endpoint, column='avg_response_time')
        forecast_err = forecast_next_interval_prophet(grouped, env, endpoint, column='error_rate')
        forecasts.append({
            'environment': env,
            'endpoint': endpoint,
            'forecast_avg_response_time_ms': forecast_rt,
            'forecast_error_rate': forecast_err
        })
    forecasts_df = pd.DataFrame(forecasts)
    print("\n--- Forecasts for Next Interval (by Environment & Endpoint) ---")
    print(forecasts_df)
    
    # ----------------------------
    # 3. Visualization Example for One Group
    # ----------------------------
    sample_group = unique_groups.iloc[0]
    env = sample_group['environment']
    endpoint = sample_group['endpoint']
    group_data = grouped[(grouped['environment'] == env) & (grouped['endpoint'] == endpoint)].sort_values('time_bin')
    
    plt.figure(figsize=(12, 6))
    plt.plot(group_data['time_bin'], group_data['avg_response_time'], marker='o', label='Avg Response Time')
    
    anomalies_spike = rt_spike_anomalies[(rt_spike_anomalies['environment'] == env) & (rt_spike_anomalies['endpoint'] == endpoint)]
    if not anomalies_spike.empty:
        plt.scatter(anomalies_spike['time_bin'], anomalies_spike['avg_response_time'], color='red', label='Spike Anomaly')
    
    anomalies_pattern = rt_pattern_anomalies[(rt_pattern_anomalies['environment'] == env) & (rt_pattern_anomalies['endpoint'] == endpoint)]
    if not anomalies_pattern.empty:
        x = group_data['time_bin'].map(lambda t: t.timestamp()).values
        y = group_data['avg_response_time'].values
        slope, intercept, _, _, _ = linregress(x, y)
        regression_line = intercept + slope * x
        plt.plot(group_data['time_bin'], regression_line, color='orange', label='Trend Line')
    
    plt.xlabel('Time Interval')
    plt.ylabel('Avg Response Time (ms)')
    plt.title(f"Response Time Trend for {env} - {endpoint}")
    plt.legend()
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig("prophet_forecast_trend.png")
    plt.show()
    
    # ----------------------------
    # 4. Rule Engine with Dynamic Thresholds & Combination
    # ----------------------------
    # Create a few sample rule objects using dynamic thresholds.
    rules = []
    rules.append(Rule(
        rule_id=1,
        description=f"Internal Server Errors (500) - Dynamic: if count >= {compute_hybrid_threshold(df, 20, lambda d: count_status(d, 500), 0.99)} in 20 minutes",
        window_minutes=20,
        condition_func=lambda d: count_status(d, 500),
        threshold=compute_hybrid_threshold(df, 20, lambda d: count_status(d, 500), 0.99),
        level="Warning"
    ))
    rules.append(Rule(
        rule_id=2,
        description=f"404 Not Found - Dynamic: if count >= {compute_hybrid_threshold(df, 20, lambda d: count_status(d, 404), 0.99)} in 20 minutes",
        window_minutes=20,
        condition_func=lambda d: count_status(d, 404),
        threshold=compute_hybrid_threshold(df, 20, lambda d: count_status(d, 404), 0.99),
        level="Warning"
    ))
    rules.append(Rule(
        rule_id=3,
        description=f"POST Requests from Safari - Dynamic: if count >= {compute_hybrid_threshold(df, 15, count_post_safari, 0.99)} in 15 minutes",
        window_minutes=15,
        condition_func=count_post_safari,
        threshold=compute_hybrid_threshold(df, 15, count_post_safari, 0.99),
        level="Warning"
    ))
    
    print("\nDefined Rules:")
    for rule in rules:
        print(rule)
        
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

if __name__ == "__main__":
    main()
