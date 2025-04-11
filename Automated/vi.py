import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime
from prophet import Prophet
import warnings


# Suppress warnings
warnings.filterwarnings("ignore")

# ---- Assume the functions below are imported or defined above ----
# For example, you can put your earlier model code in a module called model.py and import here:
from automodel import load_data, preprocess_data, detect_response_time_spike_anomalies, detect_response_time_pattern_change, detect_error_rate_anomalies, analyze_request_journeys, forecast_journey_anomalies, forecast_next_interval_prophet, Rule

# In this example, I'll assume that those functions are available.

# Define file path (adjust as necessary)
DATA_FILE = "synthetic_full_datasetlakh.csv"

# --- Streamlit Dashboard Layout ---
st.set_page_config(page_title="Anomaly Detection Dashboard", layout="wide")
st.title("Anomaly Detection and Forecasting Dashboard")

# Sidebar: Load Data and Choose Options
st.sidebar.header("Options")
file_path = st.sidebar.text_input("Dataset Path", DATA_FILE)
time_interval = st.sidebar.selectbox("Aggregation Interval", ["15min", "30min", "1H"], index=0)

# Load and preprocess data
st.sidebar.subheader("Data Loading")
if st.sidebar.button("Load Data"):
    with st.spinner("Loading data..."):
        df = load_data(file_path)
        grouped = preprocess_data(df, time_interval)
        st.sidebar.success(f"Data loaded and aggregated ({len(grouped)} rows).")
        st.session_state.df = df
        st.session_state.grouped = grouped

# Ensure data is loaded
if "df" not in st.session_state or "grouped" not in st.session_state:
    st.warning("Please load data first in the sidebar.")
    st.stop()

df = st.session_state.df
grouped = st.session_state.grouped

# --- Anomaly Detection Section ---
st.header("Anomaly Detection Results")

col1, col2, col3 = st.columns(3)

with col1:
    st.subheader("Response Time Spikes")
    rt_spike_anomalies = detect_response_time_spike_anomalies(grouped)
    st.write(rt_spike_anomalies)
    
with col2:
    st.subheader("Response Time Pattern Changes")
    rt_pattern_anomalies = detect_response_time_pattern_change(grouped, ev_target_quantile=0.99)
    st.write(rt_pattern_anomalies)
    
with col3:
    st.subheader("Error Rate Anomalies")
    error_rate_anomalies = detect_error_rate_anomalies(grouped, ev_target_quantile=0.99)
    st.write(error_rate_anomalies)

# --- Request Journey Analysis ---
st.header("Request Journey Analysis")
journey_group = analyze_request_journeys(df)
st.subheader("Journey Risk Scores")
st.write(journey_group.head(10))

journey_forecast = forecast_journey_anomalies(journey_group, time_interval)
if journey_forecast is not None:
    st.subheader("Forecast for Next Interval")
    st.write(f"Forecasted anomalous journeys count: {journey_forecast:.2f}")
else:
    st.write("Insufficient journey data for forecasting.")

# --- Forecasting for Each Group ---
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
st.write(forecasts_df)

# --- Visualization for a Selected Group ---
st.header("Visualization Example")
selected_env = st.selectbox("Select Environment", unique_groups['environment'].unique())
selected_endpoint = st.selectbox("Select Endpoint", unique_groups[unique_groups['environment'] == selected_env]['endpoint'].unique())
group_data = grouped[(grouped['environment'] == selected_env) & (grouped['endpoint'] == selected_endpoint)].sort_values('time_bin')

fig, ax = plt.subplots(figsize=(12, 6))
ax.plot(group_data['time_bin'], group_data['avg_response_time'], marker='o', label='Avg Response Time')
# Highlight spike anomalies if any
anomalies_spike = rt_spike_anomalies[(rt_spike_anomalies['environment'] == selected_env) & (rt_spike_anomalies['endpoint'] == selected_endpoint)]
if not anomalies_spike.empty:
    ax.scatter(anomalies_spike['time_bin'], anomalies_spike['avg_response_time'], color='red', label='Spike Anomaly')
ax.set_xlabel('Time Interval')
ax.set_ylabel('Avg Response Time (ms)')
ax.set_title(f"Response Time Trend for {selected_env} - {selected_endpoint}")
ax.legend()
st.pyplot(fig)

# --- Rule Engine Section ---
st.header("Rule Engine & Combined Alerts")
# For demonstration, compute thresholds over the whole grouped dataset.
# (In your production code, you may compute these per group.)
threshold_500 = np.percentile(grouped['error_count'], 99)  # example threshold for 500 errors
threshold_404 = np.percentile(grouped['error_count'], 99)  # example threshold for 404 errors

rules = []
rules.append(Rule(
    rule_id=1,
    description=f"Internal Server Errors (500) - Dynamic: if count >= {threshold_500:.2f}",
    window_minutes=20,
    condition_func=lambda d: 0,  # Replace with your actual function; dummy here
    threshold=threshold_500,
    level="Warning"
))
rules.append(Rule(
    rule_id=2,
    description=f"404 Not Found - Dynamic: if count >= {threshold_404:.2f}",
    window_minutes=20,
    condition_func=lambda d: 0,  # Replace with your actual function; dummy here
    threshold=threshold_404,
    level="Warning"
))

st.write("Defined Rules:")
for rule in rules:
    st.write(rule)

# Let user club rules together
st.subheader("Combine Rules")
user_input = st.text_input("Enter rule IDs (comma separated) to combine, or leave empty:")
combined_rule = None
if user_input:
    try:
        selected_ids = [int(x.strip()) for x in user_input.split(',') if x.strip().isdigit()]
        selected_rules = [r for r in rules if r.rule_id in selected_ids]
        if len(selected_rules) < 2:
            st.warning("Please select at least two rules to combine.")
        else:
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
            combined_description = "Combined Rule (" + " AND ".join([str(r.rule_id) for r in selected_rules]) + "): "
            combined_description += "Alert if all selected rules are triggered."
            combined_rule = CombinedRule(combined_description, selected_rules)
            st.success("Combined Rule Created:")
            st.write(combined_rule)
    except Exception as e:
        st.error("Error in combining rules.")
        
if combined_rule:
    current_time = df["timestamp_dt"].max()
    triggered, metrics = combined_rule.evaluate(df, current_time)
    st.write(f"Combined Rule Evaluation: {'TRIGGERED' if triggered else 'Not triggered'}")
    st.write("Metrics:", metrics)
