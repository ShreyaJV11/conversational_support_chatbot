import requests
import os

SALESFORCE_INSTANCE = os.getenv("SF_INSTANCE")
SALESFORCE_TOKEN = os.getenv("SF_TOKEN")


def create_salesforce_case(subject, description, email):

    url = f"{SALESFORCE_INSTANCE}/services/data/v59.0/sobjects/Case"

    headers = {
        "Authorization": f"Bearer {SALESFORCE_TOKEN}",
        "Content-Type": "application/json"
    }

    payload = {
        "Subject": subject,
        "Description": description,
        "SuppliedEmail": email,
        "Origin": "Chatbot"
    }

    response = requests.post(url, json=payload, headers=headers)

    return response.json()