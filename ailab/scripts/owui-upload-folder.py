import requests
import json
import os
from datetime import datetime
import time

# Configuration
BASE_URL = "https://ami.inspection.alpha.canada.ca"  # Replace with your Open WebUI URL
API_KEY = ""  
HEADERS = {"Authorization": f"Bearer {API_KEY}"}
LOG_PATH = "owui_log.txt"

def write_log(message):
    print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - {message}\n")
    with open(LOG_PATH, "a") as log_file:
        log_file.write(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - {message}\n") 
    print(message)
    return

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


def add_files_to_knowledge_base(file_ids, collection_id, completed_path, errored_path):
    errors = 0
    for file_id in file_ids:
        try:
            time.sleep(1)
            process_response = requests.post(
                f"{BASE_URL}/api/v1/knowledge/{collection_id}/file/add",
                headers=HEADERS,
                json={
                    "file_id": file_id,
                },
            )

            if process_response.ok:
                with open(completed_path, "a") as f:
                    f.write(file_id + "\n")
                write_log(f"File ID {file_id} added to knowledge base collection '{collection_id}'")
            else:
                # Handle duplicate content error as acceptable
                if (
                    process_response.status_code == 400
                    and "Duplicate content detected" in process_response.text
                ):
                    write_log(f"Duplicate content detected for file ID {file_id}. Skipping...")
                    continue
                write_log(f"Failed to add file to knowledge base: {process_response.text}")
                raise Exception(
                    f"Failed to add file to knowledge base: {process_response.status_code}"
                )
        except Exception as e:
            write_log(f"Request failed: {e}")
            with open(errored_path, "a") as f:
                f.write(file_id + "\n")
            errors += 1
            if errors > 5:
                write_log("Too many errors. Exiting.")
                exit()
            write_log(f"Sleeping for {errors} minutes due to errors...")
            time.sleep(errors*60)
            continue

    return


def upload_files(file_list, uploaded_path, errored_path):
    file_ids = []
    API_ENDPOINT = "/api/v1/files/"

    headers = {**HEADERS}
    errors = 0
    url = f"{BASE_URL}{API_ENDPOINT}"

    for file_path in file_list:
        try:
            time.sleep(1)
            if not os.path.exists(file_path):
                write_log(f"Error: File not found at {file_path}")
                exit()

            with open(file_path, "rb") as f:
                write_log(f"Sending POST request to: {url}")
                response = requests.post(
                    url, headers=headers, files={"file": (file_path, f, 'text/plain')}, timeout=None
                )

                # --- Handle Response ---
                write_log(f"Status Code: {response.status_code}")
                response_json = response.json() if response.status_code == 200 else None
                # print("Response JSON:", response.text)

                if response_json and "id" in response_json:
                    file_ids.append(response_json["id"])
                    write_log(f"File ID: {response_json['id']}")
                    with open(uploaded_path, "a") as f:
                        f.write(response_json["id"] + "\n")
                    with open(completed_path + ".path", "a") as f:
                        f.write(file_path + "\n")
                    write_log(f"File uploaded successfully: {file_path}")
                else:
                    write_log("No file ID found in the response.")
                    write_log("Response:" + response.text)
                    if 'stream timeout' in response.text:
                        with open(errored_path, "a") as f:
                            f.write(file_path + "\n")
                        continue
                    else:
                        raise Exception("File upload failed or no ID returned.")

                # Raise an exception for bad status codes (4xx or 5xx)
                response.raise_for_status()
        except Exception as e:
            errors += 1
            write_log(f"Request failed: {e}")
            with open(errored_path, "a") as f:
                f.write(file_path + "\n")
            if errors > 5:
                write_log("Too many errors. Exiting.")
                exit()
            write_log(f"Sleeping for {errors} minutes due to errors...")
            time.sleep(errors*60)
            continue

    return 


def get_files_in_dir(directory):
    file_list = []
    for root, dirs, files in os.walk(directory):
        for file in files:
            if not file.endswith(".json"):
                file_list.append(os.path.join(root, file))
    return file_list


# Example usage
if __name__ == "__main__":
    directory = "public-guidance/public-guidance/"
    collection_id = "76ede64d-ce05-4e12-a6da-72cffe5ffe52"
    collection_name = "Finesse-Public"

    completed_path = "owui_completed.txt"
    errored_path = "owui_errored.txt"
    file_list_path = "owui_filelist.txt"
    uploaded_path = "owui_uploaded.txt"

    completed = []
    errored = []
    file_list = []
    uploaded = []

    if os.path.exists(file_list_path):
        with open(file_list_path, "r") as f:
            file_list = f.read().splitlines()
    else:
        file_list = get_files_in_dir(directory)
        with open(file_list_path, "w") as f:
            for file in file_list:
                f.write(file + "\n")
    if os.path.exists(completed_path):
        with open(completed_path, "r") as f:
            completed = f.read().splitlines()
    if os.path.exists(errored_path):
        with open(errored_path, "r") as f:
            errored = f.read().splitlines()
    if os.path.exists(completed_path + ".path"):
        with open(completed_path + ".path", "r") as f:
            uploaded = f.read().splitlines()
    file_list = [file for file in file_list if file not in uploaded]
    if not file_list:
        write_log("No files to process.")
        exit()
    write_log(f"Files to process: {len(file_list)}")
    write_log(f"Files already processed: {len(completed)}")
    write_log(f"Files errored: {len(errored)}")

    upload_files(file_list, uploaded_path, errored_path)
    # process_files(file_ids, collection_name)
    
    if os.path.exists(uploaded_path):
        with open(uploaded_path, "r") as f:
            uploaded = f.read().splitlines()
    uploaded = [file for file in uploaded if file not in completed]
    write_log(f"Files to add to knowledge base: {len(uploaded)}")
    if not uploaded:
        write_log("No files to add to knowledge base.")
        exit()
    add_files_to_knowledge_base(uploaded, collection_id, completed_path, errored_path)

    write_log("Upload and processing completed.")
