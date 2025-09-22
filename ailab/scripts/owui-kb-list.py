import requests
import json

def main():
    # curl -X GET https://ami.inspection.alpha.canada.ca/api/v1/knowledge/list \
    # -H "Authorization: Bearer $TOKEN"
    TOKEN = ""
    BASE_URL = "http://open-webui:8080"
    response = requests.get(
        BASE_URL + "/api/v1/knowledge/list",
        headers={"Authorization": f"Bearer {TOKEN}"},
    )

    # write the response to a file
    with open("knowledge_list.json", "w") as f:
        json.dump(response.json(), f, indent=4)

if __name__ == "__main__":
    main()
