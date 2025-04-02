import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

# Generate dummy time series data (simulate 4 hours with 15-min intervals)
time_bins = pd.date_range(start=datetime.now() - timedelta(hours=4), periods=16, freq='15T')
# Generate a base response time (in ms) around 200ms with some noise
response_time = np.random.normal(200, 20, size=len(time_bins))
# Inject spike anomalies manually for demonstration
response_time[5] = 400  # Spike anomaly at one point
response_time[10] = 350  # Another spike anomaly

# Create a dummy forecast for the next interval (e.g., a slight increase)
forecast = response_time[-1] + 10  
future_time = time_bins[-1] + timedelta(minutes=15)

plt.figure(figsize=(10, 6))
plt.plot(time_bins, response_time, marker='o', label='Avg Response Time (ms)')
# Highlight anomaly points
plt.scatter([time_bins[5], time_bins[10]], [response_time[5], response_time[10]], 
            color='red', s=100, label='Anomaly')
# Mark the forecasted point
plt.scatter(future_time, forecast, color='green', marker='x', s=150, label='Forecast')
plt.xlabel('Time')
plt.ylabel('Avg Response Time (ms)')
plt.title('API Response Time Trend with Anomalies and Forecast')
plt.legend()
plt.tight_layout()
plt.savefig("response_time_forecast.png")
plt.show()
