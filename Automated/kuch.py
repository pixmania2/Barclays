import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
from scipy.stats import linregress, genpareto
from prophet import Prophet
from sklearn.cluster import KMeans
import warnings

# Suppress warnings
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
    Hybrid threshold calculation for count-based metrics (original approach).
    Uses sliding window metric values, clusters them (k=2), selects the cluster with lower mean,
    sets baseline u as the 90th percentile of that cluster, fits an EVT (GPD) to exceedances,
    and computes the final threshold at ev_target_quantile.
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
# FORCED-THRESHOLD ANOMALY DETECTION (DEMO PURPOSE)
#############################
def detect_response_time_pattern_change_demo(grouped, slope_threshold=5.0):
    """
    FOR DEMO: Detect a pattern change whenever the slope (scaled to 15-min intervals)
    exceeds a fixed threshold. This ensures anomalies are produced even if the data
    is not very volatile.
    
    slope_threshold: a fixed slope-per-interval threshold (units: ms per 15-min interval).
                     e.g. slope_threshold=5.0 means if slope * 900 > 5, we flag an anomaly.
    """
    pattern_anomalies = []
    for (env, endpoint), group in grouped.groupby(['environment', 'endpoint']):
        group = group.sort_values('time_bin')
        if len(group) < 2:
            continue
        # Compute linear regression to get slope (in ms/second).
        x = group['time_bin'].map(lambda t: t.timestamp()).values
        y = group['avg_response_time'].values
        slope, intercept, r_value, p_value, std_err = linregress(x, y)
        slope_per_interval = slope * 900  # Convert to ms per 15-min interval
        
        if slope_per_interval > slope_threshold:
            anomaly = group.iloc[-1].copy()
            anomaly['anomaly_type'] = 'Pattern Change (Demo Threshold)'
            anomaly['slope_per_interval'] = slope_per_interval
            anomaly['demo_slope_threshold'] = slope_threshold
            anomaly['p_value'] = p_value
            pattern_anomalies.append(anomaly)
    if pattern_anomalies:
        return pd.DataFrame(pattern_anomalies)
    else:
        return pd.DataFrame(columns=[
            'environment', 'endpoint', 'time_bin', 'request_count', 'error_count',
            'avg_response_time', 'error_rate', 'slope_per_interval', 'p_value', 'anomaly_type',
            'demo_slope_threshold'
        ])

def detect_error_rate_anomalies_demo(grouped, error_threshold=1.25):
    """
    FOR DEMO: Detect an error rate anomaly whenever error_rate > error_threshold.
    This ensures anomalies will appear if your error_rate crosses this fixed limit.
    
    error_threshold: a fixed fraction of errors.
    """
    anomalies_list = []
    for (env, endpoint), group in grouped.groupby(['environment', 'endpoint']):
        anomaly_mask = group['error_rate'] > error_threshold
        anomalies = group[anomaly_mask].copy()
        if not anomalies.empty:
            anomalies['anomaly_type'] = 'Error Rate (Demo Threshold)'
            anomalies['demo_error_threshold'] = error_threshold
            anomalies_list.append(anomalies)
    if anomalies_list:
        return pd.concat(anomalies_list)
    else:
        return pd.DataFrame()

