# Pipe Class: This class functions as a customizable pipeline.
# It can be adapted to work with any external or internal models,
# making it versatile for various use cases outside of just OpenAI models.
from pydantic import BaseModel
from typing import Optional, Union, Generator, Iterator

import os
import requests
import json


class Pipe:
    class Valves(BaseModel):
        OCR_API_BASE_URL: str = "http://jibity-doctr:8080/"
        OCR_API_KEY: str = "your-key"
        pass

    def __init__(self):
        self.type = "manifold"
        self.valves = self.Valves()
        # self.pipes = self.get_openai_models()
        pass

    def request_ocr(self, file_list):
        headers = {}

        params = {"det_arch": "linknet_resnet50", "reco_arch": "vitstr_base"}

        files = [
            (
                "files",
                (
                    os.path.basename(file_list[0]["name"]),
                    open(file_list[0]["file"]["path"], "rb"),
                    "application/pdf",
                ),
            ),
        ]

        response = requests.post(
            "http://jibity-doctr:8080/kie/", params=params, files=files, headers=headers
        )

        # print(f"Status: {response.status_code}")
        # print(f"Response: {response.text}")  # This will show the actual error message
        # print(f"Headers: {response.headers}")
        assert response.status_code == 200
        json_response = response.json()
        print("Response JSON:", json.dumps(json_response))
        return json_response

    def pipe(
        self,
        body: dict,
        __user__: dict,
        # __request__: Request,
        __files__: Optional[list] = None,
        **kwargs,
    ) -> Union[str, Generator, Iterator]:
        # This is where you can add your custom pipelines like RAG.
        # print(f"pipe:{__name__}")
        # print(f"body:{body}")
        # print(f"__user__:{__user__}")
        # print(f"__files__:{__files__}")
        # print(f"kwargs:{kwargs}")

        if "user" in body:
            print(body["user"])
            del body["user"]

        json_response = self.request_ocr(__files__)

        try:
            # Clear files from metadata to prevent hybrid search
            if "metadata" in body and "files" in body["metadata"]:
                body["metadata"]["files"] = []

            return json.dumps(json_response, indent=4)
        except Exception as e:
            return f"Error: {e}"


"""
title: Enhanced Message Processor
author: @admin
version: 1.2.0
required_open_webui_version: 0.5.0
icon_url: data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMjQiIGhlaWdodD0iMjQiIHZpZXdCb3g9IjAgMCAyNCAyNCIgZmlsbD0ibm9uZSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KPHBhdGggZD0iTTEyIDJMMTMuMDkgOC4yNkwyMCA5TDEzLjA5IDE1Ljc0TDEyIDIyTDEwLjkxIDE1Ljc0TDQgOUwxMC45MSA4LjI2TDEyIDJaIiBzdHJva2U9ImN1cnJlbnRDb2xvciIgc3Ryb2tlLXdpZHRoPSIyIiBzdHJva2UtbGluZWNhcD0icm91bmQiIHN0cm9rZS1saW5lam9pbj0icm91bmQiLz4KPHN2Zz4K
requirements: requests,beautifulsoup4
"""

# from pydantic import BaseModel


