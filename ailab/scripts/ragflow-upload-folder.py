import requests
import json
import os
from datetime import datetime
import time

# Configuration
BASE_URL = "https://ragflow.inspection.alpha.canada.ca"  # Replace with your Open WebUI URL
API_KEY = ""  
HEADERS = {"Authorization": f"Bearer {API_KEY}"}
LOG_PATH = "rg_log.txt"

def write_log(message):
    print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - {message}\n")
    with open(LOG_PATH, "a") as log_file:
        log_file.write(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - {message}\n") 
    print(message)
    return

def process_files(dataset_id, file_ids, completed_path, errored_path):
    endpoint = f"{BASE_URL}/api/v1/datasets/{dataset_id}/chunks"
    headers  = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}"
    }

    errors = 0
    for file_id in file_ids:
        try:
            payload  = {
                "document_ids": [file_id]
            }
            resp = requests.post(endpoint, headers=headers, json=payload, timeout=30)
            resp.raise_for_status()
            write_log(f"File ID {file_id} added to dataset {dataset_id}")
            write_log(f"Response: {resp.text}")
            with open(completed_path, "a") as f:
                f.write(file_id + "\n")
        except requests.HTTPError as http_err:
            try:         # server may return JSON error details
                err_msg = resp.json()
            except Exception:
                err_msg = resp.text
            write_log(f"❌ HTTP {resp.status_code} – {err_msg}")
            raise Exception(f"Failed to process file: {resp.status_code}")
        except Exception as e:
            write_log(f"❌ Request failed: {e}")
            with open(errored_path, "a") as f:
                f.write(file_id + "\n")
            errors += 1
            if errors > 5:
                write_log("Too many errors, stopping.")
                break
            write_log(f"Retrying in {errors} minutes...")
            time.sleep(errors*60)
    return


def get_files_in_dir(directory):
    file_list = []
    for root, dirs, files in os.walk(directory):
        for file in files:
            if not file.endswith(".json"):
                file_list.append(os.path.join(root, file))
    return file_list

def upload_files(dataset_id, file_list, uploaded_path, errored_path):

    endpoint = f"{BASE_URL}/api/v1/datasets/{dataset_id}/documents"
    headers  = {
        "Authorization": f"Bearer {API_KEY}"
    }

    errors = 0
    for path in file_list:
        try:
            files_param = []
            with open(path, "rb") as f:
                files_param.append(("file", (path, f, None)))
                
                resp = requests.post(endpoint, headers=headers, files=files_param, timeout=60)
                resp.raise_for_status()
                write_log(f"File uploaded successfully: {path}")
                write_log(f"Response: {resp.text}")
                with open(uploaded_path, "a") as f:
                    f.write(resp.json()['data'][0]['id'] + "\n")
                with open(completed_path + ".path", "a") as f:
                    f.write(path + "\n")
        except requests.HTTPError as http_err:
            try:
                err_msg = resp.json()
            except Exception:
                err_msg = resp.text
            write_log(f"❌ HTTP {resp.status_code} → {err_msg}")
            raise Exception(f"Failed to process file: {resp.status_code}")
        except Exception as e:
            write_log(f"❌ Request failed: {e}")
            with open(errored_path, "a") as f:
                f.write(path + "\n")
            errors += 1
            if errors > 5:
                write_log("Too many errors, stopping.")
                break
            write_log(f"Retrying in {errors} minutes...")
            time.sleep(errors*60)
    

def create_dataset(name):
    DATASET_NAME = name

    # OPTIONAL fields
    EMBEDDING_MODEL = "BAAI/bge-large-zh-v1.5@BAAI"
    CHUNK_METHOD    = "naive"
    PARSER_CONFIG   = {
        "auto_keywords":   0,
        "auto_questions":  0,
        "chunk_token_num": 1000,
        "delimiter":       "\n",
        "html4excel":      False,
        "layout_recognize":"DeepDOC",
        "tag_kb_ids":      [],
        "task_page_size":  12,
        "raptor":          {"use_raptor": False},
        "graphrag":        {"use_graphrag": False}
    }

    endpoint = f"{BASE_URL}/api/v1/datasets"
    headers  = {
        "Content-Type":  "application/json",
        "Authorization": f"Bearer {API_KEY}"
    }
    payload  = {
        "name":           DATASET_NAME,          # required
        "description":    "Demo dataset created via API",
        "embedding_model": EMBEDDING_MODEL,
        "permission":     "me",                  # or "team"
        "chunk_method":   CHUNK_METHOD,
        "pagerank":       0,
        "parser_config":  PARSER_CONFIG
    }

    dataset_id = None
    try:
        resp = requests.post(endpoint, headers=headers, json=payload, timeout=10)
        resp.raise_for_status()                       # raise if HTTP 4xx/5xx
        data = resp.json()                            # server’s JSON reply
        dataset_id = data["id"]
        write_log(f"Dataset created: {dataset_id}")
        write_log(json.dumps(data, indent=2, ensure_ascii=False))
    except requests.HTTPError as http_err:
        # If the server returned JSON errors, show them
        try:
            error_msg = resp.json()
        except Exception:
            error_msg = resp.text
        write_log(f"❌ HTTP error {resp.status_code} → {error_msg}")
    except requests.RequestException as e:
        write_log(f"❌ Request failed: {e}")
    
    return dataset_id

if __name__ == "__main__":
    directory = "public-guidance/public-guidance/"
    collection_id = "722d2604325d11f0b26432921762a367"
    collection_name = "Finesse-Public"

    completed_path = "rg_completed.txt"
    errored_path = "rg_errored.txt"
    file_list_path = "rg_filelist.txt"
    uploaded_path = "rg_uploaded.txt"

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
    process_files(collection_id, uploaded, completed_path, errored_path)

    write_log("Upload and processing completed.")
