import pandas as pd
from datetime import timedelta

csv_file = './Parsed_Log_Data.csv'  

def load_data(file_path):
    df = pd.read_csv(file_path)
    if 'Parsed Timestamp' in df.columns:
        df['Parsed Timestamp'] = pd.to_datetime(df['Parsed Timestamp'])
    elif 'timestamp' in df.columns:
        df['Parsed Timestamp'] = pd.to_datetime(df['timestamp'])
    else:
        raise Exception("Timestamp column not found in dataset.")
    return df

df = load_data(csv_file)

# Sorting the DataFrame
df_sorted = df.sort_values('Parsed Timestamp').copy()
df_sorted.set_index('Parsed Timestamp', inplace=True)

# Create indicator columns based on rules
df_sorted['is500'] = (df_sorted['Status Code'] == 500).astype(int)
df_sorted['is404'] = (df_sorted['Status Code'] == 404).astype(int)
df_sorted['is403'] = (df_sorted['Status Code'] == 403).astype(int)
df_sorted['is4xx'] = ((df_sorted['Status Code'] >= 400) & (df_sorted['Status Code'] < 500)).astype(int)
df_sorted['is5xx'] = ((df_sorted['Status Code'] >= 500) & (df_sorted['Status Code'] < 600)).astype(int)
# Combined errors for 4xx & 5xx
df_sorted['combinedError'] = df_sorted['is4xx'] + df_sorted['is5xx']
# POST requests from Safari
df_sorted['isSafariPost'] = ((df_sorted['Method'] == 'POST') & (df_sorted['Browser'].str.contains('Safari', na=False))).astype(int)
# Requests coming from UNKNOWN browsers
df_sorted['isUnknownBrowser'] = (df_sorted['Browser'] == 'UNKNOWN').astype(int)

# --- Define Alert Rule Functions ---
alerts = []

# Function to evaluate a rolling window series and append alerts
def evaluate_alerts(rolling_series, window_minutes, rule_name, thresholds):
    for timestamp, count in rolling_series.items():
        for threshold, severity in thresholds:
            if count >= threshold:
                alerts.append({
                    'Start Time': timestamp,
                    'End Time': timestamp + timedelta(minutes=window_minutes),
                    'Rule': rule_name,
                    'Count': count,
                    'Severity': severity
                })
              
                break



# 1. Internal Server Errors (500) in a 20-minute window
rolling_500 = df_sorted['is500'].rolling('20min').sum()
evaluate_alerts(rolling_500, 20, '500 Errors', [(20, 'Critical'), (10, 'Warning')])

# 2. 404 Not Found errors in a 20-minute window
rolling_404 = df_sorted['is404'].rolling('20min').sum()
evaluate_alerts(rolling_404, 20, '404 Errors', [(20, 'Critical'), (10, 'Warning')])

# 3. 403 Forbidden errors in a 20-minute window
rolling_403 = df_sorted['is403'].rolling('20min').sum()
evaluate_alerts(rolling_403, 20, '403 Errors', [(20, 'Critical'), (10, 'Warning')])

# 4. Aggregated Errors (4xx and 5xx) in a 20-minute window
rolling_combined = df_sorted['combinedError'].rolling('20min').sum()
evaluate_alerts(rolling_combined, 20, 'Combined 4xx & 5xx Errors', [(20, 'Critical'), (10, 'Warning')])

# 5. POST Requests from Safari in a 15-minute window
rolling_safari_post = df_sorted['isSafariPost'].rolling('15min').sum()
evaluate_alerts(rolling_safari_post, 15, 'POST Requests from Safari', [(10, 'Warning')])

# 6. Requests from UNKNOWN browsers in a 30-minute window
rolling_unknown_browser = df_sorted['isUnknownBrowser'].rolling('30min').sum()
evaluate_alerts(rolling_unknown_browser, 30, 'UNKNOWN Browser Requests', [(15, 'Warning')])

# --- Display Alert Summary ---
alerts_df = pd.DataFrame(alerts)
if not alerts_df.empty:
    alerts_df.sort_values('Start Time', inplace=True)
    print("=== Alerts Generated ===")
    print(alerts_df)
else:
    print("No alerts generated with the current thresholds.")
