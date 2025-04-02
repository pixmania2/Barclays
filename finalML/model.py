import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import timedelta
from scipy.stats import linregress
from prophet import Prophet
import warnings

filename = './synthetic_full_dataset.csv'
# Suppress common warnings (for demonstration)
warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=FutureWarning)

# ----------------------------
# Step 1: Load Data
# ----------------------------
def load_data(filename):
    df = pd.read_csv(filename)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    return df

# ----------------------------
# Step 2: Preprocess & Aggregate Data by Environment & Endpoint
# ----------------------------
def preprocess_data(df, time_interval='15min'):
    df['time_bin'] = df['timestamp'].dt.floor(time_interval)
    grouped = df.groupby(['environment', 'endpoint', 'time_bin']).agg(
        request_count=('request_id', 'count'),
        error_count=('error_flag', 'sum'),
        avg_response_time=('response_time_ms', 'mean')
    ).reset_index()
    grouped['error_rate'] = grouped['error_count'] / grouped['request_count']
    return grouped

# ----------------------------
# Step 3a: Response Time Anomaly Detection (Spike Detection)
# ----------------------------
def detect_response_time_spike_anomalies(grouped, threshold=2):
    anomalies_list = []
    for (env, endpoint), group in grouped.groupby(['environment', 'endpoint']):
        mean_rt = group['avg_response_time'].mean()
        std_rt = group['avg_response_time'].std()
        if std_rt == 0 or np.isnan(std_rt):
            continue
        anomaly_mask = group['avg_response_time'] > mean_rt + threshold * std_rt
        anomalies = group[anomaly_mask].copy()
        if not anomalies.empty:
            anomalies['anomaly_type'] = 'Spike'
            anomalies_list.append(anomalies)
    if anomalies_list:
        return pd.concat(anomalies_list)
    else:
        return pd.DataFrame()

# ----------------------------
# Step 3b: Response Time Anomaly Detection (Pattern Change Detection)
# ----------------------------
def detect_response_time_pattern_change(grouped, min_intervals=6, slope_threshold_per_interval=10):
    pattern_anomalies = []
    for (env, endpoint), group in grouped.groupby(['environment', 'endpoint']):
        group = group.sort_values('time_bin')
        if len(group) < min_intervals:
            continue
        x = group['time_bin'].map(lambda t: t.timestamp()).values
        y = group['avg_response_time'].values
        slope, intercept, r_value, p_value, std_err = linregress(x, y)
        # Convert slope to per-interval (15 min = 900 sec) increase
        slope_per_interval = slope * 900
        if slope_per_interval > slope_threshold_per_interval and p_value < 0.05:
            anomaly = group.iloc[-1].copy()
            anomaly['anomaly_type'] = 'Pattern Change'
            anomaly['slope_per_interval'] = slope_per_interval
            anomaly['p_value'] = p_value
            pattern_anomalies.append(anomaly)
    if pattern_anomalies:
        return pd.DataFrame(pattern_anomalies)
    else:
        return pd.DataFrame(columns=[
            'environment', 'endpoint', 'time_bin', 'request_count', 'error_count',
            'avg_response_time', 'error_rate', 'slope_per_interval', 'p_value', 'anomaly_type'
        ])

# ----------------------------
# Step 4: Error Rate Anomaly Detection
# ----------------------------
def detect_error_rate_anomalies(grouped, percentile_threshold=99):
    anomalies_list = []
    for (env, endpoint), group in grouped.groupby(['environment', 'endpoint']):
        threshold_value = np.percentile(group['error_rate'], percentile_threshold)
        anomaly_mask = group['error_rate'] > threshold_value
        anomalies = group[anomaly_mask].copy()
        if not anomalies.empty:
            anomalies['anomaly_type'] = 'Error Rate'
            anomalies_list.append(anomalies)
    if anomalies_list:
        return pd.concat(anomalies_list)
    else:
        return pd.DataFrame()

# ----------------------------
# Step 5: End-to-End Request Journey Analysis & Prediction
# ----------------------------
def analyze_request_journeys(df, response_time_threshold=1000, error_threshold=1):
    journey_group = df.groupby('request_id').agg(
        journey_start=('timestamp', 'min'),
        total_response_time_ms=('response_time_ms', 'sum'),
        total_requests=('request_id', 'count'),
        total_errors=('error_flag', 'sum'),
        distinct_environments=('environment', lambda x: x.nunique())
    ).reset_index()
    # Compute a simple risk score for each journey
    journey_group['risk_score'] = (
        journey_group['total_response_time_ms'] / journey_group['total_requests'] +
        100 * journey_group['total_errors'] +
        50 * (journey_group['distinct_environments'] - 1)
    )
    risk_threshold = journey_group['risk_score'].mean() + 2 * journey_group['risk_score'].std()
    journey_group['is_anomalous'] = journey_group['risk_score'] > risk_threshold
    return journey_group

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

# ----------------------------
# Step 6: Advanced Forecasting with Prophet for Environment & Endpoint Groups
# ----------------------------
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

# ----------------------------
# Utility: Alert Generation
# ----------------------------
def alert_anomalies(anomalies, metric_name):
    if anomalies.empty:
        print(f"No anomalies detected for {metric_name}.")
        return
    for _, row in anomalies.iterrows():
        if metric_name in ['avg_response_time']:
            print(f"ALERT (Spike): {row['environment']} - {row['endpoint']} at {row['time_bin']} | Avg RT: {row['avg_response_time']:.2f} ms")
        elif metric_name == 'error_rate':
            print(f"ALERT (Error Rate): {row['environment']} - {row['endpoint']} at {row['time_bin']} | Error Rate: {row['error_rate']:.2f}")
        elif metric_name == 'pattern_change':
            print(f"ALERT (Pattern Change): {row['environment']} - {row['endpoint']} at {row['time_bin']} | Slope: {row['slope_per_interval']:.2f} ms/interval (p={row['p_value']:.3f})")

# ----------------------------
# Main Function: Integrate All Steps
# ----------------------------
def main():
    filename = "synthetic_full_dataset.csv"
    df = load_data(filename)
    grouped = preprocess_data(df, time_interval='15min')
    
    # Anomaly Detection
    rt_spike_anomalies = detect_response_time_spike_anomalies(grouped, threshold=2)
    rt_pattern_anomalies = detect_response_time_pattern_change(grouped, min_intervals=6, slope_threshold_per_interval=10)
    error_rate_anomalies = detect_error_rate_anomalies(grouped, percentile_threshold=99)
    
    print("--- Response Time Spike Anomalies ---")
    print(rt_spike_anomalies)
    print("\n--- Response Time Pattern Change Anomalies ---")
    print(rt_pattern_anomalies)
    print("\n--- Error Rate Anomalies ---")
    print(error_rate_anomalies)
    
    alert_anomalies(rt_spike_anomalies, 'avg_response_time')
    alert_anomalies(rt_pattern_anomalies, 'pattern_change')
    alert_anomalies(error_rate_anomalies, 'error_rate')
    
    # End-to-End Request Journey Analysis
    journey_group = analyze_request_journeys(df, response_time_threshold=1000, error_threshold=1)
    print("\n--- Request Journey Analysis ---")
    print(journey_group.head(10))
    
    journey_forecast = forecast_journey_anomalies(journey_group, time_interval='15min')
    if journey_forecast is not None:
         print(f"\nForecasted anomalous journeys in next interval: {journey_forecast:.2f}")
    else:
         print("Insufficient journey data for forecasting.")
    
    # Forecasting for each (environment, endpoint) group using Prophet
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
    # Visualization Example for one group
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

if __name__ == "__main__":
    main()
