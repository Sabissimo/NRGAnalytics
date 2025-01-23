# upload_files_to_qlik.py

import os
import json  # Import the json module
import requests

# Define your Qlik Cloud URL and API endpoint
qlik_url = "https://" + os.environ['QLIK_TENNANT_URL'] + "/api/v1/data-files"

# Set up headers with the API key
headers = {
    "Authorization": f"Bearer {os.environ['QLIK_API_KEY']}",
}

# File to upload
base_directory = "."
qlik_connection_id = os.environ['QLIK_CONNECTION_ID']

file_names = []

# Iterate through each file in the repository
for root, _, files in os.walk(base_directory):
    for file_name in files:
        # Only process .qvs files
        if file_name.endswith(".qvs"):
            file_names.append(file_name)
           
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
            
            file_id = ""
            response = requests.get(f"{qlik_url}?connectionId={qlik_connection_id}&name={file_name}", headers=headers)
            if response.status_code == 200:
                if len(response.json()['data']) > 0:
                    file_id = response.json()['data'][0]['id']

            if file_id != "":
                # Send the POST request
                response = requests.put(
                    f"{qlik_url}/{file_id}",
                    headers=headers,
                    files=files_payload
                )
            else:
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

response = requests.get(f"{qlik_url}?connectionId={qlik_connection_id}&baseNameWildcard=*.qvs", headers=headers)
if response.status_code == 200:
    if len(response.json()['data']) > 0:
        for file in response.json()['data']:
            if not file['name'] in file_names:
                # Send the POST request
                response = requests.delete(
                    f"{qlik_url}/{file['id']}",
                    headers=headers
                )

                # Check if the upload was successful
                if response.status_code == 204:
                    print(f"File '{file['name']}' deleted successfully!")
                else:
                    print(f"Failed to delete '{file['name']}':", response.status_code, response.text)