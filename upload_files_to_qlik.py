# upload_files_to_qlik.py

import os
import json  # Import the json module
import requests

# Define your Qlik Cloud URL and API endpoint
qlik_url = "https://" + os.environ['QLIK_TENNANT_URL'] + "/api/v1/data-files" # Update with your Qlik Cloud URL

# Set up headers with the API key
headers = {
    "Authorization": f"Bearer {os.environ['QLIK_API_KEY']}",
}

# File to upload
base_directory = "."
qlik_connection_id = os.environ['QLIK_CONNECTION_ID']

# Iterate through each file in the repository
for root, _, files in os.walk(base_directory):
    for file_name in files:
        # Only process .qvs files
        if file_name.endswith(".qvs"):
            file_path = os.path.join(root, file_name)

            # Define the JSON metadata payload
            json_payload = {
                "name": f"{file_name}",  # Update with desired path in Qlik
                "connectionId": qlik_connection_id
            }

            # Prepare the multipart form-data
            files_payload = {
                "File": (file_name, open(file_path, 'rb')),
                "Json": (None, json.dumps(json_payload), "application/json")
            }

            # Send the POST request
            response = requests.post(
                qlik_url,
                headers=headers,
                files=files_payload
            )

            # Check if the upload was successful
            if response.status_code == 201:
                print(f"File '{file_name}' uploaded successfully!")
            else:
                print(f"Failed to upload '{file_name}':", response.status_code, response.text)
