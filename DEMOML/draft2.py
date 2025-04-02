import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import timedelta
from scipy.stats import linregress
from statsmodels.tsa.arima.model import ARIMA

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
# Step 3: Detect Response Time Spike Anomalies
# -------------------------------------------
def detect_response_time_spike_anomalies(grouped, threshold=2):
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
# Step 4: Detect Pattern Change Anomalies in Response Time
# -------------------------------------------
def detect_response_time_pattern_change(grouped, min_intervals=6, slope_threshold_per_interval=10):
    """
    For each endpoint with sufficient data, perform linear regression on the time series of 
    average response time. Convert the slope to a per-interval (15 min) increase by multiplying
    by 900 (seconds per interval). If the slope exceeds the threshold and is statistically significant,
    flag it as a pattern change anomaly.
    """
    pattern_anomalies = []
    endpoints = grouped['endpoint'].unique()
    
    for ep in endpoints:
        ep_data = grouped[grouped['endpoint'] == ep].sort_values('time_bin')
        if len(ep_data) < min_intervals:
            continue
        
        # Convert timestamps to seconds since epoch for regression
        x = ep_data['time_bin'].map(lambda t: t.timestamp()).values
        y = ep_data['avg_response_time'].values
        
        slope, intercept, r_value, p_value, std_err = linregress(x, y)
        # Calculate increase per interval (15 minutes = 900 seconds)
        slope_per_interval = slope * 900
        
        if slope_per_interval > slope_threshold_per_interval and p_value < 0.05:
            # Append anomaly details (using the last time bin for context)
            anomaly_info = ep_data.iloc[-1].copy()
            anomaly_info['slope_per_interval'] = slope_per_interval
            anomaly_info['p_value'] = p_value
            pattern_anomalies.append(anomaly_info)
    
    if pattern_anomalies:
        return pd.DataFrame(pattern_anomalies)
    else:
        # Return an empty DataFrame with the expected columns
        return pd.DataFrame(columns=[
            'endpoint', 'time_bin', 'request_count', 'error_count',
            'avg_response_time', 'error_rate', 'slope_per_interval', 'p_value'
        ])

# -------------------------------------------
# Step 5: Detect Anomalies in Error Rate
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
# Step 6: Advanced Forecasting with ARIMA Model
# -------------------------------------------
def forecast_next_interval_arima(grouped, endpoint, column='avg_response_time'):
    """
    Use an ARIMA(1,1,1) model to forecast the next interval for the specified column.
    If insufficient data is available or an error occurs, return None.
    """
    ep_data = grouped[grouped['endpoint'] == endpoint].sort_values('time_bin')
    # Set time_bin as index
    ts = ep_data.set_index('time_bin')[column]
    if len(ts) < 6:
         return None
    try:
         model = ARIMA(ts, order=(1, 1, 1))
         model_fit = model.fit()
         forecast = model_fit.forecast(steps=1)[0]
         return forecast
    except Exception as e:
         print(f"Forecasting error for endpoint {endpoint} ({column}): {e}")
         return None

# -------------------------------------------
# Utility: Generate Alerts for Anomalies
# -------------------------------------------
def alert_anomalies(anomalies, metric_name):
    if anomalies.empty:
        print(f"No anomalies detected for {metric_name}.")
        return
    for _, row in anomalies.iterrows():
        if metric_name == 'avg_response_time':
            print(f"ALERT (Spike): {row['endpoint']} shows a response time spike at {row['time_bin']}. Value: {row['avg_response_time']:.2f} ms")
        elif metric_name == 'error_rate':
            print(f"ALERT (Error Rate): {row['endpoint']} shows an error rate anomaly at {row['time_bin']}. Value: {row['error_rate']:.2f}")
        elif metric_name == 'pattern_change':
            print(f"ALERT (Pattern Change): {row['endpoint']} shows a long-term upward trend at {row['time_bin']} with slope {row['slope_per_interval']:.2f} ms/15min (p-value: {row['p_value']:.3f})")

# -------------------------------------------
# Main Function: Integrate All Steps
# -------------------------------------------
def main():
    # Change the filename here if needed
    filename = "synthetic_dataset.csv"  
    df = load_data(filename)
    
    # Preprocess and aggregate the data in 15-minute intervals
    grouped = preprocess_data(df, time_interval='15min')
    
    # Detect spike anomalies in average response time
    spike_anomalies = detect_response_time_spike_anomalies(grouped, threshold=2)
    print("\n--- Response Time Spike Anomalies ---")
    print(spike_anomalies)
    alert_anomalies(spike_anomalies, 'avg_response_time')
    
    # Detect pattern change anomalies in response time
    pattern_anomalies = detect_response_time_pattern_change(grouped, min_intervals=6, slope_threshold_per_interval=10)
    print("\n--- Response Time Pattern Change Anomalies ---")
    print(pattern_anomalies)
    alert_anomalies(pattern_anomalies, 'pattern_change')
    
    # Detect anomalies in error rate
    error_anomalies = detect_error_rate_anomalies(grouped, percentile_threshold=99)
    print("\n--- Error Rate Anomalies ---")
    print(error_anomalies)
    alert_anomalies(error_anomalies, 'error_rate')
    
    # -------------------------------------------
    # Step 7: Advanced Forecasting for Each Endpoint
    # -------------------------------------------
    endpoints = grouped['endpoint'].unique()
    forecasts = []
    for ep in endpoints:
        forecast_rt = forecast_next_interval_arima(grouped, ep, column='avg_response_time')
        forecast_err = forecast_next_interval_arima(grouped, ep, column='error_rate')
        forecasts.append({
            'endpoint': ep,
            'forecast_avg_response_time_ms': forecast_rt,
            'forecast_error_rate': forecast_err
        })
    forecasts_df = pd.DataFrame(forecasts)
    print("\n--- Advanced Forecasts for Next Interval ---")
    print(forecasts_df)
    
    # -------------------------------------------
    # Step 8: Visualization (Example for One Endpoint)
    # -------------------------------------------
    selected_ep = endpoints[0]
    ep_data = grouped[grouped['endpoint'] == selected_ep].sort_values('time_bin')
    
    plt.figure(figsize=(12, 6))
    plt.plot(ep_data['time_bin'], ep_data['avg_response_time'], marker='o', label='Avg Response Time')
    
    # Mark spike anomalies on the plot
    spike_anom_ep = spike_anomalies[spike_anomalies['endpoint'] == selected_ep] if not spike_anomalies.empty else pd.DataFrame()
    if not spike_anom_ep.empty:
        plt.scatter(spike_anom_ep['time_bin'], spike_anom_ep['avg_response_time'], color='red', label='Spike Anomaly')
    
    # If a pattern change anomaly was detected for this endpoint, plot the regression line
    pattern_anom_ep = pattern_anomalies[pattern_anomalies['endpoint'] == selected_ep]
    if not pattern_anom_ep.empty:
        x = ep_data['time_bin'].map(lambda t: t.timestamp()).values
        y = ep_data['avg_response_time'].values
        slope, intercept, _, _, _ = linregress(x, y)
        regression_line = intercept + slope * x
        plt.plot(ep_data['time_bin'], regression_line, color='orange', label='Trend Line')
    
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
