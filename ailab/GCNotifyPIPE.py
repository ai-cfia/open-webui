# Pipe Class: This class functions as a customizable pipeline.
# It can be adapted to work with any external or internal models,
# making it versatile for various use cases outside of just OpenAI models.
from pydantic import BaseModel
from typing import Optional, Union, Generator, Iterator
import pandas as pd

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

    def request_ocr_page(self, file_list, page_num):
        """Process a single page of the PDF"""
        headers = {}

        params = {
            "det_arch": "linknet_resnet50",
            "reco_arch": "vitstr_base",
            "pg_start": page_num,
            "pg_end": page_num
        }

        # Construct file path: /app/backend/data/uploads/{file_id}_{filename}
        file_id = file_list[0]["id"]
        filename = file_list[0]["file"]["filename"]
        file_path = f"/app/backend/data/uploads/{file_id}_{filename}"

        files = [
            (
                "files",
                (
                    os.path.basename(file_list[0]["name"]),
                    open(file_path, "rb"),
                    "application/pdf",
                ),
            ),
        ]

        response = requests.post(
            "http://jibity-doctr:8080/ocr/", params=params, files=files, headers=headers
        )

        assert response.status_code == 200
        json_response = response.json()
        return json_response
    
    def process_dataframe(self, df):
        """Process the DataFrame to extract insights or perform analysis"""
        if df is None or df.empty:
            return "No data available for analysis."

        # Example: Count total words and average confidence
        pd.set_option('display.max_columns', None)
        print(f"Dataframe head:\n{df.head(20)}")
        total_words = len(df)
        avg_confidence = df['confidence'].mean() if 'confidence' in df.columns else 0

        summary = f"Total words detected: {total_words}\nAverage confidence: {avg_confidence:.2f}\n"
        return summary

    def simplify_ocr_to_lines(self, ocr_response):
        """
        Simplify OCR response by merging words on the same line in correct order
        Uses the leftmost word's geometry as the line geometry

        Args:
            ocr_response: The OCR JSON response

        Returns:
            List of dictionaries with line-level data
        """
        try:
            simplified_lines = []

            if isinstance(ocr_response, list) and len(ocr_response) > 0:
                page_data = ocr_response[0]

                if 'items' in page_data:
                    for item_idx, item in enumerate(page_data['items']):
                        if 'blocks' in item:
                            for block_idx, block in enumerate(item['blocks']):
                                if 'lines' in block:
                                    for line_idx, line in enumerate(block['lines']):
                                        if 'words' in line and line['words']:
                                            # Sort words by x-coordinate for correct reading order
                                            sorted_words = sorted(line['words'],
                                                                 key=lambda w: w.get('geometry', [0])[0] if w.get('geometry') else 0)

                                            # Extract word texts and confidences
                                            word_texts = []
                                            word_confidences = []

                                            for word in sorted_words:
                                                if 'value' in word:
                                                    word_texts.append(word['value'])
                                                    word_confidences.append(word.get('confidence', 0))

                                            # Use leftmost word's geometry as line geometry
                                            leftmost_word = sorted_words[0]
                                            line_geometry = leftmost_word.get('geometry', [])

                                            # Create simplified line data
                                            line_data = {
                                                'text': ' '.join(word_texts),
                                                'confidence': sum(word_confidences) / len(word_confidences) if word_confidences else 0,
                                                'geometry': line_geometry,
                                                'item_id': item_idx,
                                                'block_id': block_idx,
                                                'line_id': line_idx,
                                                'word_count': len(word_texts)
                                            }

                                            simplified_lines.append(line_data)

            # Combine lines with similar y-coordinates (within 0.001)
            if simplified_lines:
                simplified_lines = self._combine_similar_y_lines(simplified_lines)

            return simplified_lines

        except Exception as e:
            print(f"Error simplifying OCR response: {e}")
            return []

    def _combine_similar_y_lines(self, lines, y_threshold=0.002):
        """
        Combine lines that have similar y-coordinates (likely same line of text)

        Args:
            lines: List of line dictionaries
            y_threshold: Maximum difference in y-coordinate to consider lines as same

        Returns:
            List of combined line dictionaries
        """
        if not lines:
            return lines

        # Sort lines by y-coordinate first
        sorted_lines = sorted(lines, key=lambda x: x['geometry'][1] if x['geometry'] and len(x['geometry']) > 1 else 0)

        combined_lines = []
        current_group = [sorted_lines[0]]

        for i in range(1, len(sorted_lines)):
            current_line = sorted_lines[i]
            previous_line = sorted_lines[i-1]

            # Get y-coordinates (second value in geometry)
            current_y = current_line['geometry'][1] if current_line['geometry'] and len(current_line['geometry']) > 1 else 0
            previous_y = previous_line['geometry'][1] if previous_line['geometry'] and len(previous_line['geometry']) > 1 else 0

            # If y-coordinates are within threshold, add to current group
            if abs(current_y - previous_y) <= y_threshold:
                current_group.append(current_line)
            else:
                # Finalize current group and start new group
                combined_line = self._merge_line_group(current_group)
                combined_lines.append(combined_line)
                current_group = [current_line]

        # Don't forget the last group
        if current_group:
            combined_line = self._merge_line_group(current_group)
            combined_lines.append(combined_line)

        return combined_lines

    def _merge_line_group(self, line_group):
        """
        Merge a group of lines with similar y-coordinates into a single line
        Sort by x-coordinate and combine text
        """
        if len(line_group) == 1:
            return line_group[0]

        # Sort by x-coordinate (leftmost first)
        sorted_group = sorted(line_group, key=lambda x: x['geometry'][0] if x['geometry'] and len(x['geometry']) > 0 else 0)

        # Combine text with spaces
        combined_text_parts = []
        total_word_count = 0
        confidence_sum = 0
        confidence_count = 0

        for line in sorted_group:
            if line['text'].strip():
                combined_text_parts.append(line['text'].strip())
            total_word_count += line['word_count']
            confidence_sum += line['confidence'] * line['word_count']
            confidence_count += line['word_count']

        # Use leftmost line's geometry and metadata
        base_line = sorted_group[0]

        return {
            'text': ' '.join(combined_text_parts),
            'confidence': confidence_sum / confidence_count if confidence_count > 0 else 0,
            'geometry': base_line['geometry'],
            'item_id': base_line['item_id'],
            'block_id': base_line['block_id'],
            'line_id': base_line['line_id'],
            'word_count': total_word_count
        }

    def ocr_to_dataframe(self, simplified_lines):
        """
        Convert simplified line data to a pandas DataFrame

        Args:
            simplified_lines: List of dictionaries from simplify_ocr_to_lines()

        Returns:
            pandas.DataFrame with line-level data
        """
        try:
            if not simplified_lines:
                return pd.DataFrame()

            # Convert list of dictionaries directly to DataFrame
            df = pd.DataFrame(simplified_lines)

            return df

        except Exception as e:
            print(f"Error converting simplified lines to DataFrame: {e}")
            return pd.DataFrame()


    def parse_page_range(self, body):
        """Extract start and end page numbers from the message content"""
        try:
            # Get the user message content
            messages = body.get('messages', [])
            if not messages:
                return 1, 1

            user_message = None
            for msg in messages:
                if msg.get('role') == 'user':
                    user_message = msg.get('content', '')
                    break

            if not user_message:
                return 1, 1

            # Parse "start: 1 , end: 2" format
            start_page = 1
            end_page = 1

            # Look for start: and end: patterns
            import re
            start_match = re.search(r'start:\s*(\d+)', user_message, re.IGNORECASE)
            end_match = re.search(r'end:\s*(\d+)', user_message, re.IGNORECASE)

            if start_match:
                start_page = int(start_match.group(1))
            if end_match:
                end_page = int(end_match.group(1))

            # Ensure valid range
            if start_page < 1:
                start_page = 1
            if end_page < start_page:
                end_page = start_page

            return start_page, end_page

        except Exception as e:
            print(f"Error parsing page range: {e}")
            return 1, 1

    def extract_text_from_ocr(self, ocr_response):
        """Extract all text from the OCR response structure"""
        try:
            extracted_text = []

            # Handle the list structure from the OCR response
            if isinstance(ocr_response, list) and len(ocr_response) > 0:
                page_data = ocr_response[0]  # Get first (and usually only) page

                # Navigate through: items -> blocks -> lines -> words -> value
                if "items" in page_data:
                    for item in page_data["items"]:
                        if "blocks" in item:
                            for block in item["blocks"]:
                                if "lines" in block:
                                    line_text = []
                                    for line in block["lines"]:
                                        if "words" in line:
                                            word_values = [
                                                word["value"]
                                                for word in line["words"]
                                                if "value" in word
                                            ]
                                            line_text.append(" ".join(word_values))
                                    extracted_text.append(" ".join(line_text))

            return "\n".join(extracted_text)

        except Exception as e:
            print(f"Error extracting text from OCR response: {e}")
            return ""

    def count_ocr_elements(self, ocr_response):
        """Count the number of text blocks/elements in the OCR response"""
        try:
            count = 0

            if isinstance(ocr_response, list) and len(ocr_response) > 0:
                page_data = ocr_response[0]

                if "items" in page_data:
                    for item in page_data["items"]:
                        if "blocks" in item:
                            count += len(item["blocks"])

            return count

        except Exception as e:
            print(f"Error counting OCR elements: {e}")
            return 0

    def pipe(
        self,
        body: dict,
        __user__: dict,
        # __request__: Request,
        __files__: Optional[list] = None,
        **kwargs,
    ) -> Union[str, Generator, Iterator]:
        # print(f"GCNotifyPIPE body: {body}")
        # This is where you can add your custom pipelines like RAG.
        if "user" in body:
            del body["user"]

        if __files__ is None or len(__files__) == 0:
            return "No files provided for processing"

        def stream_ocr_results():
            filename = __files__[0]["file"]["filename"]
            yield f"📄 **Processing file:** {filename}\n\n"

            try:
                # Parse page range from user message
                start_page, end_page = self.parse_page_range(body)
                total_pages = end_page - start_page + 1

                yield f"📊 **Page range:** Processing pages {start_page} to {end_page} ({total_pages} page{'s' if total_pages > 1 else ''})\n\n"
                yield "🔄 **Status:** Starting page-by-page OCR analysis...\n\n"

                all_results = {
                    "page_range": {"start": start_page, "end": end_page},
                    "pages": [],
                    "summary": {"total_pages": 0, "total_text": ""}
                }

                # Process each page individually within the specified range
                page_index = 0
                for page_num in range(start_page, end_page + 1):
                    page_index += 1
                    try:
                        yield f"📄 **Processing page {page_num} ({page_index}/{total_pages})**...\n\n"

                        # Step 1: Get OCR response
                        page_response = self.request_ocr_page(__files__, page_num)
                        # print(f"Page {page_num} OCR Response: {page_response}")

                        # Step 2: Simplify to lines
                        simplified_lines = self.simplify_ocr_to_lines(page_response)
                        for line in simplified_lines:  # Show first 3 lines as preview
                            yield f"> {line['text']}\n"

                        # Step 3: Convert to DataFrame
                        df = self.ocr_to_dataframe(simplified_lines)

                        # Step 4: Process DataFrame
                        if df is not None and not df.empty:
                            analysis_summary = self.process_dataframe(df)
                            yield f"✅ **Page {page_num} completed** - {len(df)} lines detected\n\n"
                            yield f"**Page {page_num} Analysis Summary:**\n```\n{analysis_summary}\n```\n\n"

                        # Store results
                        page_result = {
                            "page_number": page_num,
                            "raw_ocr_data": page_response,
                            "simplified_lines": simplified_lines,
                            "dataframe_shape": df.shape if df is not None else (0, 0)
                        }
                        all_results["pages"].append(page_result)

                        # # Extract text from the OCR response structure
                        # text_content = self.extract_text_from_ocr(page_response)

                        # if text_content.strip():
                        #     all_results["summary"]["total_text"] += text_content + "\n"

                        #     yield f"✅ **Page {page_num} completed** - {len(text_content)} characters extracted\n\n"

                        #     # Show preview of extracted text for this page
                        #     preview = text_content[:300] if len(text_content) > 300 else text_content
                        #     yield f"**Page {page_num} text preview:**\n```\n{preview}{'...' if len(text_content) > 300 else ''}\n```\n\n"
                        # else:
                        #     yield f"✅ **Page {page_num} completed** - No text detected\n\n"

                        # # Show structured data if present
                        # elements_count = self.count_ocr_elements(page_response)
                        # if elements_count > 0:
                        #     yield f"**Page {page_num} elements:** {elements_count} text blocks detected\n\n"

                    except Exception as page_error:
                        yield f"⚠️ **Page {page_num} error:** {str(page_error)}\n\n"
                        # Continue with next page
                        continue

                # Update summary
                all_results["summary"]["total_pages"] = len(all_results["pages"])

                yield "---\n\n"
                yield "## 📋 Complete OCR Results\n\n"
                yield f"**Summary:** {all_results['summary']['total_pages']} pages processed\n\n"

                # Show complete results
                complete_json = json.dumps(all_results, indent=2)
                # if len(complete_json) > 30000:
                #     yield f"**Large document** ({len(complete_json):,} characters)\n\n"
                #     yield "### 📄 Page-by-page summary:\n"
                #     for page in all_results["pages"]:
                #         page_text = str(page["data"].get("text", ""))
                #         yield f"- **Page {page['page_number']}:** {len(page_text)} characters\n"
                #     yield "\n"

                yield "### 📊 Complete Results:\n"
                # yield f"```json\n{complete_json}\n```\n\n"

                yield "🎉 **All pages processed successfully!**"

            except Exception as e:
                yield f"❌ **Error occurred:** {str(e)}\n\n"
                yield "Please check the file format and try again."

        return stream_ocr_results()


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