#############################
# OTHER ANOMALY DETECTION (DYNAMIC) - STILL AVAILABLE IF NEEDED
#############################
def detect_response_time_spike_anomalies(grouped):
    """
    Detect response time spikes per (environment, endpoint) by comparing the group's average response time
    against a dynamically computed threshold (hybrid approach).
    """
    anomalies_list = []
    for (env, endpoint), group in grouped.groupby(['environment', 'endpoint']):
        dynamic_threshold = compute_hybrid_avg_threshold(group, 15, avg_response_time, 0.90)
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
    risk_threshold = np.percentile(journey_group['risk_score'], 90)
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
# MODIFIED VISUALIZATION FUNCTIONS TO DISPLAY ONLY ONE GRAPH PER TYPE
#############################
def visualize_sample_group_forecast(grouped, forecasts_df, metric='avg_response_time', interval_minutes=15, sample_index=0):
    """
    Visualizes forecast for one (environment, endpoint) sample taken from forecasts_df.
    
    Parameters:
        grouped: The preprocessed grouped DataFrame with historical data.
        forecasts_df: A DataFrame containing forecast values for each group.
        metric: The metric to visualize ('avg_response_time' or 'error_rate').
        interval_minutes: The time interval (in minutes) used for each time bin.
        sample_index: Index of the sample in forecasts_df to plot.
    """
    forecast_col = f'forecast_{metric}_ms' if metric == 'avg_response_time' else f'forecast_{metric}'
    
    if forecasts_df.empty or sample_index >= len(forecasts_df):
        print("No forecast data available for visualization.")
        return
    
    # Select a single sample forecast row
    row = forecasts_df.iloc[sample_index]
    env = row['environment']
    endpoint = row['endpoint']
    forecast_value = row[forecast_col]
    
    # Filter historical data for the chosen sample.
    group_data = grouped[(grouped['environment'] == env) & (grouped['endpoint'] == endpoint)].sort_values('time_bin')
    if group_data.empty:
        print("No historical data available for the selected sample.")
        return

    last_time = group_data['time_bin'].max()
    forecast_time = last_time + pd.Timedelta(minutes=interval_minutes)

    plt.figure(figsize=(12, 6))
    plt.plot(group_data['time_bin'], group_data[metric], marker='o', label='Historical Data')
    plt.plot([last_time, forecast_time], [forecast_value, forecast_value], linestyle='--', color='green', linewidth=2, label='Forecast')
    plt.scatter(forecast_time, forecast_value, color='green', marker='x', s=100)
    
    plt.xlabel('Time')
    ylabel = "Avg Response Time (ms)" if metric == 'avg_response_time' else "Error Rate"
    plt.ylabel(ylabel)
    plt.title(f"{ylabel} Forecast for {env} - {endpoint}")
    plt.legend()
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.show()

def visualize_journey_forecast(journey_group, forecast_value, interval_minutes=15):
    """
    Visualizes the forecast of anomalous journey counts as a single graph.
    
    Parameters:
        journey_group: DataFrame containing aggregated journey analysis.
        forecast_value: The forecasted number of anomalous journeys for the next interval.
        interval_minutes: The duration of each time interval used for binning.
    """
    journey_group['journey_time_bin'] = pd.to_datetime(journey_group['journey_start']).dt.floor(f'{interval_minutes}min')
    grouped_journeys = journey_group.groupby('journey_time_bin').agg(anomalous_count=('is_anomalous', 'sum')).reset_index()
    if grouped_journeys.empty:
        print("Not enough journey data for visualization.")
        return

    last_time = grouped_journeys['journey_time_bin'].max()
    forecast_time = last_time + pd.Timedelta(minutes=interval_minutes)
    
    plt.figure(figsize=(12, 6))
    plt.plot(grouped_journeys['journey_time_bin'], grouped_journeys['anomalous_count'], marker='o', label='Historical Anomalous Count')
    plt.plot([last_time, forecast_time], [forecast_value, forecast_value], linestyle='--', color='purple', linewidth=2, label='Forecast')
    plt.scatter(forecast_time, forecast_value, color='purple', marker='x', s=100)
    
    plt.xlabel('Time')
    plt.ylabel('Anomalous Journey Count')
    plt.title("Forecast of Anomalous Journeys")
    plt.legend()
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.show()

