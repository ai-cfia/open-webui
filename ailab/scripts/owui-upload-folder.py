import requests
import json
import os

# Configuration
BASE_URL = "http://your-open-webui-instance"  # Replace with your Open WebUI URL
API_KEY = "your-api-key-here"  # Replace with your API key
HEADERS = {"Authorization": f"Bearer {API_KEY}"}


def process_files(file_ids, collection_name):
    for file_id in file_ids:
        # Process the file with the given ID
        process_response = requests.post(
            f"{BASE_URL}/api/v1/retrieval/process/file",
            headers=HEADERS,
            json={
                "file_id": file_id,
                "collection_name": collection_name,
            },
        )

        if process_response.ok:
            print(f"File processed successfully: {file_id}")
        else:
            print(f"Failed to process file: {process_response.text}")
            raise Exception(f"Failed to process file: {process_response.status_code}")
    return


def add_files_to_knowledge_base(file_ids, collection_id):
    for id in file_ids:
        process_response = requests.post(
            f"{BASE_URL}/api/v1/knowledge/{collection_id}/file/add",
            headers=HEADERS,
            json={
                "file_id": id,
            },
        )

        if process_response.ok:
            print(f"File added to knowledge base collection '{collection_name}'")
        else:
            print(f"Failed to add file to knowledge base: {process_response.text}")
            raise Exception(
                f"Failed to add file to knowledge base: {process_response.status_code}"
            )

    return


def upload_files(file_list):
    file_ids = []
    # --- Configuration ---
    BASE_URL = "http://your_api_base_url"  # Replace with your API's base URL
    API_ENDPOINT = "/api/v1/files/"
    TOKEN = "your_bearer_token"  # Replace with your actual bearer token
    PROCESS_FILE = False  # Set to False if you don't want processing
    # ---------------------

    url = f"{BASE_URL}{API_ENDPOINT}"

    headers = {
        "Authorization": f"Bearer {TOKEN}",
        # 'Accept': 'application/json' # Good practice, though often not strictly required by requests
    }

    params = {"process": PROCESS_FILE}
    for file_path in file_list:
        if not os.path.exists(file_path):
            print(f"Error: File not found at {file_path}")
            exit()

        with open(file_path, "rb") as f:
            print(f"Sending POST request to: {url}")
            print(f"Params: {params}")
            # print(f"Headers: {headers}") # Uncomment to see headers (be careful with tokens)
            # print(f"Files payload structure (metadata as JSON string): {files_payload}") # Uncomment to inspect payload structure

            response = requests.post(
                url, headers=headers, params=params, files={"file": f}
            )

            # --- Handle Response ---
            print(f"\nStatus Code: {response.status_code}")
            response_json = response.json() if response.status_code == 200 else None

            if response_json and "id" in response_json:
                file_ids.append(response_json["id"])
                print(f"File ID: {response_json['id']}")
            else:
                print("Response JSON:", response_json)
                print("No file ID found in the response.")
                raise Exception("File upload failed or no ID returned.")

            # Raise an exception for bad status codes (4xx or 5xx)
            response.raise_for_status()

    return file_ids


def get_files_in_dir(directory):
    file_list = []
    for root, dirs, files in os.walk(directory):
        for file in files:
            if not file.endswith(".json"):
                file_list.append(os.path.join(root, file))
    return file_list


# Example usage
if __name__ == "__main__":
    directory = "path/to/your/dir"  # Change to your file path
    collection_name = "Finesse-Public"  # Change to your collection name

    file_list = get_files_in_dir(directory)

    file_ids = upload_files(file_list)
    add_files_to_knowledge_base(file_ids, collection_name)
    process_files(file_ids, collection_name)

    print("Completed Successfully")
