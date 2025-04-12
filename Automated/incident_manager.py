import os
import json
import requests
from dotenv import load_dotenv
from datetime import datetime

# Load environment variables
load_dotenv()

class IncidentManager:
    def __init__(self):
        self.snow_url = os.getenv('SNOW_INSTANCE_URL')
        self.snow_username = os.getenv('SNOW_USERNAME')
        self.snow_password = os.getenv('SNOW_PASSWORD')
        self.slack_webhook = os.getenv('SLACK_WEBHOOK_URL')
        
        # ServiceNow API endpoint for incidents
        self.snow_incident_endpoint = f"{self.snow_url}/api/now/table/incident"
        
        # Headers for ServiceNow API
        self.snow_headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        # Headers for Slack webhook
        self.slack_headers = {
            "Content-Type": "application/json"
        }

    def create_snow_incident(self, alert):
        """Create an incident in ServiceNow"""
        try:
            # Prepare incident data
            incident_data = {
                "short_description": f"API Anomaly Alert: {alert['description']}",
                "description": f"""
                Alert Details:
                - Timestamp: {alert['timestamp']}
                - Priority: {alert['Priority']}
                - Description: {alert['description']}
                """,
                "priority": "1" if alert['Priority'] == "Critical" else "2",
                "impact": "2",  # Medium impact
                "urgency": "2",  # Medium urgency
                "category": "software",
                "subcategory": "api",
                "assignment_group": "API Support"
            }

            # Make API call to ServiceNow
            response = requests.post(
                self.snow_incident_endpoint,
                auth=(self.snow_username, self.snow_password),
                headers=self.snow_headers,
                json=incident_data
            )

            if response.status_code == 201:
                incident_number = response.json()['result']['number']
                print(f"Created ServiceNow incident: {incident_number}")
                return incident_number
            else:
                print(f"Failed to create ServiceNow incident. Status code: {response.status_code}")
                print(f"Response: {response.text}")
                return None

        except Exception as e:
            print(f"Error creating ServiceNow incident: {str(e)}")
            return None

    def send_slack_notification(self, alert, incident_number=None):
        """Send notification to Slack"""
        try:
            # Prepare Slack message
            message = {
                "blocks": [
                    {
                        "type": "header",
                        "text": {
                            "type": "plain_text",
                            "text": "🚨 API Anomaly Alert"
                        }
                    },
                    {
                        "type": "section",
                        "fields": [
                            {
                                "type": "mrkdwn",
                                "text": f"*Priority:*\n{alert['Priority']}"
                            },
                            {
                                "type": "mrkdwn",
                                "text": f"*Time:*\n{alert['timestamp']}"
                            }
                        ]
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"*Description:*\n{alert['description']}"
                        }
                    }
                ]
            }

            # Add incident number if available
            if incident_number:
                message["blocks"].append({
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*ServiceNow Incident:*\n{incident_number}"
                    }
                })

            # Make API call to Slack
            response = requests.post(
                self.slack_webhook,
                headers=self.slack_headers,
                json=message
            )

            if response.status_code == 200:
                print("Slack notification sent successfully")
            else:
                print(f"Failed to send Slack notification. Status code: {response.status_code}")
                print(f"Response: {response.text}")

        except Exception as e:
            print(f"Error sending Slack notification: {str(e)}")

    def process_alerts(self, alerts_file):
        """Process alerts from alerts.json file"""
        try:
            # Read alerts from file
            with open(alerts_file, 'r') as f:
                alerts = json.load(f)

            # Process each alert
            for alert in alerts:
                # Create ServiceNow incident
                incident_number = self.create_snow_incident(alert)
                
                # Send Slack notification
                self.send_slack_notification(alert, incident_number)

        except Exception as e:
            print(f"Error processing alerts: {str(e)}")

if __name__ == "__main__":
    # Initialize incident manager
    manager = IncidentManager()
    
    # Process alerts from alerts.json
    manager.process_alerts("alerts.json") 