#############################
# MAIN FUNCTION: INTEGRATE STEPS
#############################
def main():
    filename = "synthetic_full_datasetlakh.csv"
    df = load_data(filename)
    grouped = preprocess_data(df, time_interval='15min')
    
    # ---------------------------------------------------
    # 1. FORCED Anomaly Detection to Guarantee Some Logs
    # ---------------------------------------------------
    # Set thresholds so that some points become anomalies in your data.
    rt_pattern_anomalies = detect_response_time_pattern_change_demo(grouped, slope_threshold=2.0)
    error_rate_anomalies = detect_error_rate_anomalies_demo(grouped, error_threshold=1.25)
    
    print("--- Response Time Pattern Change Anomalies (FORCED DEMO) ---")
    print(rt_pattern_anomalies)
    print("\n--- Error Rate Anomalies (FORCED DEMO) ---")
    print(error_rate_anomalies)
    
    # ---------------------------------------------------
    # 2. Spike Detection (still dynamic)
    # ---------------------------------------------------
    rt_spike_anomalies = detect_response_time_spike_anomalies(grouped)
    print("\n--- Response Time Spike Anomalies (Dynamic) ---")
    print(rt_spike_anomalies)
    
    # ---------------------------------------------------
    # 3. Request Journey Analysis & Forecast
    # ---------------------------------------------------
    journey_group = analyze_request_journeys(df)
    journey_forecast = forecast_journey_anomalies(journey_group, time_interval='15min')
    
    print("\n--- Request Journey Analysis ---")
    print(journey_group.head(10))
    if journey_forecast is not None:
        print(f"\nForecasted anomalous journeys in next interval: {journey_forecast:.2f}")
    else:
        print("Insufficient journey data for forecasting.")
    
    # ---------------------------------------------------
    # 4. Forecasts for Each (environment, endpoint)
    # ---------------------------------------------------
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
    print("\n--- Forecasts for Next Interval (Environment & Endpoint) ---")
    print(forecasts_df)
    
    # ---------------------------------------------------
    # 5. Visualization for Forecasts (One graph per type)
    # ---------------------------------------------------
    # Visualize one sample forecast for average response time.
    visualize_sample_group_forecast(grouped, forecasts_df, metric='avg_response_time', interval_minutes=15, sample_index=0)
    # Visualize one sample forecast for error rate.
    visualize_sample_group_forecast(grouped, forecasts_df, metric='error_rate', interval_minutes=15, sample_index=0)
    # Visualize journey forecast as a single graph.
    if journey_forecast is not None:
        visualize_journey_forecast(journey_group, forecast_value=journey_forecast, interval_minutes=15)
    
    # ---------------------------------------------------
    # 6. Visualization of Historical Data & Demo Anomalies (One graph)
    # ---------------------------------------------------
    if not unique_groups.empty:
        sample_group = unique_groups.iloc[0]
        env = sample_group['environment']
        endpoint = sample_group['endpoint']
        group_data = grouped[(grouped['environment'] == env) & (grouped['endpoint'] == endpoint)].sort_values('time_bin')
        
        plt.figure(figsize=(12, 6))
        plt.plot(group_data['time_bin'], group_data['avg_response_time'], marker='o', label='Avg Response Time (ms)', color='steelblue')
        
        # Mark forced pattern change anomalies for the sample.
        anomalies_pattern = rt_pattern_anomalies[(rt_pattern_anomalies['environment'] == env) &
                                                 (rt_pattern_anomalies['endpoint'] == endpoint)]
        if not anomalies_pattern.empty:
            plt.scatter(anomalies_pattern['time_bin'], anomalies_pattern['avg_response_time'],
                        color='red', label='Pattern Anomaly (Demo)')
        
        # Mark dynamic spike anomalies for the sample.
        anomalies_spike = rt_spike_anomalies[(rt_spike_anomalies['environment'] == env) & 
                                             (rt_spike_anomalies['endpoint'] == endpoint)]
        if not anomalies_spike.empty:
            plt.scatter(anomalies_spike['time_bin'], anomalies_spike['avg_response_time'],
                        color='orange', label='Spike Anomaly (Dynamic)')
        
        plt.xlabel('Time')
        plt.ylabel('Avg Response Time (ms)')
        plt.title("API Response Time Trend with Demo & Dynamic Anomalies")
        plt.legend()
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.show()

if __name__ == "__main__":
    main()
