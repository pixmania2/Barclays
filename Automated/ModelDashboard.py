import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import warnings
import json
import os

# Import functions from your main model file, kuch.py
from kuch import (
    load_data, 
    preprocess_data, 
    detect_response_time_pattern_change_demo, 
    detect_error_rate_anomalies_demo, 
    detect_response_time_spike_anomalies, 
    analyze_request_journeys, 
    forecast_journey_anomalies, 
    forecast_next_interval_prophet
)

# Optional: set matplotlib style or warnings
warnings.filterwarnings("ignore")

# --- Streamlit Dashboard Layout ---
st.set_page_config(page_title="Anomaly Detection Dashboard", layout="wide")
st.title("Anomaly Detection and Forecasting Dashboard")

DATA_FILE = "synthetic_full_datasetlakh.csv"

# --- Sidebar: Load Data and Choose Options ---
st.sidebar.header("Options")
file_path = st.sidebar.text_input("Dataset Path", DATA_FILE)
time_interval = st.sidebar.selectbox("Aggregation Interval", ["15min", "30min", "1H"], index=0)

st.sidebar.subheader("Data Loading")
if st.sidebar.button("Load Data"):
    with st.spinner("Loading data..."):
        df = load_data(file_path)
        grouped = preprocess_data(df, time_interval)
        st.sidebar.success(f"Data loaded and aggregated ({len(grouped)} rows).")
        st.session_state.df = df
        st.session_state.grouped = grouped

# Ensure data is loaded BEFORE using session_state values.
if "df" not in st.session_state or "grouped" not in st.session_state:
    st.warning("Please load data first in the sidebar.")
    st.stop()

df = st.session_state.df
grouped = st.session_state.grouped

# --- Data Preview ---
st.write("### Data Preview")
st.dataframe(df.head())

# --- 1. Anomaly Detection Section ---
st.header("Anomaly Detection Results")

# Layout in three columns
col1, col2, col3 = st.columns(3)

with col1:
    st.subheader("Response Time Pattern Changes")
    rt_pattern_anomalies = detect_response_time_pattern_change_demo(grouped, slope_threshold=1.25)
    st.dataframe(rt_pattern_anomalies)

with col2:
    st.subheader("Error Rate Anomalies")
    error_rate_anomalies = detect_error_rate_anomalies_demo(grouped, error_threshold=0.9)
    st.dataframe(error_rate_anomalies)

with col3:
    st.subheader("Response Time Spike Anomalies (Dynamic)")
    rt_spike_anomalies = detect_response_time_spike_anomalies(grouped)
    st.dataframe(rt_spike_anomalies)

# --- 2. Request Journey Analysis ---
st.header("Request Journey Analysis")
journey_group = analyze_request_journeys(df)
st.subheader("Journey Risk Scores (Top 10)")
st.dataframe(journey_group.head(10))

journey_forecast = forecast_journey_anomalies(journey_group, time_interval)
if journey_forecast is not None:
    st.subheader("Forecast for Next Interval")
    st.write(f"Forecasted anomalous journeys count: {journey_forecast:.2f}")
else:
    st.write("Insufficient journey data for forecasting.")

# --- 3. Forecasting for Each Group ---
st.header("Forecasts by Environment & Endpoint")
unique_groups = grouped[['environment', 'endpoint']].drop_duplicates()
forecast_results = []
for idx, row in unique_groups.iterrows():
    env = row['environment']
    endpoint = row['endpoint']
    forecast_rt = forecast_next_interval_prophet(grouped, env, endpoint, column='avg_response_time')
    forecast_err = forecast_next_interval_prophet(grouped, env, endpoint, column='error_rate')
    forecast_results.append({
        'environment': env,
        'endpoint': endpoint,
        'forecast_avg_response_time_ms': forecast_rt,
        'forecast_error_rate': forecast_err
    })

forecasts_df = pd.DataFrame(forecast_results)
st.dataframe(forecasts_df)

# --- 4. Visualization for a Selected Group ---
st.header("Historical Trend & Anomaly Visualization")
selected_env = st.selectbox("Select Environment", unique_groups['environment'].unique())
selected_endpoint = st.selectbox(
    "Select Endpoint",
    unique_groups[unique_groups['environment'] == selected_env]['endpoint'].unique()
)
group_data = grouped[(grouped['environment'] == selected_env) & (grouped['endpoint'] == selected_endpoint)]
group_data = group_data.sort_values('time_bin')

fig, ax = plt.subplots(figsize=(12, 6))
ax.plot(group_data['time_bin'], group_data['avg_response_time'], marker='o', label='Avg Response Time')

# Highlight pattern-change anomalies if present
anomalies_pattern = rt_pattern_anomalies[
    (rt_pattern_anomalies['environment'] == selected_env) &
    (rt_pattern_anomalies['endpoint'] == selected_endpoint)
]
if not anomalies_pattern.empty:
    ax.scatter(anomalies_pattern['time_bin'], anomalies_pattern['avg_response_time'], color='red', label='Pattern Anomaly')

# Highlight spike anomalies if present
anomalies_spike = rt_spike_anomalies[
    (rt_spike_anomalies['environment'] == selected_env) &
    (rt_spike_anomalies['endpoint'] == selected_endpoint)
]
if not anomalies_spike.empty:
    ax.scatter(anomalies_spike['time_bin'], anomalies_spike['avg_response_time'], color='orange', label='Spike Anomaly')

ax.set_xlabel('Time Interval')
ax.set_ylabel('Avg Response Time (ms)')
ax.set_title(f"Response Time Trend for {selected_env} - {selected_endpoint}")
ax.legend()
st.pyplot(fig)

# --- 5. Sample Forecast Visualization ---
st.header("Sample Forecast Visualization")
if not forecasts_df.empty:
    st.subheader("Forecast for Average Response Time")
    # Use the first sample forecast as an example
    sample_index = 0
    sample_row = forecasts_df.iloc[sample_index]
    env = sample_row['environment']
    endpoint = sample_row['endpoint']
    forecast_value = sample_row['forecast_avg_response_time_ms']
    
    sample_group_data = grouped[(grouped['environment'] == env) & (grouped['endpoint'] == endpoint)]
    sample_group_data = sample_group_data.sort_values('time_bin')
    if not sample_group_data.empty:
        last_time = sample_group_data['time_bin'].max()
        forecast_time = last_time + pd.Timedelta(minutes=15)
        fig2, ax2 = plt.subplots(figsize=(12, 6))
        ax2.plot(sample_group_data['time_bin'], sample_group_data['avg_response_time'], marker='o', label='Historical Data')
        ax2.plot([last_time, forecast_time], [forecast_value, forecast_value], linestyle='--', color='green', linewidth=2, label='Forecast')
        ax2.scatter(forecast_time, forecast_value, color='green', marker='x', s=100)
        ax2.set_xlabel('Time')
        ax2.set_ylabel('Avg Response Time (ms)')
        ax2.set_title(f"Forecast for Avg Response Time - {env} - {endpoint}")
        ax2.legend()
        st.pyplot(fig2)
        
# --- 6. Anomaly Alerts Section ---
st.header("Anomaly Alerts")
alerts_file = "alerts.json"
if os.path.exists(alerts_file):
    try:
        with open(alerts_file, "r") as f:
            alerts = json.load(f)
        if alerts:
            alerts_df = pd.DataFrame(alerts)
            st.dataframe(alerts_df)
        else:
            st.write("No alerts available.")
    except Exception as e:
        st.error(f"Error loading alerts: {e}")
else:
    st.write("Alerts file not found. Please ensure anomaly alerts have been generated.")