class Action:
    def __init__(self):
        self.valves = self.Valves()

    class Valves(BaseModel):
        api_key: str = ""
        processing_mode: str = "standard"

    async def action(
        self,
        body: dict,
        __user__=None,
        __event_emitter__=None,
        __event_call__=None,
    ):
        # Send initial status
        await __event_emitter__(
            {"type": "status", "data": {"description": "Processing message..."}}
        )

        # Get user confirmation
        response = await __event_call__(
            {
                "type": "confirmation",
                "data": {
                    "title": "Process Message",
                    "message": "Do you want to enhance this message?",
                },
            }
        )

        if not response:
            return {"content": "Action cancelled by user"}

        # Process the message
        original_content = body.get("content", "")
        enhanced_content = f"Enhanced: {original_content}"

        return {"content": enhanced_content}

        # Access uploaded files
        if body.get("files"):
            for file in body["files"]:
                # Process file based on type
                if file["type"] == "image":
                    # Image processing logic
                    pass

        # Return new files
        return {
            "content": "Analysis complete",
            "files": [
                {
                    "type": "image",
                    "url": "generated_chart.png",
                    "name": "Analysis Chart",
                }
            ],
        }

    # async def action(self, body: dict):
    #     message = body

    #     # Access uploaded files
    #     if message.get("files"):
    #         for file in message["files"]:
    #             # Process file based on type
    #             if file["type"] == "image":
    #                 # Image processing logic
    #                 pass

    #     # Return new files
    #     return {
    #         "content": "Analysis complete",
    #         "files": [
    #             {
    #                 "type": "image",
    #                 "url": "generated_chart.png",
    #                 "name": "Analysis Chart"
    #             }
    #         ]
    #     }


import os
import requests
from datetime import datetime
from pydantic import BaseModel, Field


class Tools:
    def __init__(self):
        pass

    def describe_image_with_llamacpp(
        self,
        image_path: str = Field(
            ..., description="The full, local file path to the image to be described."
        ),
    ) -> str:
        """
        Analyzes the visual contents of an image from a file path using the fast llama.cpp backend.
        """
        pass

    # Add your custom tools using pure Python code here, make sure to add type hints and descriptions

    def get_user_name_and_email_and_id(self, __user__: dict = {}) -> str:
        """
        Get the user name, Email and ID from the user object.
        """

        # Do not include a descrption for __user__ as it should not be shown in the tool's specification
        # The session user object will be passed as a parameter when the function is called

        print(__user__)
        result = ""

        if "name" in __user__:
            result += f"User: {__user__['name']}"
        if "id" in __user__:
            result += f" (ID: {__user__['id']})"
        if "email" in __user__:
            result += f" (Email: {__user__['email']})"

        if result == "":
            result = "User: Unknown"

        return result

    def get_current_time(self) -> str:
        """
        Get the current time in a more human-readable format.
        """

        now = datetime.now()
        current_time = now.strftime("%I:%M:%S %p")  # Using 12-hour format with AM/PM
        current_date = now.strftime(
            "%A, %B %d, %Y"
        )  # Full weekday, month name, day, and year

        return f"Current Date and Time = {current_date}, {current_time}"

    def calculator(
        self,
        equation: str = Field(
            ..., description="The mathematical equation to calculate."
        ),
    ) -> str:
        """
        Calculate the result of an equation.
        """

        # Avoid using eval in production code
        # https://nedbatchelder.com/blog/201206/eval_really_is_dangerous.html
        try:
            result = eval(equation)
            return f"{equation} = {result}"
        except Exception as e:
            print(e)
            return "Invalid equation"

    def get_current_weather(
        self,
        city: str = Field(
            "New York, NY", description="Get the current weather for a given city."
        ),
    ) -> str:
        """
        Get the current weather for a given city.
        """

        api_key = os.getenv("OPENWEATHER_API_KEY")
        if not api_key:
            return (
                "API key is not set in the environment variable 'OPENWEATHER_API_KEY'."
            )

        base_url = "http://api.openweathermap.org/data/2.5/weather"
        params = {
            "q": city,
            "appid": api_key,
            "units": "metric",  # Optional: Use 'imperial' for Fahrenheit
        }

        try:
            response = requests.get(base_url, params=params)
            response.raise_for_status()  # Raise HTTPError for bad responses (4xx and 5xx)
            data = response.json()

            if data.get("cod") != 200:
                return f"Error fetching weather data: {data.get('message')}"

            weather_description = data["weather"][0]["description"]
            temperature = data["main"]["temp"]
            humidity = data["main"]["humidity"]
            wind_speed = data["wind"]["speed"]

            return f"Weather in {city}: {temperature}°C"
        except requests.RequestException as e:
            return f"Error fetching weather data: {str(e)}"
