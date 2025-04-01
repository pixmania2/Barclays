import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import timedelta

filename = './cdsynthetic_dataset.csv'  # Make sure this file exists in your working directory

# -------------------------------------------
# Step 1: Load the Synthetic Dataset
# -------------------------------------------
def load_data(filename):
    df = pd.read_csv(filename)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    return df

# -------------------------------------------
# Step 2: Preprocess Data and Aggregate Metrics
# -------------------------------------------
def preprocess_data(df, time_interval='15min'):
    # Floor each timestamp to create a time bin (e.g., every 15 minutes)
    df['time_bin'] = df['timestamp'].dt.floor(time_interval)
    
    # Group by endpoint and time_bin to aggregate metrics
    grouped = df.groupby(['endpoint', 'time_bin']).agg(
        request_count=('request_id', 'count'),
        error_count=('error', 'sum'),
        avg_response_time=('response_time_ms', 'mean')
    ).reset_index()
    
    # Calculate the error rate per time bin
    grouped['error_rate'] = grouped['error_count'] / grouped['request_count']
    return grouped

# -------------------------------------------
# Step 3: Detect Anomalies in Response Time
# -------------------------------------------
def detect_response_time_anomalies(grouped, threshold=2):
    anomalies = []
    endpoints = grouped['endpoint'].unique()
    for ep in endpoints:
        ep_data = grouped[grouped['endpoint'] == ep]
        mean_rt = ep_data['avg_response_time'].mean()
        std_rt = ep_data['avg_response_time'].std()
        # Flag bins where avg response time exceeds mean + threshold * std
        anomaly_mask = ep_data['avg_response_time'] > mean_rt + threshold * std_rt
        ep_anomalies = ep_data[anomaly_mask]
        if not ep_anomalies.empty:
            anomalies.append(ep_anomalies)
    if anomalies:
        return pd.concat(anomalies)
    else:
        return pd.DataFrame()

# -------------------------------------------
# Step 4: Detect Anomalies in Error Rate
# -------------------------------------------
def detect_error_rate_anomalies(grouped, percentile_threshold=99):
    anomalies = []
    endpoints = grouped['endpoint'].unique()
    for ep in endpoints:
        ep_data = grouped[grouped['endpoint'] == ep]
        # Determine the 99th percentile error rate for the endpoint
        threshold_value = np.percentile(ep_data['error_rate'], percentile_threshold)
        anomaly_mask = ep_data['error_rate'] > threshold_value
        ep_anomalies = ep_data[anomaly_mask]
        if not ep_anomalies.empty:
            anomalies.append(ep_anomalies)
    if anomalies:
        return pd.concat(anomalies)
    else:
        return pd.DataFrame()

# -------------------------------------------
# Step 5: Forecast Next Interval Metrics (Simple Forecast)
# -------------------------------------------
def forecast_next_interval(grouped, endpoint, column='avg_response_time'):
    ep_data = grouped[grouped['endpoint'] == endpoint].sort_values('time_bin')
    # For demonstration, use the average of the last three intervals as the forecast
    if len(ep_data) < 3:
        return None
    forecast = ep_data[column].tail(3).mean()
    return forecast

# -------------------------------------------
# Utility: Generate Alerts for Anomalies
# -------------------------------------------
def alert_anomalies(anomalies, metric_name):
    if anomalies.empty:
        print(f"No anomalies detected for {metric_name}.")
        return
    for _, row in anomalies.iterrows():
        print(f"ALERT: {row['endpoint']} shows a {metric_name} anomaly at {row['time_bin']}. Value: {row[metric_name]:.2f}")

# -------------------------------------------
# Main Function: Integrate All Steps
# -------------------------------------------
def main():
    filename = "synthetic_dataset.csv"  # Make sure this file exists in your working directory
    df = load_data(filename)
    
    # Preprocess and aggregate the data in 15-minute intervals
    grouped = preprocess_data(df, time_interval='15min')
    
    # Detect anomalies in average response time
    rt_anomalies = detect_response_time_anomalies(grouped, threshold=2)
    print("\n--- Response Time Anomalies ---")
    print(rt_anomalies)
    alert_anomalies(rt_anomalies, 'avg_response_time')
    
    # Detect anomalies in error rate
    error_anomalies = detect_error_rate_anomalies(grouped, percentile_threshold=99)
    print("\n--- Error Rate Anomalies ---")
    print(error_anomalies)
    alert_anomalies(error_anomalies, 'error_rate')
    
    # Forecast the next interval for each endpoint (both response time and error rate)
    endpoints = grouped['endpoint'].unique()
    forecasts = []
    for ep in endpoints:
        forecast_rt = forecast_next_interval(grouped, ep, column='avg_response_time')
        forecast_err = forecast_next_interval(grouped, ep, column='error_rate')
        forecasts.append({
            'endpoint': ep,
            'forecast_avg_response_time_ms': forecast_rt,
            'forecast_error_rate': forecast_err
        })
    forecasts_df = pd.DataFrame(forecasts)
    print("\n--- Forecasts for Next Interval ---")
    print(forecasts_df)
    
    # -------------------------------------------
    # Step 6: Visualization (Example for One Endpoint)
    # -------------------------------------------
    selected_ep = endpoints[0]
    ep_data = grouped[grouped['endpoint'] == selected_ep].sort_values('time_bin')
    
    plt.figure(figsize=(12, 6))
    plt.plot(ep_data['time_bin'], ep_data['avg_response_time'], marker='o', label='Avg Response Time')
    
    # Mark response time anomalies on the plot
    rt_anom_ep = rt_anomalies[rt_anomalies['endpoint'] == selected_ep]
    if not rt_anom_ep.empty:
        plt.scatter(rt_anom_ep['time_bin'], rt_anom_ep['avg_response_time'], color='red', label='Anomaly')
    
    plt.xlabel('Time Interval')
    plt.ylabel('Avg Response Time (ms)')
    plt.title(f"Response Time Trend for {selected_ep}")
    plt.legend()
    plt.xticks(rotation=45)
    plt.tight_layout()
    
    # Save the plot as an image file
    plt.savefig("response_time_trend.png")
    plt.show()

if __name__ == "__main__":
    main()
