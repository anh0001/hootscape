#!/usr/bin/env python3
import requests

def send_test_post():
    # Target URL for the POST command
    url = "http://192.168.1.84:9123/owl/command"
    
    # JSON payload mimicking the curl command data
    payload = {
        "speech": {
            "text": "Hello, HootScape, how are you doing? are you good?!",
            "rate": 1.0,
            "pitch": 1.0
        },
        "movements": [
            {"type": 5, "duration": 1},
            {"type": 6, "duration": 1}
        ]
    }
    
    # HTTP header specifying that we're sending JSON data
    headers = {"Content-Type": "application/json"}
    
    try:
        # Sending the POST request
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()  # Raise an error for bad status codes
        
        # Output the status code and response text
        print("Response status:", response.status_code)
        print("Response body:", response.text)
    except requests.exceptions.RequestException as error:
        # Output any error that occurred during the request
        print("Error occurred:", error)

if __name__ == '__main__':
    send_test_post()